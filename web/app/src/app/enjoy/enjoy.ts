import { ChangeDetectionStrategy, Component, computed, HostListener, inject, OnDestroy, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { Transmission } from '@dieselsim/physics';
import { releaseFocus } from '../drive/drive';
import { controlKey, MIC_KEYS, MICS } from '../drive/drive-keys';
import { LiveSession } from '../drive/live-session';
import { DriveEnv } from '../weather/drive-env';
import { DriveEnvPicker } from '../weather/drive-env-picker';
import { applyProject, engineChoice, parseProject } from '../spec/project';
import { SpecEdits } from '../spec/spec-edits';
import { IMPORTED, readGridFile } from '../drive/grid-file';
import { engineLibrary, MY, type MyEngine } from '../engine/my-engines';
import type { GridFile, Pedals } from '../drive/protocol';
import { avgL100, nowL100, rangeKm } from './economy';
import { Gauge, speedScale, tachScale } from './gauge';
import { touchHint } from './hints';
import { derateLit } from './lamps';
import { Pedal } from './pedal';
import { ROSTER } from './roster';

const fmt0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const PHASE = ['', 'shifting: torque phase', 'shifting: inertia phase'];

/**
 * Enjoy mode (Phase 5, ADR-012): pick an engine, tap Start, drive with your
 * thumbs. Pedals at the edges (throttle right, brake left, clutch beside it
 * on the manual), shift paddles in the top corners. Prebuilt grids only: no
 * Pyodide is ever fetched. The keys still work on a desktop.
 */
@Component({
  selector: 'app-enjoy',
  imports: [RouterLink, Pedal, Gauge, DriveEnvPicker],
  templateUrl: './enjoy.html',
  styleUrl: './enjoy.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EnjoyPage implements OnDestroy {
  protected readonly fmt0 = fmt0;
  protected readonly touchHint = touchHint;
  protected readonly presets = ROSTER;
  protected readonly preset = signal(ROSTER[0]!.key);
  /** A custom engine's grid, imported from a file (ADR-014). */
  protected readonly imported = signal<GridFile | undefined>(undefined);
  protected readonly importError = signal<string | undefined>(undefined);
  protected readonly IMPORTED = IMPORTED;
  /** "Your engines": custom engines with a drivable grid, built in this browser (ADR-014) */
  protected readonly mine = signal<MyEngine[]>([]);
  protected readonly MY = MY;
  private readonly s = new LiveSession();
  private readonly env = inject(DriveEnv);
  /** Phase 7 step 7: starts in the kept gearbox (a project's, or /spec's "Drive with"); Enjoy has auto or manual */
  protected readonly manual = signal(this.env.gearbox() === 'manual');
  private readonly edits = inject(SpecEdits);
  protected readonly projectNote = signal<string | undefined>(undefined);
  protected readonly status = this.s.status;
  protected readonly error = this.s.error;
  protected readonly v = this.s.v;
  protected readonly soundOn = this.s.soundOn;
  protected readonly soundError = this.s.soundError;
  protected readonly micName = computed(() => MICS.find(m => m.key === this.s.mic())?.name ?? '');
  protected readonly rpmFrac = computed(() => Math.min(1, (this.v()?.rpm ?? 0) / 5000));
  protected readonly phase = computed(() => PHASE[this.v()?.phase ?? 0] ?? '');
  protected readonly info = this.s.info;
  protected readonly C = (K: number) => K - 273.15;
  /** Dial scales from the engine and vehicle (the worker's info message). */
  protected readonly tach = computed(() => tachScale(this.info()?.max_rpm ?? 5000));
  protected readonly speed = computed(() => speedScale(this.info()?.vmax_kmh ?? 200));
  /** The lamp cluster: every lamp always shown, lit when on, as a real dash is. */
  protected readonly lamps = computed(() => {
    const s = this.v(), i = this.info();
    if (!s || !i) return [];
    const lowFuel = s.out_of_fuel || s.tank_L < 0.12 * i.tank_L;
    return [
      { key: 'stall', text: 'Stalled', on: s.stalled, warn: true },
      { key: 'stopped', text: 'Engine off', on: s.engine_stopped, warn: true },
      { key: 'hot', text: 'Overheat', on: !!s.overheat || s.T_coolant >= i.T_warn, warn: true },
      { key: 'derate', text: 'Derate', on: derateLit(s.T_charge, s.derate_heat), warn: true },
      { key: 'fuel', text: s.out_of_fuel ? 'Out of fuel' : 'Low fuel', on: lowFuel, warn: true },
      { key: 'fan', text: 'Fan', on: s.fan_on, warn: false },
      { key: 'cruise', text: 'Cruise', on: s.cruise, warn: false },
      { key: 'lockup', text: 'Lock-up', on: s.lockup, warn: false },
    ];
  });
  /** A temperature bar's fill, 20 C to the shutdown temperature. */
  protected tempFrac(K: number): number {
    const top = this.info()?.T_shutdown ?? 393.15, lo = 293.15;
    return Math.min(1, Math.max(0, (K - lo) / (top - lo)));
  }
  protected readonly avg = computed(() => { const s = this.v(); return s ? avgL100(s.trip_L, s.trip_km) : null; });
  protected readonly now = computed(() => { const s = this.v(); return s ? nowL100(s.inst_kmpl, s.kmh) : null; });
  protected readonly range = computed(() => { const s = this.v(); return s ? rangeKm(s.tank_L, s.trip_L, s.trip_km) : null; });
  protected fmt1(x: number | null): string { return x === null ? '—' : x.toFixed(1); }
  private pedals: Pedals = { throttle: null, brake: 0, clutch: 0 };
  private readonly held = new Set<string>();

  constructor() {
    void engineLibrary().list().then(list => {
      this.mine.set(list);
      const want = typeof location !== 'undefined' ? new URLSearchParams(location.search).get('engine') : null;
      if (want?.startsWith(MY) && list.some(e => MY + e.key === want)) this.preset.set(want);
    }).catch(() => { /* no saved engines: the roster still works */ });
    if (typeof location !== 'undefined' && location.search.includes('e2e')) {
      (globalThis as Record<string, unknown>)['__enjoy'] = {
        view: () => this.v(), level: () => this.s.levelDb(), soundError: () => this.soundError(),
        info: () => this.s.info(),
      };
    }
  }

  protected trans(): Transmission { return this.manual() ? 'manual' : 'tc'; }

  protected selectPreset(p: string): void { this.preset.set(p); this.s.stop(); }
  protected setManual(m: boolean): void { this.manual.set(m); this.s.stop(); }

  /** One tap starts the engine and the sound (the tap is the audio gesture). */
  protected async start(): Promise<void> {
    releaseFocus();
    this.pedals = { throttle: null, brake: 0, clutch: 0 };
    if (!this.soundOn()) await this.s.soundStart();
    const g = this.imported();
    const p = this.preset();
    if (p === IMPORTED && g) await this.s.loadGrid(g, this.trans(), true, this.env.air(), this.env.cfpp());
    else if (p.startsWith(MY)) {
      const saved = await engineLibrary().grid(p.slice(MY.length)).catch(() => undefined);
      if (saved) await this.s.loadGrid(saved, this.trans(), true, this.env.air(), this.env.cfpp());
      else this.s.error.set('that engine is no longer saved in this browser');
    } else await this.s.load(p, this.trans(), true, this.env.air(), this.env.cfpp());
  }

  /** "Open project" (Phase 7 step 7): as on /drive; a dual clutch drives as Auto here. */
  protected async openProject(input: HTMLInputElement): Promise<void> {
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    this.importError.set(undefined);
    this.projectNote.set(undefined);
    const parsed = parseProject(await file.text());
    if (typeof parsed === 'string') { this.importError.set(`${file.name}: ${parsed}`); return; }
    const note = applyProject(parsed, this.edits, this.env);
    this.stop();
    if (parsed.drive) this.manual.set(parsed.drive.gearbox === 'manual');
    const c = engineChoice(parsed.engine, this.presets.map(p => p.key), this.mine());
    if ('choice' in c) this.preset.set(c.choice);
    else { this.importError.set(`${file.name}: ${c.reason}`); return; }
    const dct = parsed.drive?.gearbox === 'dct' ? ' Enjoy has no dual clutch, so it drives as Auto.' : '';
    this.projectNote.set(`Opened ${file.name}.${note ? ' ' + note : ''}${dct}`);
  }

  /** "Import": a custom engine's grid file (tools/build_live_grids.py --engine). */
  protected async importGrid(input: HTMLInputElement): Promise<void> {
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    this.importError.set(undefined);
    try {
      this.imported.set(await readGridFile(file));
      this.selectPreset(IMPORTED);
    } catch (e) {
      this.importError.set(e instanceof Error ? e.message : String(e));
    }
  }

  protected stop(): void { releaseFocus(); this.s.stop(); }

  protected pedal(which: 'throttle' | 'brake' | 'clutch', value: number): void {
    this.pedals = { ...this.pedals, [which]: value };
    this.s.pedals(this.pedals);
    // a released throttle is sent as 0 once; after that the keys have it back
    if (which === 'throttle' && value === 0) this.pedals = { ...this.pedals, throttle: null };
  }

  /** A paddle or Restart, on pointerdown: acts at once, whatever other fingers are down. */
  protected press(key: string, e: PointerEvent): void {
    e.preventDefault();
    this.tap(key);
  }

  /** A paddle or Restart activated from the keyboard (Enter or Space: a click with detail 0). */
  protected keyTap(key: string, e: MouseEvent): void {
    if (e.detail === 0) this.tap(key);
  }

  /** A tap: the key goes down and up, as a keyboard press does. */
  protected tap(key: string): void {
    releaseFocus();
    this.s.key(key, true);
    this.s.key(key, false);
  }

  protected nextMic(): void {
    releaseFocus();
    const i = MICS.findIndex(m => m.key === this.s.mic());
    this.s.setMic(MICS[(i + 1) % MICS.length]!.key);
  }

  protected toggleSound(): void {
    releaseFocus();
    if (this.soundOn()) this.s.soundStop();
    else void this.s.soundStart();
  }

  @HostListener('document:keydown', ['$event'])
  protected keydown(ev: KeyboardEvent): void { this.key(ev, true); }

  @HostListener('document:keyup', ['$event'])
  protected keyup(ev: KeyboardEvent): void { this.key(ev, false); }

  private key(ev: KeyboardEvent, down: boolean): void {
    if (!this.s.running) return;
    if ((ev.target as HTMLElement | null)?.closest?.('select, input, button')) return;
    const mic = MIC_KEYS[ev.key];
    if (mic) { if (down && !ev.repeat) this.s.setMic(mic); return; }
    const k = controlKey(ev.key);
    if (!k) return;
    ev.preventDefault();
    if (down && ev.repeat) return;
    if (down) this.held.add(k); else this.held.delete(k);
    this.s.key(k, down);
  }

  @HostListener('window:blur')
  protected blur(): void {
    for (const k of this.held) this.s.key(k, false);
    this.held.clear();
  }

  ngOnDestroy(): void { this.s.dispose(); }
}
