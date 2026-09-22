// Run tests/test_physics.py, unmodified, under Pyodide in Node.
//
// This is the executable form of ADR-001: the solver runs in the browser's
// Python unchanged, and produces the same numbers as native CPython. Exit
// code mirrors the suite's, so CI can gate on it.
//
//   cd tools/pyodide && npm install && npm run suite
import { loadPyodide } from "pyodide";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "..", "..");
const ROOT = "/home/pyodide/repo";

const t0 = performance.now();
const py = await loadPyodide();
await py.loadPackage("numpy");     // see README if the CDN is unreachable
console.log(`pyodide + numpy loaded in ${((performance.now() - t0) / 1000).toFixed(1)} s`);

// copy the package and tests in exactly as they are on disk
for (const dir of ["dieselsim", "tests"]) {
  py.FS.mkdirTree(`${ROOT}/${dir}`);
  for (const f of fs.readdirSync(path.join(repo, dir))) {
    if (f.endsWith(".py"))
      py.FS.writeFile(`${ROOT}/${dir}/${f}`, fs.readFileSync(path.join(repo, dir, f)));
  }
}

const code = await py.runPythonAsync(`
import runpy, sys, time, numpy
print(f"python {sys.version.split()[0]}  numpy {numpy.__version__}")
t = time.time()
try:
    runpy.run_path("${ROOT}/tests/test_physics.py", run_name="__main__")
    rc = 0
except SystemExit as e:
    rc = int(e.code or 0)
print(f"suite wall time under pyodide: {time.time() - t:.0f} s")
print("scipy imported:", "scipy" in sys.modules)
rc
`);
process.exit(code);
