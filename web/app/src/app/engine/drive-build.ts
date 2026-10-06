import { ChangeDetectionStrategy, Component, computed, effect, inject, input, output, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { EngineRef, LiveBuildProgress } from '@dieselsim/solver';
import { poolSize } from '../solver/pool-size';
import { describe, SolverService } from '../solver/solver.service';
import { refKey } from '../spec/spec-status';
import { VEHICLE_NAMES } from './custom-engine';
import { engineLibrary, MY, type MyEngine } from './my-engines';

/**
 * "Drive it": an engine's drivable grid, built in this browser by a pool of
 * solver workers (ADR-014 step 3) and kept in "Your engines" for /drive and
 * /enjoy. Shared by the Dyno page (a custom engine) and the spec editor (an
 * edited engine, Phase 6). A new engine forgets the last one built.
 */
@Component({
  selector: 'app-drive-build',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: `
    .drivable { margin: 0 0 1.6rem; max-width: 56rem; }
    h2 { margin: 0 0 .4rem; font-size: 1.35rem; }
    .note { margin: 0.4rem 0 0.8rem; max-width: 40em; color: var(--slate-muted); }
    .controls { display: flex; flex-wrap: wrap; align-items: end; gap: 1rem 1.25rem; }
    button { font: inherit; padding: .4rem .9rem; border-radius: 4px; cursor: pointer; color: var(--slate);
      background: var(--grey-deep); border: 1px solid var(--slate-faint); }
    button:disabled { cursor: not-allowed; opacity: .55; }
    .status { min-height: 1.6em; margin: 1rem 0 0.6rem; color: var(--slate-muted); }
    .err { color: var(--slate); font-weight: 600; }
    .build-status progress { width: 12rem; vertical-align: middle; margin-right: .6rem; accent-color: var(--amber); }
    .built a { color: var(--slate); font-weight: 600; }
  `,
  template: `
    <section class="drivable" aria-labelledby="drivable-h">
      <h2 id="drivable-h">Drive it</h2>
      <p class="note">Driving needs a converged grid, warm and cold: 104 pieces, built here by {{ workers }}
        {{ workers === 1 ? 'worker' : 'workers' }}. Allow about half an hour on a 4-core laptop. It keeps what it
        finishes, so you can stop or close the tab and carry on later. On a phone, build it on a computer and import the file.</p>
      <div class="controls">
        <button type="button" class="build-drivable" (click)="build()" [disabled]="building() || disabled()">
          {{ building() ? 'Building' : 'Build drivable grid' }}</button>
        @if (building()) { <button type="button" class="cancel-build" (click)="cancel()">Stop</button> }
      </div>
      @if (progress(); as p) {
        <p class="status build-status" role="status" aria-live="polite">
          <progress [value]="p.done" [max]="p.total"></progress>
          {{ p.phase === 'assemble' ? 'Writing the grid file.' : p.phase === 'rows' ? 'Calibrating fuel, row by row.' : 'Solving cells, warm and cold.' }}
          {{ p.done }} of {{ p.total }}{{ p.resumed ? ' (' + p.resumed + ' from before)' : '' }}{{ p.etaS !== undefined ? ', about ' + fmtMin(p.etaS) + ' left' : '' }}.
        </p>
      }
      @if (error()) { <p class="err build-err">{{ error() }}</p> }
      @if (saved(); as s) {
        <p class="status built">Saved to your engines: {{ s.name }}, in the {{ vehicleName(s.vehicle) }}.
          <a [routerLink]="['/enjoy']" [queryParams]="{ engine: MY + s.key }">Drive it</a> ·
          <a [routerLink]="['/drive']" [queryParams]="{ engine: MY + s.key }">on the engineering page</a> ·
          <button type="button" class="download-grid" (click)="download()">Download grid file</button></p>
      }
    </section>
  `,
})
export class DriveBuild {
  private readonly solver = inject(SolverService);
  /** the engine to build, as the solver takes it */
  readonly engine = input.required<EngineRef>();
  /** what "Your engines" keeps for it (savedAt is stamped on save) */
  readonly record = input.required<Omit<MyEngine, 'savedAt'>>();
  /** recorded in the grid file: a custom engine's JSON, or an edited engine's base and edits */
  readonly extra = input<Record<string, unknown>>({});
  readonly disabled = input(false);
  /** true while a build runs, for the host page to hold its own controls */
  readonly busy = output<boolean>();

  protected readonly workers = poolSize();
  protected readonly building = signal(false);
  protected readonly progress = signal<LiveBuildProgress | undefined>(undefined);
  protected readonly error = signal<string | undefined>(undefined);
  protected readonly saved = signal<MyEngine | undefined>(undefined);
  protected readonly MY = MY;
  private abort: AbortController | undefined;
  private text: string | undefined;
  /** the engine as a string: a host may pass an equal but new object on every check */
  private readonly key = computed(() => refKey(this.engine()));

  constructor() {
    // a different engine: the last one's saved line and error no longer apply
    effect(() => {
      this.key();
      untracked(() => { this.saved.set(undefined); this.error.set(undefined); });
    });
  }

  protected vehicleName(k: string): string { return (VEHICLE_NAMES as Record<string, string>)[k] ?? k; }
  protected fmtMin(s: number): string { return s < 90 ? `${Math.round(s)} s` : `${Math.round(s / 60)} min`; }

  protected async build(): Promise<void> {
    if (this.building()) return;
    const rec = this.record();
    this.building.set(true);
    this.busy.emit(true);
    this.error.set(undefined);
    this.saved.set(undefined);
    this.abort = new AbortController();
    // e2e only: a small grid, so a browser test can build one in minutes
    const m = location.search.includes('e2e') ? /gridsize=(\d+)x(\d+)/.exec(location.search) : null;
    try {
      const text = await this.solver.buildLiveGrid(this.engine(), {
        key: rec.key, ...(m ? { size: [Number(m[1]), Number(m[2])] as [number, number] } : {}),
        extra: { custom: true, vehicle: rec.vehicle, ...this.extra() },
        onProgress: p => this.progress.set(p), signal: this.abort.signal,
      });
      const mine: MyEngine = { ...rec, savedAt: Date.now() };
      await engineLibrary().save(mine, text);
      this.text = text;
      this.saved.set(mine);
    } catch (err) {
      this.error.set(describe(err) === 'Stopped.'
        ? 'Stopped. What it finished is kept: build again to carry on.' : describe(err));
    } finally {
      this.building.set(false);
      this.busy.emit(false);
      this.progress.set(undefined);
    }
  }

  protected cancel(): void { this.abort?.abort(); }

  /** The grid file, for a phone or a friend: /drive and /enjoy import it. */
  protected download(): void {
    const t = this.text, e = this.saved();
    if (!t || !e) return;
    const url = URL.createObjectURL(new Blob([t + '\n'], { type: 'application/json' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `${e.key}.grid.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }
}
