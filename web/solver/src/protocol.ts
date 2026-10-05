/**
 * Messages between the main thread and the solver worker.
 *
 * Every request carries an id; every reply echoes it. A grid build may emit
 * any number of 'progress' messages before its single 'result' or 'error'.
 */
import type {
  CycleResult, EngineInfo, EngineRef, Grid, GridProgress, GridRequest, PointRequest, PointResult, RuntimeInfo,
  SolverErrorKind,
} from "./solver-port.js";

export type Request =
  | { type: "init"; id: number }
  | { type: "solvePoint"; id: number; req: PointRequest }
  | { type: "solveCycle"; id: number; req: PointRequest }
  | { type: "describeEngine"; id: number; engine: EngineRef }
  | { type: "liveCall"; id: number; fn: LiveFn; arg: string }
  | { type: "buildGrid"; id: number; req: GridRequest }
  | { type: "cancel"; id: number };

/** The bridge functions a drivable-grid build calls (ADR-014 step 3); JSON in, JSON out. */
export const LIVE_FNS = ["live_grid_plan", "live_row_limit", "live_cell", "live_grid_assemble"] as const;
export type LiveFn = (typeof LIVE_FNS)[number];

export interface WireError {
  kind: SolverErrorKind;
  message: string;
  traceback?: string;
}

export type Reply =
  | { type: "result"; id: number; value: RuntimeInfo | PointResult | CycleResult | EngineInfo | Grid | string }
  | { type: "progress"; id: number; progress: GridProgress }
  | { type: "error"; id: number; error: WireError };

/**
 * The minimum a message channel has to provide. A browser Worker, the global
 * scope inside one, and Node's worker_threads ports all adapt to this in a
 * few lines — which is what lets the real worker code be tested in Node.
 */
export interface Endpoint {
  post(msg: unknown, transfer?: ArrayBuffer[]): void;
  listen(handler: (msg: unknown) => void): void;
  close?(): void;
}
