// Port of dieselsim/live.py LiveEngine -- what actually gets integrated in
// real time -- and the driver controls (handle_key, pedal_return). Line for
// line with the Python; held to it by fixtures/live.json at the ADR-004
// per-step (1e-12) and terminal (1e-6, event-aligned) bounds.
import { clip, type LiveSpec, type Perf } from "./common.js";
import { Driveline, Gearbox, type ManualClutch } from "./driveline.js";
import type { PerfGrid } from "./grid.js";
import { Adr011Grid } from "./adr011.js";
import { FrictionModel, type EngineView, type FrictionSpec, type WearState } from "../friction.js";
import { Oil } from "../lubrication.js";
import { running_skirt_clearance, T_COOLANT_REF, WALL_FOLLOW } from "../slap.js";
import { finishVehicle, vehicleFor, type Transmission, type Vehicle } from "./vehicle.js";

export class LiveEngine {
  readonly spec: LiveSpec;
  readonly veh: Vehicle;
  readonly dl: Driveline;
  rpm: number;
  throttle = 0.0;
  engine_brake = false;
  boost = 1.0;
  turbo_rpm = 0.0;
  load_eff = 0.0;
  stalled = false;
  T_load = 0.0;
  torque = 0.0;
  fuel_kg_h = 0.0;
  // trip computer
  FUEL_DENSITY = 0.832; // kg/L
  odo_m = 0.0;
  trip_m = 0.0;
  fuel_L = 0.0;
  trip_L = 0.0;
  inst_kmpl = 0.0;
  // cruise control
  cruise_on = false;
  cruise_set = 0.0; // m/s
  _cruise_i = 0.0;
  cruise_min_kmh = 25.0;
  // cooling system
  T_coolant: number;
  fan_on = false;
  fan_frac = 0.0;
  fan_power = 0.0;
  T_charge: number;
  T_charge_ref: number;
  ic_eff = 0.0;
  rad_air = 0.0;
  derate = 1.0;
  derate_heat = 1.0;
  derate_charge = 1.0;
  engine_stopped = false;
  overheat_msg = "";
  hint = "";
  hint_t = 0.0;
  tank_L: number;
  out_of_fuel = false;
  perf: Perf;
  // ADR-011: friction live, from the cells' pressure traces
  adr011: boolean;
  T_oil: number;
  T_fric = 0.0;     // mean friction torque [N.m], held between evaluations
  fmep_live = 0.0;
  P_mech = 0.0;     // friction heat into the oil [W]
  // the live friction's sound inputs (Phase 4), held like T_fric
  Pb_live = 0.0;    // boundary friction power [W]
  skirt_live = 0.0; // running skirt clearance [m] (FINDING-023)
  vseat_live = 0.0; // valve seating speed [m/s]
  _frame = 0;
  private fric?: FrictionModel;
  private fspec?: FrictionSpec;       // private copy: its walls follow the live coolant
  private oil?: Oil;
  private wear?: WearState;
  private th0?: { liner_T_top: number; liner_T_bot: number };

  /** frames between live friction evaluations (10 Hz at 60 Hz) */
  static readonly FRICTION_EVERY = 6;

  constructor(readonly g: PerfGrid, preset = "hd_i6", trans: Transmission = "dct", view?: EngineView) {
    this.spec = g.spec;
    this.veh = finishVehicle(vehicleFor(preset, trans));
    this.dl = new Driveline(this.spec, this.veh);
    this.rpm = this.spec.idle_rpm;
    this.T_coolant = this.spec.thermal.ambient_T;
    this.T_charge = this.spec.thermal.ambient_T;
    this.T_charge_ref = this.spec.thermal.ambient_T;
    this.tank_L = this.veh.fuel_tank_L;
    this.perf = g.blendPerf(this.rpm, 0.0);
    if (this.veh.trans === "manual") {
      // a manual car is left in neutral; the driver picks a gear
      this.dl.gb.neutral = true;
      this.dl.gb.auto = false;
    }
    this.adr011 = g instanceof Adr011Grid;
    this.T_oil = this.spec.thermal.ambient_T; // cold start, like the coolant
    if (this.adr011) {
      if (!view) throw new Error("an ADR-011 grid needs the engine view (spec, cams, oil, wear) for live friction");
      this.fspec = structuredClone(view.spec);
      this.th0 = { liner_T_top: view.spec.thermal.liner_T_top, liner_T_bot: view.spec.thermal.liner_T_bot };
      this.fric = new FrictionModel(this.fspec, view.cams);
      this.oil = new Oil(this.fspec.oil, { ...view.oil });
      this.wear = { ...view.wear };
      this.update_friction();
    }
  }

  /**
   * ADR-011: friction at the live oil and coolant state, from the pressure
   * trace blended at the live operating point (live.py _update_friction).
   */
  update_friction(): void {
    const g = this.g as Adr011Grid, fs = this.fspec!;
    // _apply_thermal_state: the walls follow the coolant (only the liner is read here)
    const f = this.T_coolant - T_COOLANT_REF;
    fs.thermal.liner_T_top = this.th0!.liner_T_top + WALL_FOLLOW.liner_T_top * f;
    fs.thermal.liner_T_bot = this.th0!.liner_T_bot + WALL_FOLLOW.liner_T_bot * f;
    this.oil!.cond.T_oil = this.T_oil;
    const rpm = Math.max(this.rpm, 0.25 * this.spec.idle_rpm);
    const p = g.blendPerfT(rpm, this.load_eff, this.T_coolant);
    const r = this.fric!.evaluate(g.grid_deg, g.blendPCyl(rpm, this.load_eff, this.T_coolant), rpm, this.oil!,
      this.wear!, 1.05e5, p["fuel_mg"]!, p["p_rail"]!);
    this.fmep_live = r["fmep"]!;
    this.P_mech = r["P_mech"]!;
    this.T_fric = this.fmep_live * g.k_torque;
    // acoustics.build_sources' definitions, at the live oil and coolant
    this.Pb_live = r["Pb_rings"]! + r["Pb_skirt"]! + r["Pb_rods"]! + r["Pb_mains"]! + r["Pb_pin"]!;
    // FINDING-023: slap follows the running clearance, not the film
    this.skirt_live = running_skirt_clearance(this.fric!.eff_skirt_clearance(this.wear!), fs.geom.bore, this.T_coolant);
    this.vseat_live = r["v_seating"]!;
  }

  /** What the streaming synth takes live (live.py sound_inputs): boost,
   *  turbo speed and load, and under ADR-011 the live friction's. */
  sound_inputs(): Record<string, number> {
    const out: Record<string, number> = { boost: this.boost, turbo_rpm: this.turbo_rpm, load: this.load_eff };
    if (this.adr011) Object.assign(out, { Pb: this.Pb_live, skirt_clr: this.skirt_live, v_seating: this.vseat_live });
    return out;
  }

  /** Grid performance at the live state; torque is BRAKE torque either way. */
  private perfAt(rpm: number, load: number): Perf {
    if (this.adr011) {
      const p = (this.g as Adr011Grid).blendPerfT(rpm, load, this.T_coolant);
      p["torque"] = p["torque_ind"]! - this.T_fric;
      return p;
    }
    return this.g.blendPerf(rpm, load);
  }

  /** a manual engine stalls when the clutch drags it below this fraction of idle */
  static readonly STALL_FRAC = 0.45;

  cruise_toggle(): void {
    if (this.cruise_on) {
      this.cruise_on = false;
      return;
    }
    if (this.dl.speed_kmh() >= this.cruise_min_kmh) {
      this.cruise_on = true;
      this.cruise_set = this.dl.v;
      this._cruise_i = this.throttle;
    }
  }

  cruise_adjust(d_kmh: number): void {
    if (this.cruise_on) this.cruise_set = Math.max(this.cruise_min_kmh / 3.6, this.cruise_set + d_kmh / 3.6);
  }

  private cruise(dt: number): void {
    if (!this.cruise_on) return;
    if (this.dl.brake > 0.02 || this.dl.gb.neutral || this.dl.speed_kmh() < 0.6 * this.cruise_min_kmh) {
      this.cruise_on = false;
      return;
    }
    const err = this.cruise_set - this.dl.v;
    this._cruise_i += 0.11 * err * dt;
    this._cruise_i = clip(this._cruise_i, 0.0, 1.0);
    this.throttle = clip(0.22 * err + this._cruise_i, 0.0, 1.0);
  }

  /** Effectiveness of a crossflow core, both fluids unmixed. */
  static eff_crossflow(NTU: number, Cr: number): number {
    if (NTU <= 1e-6) return 0.0;
    if (Cr < 1e-3) return 1.0 - Math.exp(-NTU);
    const e = 1.0 - Math.exp((NTU ** 0.22 / Cr) * (Math.exp(-Cr * NTU ** 0.78) - 1.0));
    return Math.min(Math.max(e, 0.0), 0.99);
  }

  private thermal(dt: number): void {
    const t = this.spec.thermal, c = this.spec.cooling;
    const cp_air = 1005.0, rho_air = 1.2;
    const T_amb = t.ambient_T;

    // ---- airflow through the stack ----
    const v_face = this.dl.v * c.grille_recovery;
    const mdot_ram = rho_air * c.rad_core_area * v_face;
    let want: number;
    if (this.T_coolant > c.fan_on_T) want = 1.0;
    else if (this.T_coolant < c.fan_off_T) want = 0.0;
    else want = this.fan_frac;
    if (c.fan_type === "fixed") want = 1.0;
    this.fan_frac += (want - this.fan_frac) * Math.min(1.0, dt / c.fan_ramp_s);
    this.fan_on = this.fan_frac > 0.05;
    const mdot_fan = c.fan_max_flow * this.fan_frac;
    const mdot_air = Math.max(0.02, mdot_ram + mdot_fan);
    this.rad_air = mdot_air;
    this.fan_power = c.fan_power_max * this.fan_frac ** 3;

    // ---- charge-air cooler ----
    const afr = Math.max(10.0, this.perf["afr"] ?? 20.0);
    const mdot_charge = Math.max(1e-4, (this.fuel_kg_h / 3600.0) * afr);
    const pr = Math.max(1.0, this.boost);
    const eta_c = Math.max(0.4, this.spec.turbo.comp_eff_peak * 0.92);
    const T_comp_out = T_amb * (1.0 + (pr ** 0.2857 - 1.0) / eta_c);
    const C_ch = mdot_charge * cp_air;
    const C_ca = mdot_air * cp_air;
    const Cmin = Math.min(C_ch, C_ca), Cmax = Math.max(C_ch, C_ca);
    const UA_ic = c.ic_UA_ref * (mdot_air / Math.max(c.ic_air_ref, 1e-6)) ** 0.6;
    this.ic_eff = LiveEngine.eff_crossflow(UA_ic / Math.max(Cmin, 1e-6), Cmin / Math.max(Cmax, 1e-6));
    this.T_charge = T_comp_out - this.ic_eff * (T_comp_out - T_amb);
    const Q_ic = this.ic_eff * Cmin * Math.max(T_comp_out - T_amb, 0.0);
    this.T_charge_ref = T_comp_out - this.spec.turbo.intercooler_eff * (T_comp_out - T_amb);

    // ---- radiator ----
    const T_air_rad = T_amb + (c.ic_ahead_of_rad ? Q_ic / Math.max(C_ca, 1e-6) : 0.0);
    const UA_rad = c.rad_UA_ref * (mdot_air / Math.max(c.rad_air_ref, 1e-6)) ** 0.6;
    const eff_rad = 1.0 - Math.exp(-UA_rad / Math.max(C_ca, 1e-6));
    let x = (this.T_coolant - t.thermostat_open_T) / Math.max(t.thermostat_full_T - t.thermostat_open_T, 1.0);
    x = Math.min(1.0, Math.max(0.0, x));
    const Q_out = x * eff_rad * C_ca * Math.max(this.T_coolant - T_air_rad, 0.0);

    // ---- coolant + metal node ----
    const cp_cool = 3600.0, rho_cool = 1035.0, cp_metal = 480.0;
    const C = t.coolant_volume * rho_cool * cp_cool + t.metal_mass * cp_metal;
    const P_fuel = (this.fuel_kg_h / 3600.0) * 42.7e6;
    const q_wall = clip(this.perf["q_wall"] ?? 0.2, 0.05, 0.45);
    let Q_in = (q_wall + 0.02) * P_fuel;
    if (this.adr011) {
      // ADR-011: an oil node, as engine.py's two-node warm-up
      const UA_o = this.fspec!.oil.cooler_UA * (0.35 + 0.65 * Math.min(1.0, this.rpm / 1800.0));
      const Q_oc = UA_o * (this.T_oil - this.T_coolant);
      Q_in += Q_oc;
      const m_oil = this.fspec!.oil.sump_volume * this.oil!.density(this.T_oil);
      this.T_oil += ((this.P_mech + 0.055 * P_fuel - Q_oc) * dt) / (m_oil * 1900.0);
      this.T_oil = Math.min(Math.max(this.T_oil, 240.0), 430.0);
    }
    this.T_coolant += ((Q_in - Q_out) * dt) / C;
    this.T_coolant = Math.min(Math.max(this.T_coolant, 240.0), 420.0);
    this.protect();
  }

  private protect(): void {
    const c = this.spec.cooling;
    this.derate_charge = clip(this.T_charge_ref / Math.max(this.T_charge, 1.0), 0.7, 1.0);
    const T = this.T_coolant;
    if (T <= c.T_derate) {
      this.derate_heat = 1.0;
    } else {
      const f = (T - c.T_derate) / Math.max(c.T_derate_full - c.T_derate, 1.0);
      this.derate_heat = clip(1.0 - (1.0 - c.derate_floor) * f, c.derate_floor, 1.0);
    }
    if (c.allow_shutdown && T >= c.T_shutdown) this.engine_stopped = true;
    if (this.engine_stopped && T < c.T_restart) this.overheat_msg = "cooled down -- press r to restart";
    else if (this.engine_stopped) this.overheat_msg = "ENGINE STOPPED: OVERHEAT";
    else if (T >= c.T_derate) this.overheat_msg = "DERATING -- coolant temperature";
    else if (T >= c.T_warn) this.overheat_msg = "coolant temperature high";
    else this.overheat_msg = "";
    this.derate = this.derate_heat * this.derate_charge;
  }

  coolant_C(): number {
    return this.T_coolant - 273.15;
  }

  fuel_frac(): number {
    return Math.max(0.0, this.tank_L / Math.max(this.veh.fuel_tank_L, 1e-6));
  }

  range_km(): number {
    const e = this.trip_kmpl() || this.avg_kmpl();
    return e > 0.05 ? this.tank_L * e : 0.0;
  }

  refuel(): void {
    this.tank_L = this.veh.fuel_tank_L;
    this.out_of_fuel = false;
  }

  private totals(dt: number): void {
    const d = this.dl.v * dt;
    this.odo_m += d;
    this.trip_m += d;
    const litres = ((this.fuel_kg_h / 3600.0) * dt) / this.FUEL_DENSITY;
    this.fuel_L += litres;
    this.trip_L += litres;
    this.tank_L = Math.max(0.0, this.tank_L - litres);
    this.out_of_fuel = this.tank_L <= 0.0;
    const lph = this.fuel_kg_h / this.FUEL_DENSITY;
    const inst = lph > 1e-6 ? this.dl.speed_kmh() / lph : 0.0;
    const a = Math.min(1.0, dt / 0.8);
    this.inst_kmpl += (Math.min(inst, 99.9) - this.inst_kmpl) * a;
  }

  reset_trip(): void {
    this.trip_m = 0.0;
    this.trip_L = 0.0;
  }

  trip_kmpl(): number {
    return this.trip_L > 1e-6 ? this.trip_m / 1000.0 / this.trip_L : 0.0;
  }

  avg_kmpl(): number {
    return this.fuel_L > 1e-6 ? this.odo_m / 1000.0 / this.fuel_L : 0.0;
  }

  /** One 60 Hz frame, integrated in sub-steps (the converter is stiff). */
  step(dt: number, n_sub = 4): void {
    if (this.hint_t > 0.0) {
      this.hint_t = Math.max(0.0, this.hint_t - dt);
      if (this.hint_t === 0.0) this.hint = "";
    }
    this.cruise(dt);
    if (this.out_of_fuel || this.engine_stopped) {
      this.throttle = 0.0;
      this.cruise_on = false;
    }
    if (this.adr011) {
      if (this._frame % LiveEngine.FRICTION_EVERY === 0) this.update_friction();
      this._frame += 1;
    }
    for (let k = 0; k < n_sub; k++) this.sub(dt / n_sub);
    this.totals(dt);
    this.thermal(dt);
  }

  private sub(h: number): void {
    const s = this.spec, g = this.g;
    const rpm = this.rpm;
    const manual = this.veh.trans === "manual";
    if (manual && !this.stalled && rpm < LiveEngine.STALL_FRAC * s.idle_rpm
        && !this.dl.gb.neutral && (this.dl.tc as ManualClutch).cap > 0.0) {
      this.stalled = true;
      this.hint = "stalled -- clutch down (z) and press i to restart";
      this.hint_t = 4.0;
    }

    // ---- governor: idle hold, droop above rated ----
    let demand = this.stalled ? 0.0 : this.throttle;
    if (rpm < s.idle_rpm && !this.stalled) demand = Math.max(demand, Math.min(0.75, 0.01 * (s.idle_rpm - rpm)));
    if (rpm > s.rated_rpm) {
      const x = (rpm - s.rated_rpm) / Math.max(s.max_rpm - s.rated_rpm, 1.0);
      demand *= Math.max(0.02, 1.0 - 0.98 * x ** 1.4);
    }

    // ---- turbo lag ----
    const target = this.perfAt(rpm, demand);
    const tau = target["boost"]! > this.boost ? 0.55 : 0.32;
    this.boost += (target["boost"]! - this.boost) * Math.min(1.0, h / tau);
    this.turbo_rpm += (target["turbo_rpm"]! - this.turbo_rpm) * Math.min(1.0, h / tau);

    let boost_frac: number;
    if (target["boost"]! > 1.02) {
      boost_frac = clip((this.boost - 1.0) / Math.max(target["boost"]! - 1.0, 1e-3), 0.0, 1.0);
    } else {
      boost_frac = 1.0;
    }
    this.load_eff = demand * (0.35 + 0.65 * boost_frac);

    const p = this.perfAt(rpm, this.load_eff);
    this.perf = p;
    this.torque = p["torque"]!;
    this.fuel_kg_h = p["fuel_kg_h"]!;
    if (this.engine_stopped) {
      this.torque = Math.min(this.torque, this.perfAt(rpm, 0.0)["torque"]!);
      this.fuel_kg_h = 0.0;
    }
    if (this.stalled) {
      // no fuel, and friction fades to nothing as it stops
      this.torque = Math.min(0.0, this.perfAt(rpm, 0.0)["torque"]!) * Math.min(1.0, rpm / s.idle_rpm);
      this.fuel_kg_h = 0.0;
    }
    if (this.engine_brake && this.throttle < 0.02) this.torque -= 0.3 * s.rated_rpm * 0.55;

    // ---- driveline takes torque, gives back the pump load ----
    let om = (2.0 * Math.PI * rpm) / 60.0;
    const [T_load, J_add] = this.dl.step(h, om, this.torque, this.throttle);
    this.T_load = T_load;
    if (this.dl.torque_cut > 0.0) this.torque *= 1.0 - this.dl.torque_cut;
    this.torque *= this.derate;
    if (this.fan_power > 0.0 && this.spec.cooling.fan_type !== "electric") {
      this.torque -= this.fan_power / Math.max(om, 1.0);
    }

    // ---- flywheel + converter pump ----
    // an automatic's crank never drops below 60 rpm (it cannot stall); a manual's can stop
    const om_min = manual ? 0.0 : (2.0 * Math.PI * 60.0) / 60.0;
    if (this.dl.snap_w_e !== null) {
      om = Math.max(this.dl.snap_w_e, om_min);
      this.dl.snap_w_e = null;
    } else {
      const J = s.geom.flywheel_inertia + J_add;
      om += ((this.torque - this.T_load) / J) * h;
      om = Math.max(om, om_min);
    }
    this.dl.sync(om);
    const rpm_new = Math.max((om * 60.0) / (2.0 * Math.PI), manual ? 0.0 : 60.0);
    if (!manual) this.stalled = false;
    this.rpm = Math.min(rpm_new, s.max_rpm * 1.06);
  }

  // ------------------------------------------------------------ state I/O
  /** The loop's state, nested and named exactly as live_state() in the fixture generator. */
  getState(): LiveState {
    const pick = (o: object, skip: string[]) => {
      const out: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(o)) {
        if (skip.includes(k)) continue;
        if (v === null || typeof v === "number" || typeof v === "boolean" || typeof v === "string") out[k] = v;
        else if (k === "perf") out[k] = { ...(v as Perf) };
      }
      return out;
    };
    const structure = ["g", "spec", "veh", "dl", "tc", "gb"];
    return {
      live: pick(this, structure), dl: pick(this.dl, structure),
      gb: pick(this.dl.gb, structure), tc: pick(this.dl.tc, structure),
    };
  }

  /** Load a state snapshot (e.g. Python's) -- the per-step differential test. */
  setState(s: LiveState): void {
    const put = (o: object, part: Record<string, unknown>) => {
      for (const [k, v] of Object.entries(part)) {
        if (k === "kind") continue; // structural, fixed by the transmission
        (o as Record<string, unknown>)[k] = k === "perf" ? { ...(v as Perf) } : v;
      }
    };
    put(this, s.live);
    put(this.dl, s.dl);
    put(this.dl.gb, s.gb);
    put(this.dl.tc, s.tc);
  }
}

export interface LiveState {
  live: Record<string, unknown>;
  dl: Record<string, unknown>;
  gb: Record<string, unknown>;
  tc: Record<string, unknown>;
}

// ================================================================ driver input
/** Apply one driver key -- the same map as play.py's terminal (dieselsim.live.handle_key). */
function say(live: LiveEngine, msg: string, t = 2.5): void {
  live.hint = msg;
  live.hint_t = t;
}

export function handleKey(live: LiveEngine, c: string): void {
  const gb = live.dl.gb;
  const manual = live.veh.trans === "manual";
  switch (c) {
    case "w": live.cruise_on = false; live.throttle = Math.min(1.0, live.throttle + 0.08); break;
    case "s": live.throttle = Math.max(0.0, live.throttle - 0.08); break;
    case " ": live.throttle = 1.0; break;
    case "x": live.cruise_on = false; live.throttle = 0.0; break;
    case "b": live.dl.brake = Math.min(1.0, live.dl.brake + 0.35); break;
    case "e": live.engine_brake = !live.engine_brake; break;
    case "n":
      if (manual) gb.neutral = true; // out of gear any time; into gear with . ,
      else gb.neutral = !gb.neutral;
      break;
    case "m":
      if (manual) say(live, "manual box: . and , shift, z is the clutch, a is auto-clutch");
      else gb.auto = !gb.auto;
      break;
    case ".": case ",": {
      const delta = c === "." ? +1 : -1;
      if (manual) {
        const msg = live.dl.manual_shift(delta);
        if (msg) say(live, msg);
      } else {
        gb.auto = false;
        gb.request(delta);
      }
      break;
    }
    case "z":
      if (manual) live.dl.clutch_pedal = Math.min(1.0, live.dl.clutch_pedal + 0.5);
      else say(live, "no clutch pedal -- this box is automatic");
      break;
    case "a":
      if (manual) {
        live.dl.assist = !live.dl.assist;
        say(live, live.dl.assist ? "auto-clutch on" : "auto-clutch off");
      } else {
        say(live, "auto-clutch is for the manual box");
      }
      break;
    case "i":
      if (!live.stalled) say(live, "engine is running");
      else if (live.dl.clutch_pedal >= 0.9 || gb.neutral || live.dl.assist) {
        live.stalled = false;
        live.rpm = live.spec.idle_rpm;
        say(live, "started");
      } else {
        say(live, "clutch down (z) or neutral to start");
      }
      break;
    case "]": live.dl.grade = Math.min(0.2, live.dl.grade + 0.01); break;
    case "[": live.dl.grade = Math.max(-0.2, live.dl.grade - 0.01); break;
    case "l":
      // bug #6: a DCT has no converter to lock up -- say so rather than toggle a dead flag
      if (live.dl.veh.trans === "tc") {
        live.dl.lock_allowed = !live.dl.lock_allowed;
        live.hint = live.dl.lock_allowed ? "lockup allowed" : "lockup blocked";
      } else {
        live.hint = "lockup does not apply -- DCT has no converter";
      }
      live.hint_t = 2.5;
      break;
    case "c": live.cruise_toggle(); break;
    case "+": case "=": live.cruise_adjust(+5.0); break;
    case "-": live.cruise_adjust(-5.0); break;
    case "o": live.reset_trip(); break;
    case "f": live.refuel(); break;
    case "r":
      if (live.engine_stopped && live.T_coolant < live.spec.cooling.T_restart) live.engine_stopped = false;
      live.rpm = live.spec.idle_rpm;
      live.throttle = 0.0;
      live.dl.v = 0.0;
      gb.gear = 0;
      live.dl.brake = 0.0;
      live.stalled = false;
      break;
    default:
      break;
  }
}

/** The pedals return by themselves; the clutch over 1.4 s, slowly enough to slip a launch. */
export function pedalReturn(live: LiveEngine, dt: number): void {
  live.dl.brake = Math.max(0.0, live.dl.brake - dt / 0.45);
  live.dl.clutch_pedal = Math.max(0.0, live.dl.clutch_pedal - dt / 1.4);
}

export { Gearbox };
