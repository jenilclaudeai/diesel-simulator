import { ChangeDetectionStrategy, Component, computed, HostListener, OnDestroy, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FS, type Transmission } from '@dieselsim/physics';
import { GRID_VERSION, SOUND_WORKLET } from '../solver/physics-version';
import { controlKey, DRIVE_PRESETS, KEY_HELP, MIC_KEYS, MICS } from './drive-keys';
import type { DriveScript, FromWorker, GridFile, LiveView } from './protocol';
import type { FromWorklet, ToWorklet } from './sound-protocol';
import { wavBytes } from './wav';

const fmt0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });

interface GridStatus { converged: boolean; unsettled: number; stale: boolean; cells: number }

/** A clicked button keeps focus, and then space -- full throttle -- would press it again
 *  (restarting the engine, or turning the sound off). Give the keys back to the drive. */
function releaseFocus(): void {
  (document.activeElement as HTMLElement | null)?.blur?.();
}

/**
 * The real-time drive (Phase 3). Prebuilt converged grids -- no Python in
 * the browser -- driven by the TypeScript live loop in a 60 Hz worker.
 * With sound on (Phase 4), an AudioWorklet synthesises the engine from the
 * same grid's acoustic sources, fed by the loop over a MessagePort.
 */
@Component({
  selector: 'app-drive',
  imports: [RouterLink],
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
  protected readonly preset = signal('crdi15');
  protected readonly trans = signal<Transmission>('tc');
  protected readonly status = signal<'idle' | 'loading' | 'driving' | 'error'>('idle');
  protected readonly error = signal<string | undefined>(undefined);
  protected readonly gridStatus = signal<GridStatus | undefined>(undefined);
  protected readonly v = signal<LiveView | undefined>(undefined);
  protected readonly rpmFrac = computed(() => Math.min(1, (this.v()?.rpm ?? 0) / 5000));
  protected readonly mics = MICS;
  protected readonly soundOn = signal(false);
  protected readonly mic = signal('exterior_7m');
  protected readonly volume = signal(0.8);
  protected readonly levelDb = signal(-Infinity);
  protected readonly soundError = signal<string | undefined>(undefined);
  protected readonly recording = signal(false);

  private ctx?: AudioContext;
  private node?: AudioWorkletNode;
  private grid?: GridFile;
  private captureWaiter?: (m: Extract<FromWorklet, { type: 'capture' }>) => void;

  private worker?: Worker;
  private readonly held = new Set<string>();
  private scriptWaiter?: (r: Extract<FromWorker, { type: 'scriptResult' }>) => void;

  constructor() {
    // e2e hook (only with ?e2e): run a frame-exact script through the real worker
    if (typeof location !== 'undefined' && location.search.includes('e2e')) {
      (globalThis as Record<string, unknown>)['__drive'] = {
        load: (preset: string, trans: Transmission) => this.load(preset, trans, false),
        script: (script: DriveScript, init: Record<string, number> = {}) => this.runScript(script, init),
        key: (key: string, down: boolean) => this.worker?.postMessage({ type: 'key', key, down }),
        run: () => this.worker?.postMessage({ type: 'run' }),
        sound: {
          on: () => this.soundStart(),
          capture: (seconds: number) => this.capture(seconds),
          level: () => this.levelDb(),
          error: () => this.soundError(),
          mic: (m: string) => this.setMic(m),
        },
      };
    }
  }

  protected selectPreset(p: string): void { this.preset.set(p); this.stop(); }
  protected selectTrans(t: string): void { this.trans.set(t as Transmission); this.stop(); }

  protected async start(): Promise<void> {
    releaseFocus();
    await this.load(this.preset(), this.trans(), true);
  }

  private async load(preset: string, trans: Transmission, run: boolean): Promise<void> {
    this.stop();
    this.status.set('loading');
    this.error.set(undefined);
    try {
      const url = new URL(`grids/${preset}.json`, document.baseURI).href;
      const r = await fetch(url);
      if (!r.ok) throw new Error(`no prebuilt grid for ${preset} (HTTP ${r.status})`);
      const grid = (await r.json()) as GridFile;
      this.gridStatus.set({ converged: grid.converged, unsettled: grid.unsettled_cells,
        stale: grid.grid_hash !== GRID_VERSION, cells: 2 * grid.rpms.length * grid.loads.length });
      const w = new Worker(new URL('./live.worker', import.meta.url), { type: 'module' });
      this.worker = w;
      await new Promise<void>((resolve, reject) => {
        w.addEventListener('error', e => reject(new Error(`the drive worker failed: ${e.message || 'script error'}`)));
        w.addEventListener('message', (ev: MessageEvent<FromWorker>) => {
          const m = ev.data;
          if (m.type === 'ready') { w.postMessage({ type: 'load', grid, trans }); resolve(); }
          else if (m.type === 'state') this.v.set(m.view);
          else if (m.type === 'scriptResult') this.scriptWaiter?.(m);
        });
      });
      this.grid = grid;
      this.wireSound();
      if (run) w.postMessage({ type: 'run' });
      this.status.set('driving');
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : String(e));
      this.status.set('error');
    }
  }

  private runScript(script: DriveScript, init: Record<string, number>) {
    return new Promise(resolve => {
      this.scriptWaiter = resolve;
      this.worker!.postMessage({ type: 'script', script, init });
    });
  }

  protected stop(): void {
    this.post({ type: 'reset' });
    this.worker?.terminate();
    this.worker = undefined;
    this.v.set(undefined);
    if (this.status() === 'driving') this.status.set('idle');
  }

  @HostListener('document:keydown', ['$event'])
  protected keydown(ev: KeyboardEvent): void { this.key(ev, true); }

  @HostListener('document:keyup', ['$event'])
  protected keyup(ev: KeyboardEvent): void { this.key(ev, false); }

  private key(ev: KeyboardEvent, down: boolean): void {
    if (!this.worker || this.status() !== 'driving') return;
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
    this.worker.postMessage({ type: 'key', key: k, down });
  }

  /** A key held while the window loses focus never sends its keyup: release everything. */
  @HostListener('window:blur')
  protected blur(): void {
    for (const k of this.held) this.worker?.postMessage({ type: 'key', key: k, down: false });
    this.held.clear();
  }

  // ---- sound (Phase 4) ------------------------------------------------
  protected async toggleSound(): Promise<void> {
    releaseFocus();
    if (this.soundOn()) this.soundStop();
    else await this.soundStart();
  }

  /** Needs a user gesture (the button), as every browser's autoplay policy does. */
  private async soundStart(): Promise<void> {
    this.soundError.set(undefined);
    try {
      // the synth's filters are designed at 44.1 kHz; the browser resamples to the device
      const ctx = new AudioContext({ sampleRate: FS, latencyHint: 'interactive' });
      await ctx.audioWorklet.addModule(new URL(`audio/${SOUND_WORKLET}`, document.baseURI).href);
      const node = new AudioWorkletNode(ctx, 'engine-sound', { numberOfInputs: 0, outputChannelCount: [2] });
      node.port.onmessage = (ev: MessageEvent<FromWorklet>) => {
        const m = ev.data;
        if (m.type === 'level') this.levelDb.set(20 * Math.log10(Math.max(m.rms, 1e-9)));
        else if (m.type === 'capture') this.captureWaiter?.(m);
        else if (m.type === 'error') this.soundError.set(m.message);
      };
      // a processor that throws in its constructor or process() stops for good,
      // and says so only here: without this, the sound fails in silence
      node.onprocessorerror = (e: Event) =>
        this.soundError.set(`the sound processor stopped: ${(e as ErrorEvent).message || 'an error in the audio thread'}`);
      node.connect(ctx.destination);
      await ctx.resume();
      this.ctx = ctx;
      this.node = node;
      this.post({ type: 'volume', volume: this.volume() });
      this.soundOn.set(true);
      this.wireSound();
    } catch (e) {
      this.soundError.set(`sound failed to start: ${e instanceof Error ? e.message : String(e)}`);
      this.soundStop();
    }
  }

  private soundStop(): void {
    this.worker?.postMessage({ type: 'sound', port: null });
    void this.ctx?.close();
    this.ctx = undefined;
    this.node = undefined;
    this.soundOn.set(false);
    this.levelDb.set(-Infinity);
  }

  /** (Re)connect loop and synth: after sound starts, and after every engine (re)load. */
  private wireSound(): void {
    if (!this.node || !this.worker || !this.grid) return;
    const ch = new MessageChannel();
    this.post({ type: 'grid', spec: this.grid.spec, grid: this.grid, mic: this.mic() });
    this.node.port.postMessage({ type: 'loop', port: ch.port2 } satisfies ToWorklet, [ch.port2]);
    this.worker.postMessage({ type: 'sound', port: ch.port1 }, [ch.port1]);
  }

  private post(m: ToWorklet): void { this.node?.port.postMessage(m); }

  protected setMic(m: string): void { this.mic.set(m); this.post({ type: 'mic', mic: m }); }

  protected setVolume(v: number): void { this.volume.set(v); this.post({ type: 'volume', volume: v }); }

  private capture(seconds: number): Promise<Extract<FromWorklet, { type: 'capture' }>> {
    return new Promise(resolve => {
      this.captureWaiter = resolve;
      this.post({ type: 'capture', seconds });
    });
  }

  /** Ten seconds of what you hear, as a WAV file. */
  protected async record(): Promise<void> {
    this.recording.set(true);
    try {
      const m = await this.capture(10);
      const url = URL.createObjectURL(new Blob([wavBytes(m.samples, m.rate) as BlobPart], { type: 'audio/wav' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `dieselsim-${this.preset()}-${this.mic()}-${Math.round(this.v()?.rpm ?? 0)}rpm.wav`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } finally {
      this.recording.set(false);
    }
  }

  ngOnDestroy(): void { this.stop(); this.soundStop(); }
}
