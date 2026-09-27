// Port of dieselsim/livesound.py's DSP: Butterworth design without scipy,
// the resonator and peaking biquads, streaming filters, the waveguide comb,
// the shape trackers, the reverb delay line and the noise table. Held to
// livesound's pure mode by fixtures/sound.json; every recurrence runs in
// the same operation order as the Python loop.

export const FS = 44100;
export const BLOCK = 128;          // the AudioWorklet render quantum
export const NORM_TAU = 0.3;       // s, the shape-normalisation trackers
export const SRC_TAU = 0.05;       // s, source waveforms glide to a new operating point
export const NOISE_N = 1 << 18;    // Gaussian table

// ---- complex arithmetic, as CPython does it (cmath, _Py_c_quot) ----------
type C = readonly [number, number];
const cmul = (a: C, b: C): C => [a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0]];
const cadd = (a: C, b: C): C => [a[0] + b[0], a[1] + b[1]];
const csub = (a: C, b: C): C => [a[0] - b[0], a[1] - b[1]];
const cscale = (a: C, s: number): C => [a[0] * s, a[1] * s];
function cdiv(a: C, b: C): C {
  const abr = Math.abs(b[0]), abi = Math.abs(b[1]);
  if (abr >= abi) {
    const ratio = b[1] / b[0], denom = b[0] + b[1] * ratio;
    return [(a[0] + a[1] * ratio) / denom, (a[1] - a[0] * ratio) / denom];
  }
  const ratio = b[0] / b[1], denom = b[0] * ratio + b[1];
  return [(a[0] * ratio + a[1]) / denom, (a[1] * ratio - a[0]) / denom];
}
const cexpi = (y: number): C => [Math.cos(y), Math.sin(y)];     // cmath.exp(1j*y)
const cabs = (a: C): number => Math.hypot(a[0], a[1]);
function csqrt(z: C): C {
  if (z[0] === 0 && z[1] === 0) return [0, z[1]];
  const ax = Math.abs(z[0]) / 8.0, ay = Math.abs(z[1]);
  const s = 2.0 * Math.sqrt(ax + Math.hypot(ax, ay / 8.0));
  const d = ay / (2.0 * s);
  return z[0] >= 0 ? [s, Math.sign(z[1]) < 0 || Object.is(z[1], -0) ? -d : d]
                   : [d, Math.sign(z[1]) < 0 || Object.is(z[1], -0) ? -s : s];
}

export type BA = [number[], number[]];

/** Butterworth second-order sections (livesound.butter_sos): wn normalised
 *  to Nyquist, a pair for "band". */
export function butterSos(order: number, wn: number | [number, number], kind: "low" | "high" | "band"): BA[] {
  let poles: C[] = [];
  for (let k = 0; k < order; k++) poles.push(cexpi(Math.PI * (2 * k + order + 1) / (2 * order)));
  let zeros: C[] = [], gain = 1.0;
  const warp = (w: number) => 4.0 * Math.tan(Math.PI * w / 2.0);   // fs = 2
  if (kind === "low") {
    const wo = warp(wn as number);
    poles = poles.map(p => cscale(p, wo));
    gain = wo ** order;
  } else if (kind === "high") {
    const wo = warp(wn as number);
    let prod: C = [1.0, 0.0];
    for (const p of poles) prod = cmul(prod, [-p[0], -p[1]]);
    gain = cdiv([1.0, 0.0], prod)[0];
    poles = poles.map(p => cdiv([wo, 0.0], p));
    zeros = poles.map(() => [0, 0] as C);
  } else {
    const [lo, hi] = wn as [number, number];
    const w1 = warp(lo), w2 = warp(hi);
    const bw = w2 - w1, wo = Math.sqrt(w1 * w2);
    const next: C[] = [];
    for (const p of poles) {
      const h = cdiv(cscale(p, bw), [2.0, 0.0]);
      const r = csqrt(csub(cmul(h, h), [wo * wo, 0.0]));
      next.push(cadd(h, r), csub(h, r));
    }
    poles = next;
    zeros = new Array<C>(order).fill([0, 0]);
    gain = bw ** order;
  }
  // bilinear transform, fs = 2
  let num: C = [1.0, 0.0], den: C = [1.0, 0.0];
  for (const z of zeros) num = cmul(num, csub([4.0, 0.0], z));
  for (const p of poles) den = cmul(den, csub([4.0, 0.0], p));
  gain *= cdiv(num, den)[0];
  const zd: C[] = zeros.map(z => cdiv(cadd([4.0, 0.0], z), csub([4.0, 0.0], z)));
  while (zd.length < poles.length) zd.push([-1.0, 0.0]);
  const pd: C[] = poles.map(p => cdiv(cadd([4.0, 0.0], p), csub([4.0, 0.0], p)));
  const upper = pd.filter(p => p[1] > 1e-12).sort((a, b) => cabs(a) - cabs(b));
  const real = pd.filter(p => Math.abs(p[1]) <= 1e-12);
  const zr = zd.map(z => z[0]).sort((a, b) => b - a);   // +1 (highpass) before -1 (lowpass)
  const sos: BA[] = [];
  for (const p of upper) {
    const z1 = zr.shift()!, z2 = zr.shift()!;
    sos.push([[1.0, -(z1 + z2), z1 * z2], [1.0, -2.0 * p[0], cabs(p) ** 2]]);
  }
  for (const p of real) {
    const z1 = zr.shift()!;
    sos.push([[1.0, -z1, 0.0], [1.0, -p[0], 0.0]]);
  }
  sos[0] = [sos[0]![0].map(c => gain * c), sos[0]![1]];
  return sos;
}

/** acoustics._resonator's damped structural mode. */
export function resonatorBa(f0: number, Q: number, gain = 1.0, fs = FS): BA {
  f0 = Math.min(f0, 0.45 * fs);
  const r = Math.exp(-Math.PI * f0 / (Q * fs));
  const th = 2 * Math.PI * f0 / fs;
  return [[gain * (1 - r), 0.0, -gain * (1 - r) * r], [1.0, -2 * r * Math.cos(th), r * r]];
}

/** acoustics._biquad_peak. */
export function peakBa(f0: number, Q: number, gain_db: number, fs = FS): BA {
  const A = 10 ** (gain_db / 40.0);
  const w0 = 2 * Math.PI * f0 / fs;
  const alpha = Math.sin(w0) / (2 * Q);
  const b = [1 + alpha * A, -2 * Math.cos(w0), 1 - alpha * A];
  const a = [1 + alpha / A, -2 * Math.cos(w0), 1 - alpha / A];
  return [b.map(c => c / a[0]!), a.map(c => c / a[0]!)];
}

/** Transposed direct form II, state carried between blocks. */
export class Biquad {
  private readonly b0: number; private readonly b1: number; private readonly b2: number;
  private readonly a1: number; private readonly a2: number;
  z1 = 0.0; z2 = 0.0;
  constructor([b, a]: BA) {
    this.b0 = b[0]!; this.b1 = b[1]!; this.b2 = b[2]!;
    this.a1 = a[1]!; this.a2 = a[2]!;
  }
  process(x: Float64Array): Float64Array {
    const { b0, b1, b2, a1, a2 } = this;
    let z1 = this.z1, z2 = this.z2;
    const y = new Float64Array(x.length);
    for (let n = 0; n < x.length; n++) {
      const xn = x[n]!;
      const yn = b0 * xn + z1;
      z1 = b1 * xn + z2 - a1 * yn;
      z2 = b2 * xn - a2 * yn;
      y[n] = yn;
    }
    this.z1 = z1; this.z2 = z2;
    return y;
  }
}

/** A cascade of biquads (a Butterworth filter's sections). */
export class Chain {
  private readonly st: Biquad[];
  constructor(sos: BA[]) { this.st = sos.map(s => new Biquad(s)); }
  process(x: Float64Array): Float64Array {
    for (const s of this.st) x = s.process(x);
    return x;
  }
}

/** acoustics._lowpass / _highpass / _bandpass's clamps and design. */
export function butter(kind: "low" | "high" | "band", cutoff: number | [number, number], order: number, fs = FS): Chain {
  const ny = 0.5 * fs;
  if (kind === "band") {
    const [c0, c1] = cutoff as [number, number];
    const lo = Math.max(20.0, Math.min(c0, 0.9 * ny));
    const hi = Math.max(lo * 1.05, Math.min(c1, 0.95 * ny));
    return new Chain(butterSos(order, [lo / ny, hi / ny], "band"));
  }
  if (kind === "low") return new Chain(butterSos(order, Math.min(cutoff as number, 0.95 * ny) / ny, "low"));
  return new Chain(butterSos(order, Math.max(5.0, Math.min(cutoff as number, 0.9 * ny)) / ny, "high"));
}

/** acoustics._comb_waveguide, streaming: a pipe with a reflecting end and a
 *  one-pole wall loss per bounce. */
export class Comb {
  readonly D: number;
  private readonly buf: Float64Array;
  private idx = 0;
  private lp = 0.0;
  constructor(delay_s: number, private readonly refl: number, fs = FS, private readonly a_lp = 0.55) {
    this.D = Math.max(1, pyRound(delay_s * fs));
    this.buf = new Float64Array(this.D);
  }
  process(x: Float64Array): Float64Array {
    const { buf, D, refl, a_lp: a } = this;
    let idx = this.idx, lp = this.lp;
    const y = new Float64Array(x.length);
    for (let n = 0; n < x.length; n++) {
      const d = buf[idx]!;
      lp = a * lp + (1.0 - a) * d;
      const yn = x[n]! + refl * lp;
      buf[idx] = yn;
      idx += 1;
      if (idx === D) idx = 0;
      y[n] = yn;
    }
    this.idx = idx; this.lp = lp;
    return y;
  }
}

/** Python's round(): half to even. */
export function pyRound(x: number): number {
  const f = Math.floor(x), d = x - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}

/** Causal shape normalisation: y / rms, the mean square tracked by a
 *  one-pole filter over blocks, seeded from the first block. */
export class Norm {
  private readonly beta: number;
  private ms = -1.0;
  constructor(n = BLOCK, fs = FS, tau = NORM_TAU) { this.beta = Math.min(1.0, n / (tau * fs)); }
  apply(y: Float64Array): Float64Array {
    let s = 0.0;
    for (let n = 0; n < y.length; n++) s += y[n]! * y[n]!;
    const m = s / y.length;
    this.ms = this.ms < 0.0 ? m : this.ms + this.beta * (m - this.ms);
    const k = Math.sqrt(this.ms) + 1e-12;
    const out = new Float64Array(y.length);
    for (let n = 0; n < y.length; n++) out[n] = y[n]! / k;
    return out;
  }
}

/** A tapped delay line for the cabin/exterior reverb. */
export class Delay {
  private buf: Float64Array;
  constructor(n: number) { this.buf = new Float64Array(n); }
  taps(x: Float64Array, delays: readonly number[]): Float64Array[] {
    const L = this.buf.length, n = x.length;
    const z = new Float64Array(L + n);
    z.set(this.buf, 0); z.set(x, L);
    const out = delays.map(d => z.slice(L - d, L - d + n));
    this.buf = z.slice(z.length - L);
    return out;
  }
}

/** Gaussian table from mulberry32 + Box-Muller (livesound.noise_table). */
export function noiseTable(seed = 12345, n = NOISE_N): Float64Array {
  let s = seed >>> 0;
  const out = new Float64Array(n);
  const u32 = (): number => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1) >>> 0;
    t = (t ^ ((t + (Math.imul(t ^ (t >>> 7), t | 61) >>> 0)) >>> 0)) >>> 0;
    return (t ^ (t >>> 14)) >>> 0;
  };
  for (let i = 0; i < n; i += 2) {
    const u1 = (u32() + 0.5) / 4294967296.0;
    const u2 = (u32() + 0.5) / 4294967296.0;
    const r = Math.sqrt(-2.0 * Math.log(u1));
    out[i] = r * Math.cos(2.0 * Math.PI * u2);
    out[i + 1] = r * Math.sin(2.0 * Math.PI * u2);
  }
  return out;
}

export class NoiseCursor {
  private i: number;
  constructor(private readonly t: Float64Array, start: number) { this.i = ((start % t.length) + t.length) % t.length; }
  take(n: number): Float64Array {
    const L = this.t.length, out = new Float64Array(n);
    for (let k = 0; k < n; k++) out[k] = this.t[(this.i + k) % L]!;
    this.i = (this.i + n) % L;
    return out;
  }
}
