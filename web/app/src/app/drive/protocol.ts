// Messages between the drive page and its 60 Hz worker.
import type { Adr011GridData, EngineView, LiveSpec, Transmission } from '@dieselsim/physics';

/** A prebuilt grid file (tools/build_live_grids.py, public/grids/<preset>.json). */
export interface GridFile extends Adr011GridData {
  preset: string;
  name: string;
  grid_hash: string;
  converged: boolean;
  unsettled_cells: number;
  spec: LiveSpec;
  engine_view: EngineView;
  /** ADR-014: a custom engine's vehicle (a live.VEHICLE_KEYS key); roster grids use their preset's */
  vehicle?: string;
  custom?: boolean;
  engine_json?: Record<string, unknown>;
  engine_file_sha256?: string;
}

/** A frame-exact input script (the fixture generator's format). */
export interface DriveScript {
  dt: number; n: number; throttle: number[]; brake: [number, number, number][];
  grade: [number, number][]; keys: [number, string][]; holds?: [number, number, string][];
}

export type ToWorker =
  // air: Phase 7 step 4, the place's ambient pressure [Pa] and temperature [K]; absent is standard air
  | { type: 'load'; grid: GridFile; trans: Transmission; air?: { p: number; T: number } }
  | { type: 'key'; key: string; down: boolean }
  | { type: 'run' | 'pause' }
  | { type: 'script'; script: DriveScript; init: Record<string, number> }
  | { type: 'sound'; port: MessagePort | null }    // the engine-sound worklet's end (Phase 4)
  | { type: 'pedals'; pedals: Pedals };            // touch pedals (ADR-012)

/**
 * Touch pedals (ADR-012), positions 0-1. The throttle follows the finger;
 * `null` leaves it to the keys (a released pedal sends 0 once, then null).
 * Brake and clutch are held at least this far down, and otherwise spring
 * back as the keyboard's do (pedal_return).
 */
export interface Pedals { throttle: number | null; brake: number; clutch: number }

export interface LiveView {
  t: number; frames: number; hz: number;
  rpm: number; kmh: number; gear: string; trans: Transmission;
  throttle: number; brake: number; clutch: number; grade: number;
  boost: number; T_coolant: number; T_oil: number; fmep_bar: number; torque: number;
  hint: string; overheat: string; stalled: boolean; assist: boolean; cruise: boolean; lockup: boolean;
  trip_L: number; trip_km: number; inst_kmpl: number;
  phase: number;      // the gearbox's shift phase: 0 idle, 1 torque, 2 inertia
  auto: boolean;      // automatic shifting (the paddles switch it to manual)
  // the dashboard (Phase 5)
  tank_L: number; out_of_fuel: boolean; fuel_kg_h: number;
  fan_on: boolean; T_charge: number; derate: number; engine_stopped: boolean;
  derate_heat: number;  // the overheat part of derate (engine protection); the rest is charge-air density
}

/** What the dashboard needs once per engine: its scales and limits. */
export interface DashInfo {
  idle_rpm: number; rated_rpm: number; max_rpm: number;
  vmax_kmh: number;          // the speedometer's scale: min(gearing, drag-limited top speed)
  vehicle: string; tank_L: number; gears: number;
  T_warn: number; T_derate: number; T_shutdown: number; fan_on_T: number;
  /** Phase 7 step 4: what the loop does with the air, and the table's measured worst at Leh */
  weather: 'standard' | 'table' | 'no table';
  weather_check_pct: number | null;
}

export type FromWorker =
  | { type: 'ready' }
  | { type: 'state'; view: LiveView }
  | { type: 'info'; info: DashInfo }
  | { type: 'scriptResult'; events: number[][]; final: Record<string, number>; frames: number; ms: number };
