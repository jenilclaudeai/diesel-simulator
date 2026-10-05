import { ChangeDetectionStrategy, Component, computed, effect, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { PointResult, PresetInfo } from '@dieselsim/solver';
import { buildPlot, type PlotModel } from '../cycle/plots';
import { describe, SolverService } from '../solver/solver.service';
import { LastResults } from '../spec/last-results';
import { SpecEdits } from '../spec/spec-edits';
import { FIELDS, GROUPS, label, readOnly, unitFor } from '../spec/spec-meta';
import { refKey, SpecStatus } from '../spec/spec-status';
import { defaultRange, sweepValues } from './sweep-plan';

const fmt0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmtV = (v: number) => String(Number(v.toPrecision(6)));

interface Row { value: number; r: PointResult }
interface Kept { engine: string; field: string; from: number; to: number; steps: number; rpm: number; load: number; rows: Row[]; solvedWith: string }

/**
 * The sweep page (Phase 6, ADR-015): one spec field over a range, the rest of
 * the engine as edited, one operating point per value. No new solver call:
 * each value is a solvePoint with that field in its overrides.
 */
@Component({
  selector: 'app-sweep',
  imports: [RouterLink, SpecStatus],
  templateUrl: './sweep.html',
  styleUrl: '../cycle/cycle.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SweepPage implements OnInit {
  protected readonly solver = inject(SolverService);
  private readonly edits = inject(SpecEdits);
  private readonly kept = inject(LastResults);
  protected readonly fmt0 = fmt0;
  protected readonly fmt1 = fmt1;
  protected readonly fmtV = fmtV;
  protected readonly label = label;

  protected readonly engine = signal(this.edits.base());
  protected readonly field = signal('geom.compression_ratio');
  protected readonly from = signal<number | undefined>(undefined);
  protected readonly to = signal<number | undefined>(undefined);
  protected readonly steps = signal(7);
  protected readonly rpmIn = signal<number | undefined>(undefined);
  protected readonly load = signal(1.0);
  protected readonly rows = signal<Row[]>([]);
  protected readonly solvedWith = signal<string | undefined>(undefined);
  protected readonly running = signal(false);
  protected readonly progress = signal<{ n: number; of: number; value: number } | undefined>(undefined);
  protected readonly error = signal<string | undefined>(undefined);
  private stop = false;
  /** the engine's values with the edits applied: the swept field's current value */
  private readonly values = signal<Record<string, unknown> | undefined>(undefined);

  protected readonly presets = computed(() => {
    const info = this.solver.info();
    return info ? info.presets.map(k => ({ key: k, ...info.preset_info[k]! })) : [];
  });
  protected readonly spec = computed<PresetInfo | undefined>(() => this.solver.info()?.preset_info[this.engine()]);
  protected readonly rpm = computed(() => {
    const s = this.spec();
    return this.rpmIn() ?? (s ? Math.round((s.idle_rpm + 0.6 * (s.rated_rpm - s.idle_rpm)) / 50) * 50 : 2000);
  });
  /** the numeric fields that can be swept, by subsystem */
  protected readonly fieldGroups = GROUPS.map(g => ({
    title: g.title,
    fields: FIELDS.filter(f => g.classes.includes(f.cls) && !readOnly(f) && f.type !== 'bool').map(f => ({ path: f.path, label: label(f.path) })),
  }));
  private readonly schemaRow = computed(() => FIELDS.find(f => f.path === this.field())!);
  protected readonly unit = computed(() => unitFor(this.schemaRow()));
  protected readonly current = computed(() => {
    const v = this.values()?.[this.field()];
    return typeof v === 'number' ? v : undefined;
  });
  protected readonly range = computed(() => {
    const c = this.current(), d = c === undefined ? undefined : defaultRange(c, this.schemaRow().type === 'int');
    return { from: this.from() ?? d?.from, to: this.to() ?? d?.to };
  });
  protected readonly plan = computed(() => {
    const r = this.range();
    return r.from === undefined || r.to === undefined ? [] : sweepValues(r.from, r.to, this.steps(), this.schemaRow().type === 'int');
  });

  protected readonly plots = computed<PlotModel[]>(() => {
    const rows = this.rows();
    if (rows.length < 2) return [];
    const x = rows.map(r => r.value), xl = `${label(this.field())}${this.unit() ? ` (${this.unit()})` : ''}`;
    const marker = this.current() !== undefined ? [{ x: this.current()!, label: 'this engine', cls: 'pmax' }] : [];
    return [
      buildPlot({ title: 'Torque', xLabel: xl, yLabel: 'Brake torque (N·m)', desc: `Brake torque as ${xl} changes.`,
        series: [{ x, y: rows.map(r => r.r.torque), cls: 'fired', label: 'torque' }], markers: marker }),
      buildPlot({ title: 'Fuel consumption (steady state)', xLabel: xl, yLabel: 'BSFC (g/kWh)',
        desc: `Brake-specific fuel consumption, steady state (FINDING-009), as ${xl} changes.`,
        series: [{ x, y: rows.map(r => r.r.bsfc), cls: 'exh', label: 'BSFC' }], markers: marker }),
    ];
  });

  constructor() {
    effect(() => {
      const ref = this.edits.engineRef(this.engine());
      if (this.solver.status() !== 'ready') return;
      this.values.set(undefined);
      this.solver.describeSpec(ref).then(d => this.values.set(Object.fromEntries(d.fields.map(f => [f.path, f.value]))))
        .catch(e => this.error.set(describe(e)));
    });
  }

  ngOnInit(): void {
    this.solver.start().catch(() => { /* surfaced through solver.error() */ });
    const k = this.kept.get<Kept>('sweep');
    if (k) {
      this.engine.set(k.engine); this.field.set(k.field); this.from.set(k.from); this.to.set(k.to); this.steps.set(k.steps);
      this.rpmIn.set(k.rpm); this.load.set(k.load); this.rows.set(k.rows); this.solvedWith.set(k.solvedWith);
    }
  }

  protected selectEngine(key: string): void { this.engine.set(key); this.rpmIn.set(undefined); this.clearRange(); this.rows.set([]); }
  protected selectField(path: string): void { this.field.set(path); this.clearRange(); this.rows.set([]); }
  private clearRange(): void { this.from.set(undefined); this.to.set(undefined); }
  protected num(v: string): number | undefined { const n = Number(v); return v === '' || !Number.isFinite(n) ? undefined : n; }

  protected async run(): Promise<void> {
    const values = this.plan();
    if (this.running() || values.length < 2) return;
    const base = this.edits.engineRef(this.engine()) as { preset: string; overrides?: Record<string, number | boolean> };
    this.running.set(true);
    this.stop = false;
    this.rows.set([]);
    this.error.set(undefined);
    this.solvedWith.set(refKey(base));
    try {
      for (const [i, value] of values.entries()) {
        if (this.stop) break;
        this.progress.set({ n: i + 1, of: values.length, value });
        const r = await this.solver.solvePoint({ engine: { preset: base.preset, overrides: { ...(base.overrides ?? {}), [this.field()]: value } },
          rpm: this.rpm(), load: this.load() });
        this.rows.update(rs => [...rs, { value, r }]);
      }
      this.kept.set<Kept>('sweep', { engine: this.engine(), field: this.field(), from: values[0]!, to: values.at(-1)!, steps: this.steps(),
        rpm: this.rpm(), load: this.load(), rows: this.rows(), solvedWith: refKey(base) });
    } catch (e) {
      this.error.set(`At ${label(this.field())} = ${fmtV(this.progress()?.value ?? NaN)}: ${describe(e)}`);
    } finally {
      this.progress.set(undefined);
      this.running.set(false);
    }
  }

  protected halt(): void { this.stop = true; }
}
