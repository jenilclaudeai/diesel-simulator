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
}

/** A frame-exact input script (the fixture generator's format). */
export interface DriveScript {
  dt: number; n: number; throttle: number[]; brake: [number, number, number][];
  grade: [number, number][]; keys: [number, string][]; holds?: [number, number, string][];
}

export type ToWorker =
  | { type: 'load'; grid: GridFile; trans: Transmission }
  | { type: 'key'; key: string; down: boolean }
  | { type: 'run' | 'pause' }
  | { type: 'script'; script: DriveScript; init: Record<string, number> };

export interface LiveView {
  t: number; frames: number; hz: number;
  rpm: number; kmh: number; gear: string; trans: Transmission;
  throttle: number; brake: number; clutch: number; grade: number;
  boost: number; T_coolant: number; T_oil: number; fmep_bar: number; torque: number;
  hint: string; overheat: string; stalled: boolean; assist: boolean; cruise: boolean; lockup: boolean;
  trip_L: number; trip_km: number; inst_kmpl: number;
}

export type FromWorker =
  | { type: 'ready' }
  | { type: 'state'; view: LiveView }
  | { type: 'scriptResult'; events: number[][]; final: Record<string, number>; frames: number; ms: number };
