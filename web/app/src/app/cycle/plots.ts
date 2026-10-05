/**
 * The cycle page's plots (Phase 6, ADR-015): axes, ticks and paths as pure
 * functions, so the rules can be tested without Angular.
 *
 * Angles. The solver's crank axis runs 0..720 with 0 = cylinder 1's firing
 * TDC. p–θ and heat release are drawn around firing TDC (rel(): -360..360);
 * valve lift is drawn on the raw 0..720 axis, where the overlap TDC sits at
 * 360 in the middle instead of split across both edges.
 */

/** Degrees after firing TDC, -360..360: what a p–θ plot is drawn against. */
export function rel(theta: number): number {
  return theta > 360 ? theta - 720 : theta;
}

export interface Ticks { lo: number; hi: number; ticks: number[] }

const MANTISSAS = [1, 2, 2.5, 5];

/** A nice step (1, 2, 2.5 or 5 times a power of ten) of at least x. */
export function niceStep(x: number): number {
  if (!(x > 0)) return 1;
  for (let e = Math.floor(Math.log10(x)); ; e++) {
    for (const m of MANTISSAS) {
      const s = m * 10 ** e;
      if (s >= x * (1 - 1e-9)) return s;
    }
  }
}

/** Ticks on a linear axis covering lo..hi in about `target` intervals. */
export function linTicks(lo: number, hi: number, target = 5): Ticks {
  if (!(hi > lo)) hi = lo + 1;
  const step = niceStep((hi - lo) / target);
  const a = Math.floor(lo / step + 1e-9) * step, b = Math.ceil(hi / step - 1e-9) * step;
  const ticks: number[] = [];
  for (let v = a; v <= b + step * 1e-6; v += step) ticks.push(Number(v.toPrecision(12)));
  return { lo: a, hi: b, ticks };
}

/** Ticks on a log axis: whole decades covering lo..hi, labelled at 1, 2 and 5. */
export function logTicks(lo: number, hi: number): Ticks {
  const a = 10 ** Math.floor(Math.log10(lo)), b = 10 ** Math.ceil(Math.log10(hi));
  const ticks: number[] = [];
  for (let d = a; d < b * 1.0001; d *= 10)
    for (const m of [1, 2, 5]) {
      const v = Number((m * d).toPrecision(12));
      if (v >= a * 0.9999 && v <= b * 1.0001) ticks.push(v);
    }
  return { lo: a, hi: b, ticks };
}

/**
 * Label rows for vertical markers: left to right, each label takes the first
 * row whose last label ends at least `gap` pixels before it, so labels of
 * close events (SOI, SOC, p max, MFB50 within a few degrees) never print over
 * each other. A label's width is estimated from its length (`charPx`).
 */
export function labelRows(xs: number[], labels: string[], gap = 4, charPx = 6.2): number[] {
  const order = xs.map((_, i) => i).sort((i, j) => xs[i]! - xs[j]!);
  const ends: number[] = [];
  const rows = new Array<number>(xs.length).fill(0);
  for (const i of order) {
    const start = xs[i]! + 3, end = start + labels[i]!.length * charPx;
    let r = ends.findIndex(e => e + gap <= start);
    if (r < 0) { r = ends.length; ends.push(end); } else ends[r] = end;
    rows[i] = r;
  }
  return rows;
}

/** Points sorted by x, so a line through them runs left to right. */
export function sortedByX(xs: number[], ys: number[]): { x: number[]; y: number[] } {
  const idx = xs.map((_, i) => i).sort((i, j) => xs[i]! - xs[j]!);
  return { x: idx.map(i => xs[i]!), y: idx.map(i => ys[i]!) };
}

export interface PlotLine { d: string; cls: string; label: string }
export interface PlotMarker { x: number; label: string; cls: string; row: number }
export interface PlotModel {
  title: string; xLabel: string; yLabel: string; desc: string;
  W: number; H: number; M: { l: number; r: number; t: number; b: number };
  xTicks: { x: number; label: string }[]; yTicks: { y: number; label: string }[];
  lines: PlotLine[]; markers: PlotMarker[]; shade?: { x0: number; x1: number; label: string };
}

export interface Series { x: number[]; y: number[]; cls: string; label: string }

const W = 520, H = 300, M = { l: 56, r: 14, t: 14, b: 42 };
const label = (v: number) => (Math.abs(v) >= 1 || v === 0 ? String(Number(v.toPrecision(6))) : String(Number(v.toPrecision(3))));

/**
 * One plot. Linear or log axes; series are clipped to the x window (and
 * points outside it dropped); markers are vertical lines at an x.
 */
export function buildPlot(o: {
  title: string; xLabel: string; yLabel: string; desc: string;
  series: Series[]; xWindow?: [number, number]; xLog?: boolean; yLog?: boolean;
  markers?: { x: number; label: string; cls: string }[]; shade?: { x0: number; x1: number; label: string };
  xTarget?: number;
}): PlotModel {
  const inWin = (x: number) => !o.xWindow || (x >= o.xWindow[0] && x <= o.xWindow[1]);
  const pts = o.series.map(s => {
    const keep = s.x.map((x, i) => i).filter(i => inWin(s.x[i]!) && (!o.yLog || s.y[i]! > 0) && (!o.xLog || s.x[i]! > 0));
    return { ...s, x: keep.map(i => s.x[i]!), y: keep.map(i => s.y[i]!) };
  });
  const allX = pts.flatMap(s => s.x), allY = pts.flatMap(s => s.y);
  const xr = o.xWindow ?? [Math.min(...allX), Math.max(...allX)];
  const xt = o.xLog ? logTicks(xr[0], xr[1]) : o.xWindow ? { lo: xr[0], hi: xr[1], ticks: linTicks(xr[0], xr[1], o.xTarget ?? 6).ticks.filter(v => v >= xr[0] && v <= xr[1]) } : linTicks(xr[0], xr[1], o.xTarget ?? 6);
  const yt = o.yLog ? logTicks(Math.min(...allY), Math.max(...allY)) : linTicks(Math.min(0, ...allY), Math.max(...allY), 5);
  const fx = (v: number) => o.xLog
    ? M.l + (Math.log10(v) - Math.log10(xt.lo)) / (Math.log10(xt.hi) - Math.log10(xt.lo)) * (W - M.l - M.r)
    : M.l + (v - xt.lo) / (xt.hi - xt.lo) * (W - M.l - M.r);
  const fy = (v: number) => o.yLog
    ? M.t + (Math.log10(yt.hi) - Math.log10(v)) / (Math.log10(yt.hi) - Math.log10(yt.lo)) * (H - M.t - M.b)
    : M.t + (yt.hi - v) / (yt.hi - yt.lo) * (H - M.t - M.b);
  return {
    title: o.title, xLabel: o.xLabel, yLabel: o.yLabel, desc: o.desc, W, H, M,
    xTicks: xt.ticks.map(v => ({ x: fx(v), label: label(v) })),
    yTicks: yt.ticks.map(v => ({ y: fy(v), label: label(v) })),
    lines: pts.map(s => ({ d: s.x.map((x, i) => `${fx(x).toFixed(1)},${fy(s.y[i]!).toFixed(1)}`).join(' '), cls: s.cls, label: s.label })),
    markers: ((ms) => {
      const rows = labelRows(ms.map(m => fx(m.x)), ms.map(m => m.label));
      return ms.map((m, i) => ({ x: fx(m.x), label: m.label, cls: m.cls, row: rows[i]! }));
    })((o.markers ?? []).filter(m => inWin(m.x))),
    ...(o.shade ? { shade: { x0: fx(o.shade.x0), x1: fx(o.shade.x1), label: o.shade.label } } : {}),
  };
}
