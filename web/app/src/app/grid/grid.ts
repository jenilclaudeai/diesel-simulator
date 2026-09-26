import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { Grid, GridProgress, PresetInfo } from '@dieselsim/solver';
import { describe, SolverService } from '../solver/solver.service';

/** The grid the real-time loop reads: play.py's default, 8 speeds x 6 loads. */
export const N_RPM = 8;
export const N_LOAD = 6;

/** Evenly spaced from idle to maximum speed, and from no load to full load. */
export function gridAxes(s: Pick<PresetInfo, 'idle_rpm' | 'max_rpm'>): { rpms: number[]; loads: number[] } {
  const lin = (a: number, b: number, n: number) => Array.from({ length: n }, (_, i) => a + (b - a) * i / (n - 1));
  return { rpms: lin(s.idle_rpm, s.max_rpm, N_RPM), loads: lin(0, 1, N_LOAD) };
}

const fmt0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });

@Component({
  selector: 'app-grid',
  imports: [RouterLink],
  templateUrl: './grid.html',
  styleUrl: '../dyno/dyno.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GridPage implements OnInit {
  protected readonly solver = inject(SolverService);
  protected readonly fmt0 = fmt0;
  protected readonly fmt1 = fmt1;
  protected readonly fmt2 = fmt2;
  protected readonly N_RPM = N_RPM;
  protected readonly N_LOAD = N_LOAD;

  protected readonly engine = signal('crdi15');
  protected readonly grid = signal<Grid | undefined>(undefined);
  protected readonly running = signal(false);
  protected readonly progress = signal<GridProgress | undefined>(undefined);
  protected readonly runError = signal<string | undefined>(undefined);
  protected readonly elapsedS = signal<number | undefined>(undefined);

  protected readonly presets = computed(() => {
    const info = this.solver.info();
    return info ? info.presets.map(k => ({ key: k, ...info.preset_info[k]! })) : [];
  });
  protected readonly spec = computed<PresetInfo | undefined>(() => this.solver.info()?.preset_info[this.engine()]);
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

  ngOnInit(): void {
    this.solver.start().catch(() => { /* surfaced through solver.error() */ });
  }

  protected selectEngine(key: string): void {
    this.engine.set(key);
    this.grid.set(undefined);
    this.elapsedS.set(undefined);
    this.runError.set(undefined);
  }

  protected async build(): Promise<void> {
    const axes = this.axes();
    if (this.running() || !axes) return;
    this.running.set(true);
    this.grid.set(undefined);
    this.runError.set(undefined);
    this.elapsedS.set(undefined);
    const t0 = performance.now();
    try {
      const g = await this.solver.buildGrid(
        { engine: { preset: this.engine() }, rpms: axes.rpms, loads: axes.loads },
        { onProgress: p => this.progress.set(p) });
      this.grid.set(g);
      this.elapsedS.set((performance.now() - t0) / 1000);
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
