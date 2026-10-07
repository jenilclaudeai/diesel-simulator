import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { CycleResult, PresetInfo } from '@dieselsim/solver';
import { describe, SolverService } from '../solver/solver.service';
import { SpecEdits } from '../spec/spec-edits';
import { EnvChoice } from '../weather/env-choice';
import { EnvPicker } from '../weather/env-picker';
import { refKey, SpecStatus } from '../spec/spec-status';
import { LastResults } from '../spec/last-results';

interface Kept { engine: string; rpm: number; load: number; result: CycleResult; solvedWith: string; elapsedS: number }
import { buildPlot, rel, sortedByX, type PlotModel } from './plots';

const fmt0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });

/** "+9°" / "−3.5°": an angle after firing TDC */
const deg = (v: number) => `${v >= 0 ? '+' : '−'}${fmt1.format(Math.abs(v))}°`;

/**
 * The cycle page (Phase 6, ADR-015): one operating point's combustion cycle,
 * as an engine developer reads it: p–V (log-log), p–θ, heat release and
 * valve lift, for cylinder 1, solved by Python in the browser.
 */
@Component({
  selector: 'app-cycle',
  imports: [RouterLink, SpecStatus, EnvPicker],
  templateUrl: './cycle.html',
  styleUrl: './cycle.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CyclePage implements OnInit {
  protected readonly solver = inject(SolverService);
  protected readonly edits = inject(SpecEdits);
  private readonly env = inject(EnvChoice);
  protected readonly fmt0 = fmt0;

  /** starts on the spec editor's engine, so its edits are what gets solved */
  protected readonly engine = signal(this.edits.base());
  protected readonly rpmIn = signal<number | undefined>(undefined);
  protected readonly load = signal(0.6);
  protected readonly result = signal<CycleResult | undefined>(undefined);
  /** refKey() of the engine the current result was solved with (the stale banner compares it) */
  protected readonly solvedWith = signal<string | undefined>(undefined);
  protected readonly running = signal(false);
  protected readonly error = signal<string | undefined>(undefined);
  protected readonly elapsedS = signal<number | undefined>(undefined);

  protected readonly presets = computed(() => {
    const info = this.solver.info();
    return info ? info.presets.map(k => ({ key: k, ...info.preset_info[k]! })) : [];
  });
  protected readonly spec = computed<PresetInfo | undefined>(() => this.solver.info()?.preset_info[this.engine()]);
  /** the rpm asked for, or 60% of the way from idle to rated */
  protected readonly rpm = computed(() => {
    const s = this.spec();
    return this.rpmIn() ?? (s ? Math.round((s.idle_rpm + 0.6 * (s.rated_rpm - s.idle_rpm)) / 50) * 50 : 2000);
  });

  protected readonly plots = computed<PlotModel[]>(() => {
    const r = this.result();
    if (!r) return [];
    const e = r.events, s = r.summary;
    const bar = (a: number[]) => a.map(v => v / 1e5);
    const pTheta = sortedByX(r.theta.map(rel), bar(r.p));
    const pMot = sortedByX(r.theta.map(rel), bar(r.p_motored));
    const hrr = sortedByX(r.theta.map(rel), r.hrr);
    const comb = [
      { x: rel(e.soi_main), label: 'main SOI', cls: 'inj' },
      ...(e.soc_main >= 0 ? [{ x: rel(e.soc_main), label: 'main SOC', cls: 'soc' }] : []),
      ...(e.soc_pilot >= 0 && e.soi_pilot !== e.soi_main ? [{ x: rel(e.soi_pilot), label: 'pilot SOI', cls: 'inj' }] : []),
      { x: s.mfb50, label: 'MFB50', cls: 'mfb' },
    ];
    const litres = r.V.map(v => v * 1000);
    return [
      buildPlot({
        title: 'Pressure against volume (log-log)', xLabel: 'Cylinder volume (litres, log)', yLabel: 'Pressure (bar, log)',
        desc: 'Compression and expansion are near-straight lines on log axes; the area enclosed is the work.',
        xLog: true, yLog: true,
        series: [{ x: litres, y: bar(r.p_motored), cls: 'motored', label: 'motored' },
                 { x: litres, y: bar(r.p), cls: 'fired', label: 'fired' }],
      }),
      buildPlot({
        title: 'Pressure against crank angle', xLabel: 'Crank angle (degrees after firing TDC)', yLabel: 'Pressure (bar)',
        desc: 'Fired against motored (no combustion): the gap is what combustion adds.',
        xWindow: [-180, 180], xTarget: 8,
        series: [{ ...pMot, cls: 'motored', label: 'motored' }, { ...pTheta, cls: 'fired', label: 'fired' }],
        markers: [...comb, { x: rel(s.theta_pmax), label: 'p max', cls: 'pmax' }],
      }),
      buildPlot({
        title: 'Heat release rate', xLabel: 'Crank angle (degrees after firing TDC)', yLabel: 'Heat release (J per degree)',
        desc: 'Premixed spike first, then the diffusion burn.',
        xWindow: [-40, 100], xTarget: 7,
        series: [{ ...hrr, cls: 'fired', label: 'heat release' }],
        markers: comb,
      }),
      buildPlot({
        title: 'Valve lift', xLabel: 'Crank angle (0 and 720 = firing TDC, 360 = overlap TDC)', yLabel: 'Lift (mm)',
        desc: 'Exhaust then intake; the shaded band is the overlap, both valves open.',
        xWindow: [0, 720], xTarget: 8,
        series: [{ x: r.theta, y: r.lift_exh.map(v => v * 1000), cls: 'exh', label: 'exhaust' },
                 { x: r.theta, y: r.lift_int.map(v => v * 1000), cls: 'int', label: 'intake' }],
        markers: [{ x: e.evo, label: 'EVO', cls: 'exh' }, { x: e.evc, label: 'EVC', cls: 'exh' },
                  { x: e.ivo, label: 'IVO', cls: 'int' }, { x: e.ivc, label: 'IVC', cls: 'int' }],
        ...(e.ivo < e.evc ? { shade: { x0: e.ivo, x1: e.evc, label: 'overlap' } } : {}),
      }),
    ];
  });

  /** The numbers an engine developer reads off a cycle. Economy is a steady-state figure (FINDING-009). */
  protected readonly rows = computed(() => {
    const r = this.result();
    if (!r) return [];
    const s = r.summary, e = r.events;
    return [
      ['Torque', `${fmt0.format(s.torque)} N·m`],
      ['Power', `${fmt1.format(s.power / 1000)} kW`],
      ['IMEP, net (gross)', `${fmt2.format(s.imep_net / 1e5)} bar (${fmt2.format(s.imep_gross / 1e5)})`],
      ['Pumping (PMEP)', `${fmt2.format(s.pmep / 1e5)} bar`],
      ['Peak pressure', `${fmt1.format(s.p_max / 1e5)} bar at ${deg(rel(s.theta_pmax))}`],
      ['Combustion pressure rise', `${fmt2.format(s.dpdtheta_comb)} bar per degree`],
      ['Peak temperature (mean gas)', `${fmt0.format(s.T_max - 273.15)} °C`],
      ['Main injection starts', `${fmt1.format((720 - e.soi_main) % 720)}° before TDC, for ${fmt1.format(s.inj_duration_deg)}°`],
      ['Rail pressure', `${fmt0.format(s.rail_pressure / 1e5)} bar`],
      ['Ignition delay', `${fmt1.format(s.ign_delay_deg)}° (${fmt2.format(s.ign_delay_ms)} ms)`],
      ['Premixed fraction', `${fmt0.format(s.premix_fraction * 100)}%`],
      ['50% burned (MFB50)', deg(s.mfb50)],
      ['Burn duration', `${fmt0.format(s.burn_duration_deg)}°`],
      ['Air-fuel ratio', fmt1.format(s.afr)],
      ['Boost (pressure ratio)', fmt2.format(s.boost_pr)],
      ['EGR', `${fmt0.format(s.egr_fraction * 100)}%`],
      ['Fuel per cycle', `${fmt1.format(s.fuel_mg)} mg`],
      ['BSFC (steady state)', `${fmt0.format(s.bsfc)} g/kWh`],
    ] as const;
  });

  private readonly kept = inject(LastResults);

  ngOnInit(): void {
    // Expert-mode page: the solver is the whole point, so start loading now.
    this.solver.start().catch(() => { /* surfaced through solver.error() */ });
    // back from the spec editor: the last cycle, flagged out of date if the edits changed since
    const k = this.kept.get<Kept>('cycle');
    if (k) {
      this.engine.set(k.engine); this.rpmIn.set(k.rpm); this.load.set(k.load);
      this.result.set(k.result); this.solvedWith.set(k.solvedWith); this.elapsedS.set(k.elapsedS);
    }
  }

  protected selectEngine(key: string): void {
    this.engine.set(key);
    this.rpmIn.set(undefined);
    this.result.set(undefined);
    this.error.set(undefined);
    this.kept.clear('cycle');
  }

  protected setRpm(v: string): void {
    const s = this.spec(), n = Number(v);
    if (!s || !Number.isFinite(n)) return;
    this.rpmIn.set(Math.min(s.max_rpm, Math.max(s.idle_rpm, Math.round(n))));
  }

  protected async solve(): Promise<void> {
    if (this.running()) return;
    this.running.set(true);
    this.error.set(undefined);
    const t0 = performance.now();
    try {
      const engine = this.env.solveRef(this.edits.engineRef(this.engine()));
      this.result.set(await this.solver.solveCycle({ engine, rpm: this.rpm(), load: this.load() }));
      this.solvedWith.set(refKey(engine));
      this.kept.set<Kept>('cycle', { engine: this.engine(), rpm: this.rpm(), load: this.load(), result: this.result()!,
        solvedWith: refKey(engine), elapsedS: (performance.now() - t0) / 1000 });
      this.elapsedS.set((performance.now() - t0) / 1000);
    } catch (e) {
      this.error.set(describe(e));
    } finally {
      this.running.set(false);
    }
  }
}
