// End-to-end: main-thread WorkerSolver <-> real worker loop <-> Pyodide <->
// unmodified dieselsim. Dependency-free runner; exit code is the result.
import { Worker } from "node:worker_threads";
import { WorkerSolver } from "../src/worker-client.js";
import { SolverError, type GridProgress } from "../src/solver-port.js";
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
// not 25 % open; was 111.71143779402043).
const NATIVE_TORQUE = 122.62764269929146;
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
