// Port of dieselsim/thermo.py's scalar paths: gas properties, sensible
// energy, the u -> T Newton inversion, and compressible flow through an
// orifice and a poppet valve. Held to the Python original by
// fixtures/thermo.json at 1e-10 relative (ADR-004).

export const R_AIR = 287.05;   // J/kg/K
export const R_BURNED = 286.0; // J/kg/K, lean diesel products

const CP_A_INF = 1310.0, CP_A_AMP = 393.0, CP_A_TAU = 1185.0; // air
const CP_B_INF = 1500.0, CP_B_AMP = 480.0, CP_B_TAU = 1100.0; // products
const T_DISS = 2200.0;
const K_DISS = 0.35; // J/kg/K per K above T_DISS
export const T_REF = 298.15;

export function cpAir(T: number): number {
  return CP_A_INF - CP_A_AMP * Math.exp(-T / CP_A_TAU);
}

export function cpBurned(T: number): number {
  const base = CP_B_INF - CP_B_AMP * Math.exp(-T / CP_B_TAU);
  return base + (T > T_DISS ? K_DISS * (T - T_DISS) : 0.0);
}

export function gasR(yb: number): number {
  return R_AIR + (R_BURNED - R_AIR) * yb;
}

export function cpMix(T: number, yb: number): number {
  return (1.0 - yb) * cpAir(T) + yb * cpBurned(T);
}

export function cvMix(T: number, yb: number): number {
  return cpMix(T, yb) - gasR(yb);
}

export function gammaMix(T: number, yb: number): number {
  const cp = cpMix(T, yb);
  return cp / (cp - gasR(yb));
}

function intCpAir(T: number): number {
  return CP_A_INF * T + CP_A_AMP * CP_A_TAU * Math.exp(-T / CP_A_TAU);
}

function intCpBurned(T: number): number {
  const base = CP_B_INF * T + CP_B_AMP * CP_B_TAU * Math.exp(-T / CP_B_TAU);
  if (T > T_DISS) {
    const d = T - T_DISS;
    return base + 0.5 * K_DISS * d * d;
  }
  return base;
}

/** Sensible internal energy referenced to 298.15 K [J/kg]. */
export function uMix(T: number, yb: number): number {
  const h = (1.0 - yb) * (intCpAir(T) - intCpAir(T_REF)) + yb * (intCpBurned(T) - intCpBurned(T_REF));
  return h - gasR(yb) * (T - T_REF);
}

export function hMix(T: number, yb: number): number {
  return (1.0 - yb) * (intCpAir(T) - intCpAir(T_REF)) + yb * (intCpBurned(T) - intCpBurned(T_REF));
}

/** Invert u(T) by Newton iteration. */
export function TFromU(uTarget: number, yb: number, TGuess = 800.0, tol = 1e-6, itmax = 30): number {
  let T = TGuess;
  for (let i = 0; i < itmax; i++) {
    const f = uMix(T, yb) - uTarget;
    const df = cvMix(T, yb);
    const dT = -f / df;
    T += Math.max(-400.0, Math.min(400.0, dT));
    if (Math.abs(dT) < tol) break;
  }
  return Math.max(150.0, T);
}

/**
 * Mass flow [kg/s] through effective area aEff [m^2], isentropic nozzle.
 * Positive from `up` to `dn`; the caller orders the states.
 */
export function orificeMdot(pUp: number, TUp: number, pDn: number, aEff: number, gamma: number, R: number): number {
  if (aEff <= 0.0 || pUp <= 0.0) return 0.0;
  let pr = pDn / pUp;
  const prCrit = (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0));
  const c = (aEff * pUp) / Math.sqrt(R * Math.max(TUp, 60.0));
  if (pr <= prCrit) {
    return c * Math.sqrt(gamma) * (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)));
  }
  pr = Math.min(pr, 1.0);
  const term = pr ** (2.0 / gamma) - pr ** ((gamma + 1.0) / gamma);
  return c * Math.sqrt(Math.max(0.0, ((2.0 * gamma) / (gamma - 1.0)) * term));
}

/** Bidirectional flow between reservoirs 1 and 2: [mdot, yb of the stream]. */
export function signedOrifice(
  p1: number, T1: number, yb1: number, p2: number, T2: number, yb2: number, aEff: number,
): [number, number] {
  if (aEff <= 0.0) return [0.0, yb1];
  if (p1 >= p2) return [orificeMdot(p1, T1, p2, aEff, gammaMix(T1, yb1), gasR(yb1)), yb1];
  return [-orificeMdot(p2, T2, p1, aEff, gammaMix(T2, yb2), gasR(yb2)), yb2];
}

/** Effective flow area of a poppet-valve set: curtain at low lift, throat at high. */
export function valveEffectiveArea(lift: number, valveDia: number, nValves: number, cdMax: number): number {
  if (lift <= 0.0) return 0.0;
  const ld = lift / valveDia;
  const cd = cdMax * (1.0 - Math.exp(-14.0 * ld));
  const aCurtain = Math.PI * valveDia * lift;
  const aThroat = (0.85 * Math.PI * valveDia ** 2) / 4.0;
  return nValves * cd * Math.min(aCurtain, aThroat);
}

export function speedOfSound(T: number, yb = 0.0): number {
  return Math.sqrt(gammaMix(T, yb) * gasR(yb) * Math.max(T, 60.0));
}

export function airDensity(p: number, T: number): number {
  return p / (R_AIR * T);
}

/** Sutherland. */
export function airViscosity(T: number): number {
  return (1.716e-5 * (T / 273.15) ** 1.5 * (273.15 + 110.4)) / (T + 110.4);
}
