import { dualAxis, niceStepAtLeast } from './axis';

/** What a dyno chart must never do, checked on one layout. */
function invariants(leftMin: number, leftMax: number, rightMin: number, rightMax: number): string[] {
  const a = dualAxis(leftMin, leftMax, rightMin, rightMax);
  const bad: string[] = [];
  for (const [name, ax, lo, hi] of [['left', a.left, leftMin, leftMax], ['right', a.right, rightMin, rightMax]] as const) {
    // gridline labels are printed as integers, so every tick must be one
    if (!ax.ticks.every(Number.isInteger)) bad.push(`${name}: fractional tick in ${ax.ticks}`);
    if (!ax.ticks.every((v, i) => i === 0 || v - ax.ticks[i - 1]! === ax.step)) bad.push(`${name}: uneven ${ax.ticks}`);
    if (ax.ticks[0] !== ax.lo || ax.ticks.at(-1) !== ax.hi) bad.push(`${name}: ends ${ax.lo}/${ax.hi} vs ${ax.ticks}`);
    if (ax.hi < hi || ax.lo > Math.min(0, lo)) bad.push(`${name}: [${ax.lo}, ${ax.hi}] does not contain [${lo}, ${hi}]`);
  }
  if (a.left.ticks.length !== a.right.ticks.length) bad.push('axes do not share gridlines');
  if (a.left.ticks.indexOf(0) < 0 || a.left.ticks.indexOf(0) !== a.right.ticks.indexOf(0)) bad.push('zero lines not aligned');
  if (a.divisions < 3 || a.divisions > 7) bad.push(`${a.divisions} divisions`);
  // the left axis tops out at the first tick at or above its peak
  if (a.left.hi - a.left.step >= leftMax) bad.push(`left top ${a.left.hi} has a spare step above ${leftMax}`);
  return bad;
}

describe('niceStepAtLeast', () => {
  it('keeps exact hits and moves up just past them', () => {
    expect([1, 2, 5, 25, 250, 251, 2500].map(niceStepAtLeast)).toEqual([1, 2, 5, 25, 250, 500, 2500]);
  });
  it('only produces whole 1/2/2.5/5 x 10^n steps', () => {
    for (let x = 0.01; x < 1e6; x *= 1.037) {
      const s = niceStepAtLeast(x);
      const m = s / 10 ** Math.floor(Math.log10(s));
      expect(Number.isInteger(s) && s >= Math.min(x, 1) && [1, 2, 2.5, 5].some(k => Math.abs(m - k) < 1e-9)).toBe(true);
    }
  });
  it('is 1 for anything at or below 1, and for NaN', () => {
    expect([0, -3, 0.2, 1, NaN].map(niceStepAtLeast)).toEqual([1, 1, 1, 1, 1]);
  });
});

describe('dualAxis', () => {
  it('puts a 235 N·m peak on a 250 axis, not 500 (the reported bug)', () => {
    // crdi15 full-load pull, native dieselsim: 235.4 N·m at 2500 rpm
    const a = dualAxis(0, 235.4, 0, 85.1);
    expect(a.left.ticks).toEqual([0, 50, 100, 150, 200, 250]);
    expect(a.right.ticks).toEqual([0, 20, 40, 60, 80, 100]);
  });

  it('lays out the heavy-duty and single-cylinder presets', () => {
    expect(dualAxis(0, 2313.3, 0, 436).left.ticks).toEqual([0, 500, 1000, 1500, 2000, 2500]);
    expect(dualAxis(0, 2313.3, 0, 436).right.ticks).toEqual([0, 100, 200, 300, 400, 500]);
  });

  it('aligns zero when torque goes negative', () => {
    const a = dualAxis(-40, 235, -3, 84);
    expect(a.left.ticks).toEqual([-50, 0, 50, 100, 150, 200, 250]);
    expect(a.right.ticks).toEqual([-20, 0, 20, 40, 60, 80, 100]);
  });

  it('lays out every preset\'s real full-load pull, governor end included', () => {
    // native dieselsim, 10 points idle..max_rpm; the last point is high idle,
    // where the governor has pulled fuel to 4% and the engine is motoring
    expect(dualAxis(-25.1, 235.4, -12.1, 81.9).left.ticks).toEqual([-50, 0, 50, 100, 150, 200, 250]);  // crdi15
    expect(dualAxis(-62.0, 2308.4, -13.6, 423.0).left.ticks).toEqual([-500, 0, 500, 1000, 1500, 2000, 2500]);  // hd_i6
    expect(dualAxis(-4.6, 35.7, -1.6, 10.6).left.ticks).toEqual([-10, 0, 10, 20, 30, 40]);  // single
  });

  it('does not add a spare step when a peak lands on a tick with float noise', () => {
    const peak = 0.1 * 3 * 1000; // 300.00000000000006
    expect(dualAxis(0, peak, 0, 100).left.hi).toBe(300);
    expect(niceStepAtLeast(2.5 * 100 * (1 + 1e-12))).toBe(250);
  });

  it('keeps negative power inside the axis even if torque is not negative', () => {
    // cannot happen physically (P = T w), but the chart must not draw below its floor
    const a = dualAxis(0, 100, -5, 40);
    expect(a.right.lo).toBeLessThanOrEqual(-5);
    expect(a.left.ticks.indexOf(0)).toBe(a.right.ticks.indexOf(0));
  });

  it('never throws on degenerate data, and still returns a usable layout', () => {
    for (const [a, b, c, d] of [[0, 0.4, 0, 0.02], [0, 0, 0, 0], [-5, -1, -2, -0.5], [0, 1e-9, 0, 1e-9], [-0.2, 0.3, -0.1, 0.1]]) {
      const ax = dualAxis(a!, b!, c!, d!);
      expect(ax.left.ticks.length, `${a}/${b}`).toBeGreaterThanOrEqual(2);
      expect(ax.left.ticks.length).toBe(ax.right.ticks.length);
      expect(ax.left.hi >= b! && ax.left.lo <= Math.min(0, a!)).toBe(true);
    }
  });

  it('holds every invariant across the whole range the chart can see', () => {
    // torque 50 N·m .. 20 kN·m; power/torque ratio 0.02 .. 1 kW per N·m (rpm-dependent);
    // the app floors the axes at 50 N·m and 10 kW
    const failures: string[] = [];
    for (let t = 50; t <= 20000; t *= 1.013) {
      for (let k = 0.02; k <= 1; k *= 1.07) {
        const p = Math.max(10, t * k);
        failures.push(...invariants(0, t, 0, p).map(f => `${t.toFixed(1)}/${p.toFixed(1)}: ${f}`));
        failures.push(...invariants(-0.3 * t, t, -0.3 * p, p).map(f => `neg ${t.toFixed(1)}/${p.toFixed(1)}: ${f}`));
      }
    }
    expect(failures.slice(0, 5)).toEqual([]);
  });

  it('keeps both curves spanning a fair share of the plotted height', () => {
    // Span = zero-to-peak plus any negative tail, over the whole axis. Measured
    // over this range: worst 0.50 with no tail (power on its 10 kW floor),
    // 0.43 with a 10-30% governor-end tail (an extreme torque/power ratio).
    // The old headroom-and-quarters scheme reached 0.46 with no tail and put a
    // fractional value on a gridline in 20% of layouts.
    for (const [tail, bound] of [[0, 0.5], [0.1, 0.43], [0.3, 0.43]] as const) {
      let worst = 1, where = '';
      for (let t = 50; t <= 20000; t *= 1.013) {
        for (let k = 0.02; k <= 1; k *= 1.07) {
          const p = Math.max(10, t * k), a = dualAxis(-tail * t, t, -tail * p, p);
          const fill = Math.min(t * (1 + tail) / (a.left.hi - a.left.lo), p * (1 + tail) / (a.right.hi - a.right.lo));
          if (fill < worst) { worst = fill; where = `tail ${tail}, ${t.toFixed(1)}/${p.toFixed(1)}`; }
        }
      }
      expect(worst, where).toBeGreaterThanOrEqual(bound - 1e-9);
    }
  });

  it('does not spend a gridline band on a small negative tail when a finer grid fits better', () => {
    // 700 N·m peak with a -70 N·m governor end. Coarser candidate steps can
    // over-run their interval count; refining them gives 250-steps (span 0.68)
    // rather than 200-steps over six intervals (0.54).
    expect(dualAxis(-70, 700, -25, 245).left.ticks).toEqual([-250, 0, 250, 500, 750]);
  });
});
