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

export interface PresetInfo {
  name: string;
  idle_rpm: number;
  rated_rpm: number;
  max_rpm: number;
  displacement_l: number;
  n_cyl: number;
}

/** describeEngine's answer: a preset's info, or a custom engine's (ADR-014) with what it was asked for. */
export interface EngineInfo extends PresetInfo {
  requested?: { peak_torque: number; peak_power_kw: number; plateau: [number, number] | null };
}

export interface RuntimeInfo {
  /** SHA-256 of the dieselsim sources actually loaded — the physics version */
  source_hash: string;
  contract: number;
  python: string;
  numpy: string;
  presets: string[];
  preset_info: Record<string, PresetInfo>;
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

/**
 * One point's crank-angle traces (Phase 6's cycle page, ADR-015). Cylinder 1's
 * arrays are in its own crank angle, theta, 0 = its firing TDC (0..720); the
 * manifold pressures are in engine angle. The two coincide for cylinder 1
 * only, when cylinder_phase_deg is 0 (FINDING-008). SI units: Pa, m^3, K,
 * J/deg (hrr), m (valve lift).
 */
export interface CycleResult {
  rpm: number; load: number; n_cyl: number; cylinder: 1; cylinder_phase_deg: number;
  summary: {
    torque: number; power: number; bmep: number; bsfc: number;
    imep_gross: number; imep_net: number; pmep: number;
    p_max: number; theta_pmax: number; dpdtheta_comb: number; T_max: number;
    mfb50: number; ign_delay_deg: number; ign_delay_ms: number; premix_fraction: number;
    burn_duration_deg: number; inj_duration_deg: number; rail_pressure: number;
    afr: number; boost_pr: number; egr_fraction: number; fuel_mg: number;
  };
  /** degrees in the same 0..720 convention; soc_* are -1 where combustion did not start */
  events: { ivo: number; ivc: number; evo: number; evc: number; soi_main: number; soi_pilot: number;
            soc_main: number; soc_pilot: number; inj_dur_main: number };
  theta: number[]; V: number[]; p: number[]; p_motored: number[]; T: number[]; hrr: number[];
  lift_int: number[]; lift_exh: number[]; p_int_manifold: number[]; p_exh_manifold: number[];
}

export interface SolverPort {
  /** Resolves once the runtime is loaded. Safe to call repeatedly. */
  ready(): Promise<RuntimeInfo>;
  solvePoint(req: PointRequest): Promise<PointResult>;
  /** One point's crank-angle traces for the cycle page; n_cycles at least 9. */
  solveCycle(req: PointRequest): Promise<CycleResult>;
  /** Name, rpm range and (for a custom engine) the brochure numbers, without a solve. */
  describeEngine(engine: EngineRef): Promise<EngineInfo>;
  buildGrid(req: GridRequest, opts?: GridOptions): Promise<Grid>;
  dispose(): void;
}
