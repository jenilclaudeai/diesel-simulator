// The real thing (ADR-014 step 3): a drivable grid built by two Pyodide
// workers through buildLiveGrid, against the same engine built natively by
// tools/build_live_grids.py. Slow (~7 min), so not in `npm test`:
//
//   python3 tools/build_live_grids.py --engine web/solver/test/my20.engine.json \
//       --size 2x2 --out out/grids/my20-2x2.json
//   cd web/solver && npm run test:live-real
//
// Pyodide agrees with native CPython to ~1e-6, not bit for bit (the fuel
// limiter's warm-started calibration chain amplifies a 1e-10 platform
// difference; see roundtrip.test.ts), so numbers -- float32 arrays decoded --
// are held to 1e-5 relative, and the structure (keys, their order, shapes,
// the grid hash) exactly.
import { Worker } from "node:worker_threads";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { WorkerSolver } from "../src/worker-client.js";
import { buildLiveGrid, MemoryPieceStore, type LiveBuildProgress } from "../src/live-grid-build.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "..", "..", "..", "..");
const refPath = path.join(repo, "out", "grids", "my20-2x2.json");
const REL = 1e-5;
const results: boolean[] = [];
const check = (name: string, ok: boolean, note = "") => {
  results.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${note ? "  -- " + note : ""}`);
};
if (!fs.existsSync(refPath)) {
  console.log(`FAIL  no native reference at ${refPath}; build it with the command at the top of this file`);
  process.exit(1);
}
const ref = JSON.parse(fs.readFileSync(refPath, "utf8")) as Record<string, unknown>;
const engineJson = JSON.parse(fs.readFileSync(path.resolve(here, "..", "..", "test", "my20.engine.json"), "utf8"));

const workers = [0, 1].map(() => {
  const w = new Worker(new URL("./node-worker.js", import.meta.url));
  return new WorkerSolver({ post: (m, t) => w.postMessage(m, t ?? []), listen: h => { w.on("message", h); },
                            close: () => { void w.terminate(); } });
});
const t0 = performance.now();
const prog: LiveBuildProgress[] = [];
const text = await buildLiveGrid({ headline: engineJson }, workers, {
  key: "my20", size: [2, 2], store: new MemoryPieceStore(), storeKey: "real",
  extra: { custom: ref["custom"], vehicle: ref["vehicle"], engine_json: ref["engine_json"], engine_file_sha256: ref["engine_file_sha256"] },
  onProgress: p => { prog.push(p); if (p.done % 2 === 0) console.log(`  ${p.phase} ${p.done}/${p.total}${p.etaS ? `, ~${Math.round(p.etaS)} s left` : ""}`); },
});
const secs = (performance.now() - t0) / 1000;
workers.forEach(w => w.dispose());
const got = JSON.parse(text) as Record<string, unknown>;

const f32 = (b64: string) => { const b = Buffer.from(b64, "base64"); return new Float32Array(b.buffer, b.byteOffset, b.byteLength / 4); };
let worst = 0, where = "", structural: string[] = [];
const cmp = (a: unknown, b: unknown, at: string): void => {
  if (typeof a === "number" && typeof b === "number") {
    const r = Math.abs(a - b) / Math.max(Math.abs(b), 1e-9);
    if (r > worst && Math.abs(a - b) > 1e-12) { worst = r; where = at; }
  } else if (typeof a === "string" && typeof b === "string" && at.includes("_f32")) {
    const x = f32(a), y = f32(b);
    if (x.length !== y.length) { structural.push(`${at}: ${x.length} vs ${y.length} samples`); return; }
    const scale = Math.max(...Array.from(y, Math.abs), 1e-12);
    for (let k = 0; k < x.length; k++) {
      const r = Math.abs(x[k]! - y[k]!) / scale;
      if (r > worst) { worst = r; where = `${at}[${k}]`; }
    }
  } else if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) structural.push(`${at}: length ${a.length} vs ${b.length}`);
    else a.forEach((v, k) => cmp(v, b[k], `${at}[${k}]`));
  } else if (a && b && typeof a === "object" && typeof b === "object") {
    const ka = Object.keys(a), kb = Object.keys(b);
    if (ka.join() !== kb.join()) structural.push(`${at}: keys differ`);
    for (const k of ka) cmp((a as Record<string, unknown>)[k], (b as Record<string, unknown>)[k], `${at}.${k}`);
  } else if (a !== b) structural.push(`${at}: ${JSON.stringify(a)?.slice(0, 40)} vs ${JSON.stringify(b)?.slice(0, 40)}`);
};
const { build_s: _g, ...gotRest } = got, { build_s: _r, ...refRest } = ref;
cmp(gotRest, refRest, "grid");
check("the browser's grid has the native file's structure: keys in order, shapes, grid hash", structural.length === 0,
  structural.slice(0, 4).join("; ") || `${Object.keys(got).length} fields`);
check(`and its numbers within ${REL} (Pyodide vs CPython)`, worst <= REL, `worst ${worst.toExponential(2)} at ${where}`);
check("progress reported to the end", prog.at(-1)?.phase === "assemble" && prog.at(-2)?.done === 10, `built in ${secs.toFixed(0)} s with 2 workers`);
const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed  (${secs.toFixed(0)} s)`);
process.exit(failed ? 1 : 0);
