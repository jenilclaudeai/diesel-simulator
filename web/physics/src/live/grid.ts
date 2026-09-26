// Port of dieselsim/live.py PerfGrid: bilinear interpolation of the
// pre-solved (rpm, load) performance grid.
import { clip, type LiveSpec, type Perf } from "./common.js";

/** numpy.searchsorted(a, v), side="left": first index with a[i] >= v. */
function searchsorted(a: readonly number[], v: number): number {
  let lo = 0, hi = a.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (a[mid]! < v) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

export class PerfGrid {
  readonly n_rpm: number;
  readonly n_load: number;

  constructor(
    readonly spec: LiveSpec,
    readonly rpms: readonly number[],
    readonly loads: readonly number[],
    /** perf[i][j]: rpm index i, load index j */
    readonly perf: readonly (readonly Perf[])[],
  ) {
    this.n_rpm = rpms.length;
    this.n_load = loads.length;
  }

  /** Bilinear weights and the four surrounding grid indices. */
  weights(rpm: number, load: number): [number, number, number, number] {
    const r = clip(rpm, this.rpms[0]!, this.rpms[this.n_rpm - 1]!);
    const l = clip(load, this.loads[0]!, this.loads[this.n_load - 1]!);
    const i = Math.trunc(clip(searchsorted(this.rpms, r) - 1, 0, this.n_rpm - 2));
    const j = Math.trunc(clip(searchsorted(this.loads, l) - 1, 0, this.n_load - 2));
    const fr = (r - this.rpms[i]!) / (this.rpms[i + 1]! - this.rpms[i]!);
    const fl = (l - this.loads[j]!) / (this.loads[j + 1]! - this.loads[j]!);
    return [i, j, fr, fl];
  }

  blendPerf(rpm: number, load: number): Perf {
    const [i, j, fr, fl] = this.weights(rpm, load);
    const w = [(1 - fr) * (1 - fl), (1 - fr) * fl, fr * (1 - fl), fr * fl];
    const q = [this.perf[i]![j]!, this.perf[i]![j + 1]!, this.perf[i + 1]![j]!, this.perf[i + 1]![j + 1]!];
    const out: Perf = {};
    for (const k of Object.keys(q[0]!)) {
      // Python's sum() starts from 0 and adds left to right
      let s = 0;
      for (let n = 0; n < 4; n++) s += w[n]! * q[n]![k]!;
      out[k] = s;
    }
    return out;
  }
}
