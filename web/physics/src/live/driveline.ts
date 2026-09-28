// Port of dieselsim/live.py: LaunchClutch, TorqueConverter, Gearbox and the
// Driveline that couples them to the vehicle. Line for line with the
// Python (read it for the physics commentary); held to it by
// fixtures/live.json.
import { clip, copysign, sign, TWO_PI, type LiveSpec } from "./common.js";
import type { Vehicle } from "./vehicle.js";

/** The wet clutch a dual-clutch box launches on. */
export class LaunchClutch {
  cap_max: number;
  engaged = false;
  cap = 0.0;
  slip = 0.0;
  SR = 0.0;
  TR = 1.0;
  eff = 0.0;

  constructor(readonly spec: LiveSpec, readonly veh: Vehicle) {
    const T_pk = Math.max(50.0, (spec.geom.displacement * 1.9e6) / (4 * Math.PI));
    this.cap_max = veh.clutch_cap_max || 1.8 * T_pk;
  }

  target_speed(throttle: number): number {
    const idle = (2.0 * Math.PI * this.spec.idle_rpm) / 60.0;
    const launch = (2.0 * Math.PI * this.veh.launch_rpm) / 60.0;
    return idle + Math.min(1.0, Math.max(0.0, throttle)) * (launch - idle);
  }

  /** Capacity to command this instant, and whether we are stuck. */
  command(w_e: number, w_sync: number, T_eng: number, throttle: number, creep: number): [number, boolean] {
    this.slip = w_e - w_sync;
    const w_t = this.target_speed(throttle);
    const idle = (2.0 * Math.PI * this.spec.idle_rpm) / 60.0;
    if (w_sync < 0.8 * idle && throttle < 0.03) {
      this.engaged = false;
      this.cap = creep * 0.1 * this.cap_max;
      return [this.cap, false];
    }
    if (this.engaged) {
      const need = Math.abs(T_eng);
      if (need > this.cap_max) {
        this.cap = this.cap_max;
        this.engaged = false;
        return [this.cap, false];
      }
      this.cap = this.cap_max;
      return [this.cap, true];
    }
    const cap = T_eng + 9.0 * (w_e - w_t);
    this.cap = clip(cap, 0.0, this.cap_max);
    if (Math.abs(this.slip) < 3.0 && this.cap < this.cap_max) {
      this.engaged = true;
      return [this.cap, true];
    }
    return [this.cap, false];
  }

  report(w_e: number, w_in: number): void {
    this.SR = w_in / Math.max(w_e, 1.0);
    this.TR = 1.0;
    this.eff = !this.engaged ? Math.min(1.0, this.SR) : 1.0;
  }
}

/** A dry, driver-operated clutch (see ManualClutch in live.py for the physics). */
export class ManualClutch {
  static readonly BITE_K = 1.6;
  cap_max: number;
  engaged = false;
  cap = 0.0;
  slip = 0.0;
  SR = 0.0;
  TR = 1.0;
  eff = 0.0;

  constructor(readonly spec: LiveSpec, readonly veh: Vehicle) {
    const T_pk = Math.max(50.0, (spec.geom.displacement * 1.9e6) / (4 * Math.PI));
    this.cap_max = veh.clutch_cap_max || 1.8 * T_pk;
  }

  capacity(pedal: number): number {
    return this.cap_max * Math.max(0.0, 1.0 - pedal) ** ManualClutch.BITE_K;
  }

  target_speed(throttle: number): number {
    const idle = (2.0 * Math.PI * this.spec.idle_rpm) / 60.0;
    const launch = (2.0 * Math.PI * this.veh.launch_rpm) / 60.0;
    return idle + Math.min(1.0, Math.max(0.0, throttle)) * (launch - idle);
  }

  /** What the auto-clutch commands when it is not mid-shift. */
  assist_capacity(w_e: number, w_sync: number, T_eng: number, throttle: number): number {
    const idle = (2.0 * Math.PI * this.spec.idle_rpm) / 60.0;
    if (w_e <= 0.85 * idle) this.engaged = false;
    if (w_sync < 0.8 * idle && throttle < 0.03) return 0.0;
    if (this.engaged) return this.cap_max;
    const cap = T_eng + 9.0 * (w_e - this.target_speed(throttle));
    return clip(cap, 0.0, this.cap_max);
  }

  report(w_e: number, w_in: number): void {
    this.SR = w_in / Math.max(w_e, 1.0);
    this.TR = 1.0;
    this.eff = !this.engaged ? Math.min(1.0, this.SR) : 1.0;
  }
}

/** Fluid coupling with a stator. */
export class TorqueConverter {
  k_cap: number;
  stall_rpm: number;
  TR_stall: number;
  SR_couple = 0.86;
  SR = 0.0;
  TR: number;
  eff = 0.0;

  constructor(spec: LiveSpec, veh: Vehicle) {
    const T_ref = 1.05 * Math.max(0.1, (spec.geom.displacement * 1.9e6) / (4 * Math.PI));
    const n_stall = veh.stall_rpm || 0.52 * spec.rated_rpm;
    const w_stall = (2.0 * Math.PI * n_stall) / 60.0;
    this.k_cap = (T_ref / w_stall ** 2) * veh.tc_diameter_gain;
    this.stall_rpm = n_stall;
    this.TR_stall = veh.TR_stall;
    this.TR = veh.TR_stall;
  }

  private lam(SR: number): number {
    const x = Math.min(Math.max(SR, -0.3), 1.4);
    if (x < 0.0) return 1.0 + 0.9 * Math.abs(x) ** 1.6;
    return x <= 1.0 ? Math.max(-1.2, 1.0 - x ** 4.2) : -((x - 1.0) ** 1.6) * 3.0;
  }

  torques(w_e: number, w_t: number): [number, number] {
    w_e = Math.max(w_e, 1.0);
    const SR = w_t / w_e;
    this.SR = SR;
    const T_p = this.k_cap * this.lam(SR) * w_e ** 2;
    let TR: number;
    if (SR < this.SR_couple) {
      const f = Math.max(0.0, 1.0 - SR / this.SR_couple);
      TR = 1.0 + (this.TR_stall - 1.0) * f ** 1.25;
    } else {
      TR = 1.0;
    }
    this.TR = TR;
    this.eff = Math.max(0.0, TR * Math.min(SR, 1.0));
    return [T_p, TR * T_p];
  }
}

/** Clutch-to-clutch automatic with a real two-phase shift. */
export class Gearbox {
  static readonly IDLE = 0;
  static readonly TORQUE = 1;
  static readonly INERTIA = 2;

  n: number;
  gear = 0;
  gear_from = 0;
  auto = true;
  neutral = false;
  phase = Gearbox.IDLE;
  phase_t = 0.0;
  hold_t = 0.0;
  T_TORQUE: number;
  T_INERTIA: number;
  HOLD_S = 1.2;
  up_rpm: number;
  dn_rpm: number;
  torque_cut = 0.0;
  blend = 0.0;
  err0 = 0.0;
  coast = false; // this shift is an off-throttle downshift (bug #11)
  /** bug #11: coast downshifts stretch both phases (FINDING-020) */
  static readonly COAST_TORQUE_K = 2.0;
  static readonly COAST_INERTIA_K = 4.0;

  constructor(readonly spec: LiveSpec, readonly veh: Vehicle) {
    this.n = veh.gears.length;
    const heavy = Math.min(2.0, Math.max(0.7, (veh.mass / 1750.0) ** 0.18));
    if (veh.trans === "dct") {
      this.T_TORQUE = 0.045 * heavy;
      this.T_INERTIA = 0.13 * heavy;
    } else {
      this.T_TORQUE = 0.11 * heavy;
      this.T_INERTIA = 0.26 * heavy;
    }
    this.up_rpm = 0.86 * spec.rated_rpm;
    this.dn_rpm = 0.52 * spec.rated_rpm;
  }

  ratio(g?: number): number {
    const gg = g === undefined ? this.gear : g;
    return this.veh.gears[gg]! * this.veh.final;
  }

  shifting(): boolean {
    return this.phase !== Gearbox.IDLE;
  }

  t_torque(): number {
    return this.T_TORQUE * (this.coast ? Gearbox.COAST_TORQUE_K : 1.0);
  }

  t_inertia(): number {
    return this.T_INERTIA * (this.coast ? Gearbox.COAST_INERTIA_K : 1.0);
  }

  request(delta: number, kickdown = false, coast = false): boolean {
    const g = Math.trunc(clip(this.gear + delta, 0, this.n - 1));
    if (g === this.gear || this.shifting()) return false;
    this.coast = coast;
    this.gear_from = this.gear;
    this.gear = g;
    this.phase = Gearbox.TORQUE;
    this.phase_t = 0.0;
    this.blend = 0.0;
    this.hold_t = this.HOLD_S * (kickdown ? 0.4 : 1.0);
    return true;
  }

  update_schedule(dt: number, n_turbine: number, throttle: number, d_throttle: number): void {
    if (this.shifting() || this.neutral || !this.auto) return;
    this.hold_t = Math.max(0.0, this.hold_t - dt);
    if (this.hold_t > 0.0) return;
    const up = this.up_rpm * (0.8 + 0.28 * throttle);
    const r = this.veh.gears;
    let dn: number;
    if (this.gear > 0) {
      const step_dn = r[this.gear - 1]! / r[this.gear]!;
      dn = Math.min(this.dn_rpm * (0.72 + 0.3 * throttle), (0.8 * up) / step_dn);
    } else {
      dn = 0.0;
    }
    if (d_throttle > 1.2 && throttle > 0.55 && this.gear > 0) {
      for (const skip of [2, 1]) {
        const g = this.gear - skip;
        if (g < 0) continue;
        const n_after = (n_turbine * r[g]!) / r[this.gear]!;
        if (n_after < 0.95 * this.spec.rated_rpm) {
          this.request(-skip, true);
          return;
        }
      }
    }
    if (n_turbine > up && this.gear < this.n - 1) this.request(+1);
    else if (n_turbine < dn && this.gear > 0) this.request(-1, false, throttle < 0.05);
  }
}

/** Extra clutch capacity that clears the latched slip on schedule. */
export function s_inertia(dl: Driveline, gb: Gearbox): number {
  const J = dl.spec_J;
  return (J * gb.err0) / Math.max(gb.t_inertia(), 0.03);
}

/** Converter or launch clutch + clutch-to-clutch gearbox + vehicle. */
export class Driveline {
  static readonly C_LOCK = 900.0; // retired lock-up spring (FINDING-020)
  static readonly T_LOCK_MAX = 4500.0;
  static readonly LOCK_ENGAGE_S = 0.5;

  readonly kind: string;
  readonly tc: LaunchClutch | TorqueConverter | ManualClutch;
  readonly gb: Gearbox;
  rigid = false;
  i_eff: number;
  _sync_dt = 1.0 / 240.0;
  snap_w_e: number | null = null;
  v = 0.0;
  w_in = 0.0;
  J_in: number;
  spec_J: number;
  grade = 0.0;
  brake = 0.0;
  lockup = false;
  lock_allowed = true;
  slip_rpm = 0.0;
  T_pump = 0.0;
  T_turb = 0.0;
  T_clutch = 0.0;
  F_trac = 0.0;
  F_res = 0.0;
  torque_cut = 0.0;
  _thr_prev = 0.0;
  // manual box: the pedal, the auto-clutch assist and its shift sequence
  clutch_pedal = 0.0; // 0 = foot off (engaged), 1 = floored
  assist = false;
  shift_t = -1.0;     // < 0: no assisted shift in progress
  shift_to = 0;
  // converter lock-up clutch (FINDING-020)
  lock_slip0 = 0.0;
  lock_latched = false;
  static readonly SHIFT_DOWN_S = 0.12;
  static readonly SHIFT_UP_S = 0.35;

  constructor(readonly spec: LiveSpec, readonly veh: Vehicle) {
    this.kind = veh.trans;
    this.tc = this.kind === "dct" ? new LaunchClutch(spec, veh)
      : this.kind === "manual" ? new ManualClutch(spec, veh)
      : new TorqueConverter(spec, veh);
    this.gb = new Gearbox(spec, veh);
    this.i_eff = veh.gears[0]! * veh.final;
    this.J_in = (0.055 * veh.mass) / 1750.0 + 0.02;
    this.spec_J = spec.geom.flywheel_inertia + this.J_in;
  }

  w_out_at_input(g?: number): number {
    return (this.v / this.veh.r_wheel) * this.gb.ratio(g);
  }

  w_turbine(): number {
    return this.w_in;
  }

  speed_kmh(): number {
    return this.v * 3.6;
  }

  resistance(): [number, number] {
    const v = this.veh;
    const th = Math.atan(this.grade);
    const f_roll = v.Crr * v.mass * 9.81 * Math.cos(th) * (this.v > 0.05 ? 1.0 : 0.0);
    const f_grade = v.mass * 9.81 * Math.sin(th);
    const f_aero = 0.5 * 1.2 * v.CdA * this.v ** 2;
    const f_brake = this.brake * 0.55 * v.mass * 9.81;
    return [f_roll + f_grade + f_aero, f_brake];
  }

  /** After the engine has been integrated, drag the car with it. */
  sync(w_e: number): void {
    if (this.rigid) {
      const i = Math.max(this.i_eff, 1e-6);
      const v_new = Math.max(0.0, (w_e * this.veh.r_wheel) / i);
      const dv_max = 12.0 * Math.max(this._sync_dt, 1e-4);
      this.v += clip(v_new - this.v, -dv_max, dv_max);
    }
  }

  step(dt: number, w_e: number, T_eng: number, throttle: number): [number, number] {
    if (this.kind === "dct") return this.step_dct(dt, w_e, T_eng, throttle);
    if (this.kind === "manual") return this.step_manual(dt, w_e, T_eng, throttle);
    return this.step_tc(dt, w_e, T_eng, throttle);
  }

  /** Move the lever: out of neutral into 1st, or one gear up/down. */
  private select(delta: number): void {
    const gb = this.gb;
    if (gb.neutral) {
      gb.neutral = false;
      gb.gear = gb.gear_from = 0;
      return;
    }
    const g = Math.trunc(clip(gb.gear + delta, 0, gb.n - 1));
    gb.gear = gb.gear_from = g;
  }

  /** A shift on the manual box; returns the driver message, or "" if it went through. */
  manual_shift(delta: number): string {
    if (this.assist) {
      if (this.shift_t < 0.0) {
        this.shift_t = 0.0;
        this.shift_to = delta;
      }
      return "";
    }
    if (this.clutch_pedal < 0.9) return "clutch down (z) to change gear";
    this.select(delta);
    (this.tc as ManualClutch).engaged = false;
    return "";
  }

  private step_manual(dt: number, w_e: number, T_eng: number, throttle: number): [number, number] {
    const veh = this.veh, gb = this.gb, cl = this.tc as ManualClutch;
    const [f_res, f_brake] = this.resistance();

    if (this.assist && this.shift_t >= 0.0) {
      this.shift_t += dt;
      let pedal: number;
      if (this.shift_t < Driveline.SHIFT_DOWN_S) {
        pedal = this.shift_t / Driveline.SHIFT_DOWN_S;
      } else {
        if (this.shift_to !== 0) {
          this.select(this.shift_to);
          this.shift_to = 0;
          cl.engaged = false;
        }
        const up = (this.shift_t - Driveline.SHIFT_DOWN_S) / Driveline.SHIFT_UP_S;
        pedal = Math.max(0.0, 1.0 - up);
        if (up >= 1.0) this.shift_t = -1.0;
      }
      this.clutch_pedal = pedal;
    }

    const i = gb.ratio();
    const w_sync = (this.v / veh.r_wheel) * i;
    let cap: number;
    if (gb.neutral) {
      cap = 0.0;
      cl.engaged = false;
    } else if (this.assist && this.shift_t < 0.0) {
      cap = cl.assist_capacity(w_e, w_sync, T_eng, throttle);
    } else {
      cap = cl.capacity(this.clutch_pedal);
    }
    cl.cap = cap;
    cl.slip = w_e - w_sync;

    if (cl.engaged) {
      if (cap <= 0.0 || Math.abs(T_eng) > cap) cl.engaged = false;
    } else if (cap > 0.0 && Math.abs(cl.slip) < 3.0 && Math.abs(T_eng) <= cap) {
      cl.engaged = true;
      this.i_eff = i;
      this.snap_w_e = w_sync;
    }
    this.rigid = cl.engaged;
    let T_cl: number;
    if (this.rigid) T_cl = T_eng;
    else if (gb.neutral || cap <= 0.0) T_cl = 0.0;
    else T_cl = copysign(cap, w_e >= w_sync ? 1.0 : -1.0);

    cl.report(w_e, w_sync);
    this._sync_dt = dt;
    this.i_eff = i;
    this.w_in = w_sync;
    this.T_pump = T_cl;
    this.T_turb = T_cl;
    this.T_clutch = T_cl;
    gb.torque_cut = 0.0;
    this.torque_cut = 0.0;

    const F_trac = (T_cl * i * veh.eta) / veh.r_wheel;
    this.F_trac = F_trac;
    this.F_res = f_res + f_brake;
    const m_eff = veh.mass + (veh.J_wheel + veh.J_trans * i ** 2) / veh.r_wheel ** 2;
    if (this.rigid) {
      const k = veh.r_wheel / Math.max(i, 1e-6);
      const J_add = (m_eff * k * k) / Math.max(veh.eta, 0.5);
      const T_react = ((f_res + f_brake * sign(Math.max(this.v, 0.0) + 1e-9)) * k) / Math.max(veh.eta, 0.5);
      return [T_react, J_add];
    }
    let F_net = F_trac - f_res;
    if (this.v > 0.05 || F_net > f_brake) F_net -= f_brake * sign(Math.max(this.v, 0.0) + 1e-9);
    this.v = Math.max(0.0, this.v + (F_net / m_eff) * dt);
    return [T_cl, 0.0];
  }

  private step_dct(dt: number, w_e: number, T_eng: number, throttle: number): [number, number] {
    const veh = this.veh, gb = this.gb, tc = this.tc as LaunchClutch;
    const d_thr = (throttle - this._thr_prev) / Math.max(dt, 1e-6);
    this._thr_prev = throttle;
    gb.update_schedule(dt, (w_e * 60.0) / (2 * Math.PI), throttle, d_thr);

    const i_new = gb.ratio();
    const i_old = gb.ratio(gb.gear_from);
    const w_sync = (this.v / veh.r_wheel) * i_new;
    const creep = throttle > 0.02 ? 1.0 : 0.0;
    gb.torque_cut = 0.0;
    const [f_res, f_brake] = this.resistance();
    let T_cl: number, i_use: number;

    if (gb.phase === Gearbox.TORQUE) {
      gb.phase_t += dt;
      const x = Math.min(1.0, gb.phase_t / gb.t_torque());
      gb.blend = x;
      i_use = (1.0 - x) * i_old + x * i_new;
      T_cl = T_eng;
      this.rigid = false;
      if (gb.phase_t >= gb.t_torque()) {
        gb.phase = Gearbox.INERTIA;
        gb.phase_t = 0.0;
        gb.err0 = Math.abs(w_e - (this.v / veh.r_wheel) * i_new);
      }
    } else if (gb.phase === Gearbox.INERTIA) {
      gb.phase_t += dt;
      const err = w_e - w_sync;
      const cap = Math.abs(T_eng) + s_inertia(this, gb);
      T_cl = Math.abs(err) > 1e-3 ? copysign(Math.min(cap, tc.cap_max), err) : T_eng;
      gb.torque_cut = err > 0 ? 0.25 : 0.0;
      this.rigid = false;
      i_use = i_new;
      if (Math.abs(err) < 2.0 || gb.phase_t > 2.5 * gb.t_inertia()) {
        gb.phase = Gearbox.IDLE;
        gb.phase_t = 0.0;
        gb.blend = 0.0;
        gb.gear_from = gb.gear;
        tc.engaged = true;
      }
    } else if (gb.neutral) {
      T_cl = 0.0;
      this.rigid = false;
      i_use = i_new;
    } else {
      const [cap, stuck] = tc.command(w_e, w_sync, T_eng, throttle, creep);
      if (stuck && !this.rigid) {
        this.i_eff = i_new;
        this.snap_w_e = w_sync;
      }
      this.rigid = stuck;
      T_cl = stuck ? T_eng : copysign(cap, w_e >= w_sync ? 1.0 : -1.0);
      i_use = i_new;
    }

    tc.report(w_e, w_sync);
    this._sync_dt = dt;
    this.i_eff = i_use;
    this.w_in = w_sync;
    this.T_pump = T_cl;
    this.T_turb = T_cl;
    this.T_clutch = T_cl;
    this.torque_cut = gb.torque_cut;

    const F_trac = (T_cl * i_use * veh.eta) / veh.r_wheel;
    this.F_trac = F_trac;
    this.F_res = f_res + f_brake;
    const m_eff = veh.mass + (veh.J_wheel + veh.J_trans * i_use ** 2) / veh.r_wheel ** 2;

    if (this.rigid) {
      const k = veh.r_wheel / Math.max(i_use, 1e-6);
      const J_add = (m_eff * k * k) / Math.max(veh.eta, 0.5);
      const T_react = ((f_res + f_brake * sign(Math.max(this.v, 0.0) + 1e-9)) * k) / Math.max(veh.eta, 0.5);
      return [T_react, J_add];
    }

    let F_net = F_trac - f_res;
    if (this.v > 0.05 || F_net > f_brake) F_net -= f_brake * sign(Math.max(this.v, 0.0) + 1e-9);
    this.v = Math.max(0.0, this.v + (F_net / m_eff) * dt);
    return [T_cl, 0.0];
  }

  private step_tc(dt: number, w_e: number, T_eng: number, throttle: number): [number, number] {
    const veh = this.veh, gb = this.gb, tc = this.tc as TorqueConverter;
    const d_thr = (throttle - this._thr_prev) / Math.max(dt, 1e-6);
    this._thr_prev = throttle;

    gb.update_schedule(dt, (this.w_in * 60.0) / (2 * Math.PI), throttle, d_thr);

    const i_new = gb.ratio();
    const i_old = gb.ratio(gb.gear_from);
    const w_sync = this.w_out_at_input();

    // ---- lockup ----
    if (this.lock_allowed && !gb.neutral && !gb.shifting()) {
      if (!this.lockup) {
        if (this.v > veh.v_lock_min && throttle < 0.88 && gb.gear >= 2 && tc.SR > 0.62) this.lockup = true;
      } else if (this.v < 0.75 * veh.v_lock_min || throttle > 0.95
                 || w_e < (2 * Math.PI * 1.05 * this.spec.idle_rpm) / 60) {
        this.lockup = false;
      }
    } else {
      this.lockup = false;
    }

    // ---- the lock-up clutch: a clutch, not a spring (FINDING-020) ----
    const slip = w_e - this.w_in;
    if (!this.lockup) {
      this.rigid = false;
      this.lock_latched = false;
    } else if (!this.lock_latched) {
      this.lock_slip0 = slip;
      this.lock_latched = true;
    }
    const [T_p, T_t] = tc.torques(w_e, this.w_in);
    let T_lock = 0.0;
    if (this.lockup && !this.rigid) {
      const cap = Math.min(Driveline.T_LOCK_MAX,
        Math.abs(T_eng) + (this.spec.geom.flywheel_inertia * Math.abs(this.lock_slip0)) / Driveline.LOCK_ENGAGE_S);
      if (Math.abs(slip) < 3.0 || slip * this.lock_slip0 <= 0.0) {
        this.rigid = true;
        this.snap_w_e = this.w_in;
      } else {
        T_lock = copysign(cap, slip);
      }
    }
    if (this.rigid && Math.abs(T_eng) > Driveline.T_LOCK_MAX) {
      this.rigid = false;
      this.lock_latched = false;
    }
    const T_in = this.rigid ? T_eng : T_t + T_lock;
    this.slip_rpm = ((w_e - this.w_in) * 60.0) / (2 * Math.PI);

    gb.torque_cut = 0.0;
    let T_out_i: number, i_use: number;
    if (gb.neutral) {
      this.w_in += ((T_t * 0.06) / this.J_in) * dt;
      T_out_i = 0.0;
      i_use = i_new;
    } else if (gb.phase === Gearbox.TORQUE) {
      gb.phase_t += dt;
      const x = Math.min(1.0, gb.phase_t / gb.t_torque());
      gb.blend = x;
      this.w_in = this.w_out_at_input(gb.gear_from);
      i_use = (1.0 - x) * i_old + x * i_new;
      T_out_i = T_in;
      if (gb.phase_t >= gb.t_torque()) {
        gb.phase = Gearbox.INERTIA;
        gb.phase_t = 0.0;
        gb.err0 = Math.abs(this.w_in - this.w_out_at_input());
      }
    } else if (gb.phase === Gearbox.INERTIA) {
      gb.phase_t += dt;
      const err = this.w_in - w_sync;
      let cap = Math.abs(T_in) + (this.J_in * gb.err0) / Math.max(gb.t_inertia(), 0.05);
      cap = Math.min(cap, 8.0 * Math.max(Math.abs(T_in), 50.0));
      const T_cl = Math.abs(err) > 1e-3 ? copysign(cap, err) : T_in;
      gb.torque_cut = err > 0 ? 0.35 : 0.0;
      this.w_in += ((T_in - T_cl) / this.J_in) * dt;
      T_out_i = T_cl;
      i_use = i_new;
      const done = Math.abs(err) < 2.0
        || (gb.err0 > 0 && err * copysign(1.0, gb.err0) < 0)
        || gb.phase_t > 2.5 * gb.t_inertia();
      if (done) {
        this.w_in = w_sync;
        gb.phase = Gearbox.IDLE;
        gb.phase_t = 0.0;
        gb.blend = 0.0;
        gb.gear_from = gb.gear;
      }
    } else {
      this.w_in = w_sync;
      T_out_i = T_in;
      i_use = i_new;
    }

    this.torque_cut = gb.torque_cut;
    this.T_pump = this.rigid ? T_in : T_p * (gb.neutral ? 0.06 : 1.0) + T_lock;
    this.T_turb = T_out_i;
    this.T_clutch = T_out_i;

    // ---- vehicle ----
    const F_trac = (T_out_i * i_use * veh.eta) / veh.r_wheel;
    const [f_res, f_brake] = this.resistance();
    const m_eff = veh.mass + (veh.J_wheel + (veh.J_trans + this.J_in) * i_use ** 2) / veh.r_wheel ** 2;
    this._sync_dt = dt;
    this.i_eff = i_use;
    if (this.rigid) {
      // locked up: one body, solved as the DCT's clamped state
      this.F_trac = F_trac;
      this.F_res = f_res + f_brake;
      const k = veh.r_wheel / Math.max(i_use, 1e-6);
      const J_add = (m_eff * k * k) / Math.max(veh.eta, 0.5);
      const T_react = ((f_res + f_brake * sign(Math.max(this.v, 0.0) + 1e-9)) * k) / Math.max(veh.eta, 0.5);
      return [T_react, J_add];
    }
    let F_net = F_trac - f_res;
    if (this.v > 0.05 || F_net > f_brake) F_net -= f_brake * sign(Math.max(this.v, 0.0) + 1e-9);
    this.F_trac = F_trac;
    this.F_res = f_res + f_brake;
    this.v = Math.max(0.0, this.v + (F_net / m_eff) * dt);
    if (!gb.shifting() && !gb.neutral) this.w_in = this.w_out_at_input();
    this.rigid = false;
    return [this.T_pump, 0.0];
  }
}

export { TWO_PI };
