// Port of dieselsim/live.py Adr011Grid: warm and cold cells with their
// cylinder-pressure traces, interpolated on coolant temperature (ADR-011),
// and (Phase 4) their acoustic sources for the streaming synth.
import { clip, type Perf } from "./common.js";
import { PerfGrid } from "./grid.js";
import type { LiveSpec } from "./common.js";

/** The six crank-angle source waveforms the synth reads (livesound.SOURCE_KEYS). */
export const SOURCE_KEYS = ["exh_flow", "int_flow", "dpdth", "inj", "valve", "slap"] as const;
export type SourceKey = typeof SOURCE_KEYS[number];

/** One operating point's sources: waveforms on grid_deg, and their scalars. */
export type Sources = Record<SourceKey, Float64Array> & { _meta: Record<string, number> };

/** The fixture / static-asset form: traces as base64 little-endian float32. */
export interface Adr011GridData {
  rpms: number[]; loads: number[]; T_warm: number; T_cold: number; grid_deg: number[];
  perf: Perf[][]; perf_cold: Perf[][]; p_cyl_f32: string[][]; p_cyl_cold_f32: string[][];
  // Phase 4, absent from grids built before it
  src_f32?: Record<SourceKey, string>[][]; src_cold_f32?: Record<SourceKey, string>[][];
  src_meta?: Record<string, number>[][]; src_meta_cold?: Record<string, number>[][];
}

const B64 = new Int16Array(128).fill(-1);
for (let i = 0; i < 64; i++) B64["ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".charCodeAt(i)] = i;

/** Base64 to bytes without atob, which an AudioWorkletGlobalScope does not have. */
export function decodeBase64(b64: string): Uint8Array {
  let n = b64.length;
  while (n > 0 && b64.charCodeAt(n - 1) === 61) n--;               // '=' padding
  const out = new Uint8Array((n * 3) >> 2);
  let acc = 0, bits = 0, o = 0;
  for (let i = 0; i < n; i++) {
    const v = B64[b64.charCodeAt(i)] ?? -1;
    if (v < 0) throw new Error(`not base64 at ${i}`);
    acc = (acc << 6) | v;
    bits += 6;
    if (bits >= 8) { bits -= 8; out[o++] = (acc >> bits) & 0xff; }
  }
  return out;
}

function decodeF32(b64: string): Float64Array {
  const bytes = decodeBase64(b64);
  return Float64Array.from(new Float32Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 4));
}

export class Adr011Grid extends PerfGrid {
  readonly p_cyl: Float64Array[][];
  readonly p_cyl_cold: Float64Array[][];
  readonly perf_cold: Perf[][];
  readonly grid_deg: Float64Array;
  readonly T_warm: number;
  readonly T_cold: number;
  readonly k_torque: number; // fmep [Pa] -> mean torque [N.m]
  readonly src: Sources[][] | null;
  readonly src_cold: Sources[][] | null;

  constructor(spec: LiveSpec, d: Adr011GridData) {
    super(spec, d.rpms, d.loads, d.perf);
    this.p_cyl = d.p_cyl_f32.map(row => row.map(decodeF32));
    this.p_cyl_cold = d.p_cyl_cold_f32.map(row => row.map(decodeF32));
    this.perf_cold = d.perf_cold;
    this.grid_deg = Float64Array.from(d.grid_deg);
    this.T_warm = d.T_warm;
    this.T_cold = d.T_cold;
    this.k_torque = spec.geom.displacement / (4.0 * Math.PI);
    const srcs = (arrs?: Record<SourceKey, string>[][], metas?: Record<string, number>[][]): Sources[][] | null =>
      arrs && metas ? arrs.map((row, i) => row.map((a, j) => {
        const out = { _meta: { ...metas[i]![j]! } } as Sources;
        for (const k of SOURCE_KEYS) out[k] = decodeF32(a[k]);
        return out;
      })) : null;
    this.src = srcs(d.src_f32, d.src_meta);
    this.src_cold = srcs(d.src_cold_f32, d.src_meta_cold);
  }

  cold_weight(T_coolant: number): number {
    return clip((this.T_warm - T_coolant) / (this.T_warm - this.T_cold), 0.0, 1.0);
  }

  blendPerfT(rpm: number, load: number, T_coolant: number): Perf {
    const [i, j, fr, fl] = this.weights(rpm, load);
    const w = [(1 - fr) * (1 - fl), (1 - fr) * fl, fr * (1 - fl), fr * fl];
    const c = this.cold_weight(T_coolant);
    const qw = [this.perf[i]![j]!, this.perf[i]![j + 1]!, this.perf[i + 1]![j]!, this.perf[i + 1]![j + 1]!];
    const qc = [this.perf_cold[i]![j]!, this.perf_cold[i]![j + 1]!, this.perf_cold[i + 1]![j]!, this.perf_cold[i + 1]![j + 1]!];
    const out: Perf = {};
    for (const k of Object.keys(qw[0]!)) {
      let warm = 0, cold = 0;
      for (let n = 0; n < 4; n++) warm += w[n]! * qw[n]![k]!;
      for (let n = 0; n < 4; n++) cold += w[n]! * qc[n]![k]!;
      out[k] = (1.0 - c) * warm + c * cold;
    }
    out["torque_ind"] = out["torque"]! + out["fmep"]! * this.k_torque;
    return out;
  }

  blendPCyl(rpm: number, load: number, T_coolant: number): Float64Array {
    const [i, j, fr, fl] = this.weights(rpm, load);
    const w0 = (1 - fr) * (1 - fl), w1 = (1 - fr) * fl, w2 = fr * (1 - fl), w3 = fr * fl;
    const c = this.cold_weight(T_coolant);
    const P = this.p_cyl, Q = this.p_cyl_cold;
    const a = P[i]![j]!, b = P[i]![j + 1]!, e = P[i + 1]![j]!, f = P[i + 1]![j + 1]!;
    const qa = Q[i]![j]!, qb = Q[i]![j + 1]!, qe = Q[i + 1]![j]!, qf = Q[i + 1]![j + 1]!;
    const out = new Float64Array(a.length);
    for (let k = 0; k < a.length; k++) {
      const warm = w0 * a[k]! + w1 * b[k]! + w2 * e[k]! + w3 * f[k]!;
      const cold = w0 * qa[k]! + w1 * qb[k]! + w2 * qe[k]! + w3 * qf[k]!;
      out[k] = (1.0 - c) * warm + c * cold;
    }
    return out;
  }

  /** The sources at the live point (live.py blend_sources): bilinear in
   *  (rpm, load), linear warm to cold, in blendPCyl's order. */
  blendSources(rpm: number, load: number, T_coolant: number): Sources {
    if (!this.src || !this.src_cold) throw new Error("this grid carries no acoustic sources");
    const [i, j, fr, fl] = this.weights(rpm, load);
    const w0 = (1 - fr) * (1 - fl), w1 = (1 - fr) * fl, w2 = fr * (1 - fl), w3 = fr * fl;
    const c = this.cold_weight(T_coolant);
    const W = [this.src[i]![j]!, this.src[i]![j + 1]!, this.src[i + 1]![j]!, this.src[i + 1]![j + 1]!];
    const C = [this.src_cold[i]![j]!, this.src_cold[i]![j + 1]!, this.src_cold[i + 1]![j]!, this.src_cold[i + 1]![j + 1]!];
    const mix = (a: number, b: number, e: number, f: number, qa: number, qb: number, qe: number, qf: number) =>
      (1.0 - c) * (w0 * a + w1 * b + w2 * e + w3 * f) + c * (w0 * qa + w1 * qb + w2 * qe + w3 * qf);
    const out = { _meta: {} } as Sources;
    const cw = 1.0 - c;
    for (const k of SOURCE_KEYS) {
      // plain loops, mix()'s arithmetic inlined: the audio thread calls this at 20 Hz
      const a = W[0]![k], b = W[1]![k], e = W[2]![k], f = W[3]![k];
      const qa = C[0]![k], qb = C[1]![k], qe = C[2]![k], qf = C[3]![k];
      const y = new Float64Array(a.length);
      for (let n = 0; n < a.length; n++)
        y[n] = cw * (w0 * a[n]! + w1 * b[n]! + w2 * e[n]! + w3 * f[n]!) + c * (w0 * qa[n]! + w1 * qb[n]! + w2 * qe[n]! + w3 * qf[n]!);
      out[k] = y;
    }
    for (const k of Object.keys(W[0]!._meta)) {
      const m = (q: Sources) => q._meta[k]!;
      out._meta[k] = mix(m(W[0]!), m(W[1]!), m(W[2]!), m(W[3]!), m(C[0]!), m(C[1]!), m(C[2]!), m(C[3]!));
    }
    return out;
  }
}
