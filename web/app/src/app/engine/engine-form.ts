import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { VEHICLE_KEYS } from '@dieselsim/physics';
import { type CustomEngine, engineJson, engineProblems, parseEngineJson, VEHICLE_NAMES, type VehicleKey } from './custom-engine';

/**
 * A custom engine from brochure numbers (ADR-014). Emits the edited engine on
 * every valid change; reads and writes the engines/*.json format.
 */
@Component({
  selector: 'app-engine-form',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: `
    .engine-form { display: grid; grid-template-columns: repeat(auto-fill, minmax(11rem, 1fr)); gap: 0.9rem 1.2rem;
      border: 1px solid var(--slate-faint); border-radius: 6px; padding: 1rem 1.2rem 1.2rem; margin: 0 0 1.4rem;
      max-width: 56rem; }
    legend { padding: 0 0.4rem; color: var(--slate); }
    .field { display: grid; gap: 0.3rem; font-size: 0.95rem; color: var(--slate-muted); min-width: 0; }
    .field.wide { grid-column: 1 / -1; }
    .field.check { display: flex; align-items: center; gap: 0.5rem; align-self: end; padding-bottom: 0.4rem; }
    input[type=text], input[type=number], select { font: inherit; color: var(--slate); background: var(--grey);
      border: 1px solid var(--slate-faint); border-radius: 4px; padding: 0.4rem 0.5rem; min-width: 0; width: 100%;
      box-sizing: border-box; }
    .pair { display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem; }
    .files { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 0.8rem; align-items: center; }
    .file { display: inline-flex; gap: 0.5rem; align-items: center; color: var(--slate-muted); }
    button { font: inherit; padding: 0.35rem 0.8rem; border: 1px solid var(--slate-faint); border-radius: 4px;
      background: var(--grey-deep); color: var(--slate); cursor: pointer; }
    .err { grid-column: 1 / -1; margin: 0; color: var(--slate); font-weight: 600; }
  `,
  template: `
    <fieldset class="engine-form" [disabled]="disabled()">
      <legend>Your engine</legend>
      <label class="field wide"><span>Name</span>
        <input type="text" [value]="e().name" (change)="set('name', $any($event.target).value)"></label>
      <label class="field"><span>Displacement, L</span>
        <input type="number" step="0.1" min="0.1" [value]="e().displacement" (change)="num('displacement', $event)"></label>
      <label class="field"><span>Cylinders</span>
        <input type="number" step="1" min="1" [value]="e().n_cyl" (change)="num('n_cyl', $event)"></label>
      <label class="field"><span>Rated speed, rpm</span>
        <input type="number" step="50" [value]="e().rated_rpm" (change)="num('rated_rpm', $event)"></label>
      <label class="field"><span>Peak torque, N·m</span>
        <input type="number" step="5" [value]="e().peak_torque" (change)="num('peak_torque', $event)"></label>
      <label class="field"><span>Peak power, kW</span>
        <input type="number" step="1" [value]="e().peak_power" (change)="num('peak_power', $event)"></label>
      <label class="field"><span>Torque plateau, rpm</span>
        <span class="pair">
          <input type="number" step="50" aria-label="Plateau from" [value]="e().plateau?.[0] ?? ''" (change)="plateau(0, $event)">
          <input type="number" step="50" aria-label="Plateau to" [value]="e().plateau?.[1] ?? ''" (change)="plateau(1, $event)">
        </span></label>
      <label class="field check"><input type="checkbox" [checked]="e().turbocharged"
        (change)="set('turbocharged', $any($event.target).checked)"> Turbocharged</label>
      <label class="field"><span>Vehicle</span>
        <select (change)="set('vehicle', $any($event.target).value)">
          @for (v of vehicles; track v) { <option [value]="v" [selected]="v === e().vehicle">{{ vehicleNames[v] }}</option> }
        </select></label>
      <div class="files">
        <label class="file">Import JSON <input type="file" accept=".json,application/json" (change)="importFile($any($event.target))"></label>
        <button type="button" (click)="exportFile()">Export JSON</button>
      </div>
      @if (problems().length) { <p class="err" role="alert">Fix: {{ problems().join('; ') }}.</p> }
      @if (fileError()) { <p class="err" role="alert">{{ fileError() }}</p> }
    </fieldset>`,
})
export class EngineForm {
  readonly engine = input.required<CustomEngine>();
  readonly disabled = input(false);
  readonly changed = output<CustomEngine>();
  protected readonly vehicles = VEHICLE_KEYS;
  protected readonly vehicleNames = VEHICLE_NAMES;
  /** the form's own copy: edits that are not yet valid stay here, unsent */
  private readonly draft = signal<CustomEngine | undefined>(undefined);
  protected readonly e = computed(() => this.draft() ?? this.engine());
  protected readonly problems = computed(() => engineProblems(this.e()));
  protected readonly fileError = signal<string | undefined>(undefined);

  protected set<K extends keyof CustomEngine>(k: K, v: CustomEngine[K]): void {
    const next = { ...this.e(), [k]: v } as CustomEngine;
    this.draft.set(next);
    if (!engineProblems(next).length) this.changed.emit(next);
  }

  protected num(k: 'displacement' | 'n_cyl' | 'rated_rpm' | 'peak_torque' | 'peak_power', ev: Event): void {
    this.set(k, Number((ev.target as HTMLInputElement).value));
  }

  protected plateau(i: 0 | 1, ev: Event): void {
    const raw = (ev.target as HTMLInputElement).value, cur = this.e().plateau ?? [NaN, NaN];
    const next: [number, number] = [cur[0], cur[1]];
    next[i] = raw === '' ? NaN : Number(raw);
    this.set('plateau', Number.isNaN(next[0]) && Number.isNaN(next[1]) ? null : next);
  }

  protected async importFile(input: HTMLInputElement): Promise<void> {
    const f = input.files?.[0];
    input.value = '';
    if (!f) return;
    this.fileError.set(undefined);
    try {
      const e = parseEngineJson(await f.text());
      this.draft.set(e);
      this.changed.emit(e);
    } catch (err) {
      this.fileError.set(`${f.name}: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  protected exportFile(): void {
    const e = this.e();
    const url = URL.createObjectURL(new Blob([engineJson(e)], { type: 'application/json' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `${e.key || 'engine'}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }
}

export type { VehicleKey };
