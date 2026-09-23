/**
 * SolverPort — the single seam between the UI and the physics (ADR-001).
 *
 * The UI depends on this interface only. Today the implementation is the
 * Python solver running unmodified under Pyodide in a Web Worker; if that ever
 * has to become WASM, only the implementation behind this interface changes.
 *
 * Nothing here depends on Angular, so it is testable in plain Node.
 */

/** How an engine is described. Mirrors dieselsim/bridge.py. */
export type EngineRef =
  | { preset: string; overrides?: Overrides }
  | { headline: Record<string, unknown>; overrides?: Overrides };

/**
 * Dotted-path spec overrides, e.g. { "turbo.turbine_area_eff": 4e-4 }.
 * Validated in Python: an unknown path, a type mismatch or a non-finite value
 * is rejected as 'invalid-request', never silently ignored.
 */
export type Overrides = Record<string, number | boolean | string | number[]>;

export interface RuntimeInfo {
  contract: number;
  python: string;
  numpy: string;
  presets: string[];
  grid_cycles: number;
  source_keys: string[];
  /** seconds to load Pyodide, numpy and the package — the cold-start cost */
  load_s: number;
}

export interface PointRequest {
  engine: EngineRef;
  rpm: number;
  /** 0..1, fraction of the rated fuel limit at this speed */
  load: number;
  /** default 9; below 9 results drift measurably (known bug #1) */
  n_cycles?: number;
}

export interface PointResult {
  rpm: number; load: number; fuel_mg: number;
  torque: number; power: number; bmep: number; bsfc: number;
  fmep: number; eta_mech: number; p_max: number; boost_pr: number;
  turbo_rpm: number; afr: number; T_exh: number;
  nox_g_kwh: number; soot_g_kwh: number; fuel_kg_h: number;
  h_ring_mid: number;
}

export interface GridRequest {
  engine: EngineRef;
  rpms: number[];
  loads: number[];
  n_cycles?: number;
}

export interface GridCell {
  i: number; j: number;
  perf: Record<string, number>;
  meta: Record<string, number>;
  /** crank-angle sources, one per SOURCE_KEY, float32 */
  src: Record<string, Float32Array>;
}

export interface Grid {
  rpms: number[];
  loads: number[];
  cells: GridCell[];
}

export interface GridProgress {
  done: number;
  total: number;
  rpm: number;
  load: number;
}

export interface GridOptions {
  onProgress?: (p: GridProgress) => void;
  /**
   * Aborting stops the build between cells. A cell already being solved runs
   * to completion first — Python runs synchronously in the worker, and
   * interrupting mid-cell would need SharedArrayBuffer, which ADR-003 avoids
   * so the app can be hosted on GitHub Pages. Granularity is one cell.
   */
  signal?: AbortSignal;
}

export type SolverErrorKind =
  | "invalid-request"   // malformed request; message says what was wrong
  | "non-finite"        // solver produced NaN/inf; caught at the boundary
  | "python"            // any other Python exception; traceback attached
  | "load"              // Pyodide, numpy or the package failed to load
  | "cancelled"         // aborted by the caller
  | "protocol";         // internal messaging failure — a bug

export class SolverError extends Error {
  constructor(
    readonly kind: SolverErrorKind,
    message: string,
    readonly traceback?: string,
  ) {
    super(message);
    this.name = "SolverError";
  }
}

export interface SolverPort {
  /** Resolves once the runtime is loaded. Safe to call repeatedly. */
  ready(): Promise<RuntimeInfo>;
  solvePoint(req: PointRequest): Promise<PointResult>;
  buildGrid(req: GridRequest, opts?: GridOptions): Promise<Grid>;
  dispose(): void;
}
