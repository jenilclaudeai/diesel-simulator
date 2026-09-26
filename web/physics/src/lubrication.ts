// Port of dieselsim/lubrication.py: oil rheology and circuit, film
// thicknesses, the Ocvirk short bearing. Held to Python through
// fixtures/friction.json (the friction model is its only caller).

export const CP_OIL = 1950.0;          // J/kg/K
export const BARUS_ALPHA = 1.9e-8;     // 1/Pa
export const MU_BOUNDARY_BASE = 0.095;
export const LAMBDA_0 = 1.05;
export const LAMBDA_K = 4.0;

export interface Lubricant {
  vogel_a: number; vogel_b: number; vogel_c: number; density15: number; tbn0: number;
  sump_volume: number; pump_disp: number; pump_relief: number; pump_eta_vol: number;
  pump_eta_mech: number; cooler_UA: number;
}

export interface OilCondition {
  T_oil: number; oxidation: number; soot_pct: number; tbn: number;
  fuel_dilution: number; visc_multiplier: number; additive_left: number;
}

/** Lubricant with a mutable condition state. */
export class Oil {
  constructor(readonly spec: Lubricant, readonly cond: OilCondition) {}

  /** Vogel equation, atmospheric pressure, low shear [Pa.s]. */
  base_viscosity(T: number): number {
    const s = this.spec;
    const denom = Math.max(T - s.vogel_c, 12.0);
    return s.vogel_a * Math.exp(s.vogel_b / denom);
  }

  /** Temperature, pressure (Barus), shear thinning and oil condition. */
  viscosity(T: number, p = 1e5, shear_rate = 1e5): number {
    let mu = this.base_viscosity(T) * this.cond.visc_multiplier;
    if (p > 2e5) mu *= Math.exp(BARUS_ALPHA * Math.min(p, 1.2e9));
    if (shear_rate > 1e4) {
      const x = (shear_rate / 3.0e6) ** 0.62;
      mu *= 0.62 + 0.38 / (1.0 + x);
    }
    mu *= Math.exp(-4.2 * this.cond.fuel_dilution);
    return Math.max(mu, 1.2e-3);
  }

  density(T: number): number {
    return this.spec.density15 * (1.0 - 6.4e-4 * (T - 288.15));
  }

  mass(): number {
    return this.spec.sump_volume * this.density(this.cond.T_oil);
  }

  mu_boundary(): number {
    const c = this.cond;
    let mu = MU_BOUNDARY_BASE;
    mu *= 1.0 + 0.55 * (1.0 - c.additive_left);
    mu *= 1.0 + 0.09 * c.soot_pct;
    mu *= 1.0 + 0.25 * c.oxidation;
    return Math.min(mu, 0.22);
  }

  /** Pump delivery against the bearing/jet leakage network: [p_gallery, Q_pump]. */
  gallery_pressure(rpm: number, leak_factor = 1.0): [number, number] {
    const s = this.spec;
    const mu = this.viscosity(this.cond.T_oil, 3e5, 1e4);
    const Q_pump = s.pump_disp * (rpm / 60.0) * s.pump_eta_vol;
    const K = (1.3e-11 / mu) * leak_factor;
    const p = Q_pump / Math.max(K, 1e-14);
    return [Math.min(p, s.pump_relief), Q_pump];
  }

  pump_power(rpm: number, p_gallery: number): number {
    const s = this.spec;
    const Q = s.pump_disp * (rpm / 60.0);
    return (p_gallery * Q) / Math.max(s.pump_eta_mech * s.pump_eta_vol, 0.1);
  }
}

export function composite_roughness(r1: number, r2: number): number {
  return Math.sqrt(r1 * r1 + r2 * r2);
}

function ocvirk_load(eps: number, mu: number, omega: number, L: number, D: number, c_rad: number): number {
  eps = Math.min(Math.max(eps, 1e-4), 0.99999);
  return ((mu * omega * L ** 3 * D * eps) / (4.0 * c_rad ** 2 * (1.0 - eps ** 2) ** 2))
    * Math.sqrt(Math.PI ** 2 * (1.0 - eps ** 2) + 16.0 * eps ** 2);
}

/** Short-bearing eccentricity by bisection: [h_min, eps, friction torque, leak]. */
export function bearing_state(load_N: number, omega: number, mu: number, D: number, L: number,
                              c_diam: number, squeeze_credit = 1.0): [number, number, number, number] {
  const c_rad = 0.5 * c_diam;
  const W = Math.max(load_N, 1.0) / Math.max(squeeze_credit, 1e-3);
  const om = Math.max(Math.abs(omega), 1.0);
  let lo = 1e-4, hi = 0.999995, eps: number;
  if (ocvirk_load(hi, mu, om, L, D, c_rad) < W) {
    eps = hi;
  } else {
    for (let k = 0; k < 60; k++) {
      const mid = 0.5 * (lo + hi);
      if (ocvirk_load(mid, mu, om, L, D, c_rad) < W) lo = mid;
      else hi = mid;
    }
    eps = 0.5 * (lo + hi);
  }
  const h_min = c_rad * (1.0 - eps);
  const R = 0.5 * D;
  const F_visc = (2.0 * Math.PI * mu * om * R ** 2 * L) / (c_rad * Math.sqrt(Math.max(1.0 - eps ** 2, 1e-6)));
  const torque = F_visc * R;
  const leak = (Math.PI * D * c_rad ** 3 * 3.0e5 * (1.0 + 1.5 * eps ** 2)) / (12.0 * mu * L);
  return [h_min, eps, torque, leak];
}

/** Minimum film under a parabolic-faced ring, supply-limited. */
export function ring_film_thickness(mu: number, u: number, b: number, W_per_len: number,
                                    h_supply = 2.2e-6, h_floor = 12e-9): number {
  if (W_per_len <= 0.0) W_per_len = 1.0;
  const h_hyd = b * Math.sqrt((2.4 * mu * Math.abs(u)) / W_per_len);
  const h = (h_hyd * h_supply) / (h_hyd + h_supply);
  return Math.max(h, h_floor);
}

/** Piston-skirt film: partial journal bearing of length L, width ~0.3*pi*B. */
export function skirt_film_thickness(mu: number, u: number, L: number, W: number, B: number, c_diam: number): number {
  if (W < 1.0) return 0.5 * c_diam;
  const b = 0.3 * Math.PI * B;
  let h = Math.sqrt((2.0 * mu * Math.abs(u) * b * L * L) / Math.max(W, 1.0));
  h *= 0.42;
  return Math.max(Math.min(h, 0.32 * c_diam), 20e-9);
}

/** Central EHL film thickness for a line contact (Dowson-Higginson). */
export function hamrock_dowson_film(mu0: number, u_entrain: number, R_eq: number, load_per_len: number,
                                    E_eq = 2.2e11, h_floor = 8e-9): number {
  if (u_entrain <= 1e-6 || load_per_len <= 1.0) return h_floor;
  const U = (mu0 * u_entrain) / (E_eq * R_eq);
  const G = BARUS_ALPHA * E_eq;
  const W = load_per_len / (E_eq * R_eq);
  const Hc = 2.65 * U ** 0.7 * G ** 0.54 * W ** -0.13;
  return Math.max(Hc * R_eq, h_floor);
}
