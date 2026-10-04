// buildLiveGrid's scheduling, resume and cancel, against fake workers (no
// Pyodide): fast. The real build is test/live-grid-real.test.ts.
import { buildLiveGrid, MemoryPieceStore, type LiveBuildProgress, type LiveCaller } from "../src/live-grid-build.js";
import type { LiveFn } from "../src/protocol.js";

const results: boolean[] = [];
const check = (name: string, ok: boolean, note = "") => {
  results.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${note ? "  -- " + note : ""}`);
};
const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

const RPMS = [1000, 2000, 3000], LOADS = [0, 1];
class Fake implements LiveCaller {
  static live = 0; static peak = 0;
  calls: { fn: LiveFn; arg: Record<string, unknown> }[] = [];
  constructor(private readonly failAt?: { rpm: number; load: number }) {}
  async liveCall(fn: LiveFn, arg: string): Promise<string> {
    const a = JSON.parse(arg) as Record<string, unknown>;
    this.calls.push({ fn, arg: a });
    Fake.live++; Fake.peak = Math.max(Fake.peak, Fake.live);
    try {
      await sleep(fn === "live_row_limit" ? 15 : 3);
      if (fn === "live_grid_plan") return JSON.stringify({ rpms: RPMS, loads: LOADS });
      if (fn === "live_row_limit") return JSON.stringify({ fuel_limit: (a["rpm"] as number) / 100 });
      if (fn === "live_cell") {
        if (this.failAt && a["rpm"] === this.failAt.rpm && a["load"] === this.failAt.load) throw new Error("solver blew up");
        return JSON.stringify({ perf: { rpm: a["rpm"], load: a["load"], cold: a["cold"] ? 1 : 0, flim: a["fuel_limit"] },
                                p_cyl_f32: "", src_f32: {}, meta: {} });
      }
      return arg;                                   // assemble: echo what it was given
    } finally { Fake.live--; }
  }
}
const all = (ws: Fake[]) => ws.flatMap(w => w.calls);
const opts = { key: "t", size: [3, 2] as [number, number] };

// 1. a full build
{
  const ws = [new Fake(), new Fake(), new Fake()];
  Fake.peak = 0;
  const prog: LiveBuildProgress[] = [];
  const out = JSON.parse(await buildLiveGrid({ preset: "x" }, ws, { ...opts, onProgress: p => prog.push(p) }));
  const calls = all(ws), count = (fn: LiveFn) => calls.filter(c => c.fn === fn).length;
  check("every piece is asked for once: 3 rows, 12 cells, one plan, one assembly",
    count("live_row_limit") === 3 && count("live_cell") === 12 && count("live_grid_plan") === 1 && count("live_grid_assemble") === 1,
    `rows ${count("live_row_limit")}, cells ${count("live_cell")}`);
  const cellsOk = calls.filter(c => c.fn === "live_cell").every(c => c.arg["fuel_limit"] === (c.arg["rpm"] as number) / 100);
  check("each cell is solved on its own row's fuel limit (never before the row is done)", cellsOk);
  const layoutOk = (["warm", "cold"] as const).every(tag => RPMS.every((r, i) => LOADS.every((l, j) => {
    const p = out[tag][i][j].perf;
    return p.rpm === r && p.load === l && p.cold === (tag === "cold" ? 1 : 0);
  }))) && JSON.stringify(out.fuel_limits) === JSON.stringify([10, 20, 30]);
  check("the assembly gets every cell in its place, warm and cold, and the row fuel", layoutOk);
  const mono = prog.every((p, k) => k === 0 || p.done >= prog[k - 1]!.done);
  check("progress only goes up and ends complete, then assembles", mono && prog.at(-2)?.done === 15 && prog.at(-1)?.phase === "assemble",
    `${prog.length} reports, last ${prog.at(-1)?.phase} ${prog.at(-1)?.done}/${prog.at(-1)?.total}`);
  check("the workers run in parallel", Fake.peak >= 2, `at most ${Fake.peak} at once`);
}

// 2. cancel, then resume from the store
{
  const store = new MemoryPieceStore(), ac = new AbortController();
  const ws1 = [new Fake(), new Fake()];
  let err: Error | undefined;
  try {
    await buildLiveGrid({ preset: "x" }, ws1, { ...opts, store, storeKey: "k", signal: ac.signal,
      onProgress: p => { if (p.done >= 6) ac.abort(); } });
  } catch (e) { err = e as Error; }
  const kept = store.map.size;
  check("a cancelled build stops, says so, and keeps what it finished", /cancelled/.test(err?.message ?? "") && kept >= 6 && kept < 15,
    `${kept} pieces kept; ${err?.message}`);
  const ws2 = [new Fake(), new Fake()];
  let resumed = -1;
  const out = JSON.parse(await buildLiveGrid({ preset: "x" }, ws2, { ...opts, store, storeKey: "k",
    onProgress: p => { resumed = p.resumed; } }));
  const redone = all(ws2).filter(c => c.fn === "live_row_limit" || c.fn === "live_cell").length;
  check("the resumed build redoes only the missing pieces, and the file is complete", redone === 15 - kept && resumed === kept
    && out.warm.flat().length === 6 && out.cold.flat().length === 6, `redid ${redone} of ${15 - kept} missing; resumed ${resumed}`);
}

// 3. a failing cell
{
  const ws = [new Fake({ rpm: 2000, load: 1 })];
  let err: Error | undefined;
  try { await buildLiveGrid({ preset: "x" }, ws, opts); } catch (e) { err = e as Error; }
  check("a cell that fails fails the build, and nothing is assembled", err?.message === "solver blew up"
    && !ws[0]!.calls.some(c => c.fn === "live_grid_assemble"), err?.message ?? "no error");
}

const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
