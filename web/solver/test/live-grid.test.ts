// buildLiveGrid's scheduling, resume and cancel, against fake workers (no
// Pyodide): fast. The real build is test/live-grid-real.test.ts.
import { buildLiveGrid, etaSeconds, MemoryPieceStore, type LiveBuildProgress, type LiveCaller } from "../src/live-grid-build.js";
import type { LiveFn } from "../src/protocol.js";

const results: boolean[] = [];
const check = (name: string, ok: boolean, note = "") => {
  results.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${note ? "  -- " + note : ""}`);
};
const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

const RPMS = [1000, 2000, 3000], LOADS = [0, 1];
class Fake implements LiveCaller {
  static live = 0; static peak = 0; static rowMs = 15; static cellMs = 3;
  calls: { fn: LiveFn; arg: Record<string, unknown> }[] = [];
  constructor(private readonly failAt?: { rpm: number; load: number }) {}
  async liveCall(fn: LiveFn, arg: string): Promise<string> {
    const a = JSON.parse(arg) as Record<string, unknown>;
    this.calls.push({ fn, arg: a });
    Fake.live++; Fake.peak = Math.max(Fake.peak, Fake.live);
    try {
      await sleep(fn === "live_row_limit" ? Fake.rowMs : fn === "live_cell" ? Fake.cellMs : 3);
      if (fn === "live_grid_plan") return JSON.stringify({ rpms: RPMS, loads: LOADS });
      if (fn === "live_row_limit") return JSON.stringify({ fuel_limit: (a["rpm"] as number) / 100 });
      if (fn === "live_cell") {
        if (this.failAt && a["rpm"] === this.failAt.rpm && a["load"] === this.failAt.load) throw new Error("solver blew up");
        return JSON.stringify({ perf: { rpm: a["rpm"], load: a["load"], cold: a["cold"] ? 1 : 0, flim: a["fuel_limit"] },
                                p_cyl_f32: "", src_f32: {}, meta: {} });
      }
      // Phase 7 step 4: two airs per cell, and one held-out check
      if (fn === "live_weather_plan") {
        const pieces = RPMS.flatMap((_, i) => LOADS.flatMap((_, j) => [58000, 72000].map(p => ({ i, j, p, T: 298 }))));
        return JSON.stringify({ pieces, check: [{ i: 2, j: 1, p: 65000, T: 293 }] });
      }
      if (fn === "live_weather_cell") return JSON.stringify({ values: [a["rpm"], a["load"], a["fuel_limit"], a["p"]], settled: 1 });
      return arg;                                   // the assemblies: echo what they were given
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
  // Stop returns at once (test 4); these fake workers are not terminated as the
  // app's are, so let their pieces in flight end (and be kept) before counting
  await sleep(40);
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

// 4. Stop answers at once, not when the running pieces finish (B-04)
{
  Fake.rowMs = 400;
  const ac = new AbortController();
  const t = performance.now();
  setTimeout(() => ac.abort(), 50);
  let err: Error | undefined;
  try { await buildLiveGrid({ preset: "x" }, [new Fake(), new Fake()], { ...opts, signal: ac.signal }); }
  catch (e) { err = e as Error; }
  const ms = performance.now() - t;
  check("Stop rejects at once, mid-row, and says so", /cancelled/.test(err?.message ?? "") && ms < 100,
    `${ms.toFixed(0)} ms after starting (Stop at 50 ms, the rows take 400 ms); ${err?.message}`);
  Fake.rowMs = 15;
  await sleep(450);                                 // let the abandoned fake rows end before the next test
}

// 5. the ETA tracks the time really left (B-04: it read 258 min of a 19 min build)
{
  Fake.rowMs = 80; Fake.cellMs = 20;
  const reps: { t: number; eta?: number; done: number; phase: string }[] = [];
  const t0 = performance.now();
  await buildLiveGrid({ preset: "x" }, [new Fake(), new Fake(), new Fake()],
    { ...opts, onProgress: p => reps.push({ t: performance.now(), done: p.done, phase: p.phase, ...(p.etaS !== undefined ? { eta: p.etaS * 1000 } : {}) }) });
  const end = reps.filter(r => r.phase !== "assemble").at(-1)!.t, span = end - t0;
  const judged = reps.filter(r => r.eta !== undefined && end - r.t > 0.3 * span);
  const ratios = judged.map(r => r.eta! / (end - r.t));
  const worst = ratios.reduce((w, x) => Math.max(w, x, 1 / x), 1);
  check("the ETA stays within 1.5x of the time really left while 30% or more remains",
    judged.length >= 2 && worst <= 1.5, `${judged.length} reports judged, worst ${worst.toFixed(2)}x; ratios ${ratios.map(x => x.toFixed(2)).join(" ")}`);
  check("no ETA before the first piece finishes", reps.filter(r => r.done === 0).every(r => r.eta === undefined));
  Fake.rowMs = 15; Fake.cellMs = 3;
}

// 6. etaSeconds by hand
{
  const none = etaSeconds({ rowsUnstarted: 3, cellsLeft: 12, running: [], workers: 3 });
  const cells = etaSeconds({ rowS: 40, cellS: 10, rowsUnstarted: 0, cellsLeft: 12, running: [], workers: 3 });
  const early = etaSeconds({ rowS: 40, rowsUnstarted: 0, cellsLeft: 12, running: [{ kind: "row", elapsedS: 30 }], workers: 3 });
  check("etaSeconds: nothing timed, no answer; 12 cells of 10 s on 3 workers, 40 s; a row counts as 4 cells until cells are timed",
    none === undefined && cells === 40 && early !== undefined && Math.abs(early - (10 / 3 + 12 * 10 / 3)) < 1e-9,
    `${none} / ${cells} / ${early}`);
}

// 7. Phase 7 step 4: the weather table's pieces, row by row, into the file; resumable
{
  const ws = [new Fake(), new Fake()];
  const prog: LiveBuildProgress[] = [];
  const out = JSON.parse(await buildLiveGrid({ preset: "x" }, ws, { ...opts, weather: true, onProgress: p => prog.push(p) }));
  const calls = all(ws), wxCalls = calls.filter(c => c.fn === "live_weather_cell");
  const wxa = calls.find(c => c.fn === "live_weather_assemble")?.arg as
    { pieces: { values: number[] }[]; checks: { values: number[] }[]; grid: { perf: { rpm: number }[][] } } | undefined;
  const onRowFuel = wxCalls.every(c => c.arg["fuel_limit"] === (c.arg["rpm"] as number) / 100);
  const inOrder = !!wxa && wxa.pieces.length === 12 && wxa.checks.length === 1
    && wxa.pieces.every((q, n) => q.values[0] === RPMS[Math.floor(n / 4)] && q.values[1] === LOADS[Math.floor(n / 2) % 2]
      && q.values[3] === [58000, 72000][n % 2])
    && wxa.checks[0]!.values[3] === 65000 && wxa.grid.perf[2]![1]!.rpm === 3000;
  check("weather: 12 pieces and 1 check, each once, on its row's fuel, handed to the assembly in the plan's order",
    wxCalls.length === 13 && onRowFuel && inOrder, `${wxCalls.length} weather solves; in order ${inOrder}`);
  check("weather: the table goes into the file, and the progress counts its pieces",
    out.extra?.weather !== undefined && prog.at(-2)?.done === 15 + 13 && prog.at(-2)?.total === 28,
    `last count ${prog.at(-2)?.done}/${prog.at(-2)?.total}; table in the file ${out.extra?.weather !== undefined}`);
  // cancel mid-way, then resume: only the missing pieces are redone, weather ones too
  const store = new MemoryPieceStore(), ac = new AbortController();
  try {
    await buildLiveGrid({ preset: "x" }, [new Fake(), new Fake()], { ...opts, weather: true, store, storeKey: "w",
      signal: ac.signal, onProgress: p => { if (p.done >= 12) ac.abort(); } });
  } catch { /* cancelled */ }
  await sleep(60);
  const kept = store.map.size, keptWx = [...store.map.keys()].filter(k => k.startsWith("w:wx:")).length;
  const ws2 = [new Fake(), new Fake()];
  await buildLiveGrid({ preset: "x" }, ws2, { ...opts, weather: true, store, storeKey: "w" });
  const redone = all(ws2).filter(c => ["live_row_limit", "live_cell", "live_weather_cell"].includes(c.fn)).length;
  check("weather: a resumed build redoes only the missing pieces, weather ones included",
    redone === 28 - kept && kept > 0 && kept < 28, `${kept} kept (${keptWx} weather), redid ${redone} of ${28 - kept}`);
}

const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
