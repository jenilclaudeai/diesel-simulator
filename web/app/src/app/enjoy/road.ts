// P06 tier 1 (ADR-021): the road in /enjoy -- which route, the link that
// shares it, and the "road ahead" strip. The route itself is
// @dieselsim/physics's (held to dieselsim/live.py by the live fixture); this
// file only draws it.
import { Route, routeFrom } from '@dieselsim/physics';

/** '' is the open road: flat, no route (the loop as it was before P06). */
export const ROUTE_CHOICES: readonly { key: string; name: string }[] = [
  { key: '', name: 'Open road (flat)' },
  { key: 'pass', name: 'Mountain pass' },
  { key: 'city', name: 'City streets' },
  { key: 'desert', name: 'Desert highway' },
  { key: 'random', name: 'Random road' },
];

export const SEED_MAX = 999_999;

/** A fresh seed, 1 to SEED_MAX. */
export function newSeed(rand: () => number = Math.random): number {
  return 1 + Math.floor(rand() * SEED_MAX);
}

/** `?route=` -> the picker's state: 'city', 'random:1234'; anything else is the open road. */
export function parseRouteParam(q: string | null): { choice: string; seed: number | null } {
  if (!q) return { choice: '', seed: null };
  const m = /^random:(\d{1,6})$/.exec(q);
  if (m) {
    const seed = Number(m[1]);
    return seed >= 1 ? { choice: 'random', seed } : { choice: '', seed: null };
  }
  return ROUTE_CHOICES.some(c => c.key === q && c.key !== 'random') ? { choice: q, seed: null } : { choice: '', seed: null };
}

/** The picker's state -> the route key the worker loads (and `?route=`), or undefined for the open road. */
export function routeKey(choice: string, seed: number | null): string | undefined {
  if (choice === 'random') return seed !== null && seed >= 1 && seed <= SEED_MAX ? `random:${Math.floor(seed)}` : undefined;
  return choice || undefined;
}

/** Strip colours by surface (the dash's palette: slate, grey, amber). */
export const SURFACE_FILL: Record<string, string> = {
  asphalt: '#5b6470', concrete: '#9aa3a0', gravel: '#b08a52', dirt: '#8a5a3c',
};

export interface RoadAhead {
  /** the profile, as an SVG path in a w x h box; the car is at x = 0 */
  line: string;
  /** the same, closed down to the bottom edge, for the fill */
  area: string;
  /** surface bands under the profile: x from, x to, surface */
  bands: { x0: number; x1: number; surface: string }[];
  /** speed breakers ahead, as x */
  breakers: number[];
  /** metres to the next breaker within the span, else null */
  nextBreakerM: number | null;
  /** the grade and surface under the car */
  grade: number;
  surface: string;
}

/**
 * The next `span` metres of `route` from distance `s`, in a `w` x `h` box.
 * Height is exaggerated to fit: the window's altitudes fill the box, with at
 * least `minRise` metres top to bottom so a flat stretch stays flat.
 */
export function roadAhead(route: Route, s: number, span = 1500, w = 300, h = 40, minRise = 40): RoadAhead {
  const n = 60, dx = span / n;
  const alts: number[] = [];
  for (let i = 0; i <= n; i++) alts.push(route.altitude(s + i * dx));
  let lo = Math.min(...alts), hi = Math.max(...alts);
  if (hi - lo < minRise) { const mid = (hi + lo) / 2; lo = mid - minRise / 2; hi = mid + minRise / 2; }
  const pad = 3, y = (a: number) => h - pad - ((a - lo) / (hi - lo)) * (h - 2 * pad - 6);
  const X = (d: number) => (d / span) * w;
  const pts = alts.map((a, i) => `${X(i * dx).toFixed(1)},${y(a).toFixed(1)}`);
  const line = 'M' + pts.join(' L');
  const area = `${line} L${w.toFixed(1)},${h} L0,${h} Z`;

  const bands: RoadAhead['bands'] = [];
  let d = 0;
  while (d < span) {
    const seg = route.segments[route.at(s + d)]!;
    const left = seg[0] + seg[1] - ((s + d) % route.length);   // metres to this segment's end
    const step = Math.max(left, 1e-6);
    const x0 = X(d), x1 = X(Math.min(span, d + step));
    const last = bands[bands.length - 1];
    if (last && last.surface === seg[3]) last.x1 = x1;
    else bands.push({ x0, x1, surface: seg[3] });
    d += step;
  }

  const breakers: number[] = [];
  let nextBreakerM: number | null = null;
  const L = route.length;
  for (const b of route.breakers) {
    // the first lap's copy of b at or after s, then any later ones inside the span
    for (let at = b + Math.ceil((s - b) / L) * L; at <= s + span; at += L) {
      if (at < s) continue;
      breakers.push(X(at - s));
      if (nextBreakerM === null || at - s < nextBreakerM) nextBreakerM = at - s;
    }
  }
  breakers.sort((a, b) => a - b);
  const here = route.segments[route.at(s)]!;
  return { line, area, bands, breakers, nextBreakerM, grade: here[2], surface: here[3] };
}

/** The route a key names, or undefined (the open road, or a key the physics doesn't know). */
export function routeOf(key: string | undefined): Route | undefined {
  if (!key) return undefined;
  try { return routeFrom(key); } catch { return undefined; }
}

/** The picker's note: the route's length [km], its highest point above the start [m], its breakers. */
export function routeSummary(route: Route): { km: number; top: number; breakers: number } {
  return { km: route.length / 1000, top: Math.max(0, route.climb, ...route.alts), breakers: route.breakers.length };
}
