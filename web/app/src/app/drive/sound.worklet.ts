// The engine's sound on the audio thread (Phase 4): @dieselsim/physics's
// LiveSynth -- the TypeScript port held to dieselsim/livesound.py sample for
// sample -- rendering one 128-sample quantum per process() call. The 60 Hz
// loop sends its state over a MessagePort; no SharedArrayBuffer, so no
// COOP/COEP headers and GitHub Pages hosting stays possible (ADR-003).
// Bundled by scripts/prepare-assets.mjs (esbuild): Angular's builder
// bundles workers but not worklets.
import { Adr011Grid, BLOCK, FS, LiveSynth, type Adr011GridData, type SoundSpec, type Sources } from '@dieselsim/physics';
import type { LoopSound, ToWorklet } from './sound-protocol';

declare const sampleRate: number;
declare function registerProcessor(name: string, ctor: unknown): void;
declare class AudioWorkletProcessor {
  readonly port: MessagePort;
  constructor();
}

const BLEND_EVERY = 17;         // quanta between source blends: ~20 Hz
const LEVEL_EVERY = 86;         // quanta between level reports: ~4 Hz

class EngineSoundProcessor extends AudioWorkletProcessor {
  private grid?: Adr011Grid;
  private syn?: LiveSynth;
  private st?: LoopSound;
  private n = 0;
  private sq = 0;
  private peak = 0;
  private volume = 0.8;
  private cap?: Float32Array;
  private capN = 0;
  private said = false;
  private blend?: Sources;           // reused by every 20 Hz blend: no allocation on this thread

  constructor() {
    super();
    // an exception in a worklet's message handler reaches no one: report it
    this.port.onmessage = (ev: MessageEvent<ToWorklet>) => {
      try { this.onMessage(ev.data); } catch (e) { this.fail(`engine sound: ${String(e)}`); }
    };
    if (sampleRate !== FS) this.fail(`the synth is designed at ${FS} Hz; this context runs at ${sampleRate} Hz`);
  }

  private fail(msg: string): void {
    if (!this.said) this.port.postMessage({ type: 'error', message: msg });
    this.said = true;
  }

  private onMessage(m: ToWorklet): void {
    switch (m.type) {
      case 'grid':
        this.grid = new Adr011Grid(m.spec as never, m.grid as Adr011GridData);
        this.syn = new LiveSynth(m.spec as SoundSpec, m.mic);
        this.st = undefined;
        break;
      case 'loop':
        m.port.onmessage = (e: MessageEvent<LoopSound>) => { this.st = e.data; };
        break;
      case 'mic': this.syn?.setMic(m.mic); break;
      case 'volume': this.volume = m.volume; break;
      case 'capture': this.cap = new Float32Array(Math.round(m.seconds * sampleRate)); this.capN = 0; break;
      case 'reset': this.st = undefined; break;
    }
  }

  process(_inputs: Float32Array[][], outputs: Float32Array[][]): boolean {
    const out = outputs[0];
    if (!out || !out[0]) return true;
    const syn = this.syn, st = this.st, grid = this.grid;
    if (!syn || !st || !grid) return true;                  // silence until the loop speaks
    if (out[0].length !== BLOCK) { this.fail(`render quantum ${out[0].length}, expected ${BLOCK}`); return true; }
    try {
      if (syn.src === null || this.n % BLEND_EVERY === 0) {
        this.blend = grid.blendSources(st.rpm, st.load, st.T, this.blend);
        syn.setSources(this.blend);
      }
      const y = syn.block(st.rpm, st.live, st.running);
      const v = this.volume;
      for (let i = 0; i < BLOCK; i++) {
        const s = y[i]! * v;
        out[0][i] = s;
        this.sq += s * s;
        this.peak = Math.max(this.peak, Math.abs(s));
      }
      for (let c = 1; c < out.length; c++) out[c]!.set(out[0]);
      if (this.cap) {
        const k = Math.min(BLOCK, this.cap.length - this.capN);
        this.cap.set(out[0].subarray(0, k), this.capN);
        this.capN += k;
        if (this.capN >= this.cap.length) {
          this.port.postMessage({ type: 'capture', samples: this.cap, rate: sampleRate }, [this.cap.buffer]);
          this.cap = undefined;
        }
      }
    } catch (e) {
      this.fail(String(e));
    }
    if (++this.n % LEVEL_EVERY === 0) {
      this.port.postMessage({ type: 'level', rms: Math.sqrt(this.sq / (LEVEL_EVERY * BLOCK)), peak: this.peak, quanta: this.n });
      this.sq = 0;
      this.peak = 0;
    }
    return true;
  }
}

registerProcessor('engine-sound', EngineSoundProcessor);
