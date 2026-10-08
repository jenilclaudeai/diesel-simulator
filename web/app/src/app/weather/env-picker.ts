import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { altitudeNote } from './altitude';
import { humidityNote } from './humidity';
import { EnvChoice, STANDARD } from './env-choice';

const fmt1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });

/**
 * The environment a solving page solves in (Phase 7, ADR-016): five real places, each the air and
 * the fuel sold there, with its numbers shown. Changing it marks the page's results out of date
 * (app-spec-status), like a spec edit.
 */
@Component({
  selector: 'app-env-picker',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <label class="field"><span>Environment</span>
      <select class="env" [disabled]="!env.presets().length" (change)="env.set($any($event.target).value)">
        @for (p of env.presets(); track p.key) {
          <option [value]="p.key" [selected]="p.key === env.current()?.key">{{ p.name }}</option>
        }
      </select>
    </label>
    @if (line(); as l) {
      <p class="env-note">{{ l }}
        @if (caveat()) {
          <br />On this page's fast solves, a part-load difference between two airs can be the solver's
          convergence gap (FINDING-013), not the weather. Compare at full load, where the two agree closely.
        }
        @if (thin(); as t) {
          <br /><span class="env-thin">{{ t }}</span>
        }
        @if (humid(); as h) {
          <br /><span class="env-humid">{{ h }}</span>
        }
      </p>
    }
  `,
  styles: [`
    :host { display: block; margin: 0.8rem 0 0; }
    .field { display: grid; gap: 0.3rem; font-size: 0.95rem; color: var(--slate-muted); max-width: 15rem; }
    select { font: inherit; color: var(--slate); background: var(--grey-deep); border: 1px solid var(--slate-faint);
      border-radius: 4px; padding: 0.55rem 0.7rem; min-width: 15rem; }
    .env-note { margin: 0.4rem 0 0; max-width: 46em; color: var(--slate-muted); font-size: 0.9rem; }
  `],
})
export class EnvPicker {
  protected readonly env = inject(EnvChoice);
  /** the page solves at part load, where FINDING-013's fast-solve gap can exceed a weather difference */
  readonly partLoad = input(false);
  protected readonly line = computed(() => {
    const c = this.env.current();
    if (!c) return '';
    const fuel = c.cetane != null ? `${c.fuel}, cetane ${fmt0.format(c.cetane)}` : c.fuel;
    return `${c.place}: ${fmt1.format(c.p_amb / 1000)} kPa, ${fmt1.format(c.T_C)} °C, ${fmt0.format(c.rh_pct)}% humidity; ${fuel}.`;
  });
  protected readonly caveat = computed(() => this.partLoad() && this.env.current()?.key !== STANDARD);
  /** FINDING-026: what the model does in thin air, on every solving page (full load too: the turbo's ceiling) */
  protected readonly thin = computed(() => altitudeNote(this.env.current()?.p_amb));
  /** ADR-016 item 3: off the reference humidity, the page says NOx is corrected, and only NOx */
  protected readonly humid = computed(() => humidityNote(this.env.current()?.overrides));
}
