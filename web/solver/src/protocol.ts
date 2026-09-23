/**
 * Messages between the main thread and the solver worker.
 *
 * Every request carries an id; every reply echoes it. A grid build may emit
 * any number of 'progress' messages before its single 'result' or 'error'.
 */
import type {
  Grid, GridProgress, GridRequest, PointRequest, PointResult, RuntimeInfo,
  SolverErrorKind,
} from "./solver-port.js";

export type Request =
  | { type: "init"; id: number }
  | { type: "solvePoint"; id: number; req: PointRequest }
  | { type: "buildGrid"; id: number; req: GridRequest }
  | { type: "cancel"; id: number };

export interface WireError {
  kind: SolverErrorKind;
  message: string;
  traceback?: string;
}

export type Reply =
  | { type: "result"; id: number; value: RuntimeInfo | PointResult | Grid }
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
