// End-to-end: main-thread WorkerSolver <-> real worker loop <-> Pyodide <->
// unmodified dieselsim. Dependency-free runner; exit code is the result.
import { Worker } from "node:worker_threads";
import { WorkerSolver } from "../src/worker-client.js";
import { SolverError, type GridProgress } from "../src/solver-port.js";

// native CPython 3.12 / numpy 2.4.4, crdi15 1800 rpm load 0.6, n_cycles 9
const NATIVE_TORQUE = 124.39075523765574;

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

const pt = await solver.solvePoint({ engine: { preset: "crdi15" }, rpm: 1800, load: 0.6 });
const rel = Math.abs(pt.torque - NATIVE_TORQUE) / NATIVE_TORQUE;
check("solvePoint matches native CPython", rel < 1e-8, `torque ${pt.torque}, rel diff ${rel.toExponential(2)}`);

let e = await expectError(solver.solvePoint(
  { engine: { preset: "crdi15", overrides: { "turbo.turbin_area_eff": 1 } }, rpm: 1800, load: 0.6 }));
check("typo'd override is rejected, not ignored",
      e?.kind === "invalid-request" && /did you mean turbine_area_eff/.test(e.message), e?.message ?? "no error");

e = await expectError(solver.solvePoint({ engine: { preset: "nope" }, rpm: 1800, load: 0.6 }));
check("unknown preset is rejected", e?.kind === "invalid-request", e?.message.slice(0, 60) ?? "no error");

e = await expectError(solver.solvePoint({ engine: { preset: "crdi15" }, rpm: 1800, load: 1.5 }));
check("out-of-range load is rejected", e?.kind === "invalid-request", e?.message ?? "no error");

const progress: GridProgress[] = [];
const grid = await solver.buildGrid(
  { engine: { preset: "crdi15" }, rpms: [1800], loads: [0.6, 0.2] },
  { onProgress: p => progress.push(p) });
const c0 = grid.cells.find(c => c.i === 0 && c.j === 0)!;
const gridRel = Math.abs(c0.perf["torque"]! - NATIVE_TORQUE) / NATIVE_TORQUE;
check("buildGrid returns every cell", grid.cells.length === 2);
check("buildGrid reports progress per cell", progress.map(p => p.done).join(",") === "1,2");
check("grid cell matches native", gridRel < 1e-8, `rel diff ${gridRel.toExponential(2)}`);
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
check("solver still usable after cancel", Math.abs(again.torque - NATIVE_TORQUE) / NATIVE_TORQUE < 1e-8);

const [a, b] = await Promise.all([
  solver.solvePoint({ engine: { preset: "crdi15" }, rpm: 1800, load: 0.6 }),
  solver.solvePoint({ engine: { preset: "crdi15" }, rpm: 1800, load: 0.2 }),
]);
check("concurrent requests resolve to their own results", a.load === 0.6 && b.load === 0.2 && a.torque > b.torque);

const pending = solver.solvePoint({ engine: { preset: "crdi15" }, rpm: 1800, load: 0.6 });
solver.dispose();
e = await expectError(pending);
check("dispose rejects in-flight requests", e?.kind === "cancelled");
e = await expectError(solver.solvePoint({ engine: { preset: "crdi15" }, rpm: 1800, load: 0.6 }));
check("calls after dispose are rejected", e?.kind === "cancelled");

const failed = results.filter(r => !r[1]).length;
console.log(`\n${results.length - failed} passed, ${failed} failed  (${((performance.now() - t0) / 1000).toFixed(0)} s)`);
process.exit(failed ? 1 : 0);
