import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { EngineInfo, EngineRef, LiveBuildProgress, PointResult, PresetInfo } from '@dieselsim/solver';
import { engineJson, VEHICLE_NAMES } from '../engine/custom-engine';
import { engineLibrary, MY, type MyEngine } from '../engine/my-engines';
import { poolSize } from '../solver/pool-size';
import { achieved, type CustomEngine, EXAMPLE_ENGINE, headline } from '../engine/custom-engine';
import { EngineForm } from '../engine/engine-form';
import { describe, SolverService } from '../solver/solver.service';
import { dualAxis } from './axis';
import { accuracyNote } from './accuracy-note';
import { GRID_VERSION } from '../solver/physics-version';

interface Pt { rpm: number; torque: number; powerKw: number; r: PointResult; }

const N_POINTS = 10;
const W = 800, H = 420, M = { l: 60, r: 60, t: 18, b: 44 };
const fmt0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });

@Component({
  selector: 'app-dyno',
  imports: [RouterLink, EngineForm],
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
  /** ADR-014: the "Custom engine" choice, its numbers, and the builder's description of it */
  protected readonly CUSTOM = '__custom';
  protected readonly custom = signal<CustomEngine>(EXAMPLE_ENGINE);
  protected readonly customInfo = signal<EngineInfo | undefined>(undefined);
  protected readonly isCustom = computed(() => this.engine() === this.CUSTOM);
  /** ADR-014 step 3: building the custom engine's drivable grid in this browser */
  protected readonly workers = poolSize();
  protected readonly building = signal(false);
  protected readonly buildProgress = signal<LiveBuildProgress | undefined>(undefined);
  protected readonly buildError = signal<string | undefined>(undefined);
  protected readonly saved = signal<MyEngine | undefined>(undefined);
  protected readonly MY = MY;
  protected vehicleName(k: string): string { return (VEHICLE_NAMES as Record<string, string>)[k] ?? k; }
  private buildAbort: AbortController | undefined;
  private savedText: string | undefined;
  protected readonly points = signal<Pt[]>([]);
  protected readonly running = signal(false);
  protected readonly progress = signal<{ n: number; of: number; rpm: number } | undefined>(undefined);
  protected readonly runError = signal<string | undefined>(undefined);
  protected readonly elapsedS = signal<number | undefined>(undefined);

  protected readonly presets = computed(() => {
    const info = this.solver.info();
    return info ? info.presets.map(k => ({ key: k, ...info.preset_info[k]! })) : [];
  });
  /** how far this page's fast solve is from a converged one (FINDING-013) */
  protected readonly accuracy = computed(() => this.isCustom()
    ? 'Each point is solved in 9 fast cycles so a pull takes about a minute. For a custom engine, how far that is from a fully converged solve has not been measured.'
    // keyed on the solver (grid) hash: the live loop and the synth never run in a pull
    : accuracyNote(this.engine(), GRID_VERSION, r => fmt0.format(r)));
  protected readonly spec = computed<PresetInfo | undefined>(() =>
    this.isCustom() ? this.customInfo() : this.solver.info()?.preset_info[this.engine()]);
  /** a custom engine's finished pull against its brochure, as builder.verify() reports it
   *  (not while it runs: a half-run pull's peaks would read as a shortfall) */
  protected readonly achieved = computed(() => {
    const req = this.customInfo()?.requested;
    return this.isCustom() && req && this.elapsedS() !== undefined ? achieved(this.points(), req) : null;
  });
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
    // Shared gridlines, round labels on both axes, tops at the first tick at or
    // above each peak. The floors only frame an empty chart: applied to real
    // data they squashed a small engine (35.7 N·m on a 60 axis).
    const T = pts.map(p => p.torque), P = pts.map(p => p.powerKw);
    const ax = pts.length
      ? dualAxis(Math.min(0, ...T), Math.max(...T), Math.min(0, ...P), Math.max(...P))
      : dualAxis(0, 50, 0, 10);
    const tMax = ax.left.hi, tLo = ax.left.lo, pMax = ax.right.hi, pLo = ax.right.lo;
    const x = (rpm: number) => M.l + (rpm - x0) / (x1 - x0) * (W - M.l - M.r);
    const yT = (v: number) => M.t + (tMax - v) / (tMax - tLo) * (H - M.t - M.b);
    const yP = (v: number) => M.t + (pMax - v) / (pMax - pLo) * (H - M.t - M.b);
    const line = (f: (p: Pt) => number) => pts.map(p => `${x(p.rpm).toFixed(1)},${f(p).toFixed(1)}`).join(' ');
    const step = x1 - x0 > 2500 ? 1000 : 500;
    const xTicks = [];
    for (let r = Math.ceil(x0 / step) * step; r <= x1; r += step) xTicks.push({ r, x: x(r) });
    const tTicks = ax.left.ticks.map((v, i) => ({ v, y: yT(v), p: ax.right.ticks[i]! }));
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
    if (key === this.CUSTOM) void this.describeCustom();
  }

  protected customChanged(e: CustomEngine): void {
    this.custom.set(e);
    this.saved.set(undefined);
    this.points.set([]);
    this.elapsedS.set(undefined);
    void this.describeCustom();
  }

  private engineRef(): EngineRef {
    return this.isCustom() ? { headline: headline(this.custom()) } : { preset: this.engine() };
  }

  /** The builder's own rpm range and the requested numbers, for the chart and the comparison. */
  private async describeCustom(): Promise<void> {
    this.customInfo.set(undefined);
    this.runError.set(undefined);
    try {
      this.customInfo.set(await this.solver.describeEngine({ headline: headline(this.custom()) }));
    } catch (e) {
      this.runError.set(describe(e));
    }
  }

  /** Build the custom engine's drivable grid here, and keep it in "My engines". */
  protected async buildDrivable(): Promise<void> {
    if (this.building()) return;
    const e = this.custom();
    this.building.set(true);
    this.buildError.set(undefined);
    this.saved.set(undefined);
    this.buildAbort = new AbortController();
    // e2e only: a small grid, so a browser test can build one in minutes
    const m = location.search.includes('e2e') ? /gridsize=(\d+)x(\d+)/.exec(location.search) : null;
    try {
      const text = await this.solver.buildLiveGrid({ headline: headline(e) }, {
        key: e.key, ...(m ? { size: [Number(m[1]), Number(m[2])] as [number, number] } : {}),
        extra: { custom: true, vehicle: e.vehicle, engine_json: JSON.parse(engineJson(e)) },
        onProgress: p => this.buildProgress.set(p), signal: this.buildAbort.signal,
      });
      const mine: MyEngine = { key: e.key, name: e.name, vehicle: e.vehicle, savedAt: Date.now(), engine: e };
      await engineLibrary().save(mine, text);
      this.savedText = text;
      this.saved.set(mine);
    } catch (err) {
      this.buildError.set(describe(err) === 'Stopped.'
        ? 'Stopped. What it finished is kept: build again to carry on.' : describe(err));
    } finally {
      this.building.set(false);
      this.buildProgress.set(undefined);
    }
  }

  protected cancelBuild(): void { this.buildAbort?.abort(); }

  /** The grid file, for a phone or a friend: /drive and /enjoy import it. */
  protected downloadGrid(): void {
    const t = this.savedText, e = this.saved();
    if (!t || !e) return;
    const url = URL.createObjectURL(new Blob([t + '\n'], { type: 'application/json' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `${e.key}.grid.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  protected fmtMin(s: number): string { return s < 90 ? `${Math.round(s)} s` : `${Math.round(s / 60)} min`; }

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
        const r = await this.solver.solvePoint({ engine: this.engineRef(), rpm, load: 1 });
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
