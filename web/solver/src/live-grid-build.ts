/**
 * A drivable grid built in the browser (ADR-014 step 3): converged, warm and
 * cold, by a pool of solver workers. The pieces are dieselsim.bridge's
 * live_* functions -- the same ones tools/build_live_grids.py builds with --
 * so the result is the same file the native tool writes.
 *
 * Rows first: each row's converged fuel limit, then that row's cells (warm
 * and cold) the moment it is known, so no worker waits for the whole first
 * phase. Every finished piece goes to a store, so a build that is closed or
 * cancelled resumes where it stopped.
 */
import type { LiveFn } from "./protocol.js";
import { SolverError, type EngineRef } from "./solver-port.js";

/** One worker's view: a bridge live_* call. WorkerSolver implements it. */
export interface LiveCaller {
  liveCall(fn: LiveFn, arg: string): Promise<string>;
}

/** Where finished pieces are kept between sessions (IndexedDB in the app). */
export interface PieceStore {
  get(key: string): Promise<string | undefined>;
  put(key: string, value: string): Promise<void>;
  /** drop every piece under a prefix: a finished build's, once its file is kept elsewhere */
  clear(prefix: string): Promise<void>;
}

export class MemoryPieceStore implements PieceStore {
  readonly map = new Map<string, string>();
  async get(k: string) { return this.map.get(k); }
  async put(k: string, v: string) { this.map.set(k, v); }
  async clear(prefix: string) { for (const k of [...this.map.keys()]) if (k.startsWith(prefix)) this.map.delete(k); }
}

/** The browser's piece store: IndexedDB, so a closed tab resumes its build. */
export class IndexedDbPieceStore implements PieceStore {
  private dbp: Promise<IDBDatabase> | undefined;
  constructor(readonly dbName = "dieselsim-live-pieces", private readonly idb: IDBFactory = globalThis.indexedDB) {}
  private db(): Promise<IDBDatabase> {
    return (this.dbp ??= new Promise((ok, fail) => {
      const open = this.idb.open(this.dbName, 1);
      open.onupgradeneeded = () => { open.result.createObjectStore("pieces"); };
      open.onsuccess = () => ok(open.result);
      open.onerror = () => fail(open.error);
    }));
  }
  private async tx<T>(mode: IDBTransactionMode, f: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
    const t = (await this.db()).transaction("pieces", mode);
    const r = f(t.objectStore("pieces"));
    return new Promise((ok, fail) => {
      t.oncomplete = () => ok(r.result);
      t.onerror = () => fail(t.error);
      t.onabort = () => fail(t.error);
    });
  }
  async get(k: string) { return (await this.tx("readonly", s => s.get(k))) as string | undefined; }
  async put(k: string, v: string) { await this.tx("readwrite", s => s.put(v, k)); }
  async clear(prefix: string) {
    // keys are "<prefix>:...": the range [prefix, prefix + \uffff] holds exactly them
    await this.tx("readwrite", s => s.delete(IDBKeyRange.bound(prefix, prefix + "\uffff")));
  }
}

export interface LiveBuildProgress {
  phase: "rows" | "cells" | "assemble";
  /** pieces finished (row limits + cells), of total; resumed pieces count as done */
  done: number;
  total: number;
  resumed: number;
  /** seconds left, from this session's timed pieces (see etaSeconds); undefined until one finishes */
  etaS?: number;
}

export interface LiveBuildOptions {
  /** the grid's key (its "preset" field) */
  key: string;
  /** build_live_grids.py's size; default the roster's 8 x 6 */
  size?: [number, number];
  /** fields added to the file (a custom engine's vehicle, JSON, ...) */
  extra?: Record<string, unknown>;
  store?: PieceStore;
  /** a prefix for the store's keys, e.g. liveBuildKey(...) */
  storeKey?: string;
  onProgress?: (p: LiveBuildProgress) => void;
  signal?: AbortSignal;
}

interface Cell { perf: Record<string, number>; p_cyl_f32: string; src_f32: Record<string, string>; meta: Record<string, number> }
type Task = { kind: "row"; i: number } | { kind: "cell"; i: number; j: number; cold: boolean };

/**
 * A row's converged fuel calibration costs about this many cells (ADR-014:
 * 199 s against ~50 s under Pyodide). Used only until the session has timed
 * a piece of each kind.
 */
export const ROW_PER_CELL = 4;

/**
 * Seconds left: the worker-seconds still to spend, spread over the workers,
 * but never less than the longest chain left (an unfinished row, then one of
 * its cells). It replaced elapsed / pieces done x pieces left, which counted a
 * row as one piece and ignored that every worker had been busy: it read
 * 258 min at the first piece of a 19 min build (B-04).
 *
 * rowS / cellS: mean seconds per piece of each kind timed this session
 * (undefined if none yet); rowsUnstarted: rows not yet taken by a worker;
 * cellsLeft: cells not finished (running ones included); running: the elapsed
 * seconds of each piece in flight.
 */
export function etaSeconds(s: { rowS?: number; cellS?: number; rowsUnstarted: number; cellsLeft: number;
                                running: { kind: "row" | "cell"; elapsedS: number }[]; workers: number }): number | undefined {
  if (s.rowS === undefined && s.cellS === undefined) return undefined;
  const cell = s.cellS ?? s.rowS! / ROW_PER_CELL;
  const row = s.rowS ?? cell * ROW_PER_CELL;
  const left = (k: "row" | "cell", e: number) => Math.max(0, (k === "row" ? row : cell) - e);
  let work = s.rowsUnstarted * row + s.cellsLeft * cell;
  for (const r of s.running) work += r.kind === "row" ? left("row", r.elapsedS) : 0;
  for (const r of s.running) if (r.kind === "cell") work -= Math.min(cell, r.elapsedS);
  const runningRows = s.running.filter(r => r.kind === "row");
  const chain = s.rowsUnstarted > 0 ? row + cell
    : runningRows.length ? Math.max(...runningRows.map(r => left("row", r.elapsedS))) + cell
    : Math.max(0, ...s.running.map(r => left(r.kind, r.elapsedS)), s.cellsLeft > s.running.length ? cell : 0);
  return Math.max(work / s.workers, chain);
}

/** Build the grid file (as JSON text) with these workers. */
export async function buildLiveGrid(engine: EngineRef, workers: LiveCaller[], opts: LiveBuildOptions): Promise<string> {
  if (!workers.length) throw new SolverError("invalid-request", "a live-grid build needs at least one worker");
  const [n_rpm, n_load] = opts.size ?? [8, 6];
  const store = opts.store, prefix = opts.storeKey ?? "";
  const t0 = performance.now();
  const plan = JSON.parse(await workers[0]!.liveCall("live_grid_plan", JSON.stringify({ engine, n_rpm, n_load }))) as
    { rpms: number[]; loads: number[] };
  const total = n_rpm + 2 * n_rpm * n_load;
  const flims: (number | undefined)[] = new Array(n_rpm).fill(undefined);
  const cells: Record<"warm" | "cold", (Cell | undefined)[][]> = {
    warm: plan.rpms.map(() => new Array<Cell | undefined>(n_load).fill(undefined)),
    cold: plan.rpms.map(() => new Array<Cell | undefined>(n_load).fill(undefined)),
  };
  const sk = (t: Task) => `${prefix}:${t.kind === "row" ? `row:${t.i}` : `${t.cold ? "cold" : "warm"}:${t.i}:${t.j}`}`;
  let done = 0, resumed = 0;
  // this session's timings, per kind, and the pieces in flight (for etaSeconds)
  const spent = { row: 0, cell: 0 }, timed = { row: 0, cell: 0 };
  const running = new Map<Task, number>();
  const report = (phase: LiveBuildProgress["phase"]) => {
    const p: LiveBuildProgress = { phase, done, total, resumed };
    const now = performance.now(), rowsDone = flims.filter(f => f !== undefined).length;
    const runningRows = [...running.keys()].filter(t => t.kind === "row").length;
    const eta = etaSeconds({
      ...(timed.row ? { rowS: spent.row / timed.row } : {}), ...(timed.cell ? { cellS: spent.cell / timed.cell } : {}),
      rowsUnstarted: n_rpm - rowsDone - runningRows, cellsLeft: total - done - (n_rpm - rowsDone),
      running: [...running].map(([t, since]) => ({ kind: t.kind, elapsedS: (now - since) / 1000 })), workers: workers.length,
    });
    if (eta !== undefined) p.etaS = eta;
    opts.onProgress?.(p);
  };
  const cellTasks = (i: number): Task[] =>
    [false, true].flatMap(cold => plan.loads.map((_, j) => ({ kind: "cell", i, j, cold }) as Task));
  const record = (t: Task, text: string) => {
    if (t.kind === "row") flims[t.i] = (JSON.parse(text) as { fuel_limit: number }).fuel_limit;
    else cells[t.cold ? "cold" : "warm"][t.i]![t.j] = JSON.parse(text) as Cell;
  };

  // what earlier sessions finished
  const ready: Task[] = [];
  for (let i = 0; i < n_rpm; i++) {
    const row: Task = { kind: "row", i };
    const got = store ? await store.get(sk(row)) : undefined;
    if (got === undefined) { ready.push(row); continue; }
    record(row, got); done++; resumed++;
    for (const t of cellTasks(i)) {
      const c = store ? await store.get(sk(t)) : undefined;
      if (c === undefined) ready.push(t);
      else { record(t, c); done++; resumed++; }
    }
  }
  report(done < n_rpm ? "rows" : "cells");

  // the pool: each worker loops, taking the next ready task; a finished row
  // releases its cells, and a worker with nothing ready waits for a change
  const arg = (t: Task) => t.kind === "row"
    ? JSON.stringify({ engine, rpm: plan.rpms[t.i] })
    : JSON.stringify({ engine, rpm: plan.rpms[t.i], load: plan.loads[t.j], fuel_limit: flims[t.i], cold: t.cold });
  let failure: unknown, inFlight = 0;
  let changed!: () => void;
  let change = new Promise<void>(r => (changed = r));
  const notify = () => { const c = changed; change = new Promise<void>(r => (changed = r)); c(); };
  const loop = async (w: LiveCaller): Promise<void> => {
    for (;;) {
      if (failure !== undefined || opts.signal?.aborted) return;
      const t = ready.shift();
      if (!t) {
        if (inFlight === 0) return;          // nothing running could release more
        await change;
        continue;
      }
      inFlight++;
      const started = performance.now();
      running.set(t, started);
      try {
        const text = await w.liveCall(t.kind === "row" ? "live_row_limit" : "live_cell", arg(t));
        running.delete(t);
        spent[t.kind] += (performance.now() - started) / 1000; timed[t.kind]++;
        record(t, text);
        if (store) await store.put(sk(t), text);
        done++;
        if (t.kind === "row") ready.push(...cellTasks(t.i));
        report(flims.some(f => f === undefined) ? "rows" : "cells");
      } catch (e) {
        failure ??= e;
      } finally {
        running.delete(t);
        inFlight--;
        notify();
      }
    }
  };
  // Stop answers at once: a running Python piece can't be interrupted (no
  // SharedArrayBuffer, ADR-003), so waiting for the loops meant waiting up to
  // a whole row (B-04). The caller terminates the workers; finished pieces
  // are already in the store, and the loops' late results are ignored.
  const pool = Promise.all(workers.map(loop));
  const stopped = new Promise<never>((_, reject) => {
    const fire = () => reject(new SolverError("cancelled", `live-grid build cancelled after ${done}/${total} pieces (they are kept)`));
    if (opts.signal?.aborted) fire(); else opts.signal?.addEventListener("abort", fire, { once: true });
  });
  pool.catch(() => { /* after a stop the loops end on the disposed workers' errors */ });
  stopped.catch(() => { /* raced below */ });
  await Promise.race([pool, stopped]);
  if (failure !== undefined) throw failure;
  if (opts.signal?.aborted) throw new SolverError("cancelled", `live-grid build cancelled after ${done}/${total} pieces (they are kept)`);

  report("assemble");
  return workers[0]!.liveCall("live_grid_assemble", JSON.stringify({
    engine, key: opts.key, rpms: plan.rpms, loads: plan.loads, fuel_limits: flims,
    warm: cells.warm, cold: cells.cold, build_s: Math.round((performance.now() - t0) / 1000), extra: opts.extra ?? {},
  }));
}
