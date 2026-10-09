// One running engine: the 60 Hz live-loop worker and, with sound on, the
// engine-sound AudioWorklet fed by it. Shared by /drive (the engineering
// page) and /enjoy (Phase 5), so the two cannot drift apart.
import { signal } from '@angular/core';
import { FS, type Transmission } from '@dieselsim/physics';
import { GRID_VERSION, SOUND_WORKLET } from '../solver/physics-version';
import type { DashInfo, DriveScript, FromWorker, GridFile, LiveView, Pedals } from './protocol';
import type { FromWorklet, ToWorklet } from './sound-protocol';
import { wavBytes } from './wav';

export interface GridStatus { converged: boolean; unsettled: number; stale: boolean; cells: number }
export type SessionStatus = 'idle' | 'loading' | 'driving' | 'error';

export class LiveSession {
  readonly status = signal<SessionStatus>('idle');
  readonly error = signal<string | undefined>(undefined);
  readonly gridStatus = signal<GridStatus | undefined>(undefined);
  readonly v = signal<LiveView | undefined>(undefined);
  readonly info = signal<DashInfo | undefined>(undefined);
  readonly soundOn = signal(false);
  readonly mic = signal('exterior_7m');
  readonly volume = signal(0.8);
  readonly levelDb = signal(-Infinity);
  readonly soundError = signal<string | undefined>(undefined);
  readonly recording = signal(false);

  private worker?: Worker;
  private grid?: GridFile;
  private preset = '';
  private ctx?: AudioContext;
  private node?: AudioWorkletNode;
  private captureWaiter?: (m: Extract<FromWorklet, { type: 'capture' }>) => void;
  private scriptWaiter?: (r: Extract<FromWorker, { type: 'scriptResult' }>) => void;

  get running(): boolean { return !!this.worker && this.status() === 'driving'; }

  /** Load a preset's prebuilt grid into a fresh worker; `run` starts the loop. */
  async load(preset: string, trans: Transmission, run: boolean, air?: { p: number; T: number }): Promise<void> {
    this.stop();
    this.status.set('loading');
    this.error.set(undefined);
    let grid: GridFile;
    try {
      const url = new URL(`grids/${preset}.json`, document.baseURI).href;
      const r = await fetch(url);
      if (!r.ok) throw new Error(`no prebuilt grid for ${preset} (HTTP ${r.status})`);
      grid = (await r.json()) as GridFile;
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : String(e));
      this.status.set('error');
      return;
    }
    await this.loadGrid(grid, trans, run, air);
  }

  /** Load a grid already in hand (an imported custom engine, ADR-014). */
  async loadGrid(grid: GridFile, trans: Transmission, run: boolean, air?: { p: number; T: number }): Promise<void> {
    this.stop();
    this.status.set('loading');
    this.error.set(undefined);
    try {
      this.gridStatus.set({ converged: grid.converged, unsettled: grid.unsettled_cells,
        stale: grid.grid_hash !== GRID_VERSION, cells: 2 * grid.rpms.length * grid.loads.length });
      const w = new Worker(new URL('./live.worker', import.meta.url), { type: 'module' });
      this.worker = w;
      await new Promise<void>((resolve, reject) => {
        w.addEventListener('error', e => reject(new Error(`the drive worker failed: ${e.message || 'script error'}`)));
        w.addEventListener('message', (ev: MessageEvent<FromWorker>) => {
          const m = ev.data;
          if (m.type === 'ready') { w.postMessage({ type: 'load', grid, trans, air }); resolve(); }
          else if (m.type === 'state') this.v.set(m.view);
          else if (m.type === 'info') this.info.set(m.info);
          else if (m.type === 'scriptResult') this.scriptWaiter?.(m);
        });
      });
      this.grid = grid;
      this.preset = grid.preset;
      this.wireSound();
      if (run) w.postMessage({ type: 'run' });
      this.status.set('driving');
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : String(e));
      this.status.set('error');
    }
  }

  runScript(script: DriveScript, init: Record<string, number>) {
    return new Promise(resolve => {
      this.scriptWaiter = resolve;
      this.worker!.postMessage({ type: 'script', script, init });
    });
  }

  stop(): void {
    this.post({ type: 'reset' });
    this.worker?.terminate();
    this.worker = undefined;
    this.v.set(undefined);
    // the next engine's info replaces it; until then the last engine's must
    // not stand in for it (the dials' scales, the vehicle)
    this.info.set(undefined);
    if (this.status() === 'driving') this.status.set('idle');
  }

  run(): void { this.worker?.postMessage({ type: 'run' }); }

  /** A driver key (dieselsim.live.handle_key), down or up. */
  key(key: string, down: boolean): void { this.worker?.postMessage({ type: 'key', key, down }); }

  /** Touch pedals (ADR-012): positions 0-1, applied by the worker every frame. */
  pedals(p: Pedals): void { this.worker?.postMessage({ type: 'pedals', pedals: p }); }

  // ---- sound (Phase 4) ------------------------------------------------
  /** Needs a user gesture (a click or tap), as every browser's autoplay policy does. */
  async soundStart(): Promise<void> {
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

  soundStop(): void {
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

  setMic(m: string): void { this.mic.set(m); this.post({ type: 'mic', mic: m }); }

  setVolume(v: number): void { this.volume.set(v); this.post({ type: 'volume', volume: v }); }

  capture(seconds: number): Promise<Extract<FromWorklet, { type: 'capture' }>> {
    return new Promise(resolve => {
      this.captureWaiter = resolve;
      this.post({ type: 'capture', seconds });
    });
  }

  /** Ten seconds of what you hear, as a WAV file. */
  async record(): Promise<void> {
    this.recording.set(true);
    try {
      const m = await this.capture(10);
      const url = URL.createObjectURL(new Blob([wavBytes(m.samples, m.rate) as BlobPart], { type: 'audio/wav' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `dieselsim-${this.preset}-${this.mic()}-${Math.round(this.v()?.rpm ?? 0)}rpm.wav`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } finally {
      this.recording.set(false);
    }
  }

  dispose(): void { this.stop(); this.soundStop(); }
}
