import { ChangeDetectionStrategy, Component, computed, HostListener, inject, OnDestroy, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { Transmission } from '@dieselsim/physics';
import { controlKey, DRIVE_PRESETS, KEY_HELP, MIC_KEYS, MICS } from './drive-keys';
import { IMPORTED, readGridFile } from './grid-file';
import { engineLibrary, MY, type MyEngine } from '../engine/my-engines';
import { LiveSession } from './live-session';
import { DriveEnv } from '../weather/drive-env';
import { DriveEnvPicker } from '../weather/drive-env-picker';
import type { DriveScript, GridFile } from './protocol';

const fmt0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });

/** A clicked button keeps focus, and then space -- full throttle -- would press it again
 *  (restarting the engine, or turning the sound off). Give the keys back to the drive. */
export function releaseFocus(): void {
  (document.activeElement as HTMLElement | null)?.blur?.();
}

/**
 * The real-time drive (Phase 3), the engineering page. Prebuilt converged
 * grids -- no Python in the browser -- driven by the TypeScript live loop in
 * a 60 Hz worker; with sound on (Phase 4), an AudioWorklet synthesises the
 * engine. The worker and the sound live in LiveSession, shared with /enjoy.
 */
@Component({
  selector: 'app-drive',
  imports: [RouterLink, DriveEnvPicker],
  templateUrl: './drive.html',
  styleUrl: '../dyno/dyno.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DrivePage implements OnDestroy {
  protected readonly fmt0 = fmt0;
  protected readonly fmt1 = fmt1;
  protected readonly fmt2 = fmt2;
  protected readonly presets = DRIVE_PRESETS;
  protected readonly keyHelp = KEY_HELP;
  protected readonly mics = MICS;
  protected readonly preset = signal('crdi15');
  /** A custom engine's grid, imported from a file (ADR-014). */
  protected readonly imported = signal<GridFile | undefined>(undefined);
  protected readonly importError = signal<string | undefined>(undefined);
  protected readonly IMPORTED = IMPORTED;
  /** "Your engines": custom engines with a drivable grid, built in this browser (ADR-014) */
  protected readonly mine = signal<MyEngine[]>([]);
  protected readonly MY = MY;
  protected readonly trans = signal<Transmission>('tc');
  private readonly s = new LiveSession();
  private readonly env = inject(DriveEnv);
  protected readonly dashInfo = this.s.info;
  protected readonly status = this.s.status;
  protected readonly error = this.s.error;
  protected readonly gridStatus = this.s.gridStatus;
  protected readonly v = this.s.v;
  protected readonly soundOn = this.s.soundOn;
  protected readonly mic = this.s.mic;
  protected readonly volume = this.s.volume;
  protected readonly levelDb = this.s.levelDb;
  protected readonly soundError = this.s.soundError;
  protected readonly recording = this.s.recording;
  protected readonly rpmFrac = computed(() => Math.min(1, (this.v()?.rpm ?? 0) / 5000));
  private readonly held = new Set<string>();

  constructor() {
    void engineLibrary().list().then(list => {
      this.mine.set(list);
      const want = typeof location !== 'undefined' ? new URLSearchParams(location.search).get('engine') : null;
      if (want?.startsWith(MY) && list.some(e => MY + e.key === want)) this.preset.set(want);
    }).catch(() => { /* no saved engines: the roster still works */ });
    // e2e hook (only with ?e2e): run a frame-exact script through the real worker
    if (typeof location !== 'undefined' && location.search.includes('e2e')) {
      (globalThis as Record<string, unknown>)['__drive'] = {
        load: (preset: string, trans: Transmission) => this.s.load(preset, trans, false, this.env.air(), this.env.cfpp()),
        info: () => this.s.info(),
        script: (script: DriveScript, init: Record<string, number> = {}) => this.s.runScript(script, init),
        key: (key: string, down: boolean) => this.s.key(key, down),
        run: () => this.s.run(),
        sound: {
          on: () => this.s.soundStart(),
          capture: (seconds: number) => this.s.capture(seconds),
          level: () => this.levelDb(),
          error: () => this.soundError(),
          mic: (m: string) => this.s.setMic(m),
        },
      };
    }
  }

  protected selectPreset(p: string): void { this.preset.set(p); this.stop(); }
  protected selectTrans(t: string): void { this.trans.set(t as Transmission); this.stop(); }

  protected async start(): Promise<void> {
    releaseFocus();
    const g = this.imported();
    const p = this.preset();
    if (p === IMPORTED && g) await this.s.loadGrid(g, this.trans(), true, this.env.air(), this.env.cfpp());
    else if (p.startsWith(MY)) {
      const saved = await engineLibrary().grid(p.slice(MY.length)).catch(() => undefined);
      if (saved) await this.s.loadGrid(saved, this.trans(), true, this.env.air(), this.env.cfpp());
      else this.s.error.set('that engine is no longer saved in this browser');
    } else await this.s.load(p, this.trans(), true, this.env.air(), this.env.cfpp());
  }

  /** "Import grid": a custom engine's grid file (tools/build_live_grids.py --engine). */
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

  protected stop(): void { this.s.stop(); }

  @HostListener('document:keydown', ['$event'])
  protected keydown(ev: KeyboardEvent): void { this.key(ev, true); }

  @HostListener('document:keyup', ['$event'])
  protected keyup(ev: KeyboardEvent): void { this.key(ev, false); }

  private key(ev: KeyboardEvent, down: boolean): void {
    if (!this.s.running) return;
    if ((ev.target as HTMLElement | null)?.closest?.('select, input, button')) return;
    const mic = MIC_KEYS[ev.key];
    if (mic) {
      if (down && !ev.repeat) this.setMic(mic);
      return;
    }
    const k = controlKey(ev.key);
    if (!k) return;
    ev.preventDefault();
    // OS auto-repeat is ignored: taps act once, and held keys (w s b z) are
    // repeated every frame by the worker itself
    if (down && ev.repeat) return;
    if (down) this.held.add(k);
    else this.held.delete(k);
    this.s.key(k, down);
  }

  /** A key held while the window loses focus never sends its keyup: release everything. */
  @HostListener('window:blur')
  protected blur(): void {
    for (const k of this.held) this.s.key(k, false);
    this.held.clear();
  }

  // ---- sound (Phase 4) ------------------------------------------------
  protected async toggleSound(): Promise<void> {
    releaseFocus();
    if (this.soundOn()) this.s.soundStop();
    else await this.s.soundStart();
  }

  protected setMic(m: string): void { this.s.setMic(m); }

  protected setVolume(v: number): void { this.s.setVolume(v); }

  protected record(): Promise<void> { return this.s.record(); }

  ngOnDestroy(): void { this.s.dispose(); }
}
