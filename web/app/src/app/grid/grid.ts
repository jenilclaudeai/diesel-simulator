import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { EngineInfo, EngineRef, Grid, GridProgress, PresetInfo } from '@dieselsim/solver';
import { type CustomEngine, EXAMPLE_ENGINE, headline } from '../engine/custom-engine';
import { EngineForm } from '../engine/engine-form';
import { describe, SolverService } from '../solver/solver.service';
import { SpecEdits } from '../spec/spec-edits';
import { EnvChoice } from '../weather/env-choice';
import { EnvPicker } from '../weather/env-picker';
import { refKey, SpecStatus } from '../spec/spec-status';
import { LastResults } from '../spec/last-results';
import { gridAxes, N_LOAD, N_RPM } from './grid-axes';


const fmt0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });

@Component({
  selector: 'app-grid',
  imports: [RouterLink, EngineForm, SpecStatus, EnvPicker],
  templateUrl: './grid.html',
  styleUrl: '../dyno/dyno.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GridPage implements OnInit {
  protected readonly solver = inject(SolverService);
  private readonly edits = inject(SpecEdits);
  private readonly env = inject(EnvChoice);
  /** refKey() of the engine the current grid was built for (the stale banner compares it) */
  protected readonly solvedWith = signal<string | undefined>(undefined);
  protected readonly fmt0 = fmt0;
  protected readonly fmt1 = fmt1;
  protected readonly fmt2 = fmt2;
  protected readonly N_RPM = N_RPM;
  protected readonly N_LOAD = N_LOAD;

  protected readonly engine = signal(inject(SpecEdits).base());
  /** ADR-014: the "Custom engine" choice, its numbers, and the builder's description of it */
  protected readonly CUSTOM = '__custom';
  protected readonly custom = signal<CustomEngine>(EXAMPLE_ENGINE);
  protected readonly customInfo = signal<EngineInfo | undefined>(undefined);
  protected readonly isCustom = computed(() => this.engine() === this.CUSTOM);
  protected readonly grid = signal<Grid | undefined>(undefined);
  protected readonly running = signal(false);
  protected readonly progress = signal<GridProgress | undefined>(undefined);
  protected readonly runError = signal<string | undefined>(undefined);
  protected readonly elapsedS = signal<number | undefined>(undefined);

  protected readonly presets = computed(() => {
    const info = this.solver.info();
    return info ? info.presets.map(k => ({ key: k, ...info.preset_info[k]! })) : [];
  });
  protected readonly spec = computed<PresetInfo | undefined>(() =>
    this.isCustom() ? this.customInfo() : this.solver.info()?.preset_info[this.engine()]);
  protected readonly axes = computed(() => { const s = this.spec(); return s ? gridAxes(s) : undefined; });

  /** rows = loads (full load on top), columns = speeds */
  protected readonly table = computed(() => {
    const g = this.grid();
    if (!g) return undefined;
    const at = new Map(g.cells.map(c => [`${c.i},${c.j}`, c]));
    const rows = g.loads.map((load, j) => ({
      load,
      cells: g.rpms.map((rpm, i) => {
        const c = at.get(`${i},${j}`);
        return { rpm, torque: c?.perf['torque'] ?? NaN, fuel: c?.perf['fuel_mg'] ?? NaN, perf: c?.perf ?? {} };
      }),
    })).reverse();
    return { rpms: g.rpms, rows };
  });

  private readonly kept = inject(LastResults);

  ngOnInit(): void {
    this.solver.start().catch(() => { /* surfaced through solver.error() */ });
    // back from the spec editor: the last grid, flagged out of date if the edits changed since
    const k = this.kept.get<{ engine: string; grid: Grid; solvedWith: string; elapsedS: number }>('grid');
    if (k) { this.engine.set(k.engine); this.grid.set(k.grid); this.solvedWith.set(k.solvedWith); this.elapsedS.set(k.elapsedS); }
  }

  protected selectEngine(key: string): void {
    this.engine.set(key);
    this.grid.set(undefined);
    this.elapsedS.set(undefined);
    this.runError.set(undefined);
    if (key === this.CUSTOM) void this.describeCustom();
  }

  protected customChanged(e: CustomEngine): void {
    this.custom.set(e);
    this.grid.set(undefined);
    this.elapsedS.set(undefined);
    void this.describeCustom();
  }

  private async describeCustom(): Promise<void> {
    this.customInfo.set(undefined);
    this.runError.set(undefined);
    try {
      this.customInfo.set(await this.solver.describeEngine({ headline: headline(this.custom()) }));
    } catch (e) {
      this.runError.set(describe(e));
    }
  }

  private engineRef(): EngineRef {
    return this.env.solveRef(this.isCustom() ? { headline: headline(this.custom()) } : this.edits.engineRef(this.engine()));
  }

  protected async build(): Promise<void> {
    const axes = this.axes();
    if (this.running() || !axes) return;
    this.running.set(true);
    this.grid.set(undefined);
    this.runError.set(undefined);
    this.elapsedS.set(undefined);
    this.solvedWith.set(this.isCustom() ? undefined : refKey(this.engineRef()));
    const t0 = performance.now();
    try {
      const g = await this.solver.buildGrid(
        { engine: this.engineRef(), rpms: axes.rpms, loads: axes.loads },
        { onProgress: p => this.progress.set(p) });
      this.grid.set(g);
      this.elapsedS.set((performance.now() - t0) / 1000);
      if (!this.isCustom()) this.kept.set('grid', { engine: this.engine(), grid: g, solvedWith: this.solvedWith()!, elapsedS: this.elapsedS()! });
    } catch (e) {
      this.runError.set(describe(e));
    } finally {
      this.progress.set(undefined);
      this.running.set(false);
    }
  }

  /** every perf value at full precision, for checking against native Python */
  protected json(perf: Record<string, number>): string {
    return JSON.stringify(perf);
  }
}
