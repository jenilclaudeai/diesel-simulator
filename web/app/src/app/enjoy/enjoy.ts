import { ChangeDetectionStrategy, Component, computed, HostListener, OnDestroy, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { Transmission } from '@dieselsim/physics';
import { releaseFocus } from '../drive/drive';
import { controlKey, DRIVE_PRESETS, MIC_KEYS, MICS } from '../drive/drive-keys';
import { LiveSession } from '../drive/live-session';
import type { Pedals } from '../drive/protocol';
import { Pedal } from './pedal';

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
  imports: [RouterLink, Pedal],
  templateUrl: './enjoy.html',
  styleUrl: './enjoy.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EnjoyPage implements OnDestroy {
  protected readonly fmt0 = fmt0;
  protected readonly presets = DRIVE_PRESETS;
  protected readonly preset = signal('crdi15');
  protected readonly manual = signal(false);
  private readonly s = new LiveSession();
  protected readonly status = this.s.status;
  protected readonly error = this.s.error;
  protected readonly v = this.s.v;
  protected readonly soundOn = this.s.soundOn;
  protected readonly soundError = this.s.soundError;
  protected readonly micName = computed(() => MICS.find(m => m.key === this.s.mic())?.name ?? '');
  protected readonly rpmFrac = computed(() => Math.min(1, (this.v()?.rpm ?? 0) / 5000));
  protected readonly phase = computed(() => PHASE[this.v()?.phase ?? 0] ?? '');
  private pedals: Pedals = { throttle: null, brake: 0, clutch: 0 };
  private readonly held = new Set<string>();

  constructor() {
    if (typeof location !== 'undefined' && location.search.includes('e2e')) {
      (globalThis as Record<string, unknown>)['__enjoy'] = {
        view: () => this.v(), level: () => this.s.levelDb(), soundError: () => this.soundError(),
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
    await this.s.load(this.preset(), this.trans(), true);
  }

  protected stop(): void { releaseFocus(); this.s.stop(); }

  protected pedal(which: 'throttle' | 'brake' | 'clutch', value: number): void {
    this.pedals = { ...this.pedals, [which]: value };
    this.s.pedals(this.pedals);
    // a released throttle is sent as 0 once; after that the keys have it back
    if (which === 'throttle' && value === 0) this.pedals = { ...this.pedals, throttle: null };
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
