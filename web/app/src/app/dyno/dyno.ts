import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import type { PointResult, PresetInfo } from '@dieselsim/solver';
import { describe, SolverService } from '../solver/solver.service';

interface Pt { rpm: number; torque: number; powerKw: number; r: PointResult; }

const N_POINTS = 10;
const W = 800, H = 420, M = { l: 60, r: 60, t: 18, b: 44 };
const fmt0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });

/** 1, 2 or 5 times a power of ten, at or above x. */
function niceCeil(x: number): number {
  if (x <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(x));
  return [1, 2, 2.5, 5, 10].map(m => m * p).find(v => v >= x)!;
}

@Component({
  selector: 'app-dyno',
  templateUrl: './dyno.html',
  styleUrl: './dyno.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Dyno implements OnInit {
  protected readonly solver = inject(SolverService);
  protected readonly fmt0 = fmt0;
  protected readonly fmt1 = fmt1;
  protected readonly fmt2 = fmt2;

  protected readonly engine = signal('crdi15');
  protected readonly points = signal<Pt[]>([]);
  protected readonly running = signal(false);
  protected readonly progress = signal<{ n: number; of: number; rpm: number } | undefined>(undefined);
  protected readonly runError = signal<string | undefined>(undefined);
  protected readonly elapsedS = signal<number | undefined>(undefined);

  protected readonly presets = computed(() => {
    const info = this.solver.info();
    return info ? info.presets.map(k => ({ key: k, ...info.preset_info[k]! })) : [];
  });
  protected readonly spec = computed<PresetInfo | undefined>(() => this.solver.info()?.preset_info[this.engine()]);
  protected readonly rpms = computed(() => {
    const s = this.spec();
    if (!s) return [];
    return Array.from({ length: N_POINTS }, (_, i) =>
      Math.round((s.idle_rpm + (s.max_rpm - s.idle_rpm) * i / (N_POINTS - 1)) / 50) * 50);
  });

  protected readonly peaks = computed(() => {
    const p = this.points();
    if (!p.length) return undefined;
    const t = p.reduce((a, b) => (b.torque > a.torque ? b : a));
    const w = p.reduce((a, b) => (b.powerKw > a.powerKw ? b : a));
    return { torque: t, power: w };
  });

  /** Chart geometry. Torque and power share their zero line. */
  protected readonly chart = computed(() => {
    const rpms = this.rpms(), pts = this.points();
    if (!rpms.length) return undefined;
    const x0 = rpms[0]!, x1 = rpms[rpms.length - 1]!;
    const tMax = niceCeil(Math.max(50, ...pts.map(p => p.torque)) * 1.08);
    const tMin = Math.min(0, ...pts.map(p => p.torque));
    const tLo = tMin < 0 ? -niceCeil(-tMin) : 0;
    const pMax = niceCeil(Math.max(10, ...pts.map(p => p.powerKw)) * 1.08);
    const pLo = tLo === 0 ? 0 : (tLo / tMax) * pMax;
    const x = (rpm: number) => M.l + (rpm - x0) / (x1 - x0) * (W - M.l - M.r);
    const yT = (v: number) => M.t + (tMax - v) / (tMax - tLo) * (H - M.t - M.b);
    const yP = (v: number) => M.t + (pMax - v) / (pMax - pLo) * (H - M.t - M.b);
    const line = (f: (p: Pt) => number) => pts.map(p => `${x(p.rpm).toFixed(1)},${f(p).toFixed(1)}`).join(' ');
    const step = x1 - x0 > 2500 ? 1000 : 500;
    const xTicks = [];
    for (let r = Math.ceil(x0 / step) * step; r <= x1; r += step) xTicks.push({ r, x: x(r) });
    const tTicks = [0, 0.25, 0.5, 0.75, 1].map(f => tLo + (tMax - tLo) * f)
      .map(v => ({ v, y: yT(v), p: pLo + (pMax - pLo) * ((v - tLo) / (tMax - tLo)) }));
    return {
      W, H, M, xTicks, tTicks, zeroY: yT(0), negative: tLo < 0,
      torque: line(p => yT(p.torque)), power: line(p => yP(p.powerKw)),
      dots: pts.map(p => ({ x: x(p.rpm), yt: yT(p.torque), yp: yP(p.powerKw) })),
    };
  });

  protected readonly summary = computed(() => {
    const pk = this.peaks(), s = this.spec();
    if (!pk || !s) return 'Torque and power curve, not yet run.';
    return `${s.name}: peak torque ${fmt0.format(pk.torque.torque)} newton-metres at ${fmt0.format(pk.torque.rpm)} rpm, ` +
           `peak power ${fmt0.format(pk.power.powerKw)} kilowatts at ${fmt0.format(pk.power.rpm)} rpm.`;
  });

  ngOnInit(): void {
    // Expert-mode page: the solver is the whole point, so start loading now.
    this.solver.start().catch(() => { /* surfaced through solver.error() */ });
  }

  protected selectEngine(key: string): void {
    this.engine.set(key);
    this.points.set([]);
    this.elapsedS.set(undefined);
    this.runError.set(undefined);
  }

  protected async run(): Promise<void> {
    if (this.running()) return;
    this.running.set(true);
    this.points.set([]);
    this.runError.set(undefined);
    this.elapsedS.set(undefined);
    const t0 = performance.now();
    const rpms = this.rpms();
    try {
      for (const [i, rpm] of rpms.entries()) {
        this.progress.set({ n: i + 1, of: rpms.length, rpm });
        const r = await this.solver.solvePoint({ engine: { preset: this.engine() }, rpm, load: 1 });
        this.points.update(p => [...p, { rpm, torque: r.torque, powerKw: r.power / 1000, r }]);
      }
      this.elapsedS.set((performance.now() - t0) / 1000);
    } catch (e) {
      this.runError.set(describe(e));
    } finally {
      this.progress.set(undefined);
      this.running.set(false);
    }
  }
}
