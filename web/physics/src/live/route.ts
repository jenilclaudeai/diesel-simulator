// P06 (ADR-021): routes the live loop drives -- dieselsim/live.py's Route,
// random_route and ROUTES, line for line (the live fixture holds them equal).

/** Rolling resistance by surface, times the vehicle's own (asphalt). */
export const SURFACES: Record<string, number> = { asphalt: 1.0, concrete: 0.9, gravel: 2.0, dirt: 2.6 };
export const BREAKER_SAFE_KMH = 15.0;
export const BREAKER_FULL_KMH = 50.0;
export const BREAKER_LOSS = 0.06;
export const BREAKER_PULSE_S = 0.15;

/** Uniform floats in [0, 1) from mulberry32 (as livesound / dsp.noiseTable). */
export function mulberry32(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1) >>> 0;
    t = (t ^ ((t + (Math.imul(t ^ (t >>> 7), t | 61) >>> 0)) >>> 0)) >>> 0;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296.0;
  };
}

/** ln x for x in about (0.25, 4) by series (live._ln): +, -, *, / only, so it equals Python's to the bit. */
export function lnSeries(x: number): number {
  const z = (x - 1.0) / (x + 1.0);
  const z2 = z * z;
  let term = z, s = 0.0;
  for (let k = 0; k < 60; k++) {
    s += term / (2 * k + 1);
    term *= z2;
  }
  return 2.0 * s;
}

/** e ** y for |y| up to about 3 by its Taylor series (live._exp). */
export function expSeries(y: number): number {
  let term = 1.0, s = 1.0;
  for (let n = 1; n < 40; n++) {
    term *= y / n;
    s += term;
  }
  return s;
}

/** x to the nearest multiple of step, halves up (live._q: floor(x + 0.5), not Math.round). */
function q(x: number, step: number): number {
  return Math.floor(x / step + 0.5) * step;
}

/** [start m, length m, grade, surface, wind m/s (headwind positive)] */
export type Segment = [number, number, number, string, number];

export class Route {
  readonly segments: Segment[] = [];
  readonly alts: number[] = [];
  readonly length: number;
  readonly climb: number;
  readonly breakers: number[];

  constructor(readonly name: string, segments: [number, number, string, number][], breakers: number[],
              readonly seed: number | null = null) {
    let start = 0.0, alt = 0.0;
    for (const [length, grade, surface, wind] of segments) {
      if (!(surface in SURFACES)) throw new Error(`unknown surface ${surface}`);
      this.segments.push([start, length, grade, surface, wind]);
      this.alts.push(alt);
      start += length;
      alt += length * grade;
    }
    this.length = start;
    this.climb = alt;
    this.breakers = [...breakers].sort((a, b) => a - b);
  }

  /** The segment index at distance s (the route repeats). */
  at(s: number): number {
    const x = s % this.length;
    let lo = 0, hi = this.segments.length - 1;
    while (lo < hi) {
      const mid = Math.floor((lo + hi + 1) / 2);
      if (this.segments[mid]![0] <= x) lo = mid;
      else hi = mid - 1;
    }
    return lo;
  }

  /** Metres above the start at distance s; each lap adds the route's climb. */
  altitude(s: number): number {
    const laps = Math.floor(s / this.length);
    const x = s - laps * this.length;
    const i = this.at(x);
    const seg = this.segments[i]!;
    return laps * this.climb + this.alts[i]! + (x - seg[0]) * seg[2];
  }

  /** How many breakers lie in (s0, s1], counted over laps. */
  breakersBetween(s0: number, s1: number): number {
    if (s1 <= s0) return 0;
    let n = 0;
    const L = this.length;
    for (const b of this.breakers) n += Math.floor((s1 - b) / L) - Math.floor((s0 - b) / L);
    return n;
  }
}

/** A seeded route (live.random_route). */
export function randomRoute(seed: number, length_m = 12000.0): Route {
  const r = mulberry32(seed);
  const segs: [number, number, string, number][] = [];
  const breakers: number[] = [];
  let s = 0.0, g = 0.0, alt = 0.0;
  while (s < length_m) {
    const length = q(200.0 + 600.0 * r(), 10.0);
    g = Math.min(0.08, Math.max(-0.08, 0.5 * g + (r() - 0.5) * 0.12));
    g = q(g, 0.005);
    const a1 = alt + length * g;
    if (!(0.0 <= a1 && a1 <= 2500.0)) g = -g;
    const u = r();
    const surface = u < 0.70 ? "asphalt" : u < 0.82 ? "concrete" : u < 0.94 ? "gravel" : "dirt";
    const wind = q((r() - 0.5) * 16.0, 0.5);
    if ((surface === "asphalt" || surface === "concrete") && r() < 0.25) breakers.push(s + q(length * r(), 1.0));
    segs.push([length, g, surface, wind]);
    s += length;
    alt += length * g;
  }
  return new Route(`random ${seed}`, segs, breakers, seed);
}

export const ROUTES: Record<string, Route> = {
  pass: new Route("Mountain pass", [
    [800, 0.0, "asphalt", 0.0], [1500, 0.06, "asphalt", 2.0], [1200, 0.08, "asphalt", 4.0],
    [600, 0.03, "concrete", 6.0], [900, 0.07, "asphalt", 6.0], [500, 0.0, "asphalt", 8.0],
    [1400, -0.06, "asphalt", -4.0], [1500, -0.07, "asphalt", -2.0], [900, -0.02, "asphalt", 0.0]], []),
  city: new Route("City streets", [
    [400, 0.0, "asphalt", 0.0], [300, 0.02, "concrete", 0.0], [500, 0.0, "asphalt", 0.0],
    [300, -0.02, "asphalt", 0.0], [600, 0.01, "concrete", 0.0], [400, 0.0, "asphalt", 0.0]],
    [250, 650, 1050, 1450, 1900, 2300]),
  desert: new Route("Desert highway", [
    [3000, 0.0, "asphalt", 6.0], [800, 0.01, "asphalt", 8.0], [1200, 0.0, "gravel", 8.0],
    [2000, -0.01, "asphalt", -6.0], [1500, 0.0, "dirt", -4.0], [2500, 0.0, "asphalt", 0.0]], []),
};

/** A named route ('pass', 'city', 'desert') or 'random:<seed>'. */
export function routeFrom(key: string): Route {
  if (key.startsWith("random:")) return randomRoute(parseInt(key.slice(7), 10));
  const r = ROUTES[key];
  if (!r) throw new Error(`unknown route ${key}`);
  return r;
}
