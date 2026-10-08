// Shared pieces of the live-loop port (dieselsim/live.py).
//
// State fields keep their Python names (T_coolant, phase_t, _cruise_i, ...)
// so that a state snapshot from the Python reference loads into the port
// field for field -- the per-step differential test depends on it (ADR-004).

/** The parts of EngineSpec the live loop reads, in dataclasses.asdict form. */
export interface LiveSpec {
  idle_rpm: number;
  rated_rpm: number;
  max_rpm: number;
  geom: { displacement: number; flywheel_inertia: number };
  thermal: {
    ambient_T: number; ambient_p: number; thermostat_open_T: number; thermostat_full_T: number;
    coolant_volume: number; metal_mass: number;
  };
  cooling: {
    grille_recovery: number; rad_core_area: number; fan_on_T: number; fan_off_T: number;
    fan_type: string; fan_ramp_s: number; fan_max_flow: number; fan_power_max: number;
    ic_UA_ref: number; ic_air_ref: number; ic_ahead_of_rad: boolean;
    rad_UA_ref: number; rad_air_ref: number;
    T_warn: number; T_derate: number; T_derate_full: number; derate_floor: number;
    allow_shutdown: boolean; T_shutdown: number; T_restart: number;
  };
  turbo: { comp_eff_peak: number; intercooler_eff: number; enabled?: boolean };
}

export type Perf = Record<string, number>;

export const TWO_PI = 2.0 * Math.PI;

export function clip(x: number, lo: number, hi: number): number {
  return Math.min(Math.max(x, lo), hi); // numpy.clip on scalars
}

/** math.copysign: |x| with the sign of y, including -0.0. */
export function copysign(x: number, y: number): number {
  return y < 0 || Object.is(y, -0) ? -Math.abs(x) : Math.abs(x);
}

/** numpy.sign */
export function sign(x: number): number {
  return x > 0 ? 1 : x < 0 ? -1 : 0;
}
