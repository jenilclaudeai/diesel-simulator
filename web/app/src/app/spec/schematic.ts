import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import type { CompressorMap, CycleResult } from '@dieselsim/solver';
import { linTicks } from '../cycle/plots';
import { arcPath, CLEARANCE_X, cylinderSection, dialPoint, ringPack, valveDial } from './schematics';

type Vals = Record<string, unknown>;
const n = (v: Vals, k: string) => Number(v[k]);
const f1 = (x: number) => x.toFixed(1), f0 = (x: number) => x.toFixed(0);

/**
 * ADR-009's live 2D schematics on the spec page (Phase 6, ADR-015): drawn
 * from the spec fields, with the edits applied, so they redraw as they
 * change. kind: cylinder | valves | air | friction.
 */
@Component({
  selector: 'app-schematic',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './schematic.html',
  styleUrl: './schematic.css',
})
export class Schematic {
  readonly kind = input.required<string>();
  /** spec values by dotted path, edits applied */
  readonly v = input.required<Vals>();
  readonly cmap = input<CompressorMap | undefined>(undefined);
  /** the operating point of the last cycle solved for exactly this engine and these edits */
  readonly point = input<CycleResult['compressor'] | undefined>(undefined);
  protected readonly f1 = f1;
  protected readonly f0 = f0;
  protected readonly X = CLEARANCE_X;

  protected readonly crank = signal(30);
  protected readonly section = computed(() => {
    const v = this.v();
    return cylinderSection({ bore: n(v, 'geom.bore'), stroke: n(v, 'geom.stroke'), conrod: n(v, 'geom.conrod'),
      compression_ratio: n(v, 'geom.compression_ratio'), pin_offset: n(v, 'geom.pin_offset') }, this.crank());
  });
  protected readonly geomText = computed(() => {
    const v = this.v();
    return { bore: n(v, 'geom.bore') * 1000, stroke: n(v, 'geom.stroke') * 1000, rod: n(v, 'geom.conrod') * 1000,
      cr: n(v, 'geom.compression_ratio'), off: n(v, 'geom.pin_offset') * 1000 };
  });

  protected readonly dial = computed(() => {
    const v = this.v();
    const d = valveDial(n(v, 'valves.ivo_deg'), n(v, 'valves.ivc_deg'), n(v, 'valves.evo_deg'), n(v, 'valves.evc_deg'),
      n(v, 'inj.soi_deg_btdc'));
    const C = 130, R = 92;
    return { ...d, C, R,
      intakePath: arcPath(C, C, R - 14, d.intake.from, d.intake.deg),
      exhaustPath: arcPath(C, C, R, d.exhaust.from, d.exhaust.deg),
      overlapPath: d.overlap > 0 ? arcPath(C, C, R - 7, d.intake.from, d.overlap) : '',
      inj: dialPoint(C, C, R + 12, d.injection), injIn: dialPoint(C, C, R - 26, d.injection),
      tdc: dialPoint(C, C, R + 22, 0), bdc: dialPoint(C, C, R + 22, 180) };
  });

  protected readonly map = computed(() => {
    const m = this.cmap();
    if (!m || !m.enabled) return undefined;
    const W = 520, H = 300, M = { l: 52, r: 14, t: 12, b: 40 };
    const allM = m.lines.flatMap(l => l.m), allP = m.lines.flatMap(l => l.pr);
    const xt = linTicks(0, Math.max(...allM), 6), yt = linTicks(1, Math.max(...allP), 5);
    const fx = (x: number) => M.l + (x - xt.lo) / (xt.hi - xt.lo) * (W - M.l - M.r);
    const fy = (y: number) => M.t + (yt.hi - y) / (yt.hi - yt.lo) * (H - M.t - M.b);
    const pts = (ms: number[], ps: number[]) => ms.map((x, i) => `${fx(x).toFixed(1)},${fy(ps[i]!).toFixed(1)}`).join(' ');
    const p = this.point();
    return { W, H, M,
      xTicks: xt.ticks.map(t => ({ x: fx(t), label: String(Number(t.toPrecision(4))) })),
      yTicks: yt.ticks.map(t => ({ y: fy(t), label: String(Number(t.toPrecision(4))) })),
      lines: m.lines.map(l => ({ d: pts(l.m, l.pr), label: `${Math.round(l.u * 100)}%`, lx: fx(l.m.at(-1)!) + 3, ly: fy(l.pr.at(-1)!) })),
      surge: pts(m.surge.map(s => s.m), m.surge.map(s => s.pr)),
      choke: pts(m.choke.map(s => s.m), m.choke.map(s => s.pr)),
      point: p ? { x: fx(p.m_corr), y: fy(p.pr), pr: p.pr, m: p.m_corr, margin: p.surge_margin } : undefined,
      nRef: m.n_corr_ref };
  });

  protected readonly rings = computed(() => {
    const v = this.v();
    const nComp = Math.max(1, Math.round(n(v, 'trib.n_comp_rings')));
    const rw = n(v, 'trib.ring_axial_width'), ow = n(v, 'trib.oil_ring_width');
    const pack = ringPack(nComp, rw);
    const k = 230 / pack.height;                                   // px per m, down the piston edge
    const skirt = n(v, 'trib.skirt_clearance_new'), bore = n(v, 'geom.bore');
    const main = { d: n(v, 'trib.main_dia'), c: n(v, 'trib.main_clearance_new') };
    const rod = { d: n(v, 'trib.rod_dia'), c: n(v, 'trib.rod_clearance_new') };
    const bearing = (b: { d: number; c: number }) => {
      const R = 46, gap = Math.max(0.5, (b.c / 2) / b.d * 2 * R * CLEARANCE_X);   // radial clearance, exaggerated
      return { R, r: R - gap, d: b.d * 1000, um: b.c * 1e6 };
    };
    return { k, h: pack.height * k, oilLandMm: ow * 1000,
      rings: pack.rings.map(r => ({ y: 10 + r.y * k, h: r.h * k, kind: r.kind, mm: r.h * 1000 })),
      nComp, skirtUm: skirt * 1e6, skirtPx: Math.max(1, (skirt / 2) / bore * 120 * CLEARANCE_X), ringGapMm: n(v, 'trib.ring_gap_new') * 1000,
      main: bearing(main), rod: bearing(rod) };
  });
}
