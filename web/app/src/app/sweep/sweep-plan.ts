/**
 * The values a sweep solves at (Phase 6, ADR-015): `steps` points evenly from
 * `from` to `to`, ends included. Integer fields are rounded and duplicates
 * dropped (a sweep of nozzle holes from 6 to 8 in 7 steps is 6, 7, 8).
 */
export function sweepValues(from: number, to: number, steps: number, integer: boolean): number[] {
  const n = Math.max(2, Math.min(25, Math.round(steps)));
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    let v = from + (to - from) * i / (n - 1);
    v = integer ? Math.round(v) : Number(v.toPrecision(10));
    if (!out.includes(v)) out.push(v);
  }
  return out;
}

/** The default range: the engine's value ±20%, rounded to 3 significant figures; ints at least ±1. */
export function defaultRange(value: number, integer: boolean): { from: number; to: number } {
  if (integer) {
    const d = Math.max(1, Math.round(Math.abs(value) * 0.2));
    return { from: value - d, to: value + d };
  }
  if (value === 0) return { from: 0, to: 1 };
  const r = (x: number) => Number(x.toPrecision(3));
  return value > 0 ? { from: r(value * 0.8), to: r(value * 1.2) } : { from: r(value * 1.2), to: r(value * 0.8) };
}
