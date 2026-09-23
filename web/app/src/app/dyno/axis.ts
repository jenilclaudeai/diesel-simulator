/**
 * Tick selection for the dyno chart's two y axes (torque left, power right).
 *
 * Both axes share one set of gridlines and one zero line, like a printed dyno
 * sheet, and both carry round labels. Pure functions, no Angular, so the rules
 * can be tested exhaustively.
 */

export interface Axis {
  /** bottom of the axis: 0, or a whole number of steps below it */
  lo: number;
  /** top of the axis: the first tick at or above the data */
  hi: number;
  step: number;
  /** lo, lo + step, ..., hi */
  ticks: number[];
}

export interface DualAxis {
  left: Axis;
  right: Axis;
  /** gridline intervals, the same on both axes */
  divisions: number;
}

/**
 * 1, 2, 2.5 and 5 times a power of ten. Only whole-number steps are produced,
 * because the chart labels integers: 2.5 appears as 25, 250, ... never as 2.5.
 */
const MANTISSAS = [1, 2, 2.5, 5];

/** Relative slack so a value that lands exactly on a tick is not pushed past it. */
const EPS = 1e-9;

/** The smallest nice whole-number step that is at least `x`. */
export function niceStepAtLeast(x: number): number {
  if (!(x > 1)) return 1; // also catches NaN
  for (let e = Math.floor(Math.log10(x)); ; e++) {
    for (const m of MANTISSAS) {
      const s = m * 10 ** e;
      if (Number.isInteger(s) && s >= x * (1 - EPS)) return s;
    }
  }
}

/** Whole steps needed to cover a non-negative extent. */
function stepsToCover(extent: number, step: number): number {
  return extent > 0 ? Math.ceil(extent / step - EPS) : 0;
}

function axis(step: number, below: number, above: number): Axis {
  const ticks = Array.from({ length: below + above + 1 }, (_, i) => (i - below) * step);
  return { lo: -below * step, hi: above * step, step, ticks };
}

/**
 * Choose shared gridlines for two quantities that share a zero, such as torque
 * and power (same sign at every rpm).
 *
 * Every candidate torque step giving `minDiv`..`maxDiv` intervals is tried; the
 * power step is then the smallest nice step that fits the same intervals. The
 * layout kept is the one whose worse-filled curve spans the most of the plotted
 * height (negative tail included), ties going to the interval count nearest five.
 *
 * Never throws. Values too small for 3 whole-number intervals (a fraction of a
 * newton-metre) or with no positive part still get a valid layout, outside the
 * preferred interval range, rather than breaking the chart mid-pull.
 */
export function dualAxis(
  leftMin: number, leftMax: number, rightMin: number, rightMax: number,
  minDiv = 3, maxDiv = 7,
): DualAxis {
  const lNeg = Math.max(0, -leftMin), rNeg = Math.max(0, -rightMin);
  let best: { score: number; tie: number; out: DualAxis } | undefined;
  let fallback: DualAxis | undefined;

  const tried = new Set<number>();
  for (let d = minDiv; d <= maxDiv; d++) {
    // smallest nice left step that covers the whole left range in d intervals
    let s = niceStepAtLeast((leftMax + lNeg) / d);
    while (stepsToCover(leftMax, s) + stepsToCover(lNeg, s) > d) s = niceStepAtLeast(s * (1 + 1e-6));
    if (tried.has(s)) continue;
    tried.add(s);

    const above = Math.max(1, stepsToCover(leftMax, s));
    // power can only go negative where torque does, but guard anyway
    const below = Math.max(stepsToCover(lNeg, s), rNeg > 0 ? 1 : 0);
    // r >= rightMax / above and >= rNeg / below, so it always fits: no search
    const r = niceStepAtLeast(Math.max(rightMax / above, below ? rNeg / below : 0));
    if (above + below < minDiv || above + below > maxDiv) {
      fallback ??= { left: axis(s, below, above), right: axis(r, below, above), divisions: above + below };
      continue;
    }

    // share of the plotted height each curve's data spans, zero to peak plus
    // any negative tail; a whole gridline band spent on a small governor-end
    // dip counts against the layout
    const span = (above + below);
    const score = Math.min((leftMax + lNeg) / (span * s), (rightMax + rNeg) / (span * r));
    const tie = -Math.abs(above + below - 5);
    if (!best || score > best.score + EPS || (Math.abs(score - best.score) <= EPS && tie > best.tie)) {
      best = { score, tie, out: { left: axis(s, below, above), right: axis(r, below, above), divisions: above + below } };
    }
  }
  return best?.out ?? fallback!;
}
