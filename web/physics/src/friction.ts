// Port of dieselsim/friction.py FrictionModel.evaluate (and the wear.py
// "effective" parameters it reads): crank-angle-resolved mechanical
// friction from a cylinder-pressure trace. ADR-011: the real-time loop
// evaluates this from each grid cell's stored trace at the LIVE oil and
// coolant state. Held to Python by fixtures/friction.json at 1e-6.
//
// Not ported: the phase-summed instantaneous torque trace (friction.py's
// `torque`), which the live loop does not use -- only cycle means are.
import { Cam, SliderCrank, type CamSpec } from "./kinematics.js";
import {
  bearing_state, composite_roughness, hamrock_dowson_film, LAMBDA_0, LAMBDA_K, Oil,
  ring_film_thickness, skirt_film_thickness, type Lubricant, type OilCondition,
} from "./lubrication.js";

/** The parts of EngineSpec the friction model reads (dataclasses.asdict + derived geometry). */
export interface FrictionSpec {
  geom: {
    bore: number; n_cyl: number; recip_mass: number; rot_mass_bigend: number; conrod: number;
    pin_offset: number; crank_radius: number; piston_area: number; displacement: number;
    clearance_volume: number;
  };
  trib: Record<string, number>;
  valves: Record<string, number>;
  thermal: { liner_T_top: number; liner_T_bot: number };
  oil: Lubricant;
}

/** wear.py WearState fields the friction model reads (all zero on a new engine). */
export interface WearState {
  ring_tension_loss: number; bore_wear_tdc: number; skirt_wear: number;
  main_clearance_growth: number; rod_clearance_growth: number;
  cam_wear_int: number; cam_wear_exh: number;
}

export interface EngineView {
  spec: FrictionSpec;
  cams: { intake: CamSpec; exhaust: CamSpec };
  oil: OilCondition;
  wear: WearState;
}

export type FrictionResult = Record<string, number>;

const lambdaShare = (lam: number) => 1.0 / (1.0 + (lam / LAMBDA_0) ** LAMBDA_K);

/** numpy.mean over a Float64Array (sequential sum; numpy's pairwise sum differs by ulps). */
function mean(a: Float64Array): number {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += a[i]!;
  return s / a.length;
}

export class FrictionModel {
  readonly sc: SliderCrank;
  readonly camInt: Cam;
  readonly camExh: Cam;
  readonly sigma_ring: number;
  readonly sigma_brg: number;
  readonly sigma_cam: number;

  constructor(readonly spec: FrictionSpec, cams: { intake: CamSpec; exhaust: CamSpec }) {
    const g = spec.geom, t = spec.trib;
    this.sc = new SliderCrank({ a: g.crank_radius, l: g.conrod, e: g.pin_offset, Ap: g.piston_area, Vc: g.clearance_volume });
    this.camInt = new Cam(cams.intake);
    this.camExh = new Cam(cams.exhaust);
    this.sigma_ring = composite_roughness(t["ring_face_roughness"]!, t["bore_roughness"]!);
    this.sigma_brg = composite_roughness(t["bearing_roughness"]!, 0.2e-6);
    this.sigma_cam = composite_roughness(0.15e-6, 0.2e-6);
  }

  // ---- wear.py "effective" parameters ----
  private eff(w: WearState) {
    const t = this.spec.trib, vt = this.spec.valves;
    const skirt = t["skirt_clearance_new"]! + 2.0 * w.skirt_wear + 2.0 * w.bore_wear_tdc;
    const main = t["main_clearance_new"]! + w.main_clearance_growth;
    const rod = t["rod_clearance_new"]! + w.rod_clearance_growth;
    const fm = (main / t["main_clearance_new"]!) ** 3;
    const fr = (rod / t["rod_clearance_new"]!) ** 3;
    return {
      skirt, main, rod, leak: 0.55 * fm + 0.45 * fr,
      lift_int: Math.max(0.2 * vt["intake_lift_max"]!, vt["intake_lift_max"]! - w.cam_wear_int),
      lift_exh: Math.max(0.2 * vt["exhaust_lift_max"]!, vt["exhaust_lift_max"]! - w.cam_wear_exh),
    };
  }

  /**
   * theta_deg: crank angle grid for ONE cylinder, 0..720, uniform.
   * p_cyl: cylinder pressure on that grid [Pa].
   */
  evaluate(theta_deg: ArrayLike<number>, p_cyl: ArrayLike<number>, rpm: number, oil: Oil, wear: WearState,
           p_crank = 1.05e5, fuel_mg = 0.0, p_rail = 0.0): FrictionResult {
    const spec = this.spec, g = spec.geom, t = spec.trib;
    const ns = theta_deg.length;
    const n = g.n_cyl;
    const om = (2.0 * Math.PI * rpm) / 60.0;
    const DEG = Math.PI / 180;
    const dth = (theta_deg[1]! - theta_deg[0]!) * DEG;
    const E = this.eff(wear);
    const F64 = () => new Float64Array(ns);

    // ---- kinematics and forces ----
    const dxdth = F64(), u_pist = F64(), beta = F64(), F_rod = F64(), F_side = F64(), absU = F64();
    const A_p = g.piston_area;
    for (let k = 0; k < ns; k++) {
      const th = theta_deg[k]! * DEG;
      dxdth[k] = this.sc.dxDtheta(th);
      u_pist[k] = om * dxdth[k]!;
      absU[k] = Math.abs(u_pist[k]!);
      const acc = om ** 2 * this.sc.d2xDtheta2(th) + 0.0 * dxdth[k]!;
      beta[k] = this.sc.beta(th);
      const F_gas = (p_cyl[k]! - p_crank) * A_p;
      const F_inert = -g.recip_mass * acc;
      const F_axial = F_gas + F_inert;
      F_rod[k] = F_axial / Math.cos(beta[k]!);
      F_side[k] = Math.abs(F_axial * Math.tan(beta[k]!));
    }

    // ---- oil properties at the local temperatures ----
    const T_oil = oil.cond.T_oil;
    const T_liner = 0.55 * spec.thermal.liner_T_top + 0.45 * spec.thermal.liner_T_bot;
    const T_ring = Math.min(T_liner + 25.0, T_oil + 95.0);
    const mu_ring = oil.viscosity(T_ring, 5e6, 2.0e6);
    const mu_skirt = oil.viscosity(T_liner - 20.0, 1e6, 5.0e5);
    const mu_brg = oil.viscosity(T_oil + 12.0, 2.0e7, 1.0e6);
    const mu_cam = oil.viscosity(T_oil + 5.0, 1e5, 1.0e6);
    const mu_b = oil.mu_boundary();

    // ---- 1. ring pack ----
    const b1 = t["ring_axial_width"]!;
    const tension_loss = 1.0 - wear.ring_tension_loss;
    const h_sup = t["oil_supply_film"]! * (1.0 + 2.2 * wear.ring_tension_loss + 6.0e3 * wear.bore_wear_tdc);
    const F_top = F64(), Pb_rings = F64();
    let h_ring_min = 1.0;
    let h = F64();
    for (let i = 0; i < t["n_comp_rings"]!; i++) {
      const frac = i === 0 ? 1.0 : 0.18 ** i;
      h = F64();
      for (let k = 0; k < ns; k++) {
        const p_behind = p_crank + (p_cyl[k]! - p_crank) * frac;
        const Wl = (2.0 * t["ring_tangential_load"]! * tension_loss) / g.bore + Math.max(p_behind - p_crank, 0.0) * b1;
        h[k] = ring_film_thickness(mu_ring, u_pist[k]!, b1, Wl, h_sup);
        const fb = lambdaShare(h[k]! / this.sigma_ring);
        const W_tot = Wl * Math.PI * g.bore;
        const A_face = Math.PI * g.bore * b1;
        const F_b = mu_b * fb * W_tot;
        const F_h = ((1.0 - fb) * mu_ring * absU[k]! * A_face) / h[k]!;
        F_top[k] = F_top[k]! + (F_b + F_h);
        Pb_rings[k] = Pb_rings[k]! + (F_b * absU[k]!);
        h_ring_min = Math.min(h_ring_min, h[k]!);
      }
    }
    const b_o = t["oil_ring_width"]!;
    const Wl_o = (2.0 * t["oil_ring_load"]! * tension_loss) / g.bore;
    const F_rings = F64();
    for (let k = 0; k < ns; k++) {
      const h_o = ring_film_thickness(mu_ring, u_pist[k]!, b_o, Wl_o, 0.55 * h_sup);
      const fb_o = lambdaShare(h_o / this.sigma_ring);
      const W_o = Wl_o * Math.PI * g.bore;
      const F_oil_ring = mu_b * fb_o * W_o + ((1.0 - fb_o) * mu_ring * absU[k]! * Math.PI * g.bore * b_o) / h_o;
      F_rings[k] = F_top[k]! + F_oil_ring;
      Pb_rings[k] = Pb_rings[k]! + (mu_b * fb_o * W_o * absU[k]!);
    }

    // ---- 2. piston skirt ----
    const c_sk = E.skirt;
    const L_sk = 0.62 * g.bore;
    const sig_sk = composite_roughness(0.5e-6, t["bore_roughness"]!);
    const F_skirt = F64(), Pb_skirt = F64();
    let h_sk_min = Infinity;
    for (let k = 0; k < ns; k++) {
      const h_sk = skirt_film_thickness(mu_skirt, u_pist[k]!, L_sk, F_side[k]!, g.bore, c_sk);
      h_sk_min = Math.min(h_sk_min, h_sk);
      const fb_sk = lambdaShare(h_sk / sig_sk);
      F_skirt[k] = mu_b * fb_sk * F_side[k]! + ((1.0 - fb_sk) * mu_skirt * absU[k]! * t["skirt_area"]!) / Math.max(h_sk, 1e-9);
      Pb_skirt[k] = mu_b * fb_sk * F_side[k]! * absU[k]!;
    }

    // ---- 3. big ends, 3b. pin, 4. mains ----
    const F_cent_rod = g.rot_mass_bigend * om ** 2 * g.crank_radius;
    const share = t["n_mains"]! / Math.max(n, 1);
    const T_rod = F64(), T_main = F64(), T_pin = F64(), P_pin_inst = F64();
    const Pb_rods = F64(), Pb_mains = F64();
    let h_rod_min = Infinity, h_main_min = Infinity;
    const r_pin = 0.5 * t["pin_dia"]!;
    for (let k = 0; k < ns; k++) {
      const W_rod = Math.abs(F_rod[k]!) + F_cent_rod;
      const [hr, , tqr] = bearing_state(W_rod, om, mu_brg, t["rod_dia"]!, t["rod_width"]!, E.rod, 3.2);
      h_rod_min = Math.min(h_rod_min, hr);
      const fb_rod = lambdaShare(hr / this.sigma_brg);
      const T_rod_b = mu_b * fb_rod * W_rod * 0.5 * t["rod_dia"]!;
      T_rod[k] = tqr * (1.0 - fb_rod) + T_rod_b;
      Pb_rods[k] = T_rod_b * om;

      // np.gradient(beta, dth): central inside, one-sided at the ends
      const dbeta = k === 0 ? (beta[1]! - beta[0]!) / dth
        : k === ns - 1 ? (beta[ns - 1]! - beta[ns - 2]!) / dth
        : (beta[k + 1]! - beta[k - 1]!) / (2.0 * dth);
      const u_pin = Math.abs(dbeta) * om * r_pin;
      const mu_pin = t["pin_mu_boundary"]! * (1.0 + 0.9 * Math.exp(-u_pin / 0.05));
      P_pin_inst[k] = mu_pin * Math.abs(F_rod[k]!) * u_pin;
      T_pin[k] = P_pin_inst[k]! / Math.max(om, 1.0);

      const W_main = (0.5 * W_rod) / Math.max(share, 0.5) + 0.5 * g.rot_mass_bigend * om ** 2 * g.crank_radius;
      const [hm, , tqm] = bearing_state(W_main, om, mu_brg, t["main_dia"]!, t["main_width"]!, E.main, 2.4);
      h_main_min = Math.min(h_main_min, hm);
      const fb_main = lambdaShare(hm / this.sigma_brg);
      const T_main_b = mu_b * fb_main * W_main * 0.5 * t["main_dia"]!;
      T_main[k] = tqm * (1.0 - fb_main) + T_main_b;
      Pb_mains[k] = T_main_b * om;
    }

    // ---- 5. valvetrain ----
    const vt = spec.valves;
    const T_vt = F64();
    let Pb_vt = 0.0, v_seat_max = 0.0;
    for (const [cam, nv, dv_, lift_max, is_exh] of [
      [this.camInt, vt["n_intake_valves"]!, vt["intake_valve_dia"]!, E.lift_int, false],
      [this.camExh, vt["n_exhaust_valves"]!, vt["exhaust_valve_dia"]!, E.lift_exh, true],
    ] as const) {
      const scale = lift_max / Math.max(cam.liftMax, 1e-9);
      const A_v = (Math.PI * dv_ ** 2) / 4.0;
      const pb = F64();
      for (let k = 0; k < ns; k++) {
        const d = theta_deg[k]!;
        const L = cam.camLift(d) * scale;
        const dL = cam.dliftDtheta(d) * scale;
        const d2L = cam.d2liftDtheta2(d) * scale;
        const F_spring = vt["valve_spring_preload"]! + vt["valve_spring_rate"]! * L;
        const F_in = vt["valve_train_eq_mass"]! * d2L * om ** 2;
        const F_gasv = is_exh ? Math.max(p_cyl[k]! - 1.1e5, 0.0) * A_v : 0.0;
        const F_cam = Math.max(F_spring + F_in + F_gasv, 0.0) * nv;
        let T_lobe: number;
        if (vt["follower_radius"]! > 0.0) { // roller follower
          const mu_roll = 0.0035 + 0.01 * Math.exp((-Math.abs(dL) * om) / 0.35);
          const u_sl = 0.06 * Math.abs(dL) * om;
          T_lobe = mu_roll * F_cam * (vt["cam_base_radius"]! + L);
          const R_eq_r = 1.0 / (1.0 / Math.max(vt["cam_base_radius"]!, 1e-4) + 1.0 / Math.max(vt["follower_radius"]!, 1e-4));
          const w_line_r = Math.max(F_cam, 1.0) / (nv * 0.012);
          const u_roll = 0.5 * om * (vt["cam_base_radius"]! + L);
          const h_er = hamrock_dowson_film(mu_cam, Math.max(u_roll, 1e-4), R_eq_r, w_line_r, 2.2e11, 0.1 * this.sigma_cam);
          const fb_r = lambdaShare(h_er / this.sigma_cam);
          pb[k] = mu_b * fb_r * F_cam * u_sl;
        } else { // flat tappet, high sliding
          const om_c = 0.5 * om;
          const u_sl = om_c * (vt["cam_base_radius"]! + L);
          const u_ent = (om_c * Math.abs(vt["cam_base_radius"]! + L + 8.0 * d2L)) / 2.0;
          const R_eq = vt["cam_base_radius"]!;
          const w_line = Math.max(F_cam, 1.0) / (nv * 0.012);
          const h_e = hamrock_dowson_film(mu_cam, Math.max(u_ent, 1e-4), R_eq, w_line, 2.2e11, 0.1 * this.sigma_cam);
          const fb_c = lambdaShare(h_e / this.sigma_cam);
          const mu_eff = mu_b * fb_c + (1.0 - fb_c) * 0.008;
          T_lobe = mu_eff * F_cam * (vt["cam_base_radius"]! + L);
          pb[k] = mu_b * fb_c * F_cam * u_sl;
        }
        T_vt[k] = T_vt[k]! + (T_lobe * 0.5);
      }
      Pb_vt += mean(pb);
      v_seat_max = Math.max(v_seat_max, cam.seatingVelocity(om));
    }

    // ---- 6. windage and churning ----
    const rho_oil = oil.density(T_oil);
    let P_wind = t["windage_k"]! * rpm ** 2.7 * (rho_oil / 860.0) * n / 6.0;
    P_wind += t["gear_train_k"]! * rpm ** 2;
    P_wind += t["seal_drag_Nm"]! * om;

    // ---- 7. accessories ----
    const [p_gal] = oil.gallery_pressure(rpm, E.leak);
    const P_oilpump = oil.pump_power(rpm, p_gal);
    const P_water = t["water_pump_k"]! * rpm ** 3;
    const P_fan = t["fan_k"]! * rpm ** 3 * t["fan_duty"]!;
    const P_alt = t["alternator_load_W"]! / t["alternator_eta"]!;
    const P_aircomp = t["aircomp_load_W"]!;
    const mdot_f = (fuel_mg * 1e-6 * n * rpm) / 120.0;
    const Q_f = (mdot_f / 830.0) * t["fuel_pump_spill"]!;
    const P_fuelpump = (p_rail * Q_f) / t["fuel_pump_eta"]!;
    const P_acc = P_oilpump + P_water + P_fan + P_alt + P_aircomp + P_fuelpump;

    // ---- film where the ring actually slides ----
    let umax = 0;
    for (let k = 0; k < ns; k++) umax = Math.max(umax, absU[k]!);
    let h_mid = Infinity, anyFast = false;
    for (let k = 0; k < ns; k++) {
      if (absU[k]! > 0.35 * umax) { anyFast = true; h_mid = Math.min(h_mid, h[k]!); }
    }
    if (!anyFast) h_mid = h_ring_min;

    // ---- cycle-average powers ----
    const prod = (a: Float64Array, b: Float64Array) => { const o = F64(); for (let k = 0; k < ns; k++) o[k] = a[k]! * b[k]!; return o; };
    const P_ring_tot = mean(prod(F_rings, absU)) * n;
    const P_skirt_tot = mean(prod(F_skirt, absU)) * n;
    const P_rod_tot = mean(T_rod) * om * n;
    const P_main_tot = mean(T_main) * om * n;
    const P_vt_tot = mean(T_vt) * om * n;
    const P_pin_tot = mean(P_pin_inst) * n;
    const P_mech = P_ring_tot + P_skirt_tot + P_rod_tot + P_main_tot + P_pin_tot + P_vt_tot;
    const P_fric = P_mech + P_wind + P_acc;
    const W_cycle = P_fric * (120.0 / rpm);
    const fmep = W_cycle / g.displacement;

    return {
      fmep, P_friction: P_fric, P_mech,
      P_rings: P_ring_tot, P_skirt: P_skirt_tot, P_rods: P_rod_tot, P_mains: P_main_tot,
      P_valvetrain: P_vt_tot, P_pin: P_pin_tot, P_windage: P_wind, P_accessories: P_acc,
      P_oilpump, P_fuelpump,
      Pb_rings: mean(Pb_rings) * n, Pb_skirt: mean(Pb_skirt) * n, Pb_rods: mean(Pb_rods) * n,
      Pb_mains: mean(Pb_mains) * n, Pb_pin: mean(P_pin_inst) * n, Pb_valvetrain: Pb_vt * n,
      h_ring: h_ring_min, h_rod: h_rod_min, h_main: h_main_min, h_skirt: h_sk_min,
      lambda_ring: h_mid / this.sigma_ring, h_ring_mid: h_mid, gallery_pressure: p_gal,
      v_seating: v_seat_max,
    };
  }
}
