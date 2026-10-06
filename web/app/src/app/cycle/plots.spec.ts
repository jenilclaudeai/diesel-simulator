import { describe, expect, it } from 'vitest';
import { buildPlot, labelRows, linTicks, logTicks, niceStep, rel, sortedByX } from './plots';

describe('rel: degrees after firing TDC', () => {
  it('keeps 0..360 and moves 360..720 to -360..0', () => {
    expect([0, 9, 359, 360, 361, 700, 719].map(rel)).toEqual([0, 9, 359, 360, -359, -20, -1]);
  });
  it('a trace sorted by rel runs left to right across firing TDC', () => {
    const theta = Array.from({ length: 720 }, (_, i) => i);
    const s = sortedByX(theta.map(rel), theta);
    expect(s.x[0]).toBe(-359);
    expect(s.x.at(-1)).toBe(360);
    expect(s.x.every((x, i) => i === 0 || x > s.x[i - 1]!)).toBe(true);
    // the sample just before TDC (raw 719) sits just left of the one at TDC (raw 0)
    const i0 = s.x.indexOf(0);
    expect(s.y[i0 - 1]).toBe(719);
    expect(s.y[i0]).toBe(0);
  });
});

describe('ticks', () => {
  it('nice steps are 1, 2, 2.5 or 5 times a power of ten', () => {
    expect([3, 0.12, 25, 28.4, 1].map(niceStep)).toEqual([5, 0.2, 25, 50, 1]);
  });
  it('a linear axis covers the data with round ends', () => {
    expect(linTicks(0, 142)).toEqual({ lo: 0, hi: 150, ticks: [0, 50, 100, 150] });
  });
  it('a log axis spans whole decades, labelled at 1, 2 and 5', () => {
    expect(logTicks(1.2, 140)).toEqual({ lo: 1, hi: 1000, ticks: [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000] });
  });
});

describe('buildPlot', () => {
  const series = [{ x: [-50, -10, 0, 10, 50], y: [1, 2, 3, 2, 1], cls: 'a', label: 'A' }];
  it('clips series and markers to the x window', () => {
    const p = buildPlot({ title: 't', xLabel: 'x', yLabel: 'y', desc: 'd', series, xWindow: [-20, 20],
      markers: [{ x: 5, label: 'in', cls: 'm' }, { x: 40, label: 'out', cls: 'm' }] });
    expect(p.lines[0]!.d.split(' ').length).toBe(3);
    expect(p.markers.map(m => m.label)).toEqual(['in']);
  });
  it('a log axis drops points that are not positive', () => {
    const p = buildPlot({ title: 't', xLabel: 'x', yLabel: 'y', desc: 'd', yLog: true, xLog: true,
      series: [{ x: [0, 0.1, 1, 10], y: [5, 0, 20, 2], cls: 'a', label: 'A' }] });
    expect(p.lines[0]!.d.split(' ').length).toBe(2);
  });
  it('maps the window ends to the plot edges', () => {
    const p = buildPlot({ title: 't', xLabel: 'x', yLabel: 'y', desc: 'd', series, xWindow: [-50, 50] });
    const xs = p.lines[0]!.d.split(' ').map(s => Number(s.split(',')[0]));
    expect(xs[0]).toBeCloseTo(p.M.l, 6);
    expect(xs.at(-1)).toBeCloseTo(p.W - p.M.r, 6);
  });
});

describe('labelRows: marker labels never print over each other', () => {
  it('close markers go to separate rows; a far one reuses the first row', () => {
    // three events within a few pixels, then one far to the right
    expect(labelRows([100, 104, 108, 300], ['main SOI', 'main SOC', 'MFB50', 'p max'])).toEqual([0, 1, 2, 0]);
  });
  it('no two labels in one row overlap, in any input order', () => {
    const xs = [250, 40, 45, 200, 47, 120], labels = ['p max', 'pilot SOI', 'main SOI', 'MFB50', 'main SOC', 'x'];
    const rows = labelRows(xs, labels);
    const spans = xs.map((x, i) => ({ r: rows[i]!, a: x + 3, b: x + 3 + labels[i]!.length * 6.2 }));
    for (const s of spans) for (const t of spans)
      if (s !== t && s.r === t.r) expect(s.b <= t.a - 4 || t.b <= s.a - 4).toBe(true);
  });
});
