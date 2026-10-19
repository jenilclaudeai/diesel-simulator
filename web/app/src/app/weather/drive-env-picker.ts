import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { DriveEnv, FUELS, fuelLine, PLACES, SOLD_HERE, weatherLine } from './drive-env';
import { temperature, temperatureUnit, UNIT_SYSTEMS, Units } from '../units/units';

/**
 * The place Drive and Enjoy drive in (Phase 7 step 4). A change stops the engine (the page's own
 * `changed` handler), like a change of engine: the air is set when the engine is made.
 */
@Component({
  selector: 'app-drive-env',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <label class="field"><span>Place</span>
      <select class="drive-env" (change)="pick($any($event.target).value)">
        @for (p of places; track p.key) {
          <option [value]="p.key" [selected]="p.key === env.current()">{{ p.name }}</option>
        }
      </select>
    </label>
    <label class="field"><span>Fuel</span>
      <select class="drive-fuel" (change)="pickFuel($any($event.target).value)">
        <option [value]="SOLD_HERE" [selected]="env.fuel() === SOLD_HERE">Sold here</option>
        @for (f of fuels; track f.key) {
          <option [value]="f.key" [selected]="f.key === env.fuel()">{{ f.name }} (CFPP {{ cfpp(f.cfpp_C) }})</option>
        }
      </select>
    </label>
    <label class="field"><span>Units</span>
      <select class="drive-units" (change)="units.set($any($event.target).value)">
        @for (s of systems; track s.key) {
          <option [value]="s.key" [selected]="s.key === units.system()">{{ s.name }}</option>
        }
      </select>
    </label>
    @if (line(); as l) { <p class="drive-env-note">{{ l }}</p> }
    @if (fuelNote(); as f) { <p class="drive-fuel-note">{{ f }}</p> }
  `,
  styles: [`
    :host { display: block; }
    .field { display: grid; gap: 0.3rem; font-size: 0.95rem; color: var(--slate-muted); }
    select { font: inherit; color: var(--slate); background: var(--grey-deep); border: 1px solid var(--slate-faint);
      border-radius: 4px; padding: 0.45rem 0.6rem; }
    .drive-env-note, .drive-fuel-note { margin: 0.35rem 0 0; max-width: 46em; color: var(--slate-muted); font-size: 0.85rem; }
  `],
})
export class DriveEnvPicker {
  protected readonly env = inject(DriveEnv);
  protected readonly places = PLACES;
  /** the running engine's weather state and its table's measured worst (DashInfo), if one runs */
  readonly state = input<'standard' | 'table' | 'no table' | undefined>(undefined);
  readonly checkPct = input<number | null | undefined>(undefined);
  readonly changed = output<string>();
  /** Phase 8: the driver's units, shared by /drive and /enjoy; a change doesn't stop the engine */
  protected readonly units = inject(Units);
  protected readonly systems = UNIT_SYSTEMS;
  protected readonly line = computed(() => weatherLine(this.env.current(), this.state(), this.checkPct(), this.units.system()));
  protected readonly fuels = FUELS;
  protected readonly SOLD_HERE = SOLD_HERE;
  /** Phase 7 step 6: what the picked fuel does at this place ('' for the place's own) */
  protected readonly fuelNote = computed(() => fuelLine(this.env.current(), this.env.fuel(), this.units.system()));
  protected cfpp(C: number): string {
    const s = this.units.system();
    return `${Math.round(temperature(C, s))} ${temperatureUnit(s)}`;
  }

  protected pickFuel(key: string): void {
    this.env.setFuel(key);
    this.changed.emit(key);
  }

  protected pick(key: string): void {
    this.env.set(key);
    this.changed.emit(key);
  }
}
