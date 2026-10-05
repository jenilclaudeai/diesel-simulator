import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { PresetInfo } from '@dieselsim/solver';
import { buildPlot, type PlotModel } from '../cycle/plots';
import { describe, SolverService } from '../solver/solver.service';
import { LastResults } from '../spec/last-results';
import { SpecEdits } from '../spec/spec-edits';
import { refKey, SpecStatus } from '../spec/spec-status';
import { estimateS, fmtDuration } from './durability-plan';

const fmt0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const fmt3 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 3, minimumFractionDigits: 3 });

type Row = Record<string, number>;
interface Kept { engine: string; hours: number; stepH: number; rows: Row[]; solvedWith: string }

/**
 * The durability page (Phase 6, ADR-015): the engine aged over a duty cycle,
 * block by block, in the browser. Life consumed, 0 = new (FINDING-019): the
 * solver's `health` field counts up, it is not remaining health.
 */
@Component({
  selector: 'app-durability',
  imports: [RouterLink, SpecStatus],
  templateUrl: './durability.html',
  styleUrl: '../cycle/cycle.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DurabilityPage implements OnInit {
  protected readonly solver = inject(SolverService);
  private readonly edits = inject(SpecEdits);
  private readonly kept = inject(LastResults);
  protected readonly fmt0 = fmt0;
  protected readonly fmt1 = fmt1;
  protected readonly fmt2 = fmt2;
  protected readonly fmt3 = fmt3;
  protected readonly fmtDuration = fmtDuration;

  protected readonly engine = signal(this.edits.base());
  /** the recommended default (ADR-015): 1,000 h, about 7.5 minutes in the browser */
  protected readonly hours = signal(1000);
  protected readonly stepH = signal(50);
  protected readonly rows = signal<Row[]>([]);
  protected readonly solvedWith = signal<string | undefined>(undefined);
  protected readonly running = signal(false);
  protected readonly error = signal<string | undefined>(undefined);
  protected readonly etaS = signal<number | undefined>(undefined);
  private stop = false;

  protected readonly presets = computed(() => {
    const info = this.solver.info();
    return info ? info.presets.map(k => ({ key: k, ...info.preset_info[k]! })) : [];
  });
  protected readonly spec = computed<PresetInfo | undefined>(() => this.solver.info()?.preset_info[this.engine()]);
  /** before starting: the measured cost (2.8 min per 1,000 h natively, about 2.65x in the browser) */
  protected readonly estimate = computed(() => estimateS(this.hours()));
  protected readonly last = computed(() => this.rows().at(-1));

  protected readonly plots = computed<PlotModel[]>(() => {
    const rows = this.rows();
    if (!rows.length) return [];
    const x = [0, ...rows.map(r => r['hours']!)];
    const s = (k: string, at0: number) => [at0, ...rows.map(r => r[k]!)];
    const changes = rows.filter((r, i) => i > 0 && r['oil_changes']! > rows[i - 1]!['oil_changes']!)
      .map(r => ({ x: r['hours']! - r['oil_run_h']!, label: 'oil change', cls: 'inj' }));
    const p = (title: string, yLabel: string, desc: string, y: number[], cls: string, markers = changes) =>
      buildPlot({ title, xLabel: 'Running hours', yLabel, desc, series: [{ x, y, cls, label: title }], markers });
    return [
      p('Life consumed', 'Life consumed (%, 0 = new)', 'How much of the engine\'s life the duty cycle has used: 0 is new (FINDING-019).',
        s('health', 0), 'fired'),
      p('Bore wear', 'Bore wear at TDC (µm)', 'Liner wear at the top ring reversal, where it is worst.', s('bore_wear_um', 0), 'exh'),
      p('Oil soot', 'Soot in the oil (%)', 'Soot loading in the oil; it resets at each oil change.', s('oil_soot', 0), 'exh'),
      p('Rated torque', 'Torque at rated speed (N·m)', 'Full-load torque at rated speed as the engine wears.',
        [rows[0]!['torque']!, ...rows.map(r => r['torque']!)], 'fired', []),
    ];
  });

  ngOnInit(): void {
    this.solver.start().catch(() => { /* surfaced through solver.error() */ });
    const k = this.kept.get<Kept>('durability');
    if (k) { this.engine.set(k.engine); this.hours.set(k.hours); this.stepH.set(k.stepH); this.rows.set(k.rows); this.solvedWith.set(k.solvedWith); }
  }

  protected selectEngine(key: string): void { this.engine.set(key); this.rows.set([]); this.kept.clear('durability'); }
  protected num(v: string, lo: number, hi: number): number | undefined {
    const n = Number(v);
    return v === '' || !Number.isFinite(n) ? undefined : Math.min(hi, Math.max(lo, n));
  }

  protected async run(): Promise<void> {
    if (this.running()) return;
    const engine = this.edits.engineRef(this.engine());
    this.running.set(true);
    this.stop = false;
    this.rows.set([]);
    this.error.set(undefined);
    this.etaS.set(undefined);
    this.solvedWith.set(refKey(engine));
    const t0 = performance.now();
    let id: string | undefined;
    try {
      const s = await this.solver.durabilityStart(engine, this.hours(), this.stepH());
      id = s.id;
      for (;;) {
        if (this.stop) { await this.solver.durabilityStop(id); break; }
        const r = await this.solver.durabilityNext(id, 1);
        this.rows.update(rows => [...rows, ...r.rows]);
        const done = this.rows().at(-1)?.['hours'] ?? 0;
        if (done > 0) this.etaS.set(((performance.now() - t0) / 1000) / done * Math.max(0, this.hours() - done));
        if (r.done) break;
      }
      this.kept.set<Kept>('durability', { engine: this.engine(), hours: this.hours(), stepH: this.stepH(), rows: this.rows(), solvedWith: refKey(engine) });
    } catch (e) {
      this.error.set(describe(e));
    } finally {
      this.etaS.set(undefined);
      this.running.set(false);
    }
  }

  protected halt(): void { this.stop = true; }
}
