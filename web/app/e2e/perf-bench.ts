// The drive page's per-step costs, measured in a browser (see perf.mjs).
// Bundled by esbuild with @dieselsim/physics -- the same code the sound
// worklet and the live-loop worker run -- and exposed as globalThis.bench.
import { Adr011Grid, LiveEngine, LiveSynth, handleKey, type Adr011GridData, type EngineView, type LiveSpec, type SoundSpec } from '@dieselsim/physics';

interface GridFile extends Adr011GridData { preset: string; spec: LiveSpec & SoundSpec; engine_view: EngineView }
interface Stats { n: number; mean: number; p50: number; p99: number; p999: number; max: number; over: number }

function stats(ts: number[], budget: number): Stats {
  const s = [...ts].sort((a, b) => a - b), n = s.length;
  const q = (p: number) => s[Math.min(n - 1, Math.floor(p * n))]!;
  return { n, mean: ts.reduce((a, b) => a + b, 0) / n, p50: q(0.5), p99: q(0.99), p999: q(0.999), max: s[n - 1]!,
    over: ts.filter(t => t > budget).length };
}

/** The synth: one 128-sample quantum per call, sources re-blended every 17 (20 Hz), as the worklet does. */
function synth(g: GridFile, seconds: number): Stats {
  const grid = new Adr011Grid(g.spec, g), syn = new LiveSynth(g.spec, 'exterior_7m');
  const live = { boost: 1.8, turbo_rpm: 9e4, load: 0.5, Pb: 500, skirt_clr: 2e-5, v_seating: 0.05 };
  let blend = grid.blendSources(1500, 0.5, 330);
  syn.setSources(blend);
  for (let i = 0; i < 344; i++) syn.block(1500, live);                  // JIT warm-up, 1 s
  const n = Math.round(seconds * 44100 / 128), ts: number[] = [];
  for (let i = 0; i < n; i++) {
    const rpm = 1200 + 800 * (0.5 + 0.5 * Math.sin(i / 300)), t0 = performance.now();
    if (i % 17 === 0) { blend = grid.blendSources(rpm, 0.5, 330, blend); syn.setSources(blend); }   // as the worklet does
    syn.block(rpm, live);
    ts.push(performance.now() - t0);
  }
  return stats(ts, 128 / 44100 * 1000);
}

/** The live loop at 60 Hz (ADR-011 friction every 6th frame), driving: launch, shifts, cruise. */
function loop(g: GridFile, seconds: number): { plain: Stats; friction: Stats } {
  const grid = new Adr011Grid(g.spec, g);
  const e = new LiveEngine(grid, g.preset, 'tc', g.engine_view);
  const plain: number[] = [], fric: number[] = [], n = Math.round(seconds * 60);
  for (let f = 0; f < n + 120; f++) {
    e.throttle = f < 60 ? 0 : f < 1500 ? 0.7 : 0.3;
    if (f === 900) handleKey(e, 'l');
    const withFriction = e._frame % LiveEngine.FRICTION_EVERY === 0, t0 = performance.now();
    e.step(1 / 60);
    const dt = performance.now() - t0;
    if (f >= 120) (withFriction ? fric : plain).push(dt);                // after warm-up
  }
  return { plain: stats(plain, 1000 / 60), friction: stats(fric, 1000 / 60) };
}

(globalThis as Record<string, unknown>)['bench'] = { synth, loop };
