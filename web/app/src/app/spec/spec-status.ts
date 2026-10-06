import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { EngineRef } from '@dieselsim/solver';
import { SpecEdits } from './spec-edits';
import { EnvChoice } from '../weather/env-choice';

/** A stable key for an engine reference: overrides sorted, so equal edits give equal keys. */
export function refKey(ref: EngineRef): string {
  const r = ref as Record<string, unknown>;
  const ov = (r['overrides'] ?? {}) as Record<string, unknown>;
  const sorted = Object.fromEntries(Object.keys(ov).sort().map(k => [k, ov[k]]));
  return JSON.stringify({ ...r, overrides: sorted });
}

/** Results are stale when they were solved for a different engine reference than the page would solve now. */
export function isStale(solvedWith: string | undefined, now: EngineRef): boolean {
  return solvedWith !== undefined && solvedWith !== refKey(now);
}

/**
 * The spec edits' status on a page that solves (Phase 6, ADR-015): which
 * edits apply to this engine, and, when the page's results were solved
 * before the latest edits, a banner saying so with a button to solve again
 * (PLAN.md: the grid-invalidation banner).
 */
@Component({
  selector: 'app-spec-status',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (stale()) {
      <div class="stale" role="alert">
        <strong>These results are out of date.</strong> They were solved before your latest spec edits or a change of environment.
        <button type="button" class="rerun" (click)="rerun.emit()" [disabled]="busy()">{{ again() }}</button>
      </div>
    }
    @if (count()) {
      <p class="edits">With your spec edits: {{ count() }} {{ count() === 1 ? 'field' : 'fields' }} changed on this engine.
        <a routerLink="/spec">Edit</a></p>
    }
  `,
  styles: [`
    :host { display: block; }
    .stale { margin: 0.8rem 0 0; padding: 0.6rem 0.8rem; border-left: 4px solid var(--amber-ink);
      background: rgba(211, 148, 34, 0.14); max-width: 46em; }
    .rerun { margin-left: 0.6rem; font: inherit; font-weight: 700; color: var(--slate); background: var(--amber);
      border: 0; border-radius: 4px; padding: 0.3rem 0.8rem; cursor: pointer; }
    .rerun:disabled { opacity: 0.55; cursor: not-allowed; }
    .edits { margin: 0.6rem 0 0; color: var(--slate-muted); }
  `],
})
export class SpecStatus {
  private readonly edits = inject(SpecEdits);
  private readonly env = inject(EnvChoice);
  /** the engine the page has selected (a preset key) */
  readonly engine = input.required<string>();
  /** refKey() of what the page's current results were solved with, or undefined if it has none */
  readonly solvedWith = input<string | undefined>(undefined);
  readonly busy = input(false);
  readonly again = input('Solve again');
  readonly rerun = output<void>();
  protected readonly count = computed(() => (this.engine() === this.edits.base() ? this.edits.count() : 0));
  protected readonly stale = computed(() => isStale(this.solvedWith(), this.env.solveRef(this.edits.engineRef(this.engine()))));
}
