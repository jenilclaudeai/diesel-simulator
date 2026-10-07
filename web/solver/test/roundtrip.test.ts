// End-to-end: main-thread WorkerSolver <-> real worker loop <-> Pyodide <->
// unmodified dieselsim. Dependency-free runner; exit code is the result.
import { Worker } from "node:worker_threads";
import { WorkerSolver } from "../src/worker-client.js";
import { SolverError, type GridProgress } from "../src/solver-port.js";
import type { LiveFn } from "../src/protocol.js";
import { sourceHash } from "../src/cache-key.js";
import { CachedSolver } from "../src/cached-solver.js";
import { MemoryGridCache } from "../src/grid-cache.js";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// native CPython 3.12 / numpy 2.1.0, crdi15 1800 rpm load 0.6, n_cycles 9.
// Re-baselined 2026-09-25 for FINDING-013 item 1 (was 124.39075523765574):
// the torque limiter now calibrates under the full-load schedules it is
// judged under, which lowers crdi15's calibrated fuel at 1800 rpm ~11%, and
// "load 0.6" is 60% of it. Same change as the golden in tests/test_physics.py.
// Re-baselined again for FINDING-016 (ignition resolved within the crank
// step; was 111.71833782635092) and FINDING-015 (cam friction time base and
// inlet viscosity; was 111.69609690984224).
// Re-baselined for FINDING-013 item 2 (EGR valve starts at 0.14 x command,
// not 25 % open; was 111.71143779402043) and FINDING-018 (continuous cam
// lift; was 122.62764269929146).
const NATIVE_TORQUE = 122.58034073824089;
// Agreement with native was ~1e-10 and the tolerance 1e-8. After item 1 it is
// 1.2e-6 here: the limiter's calibration is a chain of warm-started 9-cycle
// solves, and without EGR the VGT limit cycle (FINDING-013 item 3) is active
// in it, amplifying a 1e-10 platform difference ~10x per solve (measured,
// same iteration count on both: 1.3e-10, 7.6e-11, 1.8e-8, 7.5e-8, 3.7e-7,
// 1.1e-6). 1e-5 still catches any transport error (wrong preset, lost
// override, corrupt payload), which would be >= 1e-3.
const REL_TOL = 1e-5;

const results: [string, boolean, string][] = [];
const check = (name: string, ok: boolean, note = "") => {
  results.push([name, ok, note]);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${note ? "  -- " + note : ""}`);
};
const expectError = async (p: Promise<unknown>) => {
  try { await p; return undefined; } catch (e) { return e as SolverError; }
};

const worker = new Worker(new URL("./node-worker.js", import.meta.url));
const solver = new WorkerSolver({
  post: (m, t) => worker.postMessage(m, t ?? []),
  listen: h => { worker.on("message", h); },
  close: () => { void worker.terminate(); },
});

const t0 = performance.now();
const info = await solver.ready();
check("ready() loads runtime", info.contract === 1 && info.presets.includes("crdi15"),
      `python ${info.python}, numpy ${info.numpy}, load ${info.load_s.toFixed(1)} s`);
check("ready() is idempotent", (await solver.ready()) === info);
// Phase 7 (ADR-016): the presets come from dieselsim/environment.py, loaded in the worker
const envs = info.environments ?? [];
const plateau = envs.find(e => e.key === "plateau");
check("runtime info carries the five environment presets (dieselsim/environment.py, in the worker)",
      envs.map(e => e.key).join() === "standard,desert,winter,plateau,tropics"
      && !!plateau && Math.abs(plateau.overrides["thermal.ambient_p"]! / 65764 - 1) < 1e-4,
      envs.map(e => `${e.key} ${(e.p_amb / 1000).toFixed(1)} kPa ${e.T_C} °C`).join("; "));

const pt = await solver.solvePoint({ engine: { preset: "crdi15" }, rpm: 1800, load: 0.6 });
const rel = Math.abs(pt.torque - NATIVE_TORQUE) / NATIVE_TORQUE;
check("solvePoint matches native CPython", rel < REL_TOL, `torque ${pt.torque}, rel diff ${rel.toExponential(2)}`);

let e = await expectError(solver.solvePoint(
  { engine: { preset: "crdi15", overrides: { "turbo.turbin_area_eff": 1 } }, rpm: 1800, load: 0.6 }));
check("typo'd override is rejected, not ignored",
      e?.kind === "invalid-request" && /did you mean turbine_area_eff/.test(e.message), e?.message ?? "no error");

e = await expectError(solver.solvePoint({ engine: { preset: "nope" }, rpm: 1800, load: 0.6 }));
check("unknown preset is rejected", e?.kind === "invalid-request", e?.message.slice(0, 60) ?? "no error");

e = await expectError(solver.solvePoint({ engine: { preset: "crdi15" }, rpm: 1800, load: 1.5 }));
check("out-of-range load is rejected", e?.kind === "invalid-request", e?.message ?? "no error");

// Phase 6 (ADR-015): a cycle's traces through the real worker match native CPython
// (bridge.solve_cycle, crdi15 1800 rpm 0.6, native, 2026-10-05): the peak, the IMEP,
// and the whole pressure trace through its sum
const NATIVE_CYCLE = { p_max: 13004649.134651296, imep_net: 1134730.1025235609, p_sum: 911129969.1293999 };
const cyc = await solver.solveCycle({ engine: { preset: "crdi15" }, rpm: 1800, load: 0.6 });
// (optional chaining: a wrongly shaped answer fails the check rather than crashing the test)
const cycRel = Math.max(Math.abs((cyc.summary?.p_max ?? NaN) - NATIVE_CYCLE.p_max) / NATIVE_CYCLE.p_max,
  Math.abs((cyc.summary?.imep_net ?? NaN) - NATIVE_CYCLE.imep_net) / NATIVE_CYCLE.imep_net,
  Math.abs((cyc.p?.reduce((a, b) => a + b, 0) ?? NaN) - NATIVE_CYCLE.p_sum) / NATIVE_CYCLE.p_sum);
check("solveCycle matches native CPython: p_max, imep_net and the whole p trace; 720 points; cylinder 1 at phase 0",
  cycRel < REL_TOL && cyc.theta?.length === 720 && cyc.p?.length === 720 && cyc.V?.length === 720 && cyc.cylinder_phase_deg === 0,
  `worst rel diff ${cycRel.toExponential(2)}, p_max ${((cyc.summary?.p_max ?? NaN) / 1e5).toFixed(1)} bar`);
e = await expectError(solver.solveCycle({ engine: { preset: "crdi15" }, rpm: 1800, load: 0.6, n_cycles: 6 }));
check("solveCycle refuses n_cycles below 9", e?.kind === "invalid-request", e?.message ?? "no error");

// Phase 6 (ADR-015): a durability run stepped through the real worker matches native
// (DieselEngine.durability_run(50, step_h=50) on crdi15, native, 2026-10-05)
const NATIVE_DUR = { torque: 202.37961214603365, bore_wear_um: 0.033379075126331016, health: 0.02781589593860918 };
const dStart = JSON.parse(await solver.durabilityCall("durability_start",
  JSON.stringify({ engine: { preset: "crdi15" }, hours: 50, step_h: 50 }))) as { id: string };
const dNext = JSON.parse(await solver.durabilityCall("durability_next", JSON.stringify({ id: dStart.id }))) as
  { rows: Record<string, number>[]; done: boolean };
const dRow = dNext.rows?.[0];
const dRel = Math.max(...(["torque", "bore_wear_um", "health"] as const).map(k =>
  Math.abs((dRow?.[k] ?? NaN) - NATIVE_DUR[k]) / NATIVE_DUR[k]));
check("a durability run stepped through the worker matches native: one 50 h block, its torque, bore wear and life consumed",
  dNext.rows?.length === 1 && dRow?.["hours"] === 50 && dRel < REL_TOL, `worst rel diff ${dRel.toExponential(2)}`);
const dDone = JSON.parse(await solver.durabilityCall("durability_next", JSON.stringify({ id: dStart.id }))) as { done: boolean };
const dStop = JSON.parse(await solver.durabilityCall("durability_stop", JSON.stringify({ id: dStart.id }))) as { stopped: boolean };
check("the run says when it is done, and is gone after", dDone.done === true && dStop.stopped === false,
  `done ${dDone.done}, stop after done ${dStop.stopped}`);
// Phase 6 (ADR-015): the spec editor's view of an engine, overrides applied
const sd = await solver.describeSpec({ preset: "crdi15", overrides: { "geom.compression_ratio": 17 } });
const cr = sd.fields?.find(f => f.path === "geom.compression_ratio");
check("describeSpec: every field with its dotted path, overrides applied",
  sd.fields?.length === 188 && cr?.value === 17 && cr?.type === "number" && sd.fields.filter(f => f.type === "list").length === 2,
  `${sd.fields?.length} fields; compression ratio ${String(cr?.value)}`);
// ADR-009: the compressor map for the schematic, and the cycle's point on it
const cmap = await solver.compressorMap({ preset: "crdi15" });
const naMap = await solver.compressorMap({ preset: "single" });
check("compressorMap: six speed lines and the surge line from the solver; none without a turbo; the cycle's point on the map",
  cmap.enabled === true && cmap.lines.length === 6 && cmap.surge.length === 6 && naMap.enabled === false
  && (cyc.compressor?.pr ?? 0) > 1 && (cyc.compressor?.m_corr ?? 0) > 0,
  `${cmap.enabled ? cmap.lines.length : 0} lines; cycle at PR ${cyc.compressor?.pr.toFixed(2)}, ${cyc.compressor?.m_corr.toFixed(4)} kg/s`);
e = await expectError(solver.durabilityCall("solve_point" as never, "{}"));
check("durabilityCall refuses a non-durability function", e?.kind === "protocol", e?.message ?? "no error");

// ADR-014: a custom engine from brochure numbers, described by the builder itself
const MY20 = { name: "2.0 L four", displacement: 2.0, n_cyl: 4, rated_rpm: 4000, peak_torque: 320,
               peak_power: 103, plateau: [1750, 2500], vehicle: "crdi15" };
const desc = await solver.describeEngine({ headline: MY20 });
check("describeEngine: a custom engine's rpm range and requested numbers (ADR-014)",
      desc.name === "2.0 L four" && desc.idle_rpm > 0 && desc.max_rpm > desc.rated_rpm
      && desc.requested?.peak_torque === 320 && desc.requested?.plateau?.[0] === 1750,
      `idle ${desc.idle_rpm} rated ${desc.rated_rpm} max ${desc.max_rpm}, requested ${JSON.stringify(desc.requested)}`);
e = await expectError(solver.describeEngine({ headline: { ...MY20, n_cyl: "four" } }));
check("a custom engine the builder cannot make is an invalid request", e?.kind === "invalid-request"
      && /cannot make this engine/.test(e.message), e?.message.slice(0, 80) ?? "no error");

// ADR-014 step 3: the live-grid pieces, and only those, over the wire
const plan = JSON.parse(await solver.liveCall("live_grid_plan", JSON.stringify({ engine: { headline: MY20 } })));
check("liveCall: a drivable grid's plan is the roster's 8 x 6", plan.rpms.length === 8 && plan.loads.length === 6
      && plan.rpms[0] === desc.idle_rpm && plan.T_cold === 273, `rpms ${plan.rpms[0]}..${plan.rpms.at(-1)}, loads ${plan.loads.length}`);
e = await expectError(solver.liveCall("solve_point" as LiveFn, "{}"));
check("liveCall refuses a bridge function that is not a live-grid piece", e?.kind === "protocol", e?.message ?? "no error");

const progress: GridProgress[] = [];
const grid = await solver.buildGrid(
  { engine: { preset: "crdi15" }, rpms: [1800], loads: [0.6, 0.2] },
  { onProgress: p => progress.push(p) });
const c0 = grid.cells.find(c => c.i === 0 && c.j === 0)!;
const gridRel = Math.abs(c0.perf["torque"]! - NATIVE_TORQUE) / NATIVE_TORQUE;
check("buildGrid returns every cell", grid.cells.length === 2);
check("buildGrid reports progress per cell", progress.map(p => p.done).join(",") === "1,2");
check("grid cell matches native", gridRel < REL_TOL, `rel diff ${gridRel.toExponential(2)}`);
const n = c0.src["dpdth"]?.length ?? 0;
check("sources arrive as Float32Array", c0.src["dpdth"] instanceof Float32Array && n > 0
      && info.source_keys.every(k => c0.src[k]?.length === n), `${info.source_keys.length} sources x ${n} samples`);

const ac = new AbortController();
const seen: number[] = [];
e = await expectError(solver.buildGrid(
  { engine: { preset: "crdi15" }, rpms: [1200, 1800, 2400], loads: [0.2, 0.6] },
  { signal: ac.signal, onProgress: p => { seen.push(p.done); if (p.done === 1) ac.abort(); } }));
check("abort cancels a grid build", e?.kind === "cancelled", `${e?.message}`);
check("cancellation lands at a cell boundary", seen.length >= 1 && seen.length < 6,
      `stopped after ${seen.length}/6 cells`);

const again = await solver.solvePoint({ engine: { preset: "crdi15" }, rpm: 1800, load: 0.6 });
check("solver still usable after cancel", Math.abs(again.torque - NATIVE_TORQUE) / NATIVE_TORQUE < REL_TOL);

const [a, b] = await Promise.all([
  solver.solvePoint({ engine: { preset: "crdi15" }, rpm: 1800, load: 0.6 }),
  solver.solvePoint({ engine: { preset: "crdi15" }, rpm: 1800, load: 0.2 }),
]);
check("concurrent requests resolve to their own results", a.load === 0.6 && b.load === 0.2 && a.torque > b.torque);

// The main thread must be able to compute the physics version WITHOUT booting
// Pyodide, or cached grids cannot open instantly. So TypeScript's sourceHash()
// has to agree exactly with Python's source_hash(). If they ever differ, every
// cache lookup misses forever, silently.
const pkg = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..", "dieselsim");
const files = Object.fromEntries(fs.readdirSync(pkg).filter(f => f.endsWith(".py"))
  .map(f => [f, new Uint8Array(fs.readFileSync(path.join(pkg, f)))]));
const tsHash = await sourceHash(files);
check("TypeScript sourceHash() == Python source_hash()", tsHash === info.source_hash,
      `${tsHash.slice(0, 16)}… vs ${info.source_hash.slice(0, 16)}…`);

const cached = new CachedSolver(solver, new MemoryGridCache(), tsHash);
const cellReq = { engine: { preset: "crdi15" }, rpms: [1800], loads: [0.6] };
const tMiss = performance.now();
const g1 = await cached.buildGrid(cellReq);
const missS = (performance.now() - tMiss) / 1000;
const tHit = performance.now();
const g2 = await cached.buildGrid(cellReq);
const hitMs = performance.now() - tHit;
check("real solver: miss then hit", cached.lastCacheEvent?.outcome === "hit"
      && g2.cells[0]!.perf["torque"] === g1.cells[0]!.perf["torque"],
      `miss ${missS.toFixed(1)} s, hit ${hitMs.toFixed(1)} ms`);

const pending = solver.solvePoint({ engine: { preset: "crdi15" }, rpm: 1800, load: 0.6 });
solver.dispose();
e = await expectError(pending);
check("dispose rejects in-flight requests", e?.kind === "cancelled");
e = await expectError(solver.solvePoint({ engine: { preset: "crdi15" }, rpm: 1800, load: 0.6 }));
check("calls after dispose are rejected", e?.kind === "cancelled");

const failed = results.filter(r => !r[1]).length;
console.log(`\n${results.length - failed} passed, ${failed} failed  (${((performance.now() - t0) / 1000).toFixed(0)} s)`);
process.exit(failed ? 1 : 0);
