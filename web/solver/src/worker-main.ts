/**
 * Runs inside the solver worker. Owns the Pyodide instance and answers
 * requests from worker-client.ts.
 *
 * Environment-neutral: how Pyodide is loaded and where the dieselsim sources
 * come from are injected, so the same loop runs in a browser Worker and under
 * Node's worker_threads.
 */
import type { PyodideInterface } from "pyodide";
import type { Endpoint, Reply, Request, WireError } from "./protocol.js";
import type {
  Grid, GridCell, GridRequest, PointRequest, PointResult, RuntimeInfo,
} from "./solver-port.js";

export interface WorkerRuntime {
  /** Load Pyodide itself. Browser: loadPyodide({ indexURL }). */
  loadPyodide(): Promise<PyodideInterface>;
  /** The dieselsim package, as file name -> source text. */
  loadSources(): Promise<Record<string, string>>;
}

const PKG_ROOT = "/home/pyodide";

export function serveSolver(ep: Endpoint, rt: WorkerRuntime): void {
  let booting: Promise<{ py: PyodideInterface; info: RuntimeInfo }> | undefined;
  const cancelled = new Set<number>();

  const boot = () => (booting ??= (async () => {
    const t0 = performance.now();
    const py = await rt.loadPyodide();
    await py.loadPackage("numpy");
    py.FS.mkdirTree(`${PKG_ROOT}/dieselsim`);
    for (const [name, text] of Object.entries(await rt.loadSources())) {
      py.FS.writeFile(`${PKG_ROOT}/dieselsim/${name}`, text);
    }
    py.runPython(
      `import sys, warnings\n` +
      `warnings.filterwarnings("ignore", category=RuntimeWarning)\n` +
      `sys.path.insert(0, "${PKG_ROOT}")\n` +
      `import dieselsim.bridge`);
    const info = JSON.parse(callBridge(py, "runtime_info", "{}")) as RuntimeInfo;
    info.load_s = (performance.now() - t0) / 1000;
    return { py, info };
  })());

  const reply = (msg: Reply, transfer?: ArrayBuffer[]) => ep.post(msg, transfer);

  ep.listen(async (raw) => {
    const msg = raw as Request;
    if (msg.type === "cancel") { cancelled.add(msg.id); return; }
    try {
      if (msg.type === "init") {
        const { info } = await boot().catch(e => { throw asLoadError(e); });
        reply({ type: "result", id: msg.id, value: info });
      } else if (msg.type === "solvePoint") {
        const { py } = await boot();
        reply({ type: "result", id: msg.id, value: solvePoint(py, msg.req) });
      } else if (msg.type === "buildGrid") {
        const { py } = await boot();
        const grid = await buildGrid(py, msg.id, msg.req, cancelled, reply);
        const transfer = grid.cells.flatMap(
          c => Object.values(c.src).map(a => a.buffer as ArrayBuffer));
        reply({ type: "result", id: msg.id, value: grid }, transfer);
      } else {
        throw wire("protocol", `unknown request type '${(raw as { type?: unknown }).type}'`);
      }
    } catch (e) {
      reply({ type: "error", id: msg.id, error: toWire(e) });
    } finally {
      cancelled.delete(msg.id);
    }
  });
}

function callBridge(py: PyodideInterface, fn: string, arg: string): string {
  const bridge = py.pyimport("dieselsim.bridge");
  try {
    return bridge[fn](arg) as string;
  } finally {
    bridge.destroy();
  }
}

function solvePoint(py: PyodideInterface, req: PointRequest): PointResult {
  return JSON.parse(callBridge(py, "solve_point", JSON.stringify(req))) as PointResult;
}

async function buildGrid(
  py: PyodideInterface, id: number, req: GridRequest,
  cancelled: Set<number>, reply: (m: Reply) => void,
): Promise<Grid> {
  const total = req.rpms.length * req.loads.length;
  const cells: GridCell[] = [];
  const bridge = py.pyimport("dieselsim.bridge");
  try {
    for (const [i, rpm] of req.rpms.entries()) {
      for (const [j, load] of req.loads.entries()) {
        // Yield to the event loop so a pending 'cancel' can be seen. Python
        // runs synchronously, so this is the only point cancellation can land.
        await new Promise(r => setTimeout(r, 0));
        if (cancelled.has(id)) throw wire("cancelled", `grid build cancelled after ${cells.length}/${total} cells`);

        const cellReq: Record<string, unknown> = { engine: req.engine, rpm, load };
        if (req.n_cycles !== undefined) cellReq["n_cycles"] = req.n_cycles;
        const res = bridge.solve_grid_cell(JSON.stringify(cellReq));
        try {
          const [head, arrays] = res.toJs({ dict_converter: Object.fromEntries }) as
            [string, Record<string, Uint8Array>];
          const parsed = JSON.parse(head) as { perf: Record<string, number>; meta: Record<string, number>; n: number };
          const src: Record<string, Float32Array> = {};
          for (const [k, bytes] of Object.entries(arrays)) {
            // Copy into a fresh, aligned buffer. The bytes are little-endian
            // float32 ('<f4'); every browser in practical use is little-endian.
            const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
            src[k] = new Float32Array(buf);
            if (src[k].length !== parsed.n) throw wire("protocol", `source '${k}' has ${src[k].length} samples, expected ${parsed.n}`);
          }
          cells.push({ i, j, perf: parsed.perf, meta: parsed.meta, src });
        } finally {
          res.destroy();
        }
        reply({ type: "progress", id, progress: { done: cells.length, total, rpm, load } });
      }
    }
  } finally {
    bridge.destroy();
  }
  return { rpms: req.rpms, loads: req.loads, cells };
}

// ---------------------------------------------------------------- errors

class WireFault extends Error {
  constructor(readonly w: WireError) { super(w.message); }
}
function wire(kind: WireError["kind"], message: string): WireFault {
  return new WireFault({ kind, message });
}
function asLoadError(e: unknown): WireFault {
  return e instanceof WireFault ? e : wire("load", `runtime failed to load: ${(e as Error)?.message ?? String(e)}`);
}

/** Map anything thrown — including Python exceptions — onto the wire format. */
function toWire(e: unknown): WireError {
  if (e instanceof WireFault) return e.w;
  const err = e as { type?: string; message?: string };
  const text = err?.message ?? String(e);
  if (err?.type) {                            // Pyodide's PythonError carries the Python class name
    const last = text.trim().split("\n").pop() ?? text;
    const clean = last.replace(/^[\w.]+:\s*/, "");
    if (err.type === "RequestError") return { kind: "invalid-request", message: clean };
    if (err.type === "ArithmeticError") return { kind: "non-finite", message: clean, traceback: text };
    return { kind: "python", message: `${err.type}: ${clean}`, traceback: text };
  }
  return { kind: "protocol", message: text };
}
