// Port of dieselsim/live.py Adr011Grid: warm and cold cells with their
// cylinder-pressure traces, interpolated on coolant temperature (ADR-011).
import { clip, type Perf } from "./common.js";
import { PerfGrid } from "./grid.js";
import type { LiveSpec } from "./common.js";

/** The fixture / static-asset form: traces as base64 little-endian float32. */
export interface Adr011GridData {
  rpms: number[]; loads: number[]; T_warm: number; T_cold: number; grid_deg: number[];
  perf: Perf[][]; perf_cold: Perf[][]; p_cyl_f32: string[][]; p_cyl_cold_f32: string[][];
}

function decodeF32(b64: string): Float64Array {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
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

  constructor(spec: LiveSpec, d: Adr011GridData) {
    super(spec, d.rpms, d.loads, d.perf);
    this.p_cyl = d.p_cyl_f32.map(row => row.map(decodeF32));
    this.p_cyl_cold = d.p_cyl_cold_f32.map(row => row.map(decodeF32));
    this.perf_cold = d.perf_cold;
    this.grid_deg = Float64Array.from(d.grid_deg);
    this.T_warm = d.T_warm;
    this.T_cold = d.T_cold;
    this.k_torque = spec.geom.displacement / (4.0 * Math.PI);
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
}
