// The numpy step of prepare-assets.mjs on a network that cannot reach the
// Pyodide CDN (a corporate proxy, an offline laptop). No download is needed:
// every case points PYODIDE_CDN at a host that cannot resolve.
//
//   A. a build (no --dev): stops, exit 1, and says what to do
//   B. npm start (--dev), outside CI: carries on, NUMPY_BUNDLED = false
//   C. --dev inside CI: still stops -- a deployable build never lacks numpy
//   D. PYODIDE_WHEEL_DIR pointing at a wrong file: stops, names the path
//
// The wheel already in public/pyodide (if any) is moved aside first and put
// back at the end, and prepare-assets is re-run so the tree is left as found.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const app = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const script = path.join(app, "scripts", "prepare-assets.mjs");
const outPy = path.join(app, "public", "pyodide");
const gen = path.join(app, "src", "app", "solver", "physics-version.ts");
const BAD = "https://nonexistent.invalid/pyodide";

const results = [];
const check = (name, ok, note = "") => {
  results.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${note ? "  -- " + note : ""}`);
};
function run(args, env) {
  const e = { ...process.env, ...env };
  for (const [k, v] of Object.entries(env)) if (v === undefined) delete e[k];
  const r = spawnSync(process.execPath, [script, ...args], { env: e, encoding: "utf8" });
  return { code: r.status, out: (r.stdout ?? "") + (r.stderr ?? "") };
}
const bundled = () => (fs.readFileSync(gen, "utf8").match(/NUMPY_BUNDLED = (true|false)/) ?? [])[1];

const aside = fs.mkdtempSync(path.join(os.tmpdir(), "wheel-"));
const wheels = fs.existsSync(outPy) ? fs.readdirSync(outPy).filter(f => /^numpy-.*\.whl$/.test(f)) : [];
for (const w of wheels) fs.renameSync(path.join(outPy, w), path.join(aside, w));
try {
  const a = run([], { PYODIDE_CDN: BAD, CI: undefined, PYODIDE_WHEEL_DIR: undefined });
  check("A. a build without the wheel stops, and says what to do",
    a.code !== 0 && /cannot reach nonexistent\.invalid/.test(a.out) && /NODE_USE_ENV_PROXY/.test(a.out)
      && /PYODIDE_WHEEL_DIR/.test(a.out),
    `exit ${a.code}`);

  const b = run(["--dev"], { PYODIDE_CDN: BAD, CI: undefined, PYODIDE_WHEEL_DIR: undefined });
  check("B. npm start without the wheel carries on, and the app is told",
    b.code === 0 && /carrying on WITHOUT numpy/.test(b.out) && bundled() === "false",
    `exit ${b.code}, NUMPY_BUNDLED ${bundled()}`);

  const c = run(["--dev"], { PYODIDE_CDN: BAD, CI: "true", PYODIDE_WHEEL_DIR: undefined });
  check("C. inside CI, --dev still stops", c.code !== 0 && /numpy wheel not available/.test(c.out), `exit ${c.code}`);

  const d = run([], { PYODIDE_WHEEL_DIR: "/nonexistent", CI: undefined });
  check("D. a wrong PYODIDE_WHEEL_DIR stops and names the file",
    d.code !== 0 && /cannot read \/nonexistent\/numpy-/.test(d.out), `exit ${d.code}`);
} finally {
  for (const w of wheels) fs.renameSync(path.join(aside, w), path.join(outPy, w));
  fs.rmSync(aside, { recursive: true, force: true });
  // leave the tree as a normal prepare-assets leaves it
  const r = run([], {});
  if (r.code !== 0) console.log(`note: restoring prepare-assets failed (exit ${r.code}); run it again`);
}
const failed = results.filter(x => !x).length;
console.log(`\n${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
