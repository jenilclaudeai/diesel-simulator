// Node worker_threads adapter for the real worker loop. The only
// Node-specific code on the worker side; serveSolver itself is shared with
// the browser.
import { parentPort } from "node:worker_threads";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadPyodide } from "pyodide";
import { serveSolver } from "../src/worker-main.js";

// compiled to web/solver/dist/test/ -> repo root is four levels up
const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");
const port = parentPort!;

serveSolver(
  {
    post: (m, t) => port.postMessage(m, t ?? []),
    listen: h => { port.on("message", h); },
  },
  {
    // Route Python's stdout/stderr explicitly. Pyodide's default writer calls
    // fs.writeSync on process.stdout's fd, which is undefined inside a
    // worker_threads worker, so anything Python printed was lost behind an
    // "Error thrown in write" trace.
    loadPyodide: () => loadPyodide({
      stdout: s => console.log(`[py] ${s}`),
      stderr: s => console.error(`[py:err] ${s}`),
    }),
    loadSources: async () => Object.fromEntries(
      fs.readdirSync(path.join(repo, "dieselsim"))
        .filter(f => f.endsWith(".py"))
        .map(f => [f, fs.readFileSync(path.join(repo, "dieselsim", f), "utf8")])),
  },
);
