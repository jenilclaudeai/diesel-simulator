// Port of dieselsim/kinematics.py: exact offset slider-crank and cam / valve
// lift. Held to the Python original by fixtures/kinematics.json at 1e-12
// relative (ADR-004). Operation order follows the Python line for line, so
// agreement is to the last few ulps, not merely within tolerance.

const DEG = Math.PI / 180; // CPython's math.radians multiplies by pi/180

/** Python's float modulo: the result takes the divisor's sign. */
function pyMod(x: number, m: number): number {
  const r = x % m;
  return r !== 0 && (r < 0) !== (m < 0) ? r + m : r;
}

export interface CrankGeometry {
  a: number;  // crank radius [m]
  l: number;  // con-rod length [m]
  e: number;  // gudgeon-pin offset [m], + toward the thrust side
  Ap: number; // piston area [m^2]
  Vc: number; // clearance volume [m^3]
}

/**
 * Offset slider-crank. x is measured from the TDC position, positive
 * downwards. Angles in radians from TDC firing.
 */
export class SliderCrank {
  private readonly xTdc: number;

  constructor(private readonly g: CrankGeometry) {
    this.xTdc = this.xRaw(0.0);
  }

  private sinBeta(th: number): number {
    return (this.g.a * Math.sin(th) - this.g.e) / this.g.l;
  }

  private xRaw(th: number): number {
    const sb = this.sinBeta(th);
    const cb = Math.sqrt(Math.max(1e-12, 1.0 - sb * sb));
    return -this.g.a * Math.cos(th) - this.g.l * cb;
  }

  /** Piston distance from TDC [m]. */
  displacement(th: number): number {
    return this.xRaw(th) - this.xTdc;
  }

  dxDtheta(th: number): number {
    const { a, l } = this.g;
    const sb = this.sinBeta(th);
    const cb = Math.sqrt(Math.max(1e-12, 1.0 - sb * sb));
    const dsb = (a * Math.cos(th)) / l;
    return a * Math.sin(th) + ((l * sb * dsb) / cb);
  }

  d2xDtheta2(th: number): number {
    const { a, l } = this.g;
    const sb = this.sinBeta(th);
    const cb = Math.sqrt(Math.max(1e-12, 1.0 - sb * sb));
    const dsb = (a * Math.cos(th)) / l;
    const d2sb = (-a * Math.sin(th)) / l;
    const t1 = (l * (dsb * dsb + sb * d2sb)) / cb;
    const t2 = (l * sb * dsb * (sb * dsb)) / cb ** 3;
    return a * Math.cos(th) + t1 + t2;
  }

  volume(th: number): number {
    return this.g.Vc + this.g.Ap * this.displacement(th);
  }

  dVDtheta(th: number): number {
    return this.g.Ap * this.dxDtheta(th);
  }

  /** Con-rod angle from the cylinder axis [rad]. */
  beta(th: number): number {
    return Math.asin(Math.min(1.0, Math.max(-1.0, this.sinBeta(th))));
  }
}

/**
 * Normalised lift for u in [0, 1]: raised cosine sin^2(pi u) with
 * constant-velocity ramps over [0, ramp/2] and [1 - ramp/2, 1] up to the
 * ramp height h_r = sin^2(pi ramp / 2), where they meet the flank
 * (FINDING-018).
 */
export function coreProfile(u: number, ramp: number): number {
  const r = Math.max(ramp, 1e-4);
  const hR = 0.5 * (1.0 - Math.cos(Math.PI * r));
  const uR = 0.5 * r;
  if (!(u >= 0.0 && u <= 1.0)) return 0.0;
  if (u < uR) return hR * (u / uR);
  if (u > 1.0 - uR) return hR * ((1.0 - u) / uR);
  const s = Math.sin(Math.PI * Math.min(1.0, Math.max(0.0, u)));
  return s * s;
}

export interface CamSpec {
  open_deg: number;
  close_deg: number;
  lift_max: number; // m
  lash: number;     // m
  ramp: number;     // ramp_fraction
}

/** Valve lift, velocity and acceleration versus crank angle in degrees. */
export class Cam {
  readonly openDeg: number;
  readonly closeDeg: number;
  readonly dur: number;
  readonly liftMax: number;
  readonly lash: number;
  readonly ramp: number;
  readonly hRamp: number;

  constructor(c: CamSpec) {
    this.openDeg = pyMod(c.open_deg, 720.0);
    this.closeDeg = pyMod(c.close_deg, 720.0);
    let dur = pyMod(this.closeDeg - this.openDeg, 720.0);
    if (dur <= 0) dur += 720.0;
    this.dur = dur;
    this.liftMax = c.lift_max;
    this.lash = c.lash;
    this.ramp = c.ramp;
    this.hRamp = 0.5 * (1.0 - Math.cos(Math.PI * c.ramp)) * c.lift_max;
  }

  private phase(thetaDeg: number): number {
    return pyMod(thetaDeg - this.openDeg, 720.0) / this.dur;
  }

  /** Lift at the valve, after lash [m]. */
  lift(thetaDeg: number): number {
    return Math.max(0.0, this.camLift(thetaDeg) - this.lash);
  }

  /** Lift at the cam, before lash [m]. */
  camLift(thetaDeg: number): number {
    const u = this.phase(thetaDeg);
    return u <= 1.0 ? coreProfile(u, this.ramp) * this.liftMax : 0.0;
  }

  dliftDtheta(thetaDeg: number, dth = 0.05): number {
    return (this.camLift(thetaDeg + dth) - this.camLift(thetaDeg - dth)) / (2.0 * (dth * DEG));
  }

  d2liftDtheta2(thetaDeg: number, dth = 0.1): number {
    const h = dth * DEG;
    return (this.camLift(thetaDeg + dth) - 2.0 * this.camLift(thetaDeg) + this.camLift(thetaDeg - dth)) / h ** 2;
  }

  /**
   * Valve closing velocity at seat contact [m/s]: the ramp speed when the
   * lash is inside the closing ramp; the lash penalty only off the ramp.
   */
  seatingVelocity(omega: number): number {
    const vRamp = this.hRamp / (0.5 * this.ramp * this.dur * DEG);
    if (this.lash <= this.hRamp) return vRamp * omega;
    return vRamp * omega * (1.0 + (2.2 * this.lash) / Math.max(this.hRamp, 1e-9));
  }
}
