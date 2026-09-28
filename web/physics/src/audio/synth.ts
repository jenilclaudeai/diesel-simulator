// Port of dieselsim/livesound.py LiveSynth: one engine's sound, BLOCK
// samples at a time, for the AudioWorklet. The streaming form of
// acoustics.EngineSound.render (physical source levels, FINDINGs 003, 004,
// 017, 021); held to livesound's pure mode by fixtures/sound.json. Every
// expression keeps the Python's operation order.
import type { SourceKey, Sources } from "../live/adr011.js";
import { SOURCE_KEYS } from "../live/adr011.js";
import {
  BLOCK, Biquad, Chain, Comb, Delay, FS, NOISE_N, Norm, NoiseCursor, SRC_TAU,
  butter, noiseTable, peakBa, resonatorBa,
} from "./dsp.js";

export const C_AIR_STP = 343.0;
export const SPL_CAL = 0.10;

export type Part = "exhaust" | "intake" | "combustion" | "mech" | "turbo" | "gear" | "rumble";

export interface Mic {
  gains: Record<Part, number>;   // in acoustics.MICS order: the mix sums in this order
  lp_hz: number; hp_hz: number; distance_m: number; reverb: number;
}

/** acoustics.MICS (the fixture carries the table; the tests compare). */
export const MICS: Record<string, Mic> = {
  exhaust_tip: { gains: { exhaust: 1.00, intake: 0.05, combustion: 0.16, mech: 0.10, turbo: 0.10, gear: 0.03, rumble: 0.20 },
    lp_hz: 5200, hp_hz: 28, distance_m: 0.5, reverb: 0.0 },
  intake: { gains: { exhaust: 0.10, intake: 1.00, combustion: 0.18, mech: 0.12, turbo: 0.55, gear: 0.05, rumble: 0.15 },
    lp_hz: 7500, hp_hz: 45, distance_m: 0.4, reverb: 0.0 },
  engine_bay: { gains: { exhaust: 0.30, intake: 0.35, combustion: 1.00, mech: 0.95, turbo: 0.45, gear: 0.55, rumble: 0.55 },
    lp_hz: 11000, hp_hz: 55, distance_m: 0.8, reverb: 0.0 },
  cabin: { gains: { exhaust: 0.38, intake: 0.20, combustion: 0.42, mech: 0.22, turbo: 0.20, gear: 0.14, rumble: 0.60 },
    lp_hz: 1900, hp_hz: 32, distance_m: 2.0, reverb: 0.25 },
  exterior_7m: { gains: { exhaust: 0.85, intake: 0.30, combustion: 0.55, mech: 0.35, turbo: 0.30, gear: 0.22, rumble: 0.35 },
    lp_hz: 6500, hp_hz: 60, distance_m: 7.0, reverb: 0.35 },
};

/** What the synth reads from an EngineSpec (the grids' "spec" carries all of it). */
export interface SoundSpec {
  rated_rpm?: number;
  geom: { displacement: number };
  air: {
    muffler_volume: number; muffler_length: number; exhaust_pipe_length: number;
    runner_length_int: number; airbox_neck_area: number; airbox_neck_len: number; airbox_volume: number;
  };
  turbo: { enabled: boolean; comp_blades: number };
  crank_gear_teeth: number; cam_gear_teeth: number; injpump_gear_teeth: number;
}

type Arr = Float64Array;
const zeros = (n: number): Arr => new Float64Array(n);
const map = (a: Arr, f: (v: number, i: number) => number): Arr => {
  const y = new Float64Array(a.length);
  for (let i = 0; i < a.length; i++) y[i] = f(a[i]!, i);
  return y;
};
/** numpy.cumsum: sequential. */
const cumsum = (a: Arr): Arr => {
  const y = new Float64Array(a.length);
  let s = 0.0;
  for (let i = 0; i < a.length; i++) { s = i === 0 ? a[0]! : s + a[i]!; y[i] = s; }
  return y;
};
const mean = (a: Arr): number => { let s = 0.0; for (const v of a) s += v; return s / a.length; };
/** Python's float %: the sign of the divisor. */
const pymod = (x: number, m: number): number => { const r = x % m; return r !== 0 && (r < 0) !== (m < 0) ? r + m : r; };

export class LiveSynth {
  readonly fs: number;
  readonly dtheta: number;
  readonly n_src: number;
  private readonly ref_mdot: number;
  private readonly ref_Pb: number;
  private readonly ref_dpdt = 5.0e9;
  private readonly ref_vseat = 0.10;
  private readonly ref_turbo = 1.2e5;
  private readonly ref_boost: number;          // FINDING-022
  private readonly n_hiss: NoiseCursor;
  private readonly n_whoosh: NoiseCursor;
  private readonly n_rumble: NoiseCursor;
  src: Sources | null = null;
  private target: Sources | null = null;
  theta = 0.0;               // crank angle, unwrapped [deg]
  rpm: number | null = null;
  private ph_t = 0.0;
  private ph_bp = 0.0;
  // the signal chain
  private exh_lp!: Chain; private exh_hp!: Chain; private exh_turb!: Chain | null;
  private exh_comb: Comb | null = null; private exh_peaks: Biquad[] = [];
  private exh_q0: number | null = null; private int_q0: number | null = null;
  private int_comb!: Comb; private int_helm!: Biquad; private hiss_bp!: Chain;
  private knock!: [Biquad, number, number][];
  private tick!: [Biquad, Biquad]; private injr!: [Biquad, Biquad]; private slapr!: [Biquad, Biquad];
  private whoosh_bp!: Chain; private rumble_bp!: Chain;
  private norm!: Record<string, Norm>;
  mic!: Mic;
  micName!: string;
  private out_lp!: Chain; private out_hp!: Chain;
  private rev_taps!: number[]; private readonly rev_gains = [0.42, 0.33, 0.26, 0.18];
  private rev!: Delay; private rev_lp!: Chain;
  last_parts: Record<Part, Arr> | null = null;

  constructor(readonly spec: SoundSpec, mic = "exterior_7m", fs = FS, noise_seed = 12345, dtheta = 0.5) {
    this.fs = fs; this.dtheta = dtheta;
    this.n_src = Math.round(720.0 / dtheta);
    const g = spec.geom;
    const rated = Math.max(spec.rated_rpm ?? 2000.0, 1.0);
    const pr = spec.turbo.enabled ? 2.2 : 1.0;
    // acoustics.EngineSound's physical reference levels (FINDING-004)
    this.ref_mdot = Math.max(g.displacement * (rated / 120.0) * 1.19 * 1.15 * pr, 1e-6);
    this.ref_Pb = Math.max(0.5 * 1.1e5 * g.displacement * (rated / 120.0), 1.0);
    this.ref_boost = Math.max(pr - 1.0, 1e-6);
    const table = noiseTable(noise_seed);
    this.n_hiss = new NoiseCursor(table, 0);
    this.n_whoosh = new NoiseCursor(table, Math.floor(NOISE_N / 3));
    this.n_rumble = new NoiseCursor(table, Math.floor(2 * NOISE_N / 3));
    this.build(mic);
  }

  private build(mic: string): void {
    const s = this.spec, a = s.air;
    const V_m = Math.max(a.muffler_volume, 1e-4);
    this.exh_lp = butter("low", 900.0 * (0.02 / V_m) ** 0.25, 2);
    this.exh_hp = butter("high", 35.0, 1);
    this.exh_turb = s.turbo.enabled ? butter("low", 1400.0, 1) : null;
    this.int_comb = new Comb(4.0 * a.runner_length_int / C_AIR_STP, -0.45);
    const A_n = a.airbox_neck_area, L_n = a.airbox_neck_len, V_b = a.airbox_volume;
    const f_h = C_AIR_STP / (2 * Math.PI) * Math.sqrt(
      A_n / Math.max(V_b * (L_n + 0.85 * Math.sqrt(A_n / Math.PI)), 1e-9));
    this.int_helm = new Biquad(resonatorBa(Math.max(f_h, 25.0), 3.5, 2.0));
    this.hiss_bp = butter("band", [700.0, 6500.0], 2);
    this.knock = ([[680.0, 11.0, 1.00], [1450.0, 14.0, 0.72], [2350.0, 16.0, 0.55],
                   [3600.0, 18.0, 0.42], [5200.0, 20.0, 0.26]] as const)
      .map(([f0, Q, gn]) => [new Biquad(resonatorBa(f0, Q, 1.0)), f0, gn]);
    this.tick = [new Biquad(resonatorBa(3100.0, 26.0)), new Biquad(resonatorBa(5400.0, 30.0))];
    this.injr = [new Biquad(resonatorBa(4200.0, 34.0)), new Biquad(resonatorBa(6800.0, 36.0))];
    this.slapr = [new Biquad(resonatorBa(900.0, 9.0)), new Biquad(resonatorBa(1750.0, 12.0))];
    this.whoosh_bp = butter("band", [1200.0, 9000.0], 2);
    this.rumble_bp = butter("band", [40.0, 480.0], 2);
    this.norm = {};
    for (const k of ["exh", "int", "hiss", "exc", "knock", "tick", "inj", "slap", "whoosh", "turbo", "gear", "rumble"])
      this.norm[k] = new Norm();
    this.setMic(mic);
  }

  setMic(mic: string): void {
    const m = MICS[mic];
    if (!m) throw new Error(`unknown microphone ${mic}`);
    this.mic = m; this.micName = mic;
    this.out_lp = butter("low", m.lp_hz, 3);
    this.out_hp = butter("high", m.hp_hz, 2);
    this.rev_taps = [0.021, 0.037, 0.053, 0.079].map(d => Math.trunc(d * this.fs));
    this.rev = new Delay(Math.max(...this.rev_taps));
    this.rev_lp = butter("low", 2500.0, 1);
  }

  setSources(src: Sources): void {
    const t = { _meta: { ...src._meta } } as Sources;
    for (const k of SOURCE_KEYS) t[k] = Float64Array.from(src[k]);
    this.target = t;
    if (this.src === null) {
      const c = { _meta: { ...t._meta } } as Sources;
      for (const k of SOURCE_KEYS) c[k] = Float64Array.from(t[k]);
      this.src = c;
    }
  }

  private glide(): void {
    const a = Math.min(1.0, BLOCK / (SRC_TAU * this.fs));
    const s = this.src!, t = this.target!;
    // in place: the audio thread must not allocate 70 KB a block
    for (const k of SOURCE_KEYS) {
      const x = s[k], y = t[k];
      for (let i = 0; i < x.length; i++) x[i] = x[i]! + a * (y[i]! - x[i]!);
    }
    for (const [k, v] of Object.entries(t._meta)) s._meta[k] = s._meta[k]! + a * (v - s._meta[k]!);
  }

  private sample(name: SourceKey, theta: Arr): Arr {
    const s = this.src![name], n = this.n_src;
    return map(theta, th => {
      const u = th / this.dtheta;
      let i = Math.floor(u);
      const f = u - i;
      i = ((i % n) + n) % n;
      const j = (i + 1) % n;
      return s[i]! + (s[j]! - s[i]!) * f;
    });
  }

  /** The next BLOCK samples. `live`: boost, turbo_rpm, load, Pb, skirt_clr,
   *  v_seating from the real-time loop (each optional). */
  block(rpm: number, live: Record<string, number> | null = null, running = true): Arr {
    const n = BLOCK, fs = this.fs, s = this.spec;
    this.glide();
    const meta: Record<string, number> = { ...this.src!._meta, ...(live ?? {}) };
    const r0 = this.rpm ?? rpm;
    this.rpm = rpm;
    const rpm_s = new Float64Array(n);
    for (let i = 0; i < n; i++) rpm_s[i] = Math.max(r0 + (rpm - r0) * (i + 1) / n, 50.0);
    const S = cumsum(map(rpm_s, r => 6.0 * r / fs));
    const theta_u = map(S, v => this.theta + v);
    this.theta = pymod(theta_u[n - 1]!, 720.0 * 3600.0);
    const theta = map(theta_u, v => pymod(v, 720.0));
    if (!running) return zeros(n);
    const rpmRef = Math.max(meta["rpm"]!, 1.0);
    const spd = map(rpm_s, r => r / rpmRef);
    const N = this.norm;

    // ---- exhaust ----
    const c_exh = Math.sqrt(1.4 * 287.0 * Math.max(meta["T_exh"]!, 400.0));
    if (this.exh_comb === null) {
      this.exh_comb = new Comb(2.0 * s.air.exhaust_pipe_length / c_exh, -0.62);
      const f_hx = c_exh / (2.0 * Math.max(s.air.muffler_length, 0.25));
      this.exh_peaks = [1, 3].map(kk => new Biquad(peakBa(Math.min(kk * f_hx, 0.4 * fs), 2.2, -14.0)));
      this.exh_q0 = null;
    }
    const q = map(this.sample("exh_flow", theta), (v, i) => v * spd[i]!);
    let prev = this.exh_q0 ?? q[0]!;
    const dq = map(q, (v, i) => (v - (i === 0 ? prev : q[i - 1]!)) * fs);
    this.exh_q0 = q[n - 1]!;
    let y = this.exh_comb.process(dq);
    y = this.exh_lp.process(y);
    for (const b of this.exh_peaks) y = b.process(y);
    y = this.exh_hp.process(y);
    if (this.exh_turb) y = this.exh_turb.process(y);
    const kExh = (meta["mdot_air"]! / this.ref_mdot) ** 1.5;
    const exhaust = map(N["exh"]!.apply(y), v => v * kExh);

    // ---- intake ----
    const qi = map(this.sample("int_flow", theta), (v, i) => v * spd[i]!);
    prev = this.int_q0 ?? qi[0]!;
    const dqi = map(qi, (v, i) => (v - (i === 0 ? prev : qi[i - 1]!)) * fs);
    this.int_q0 = qi[n - 1]!;
    const yc = this.int_comb.process(dqi);
    const yh = this.int_helm.process(yc);
    const yi = map(yh, (v, i) => v + 0.5 * yc[i]!);
    let hiss = this.hiss_bp.process(this.n_hiss.take(n));
    const mdot = meta["mdot_air"]!;
    hiss = map(hiss, (v, i) => v * (mdot * spd[i]! ** 1.5) ** 1.5 * 4.0);
    const ni = N["int"]!.apply(yi), nh = N["hiss"]!.apply(hiss);
    const kInt = (mdot / this.ref_mdot) ** 1.5;          // FINDING-022
    const intake = map(ni, (v, i) => (v + 0.45 * nh[i]!) * kInt);

    // ---- combustion ----
    const dp = this.sample("dpdth", theta);
    const exc = N["exc"]!.apply(map(dp, (v, i) => v * (rpm_s[i]! / 60.0 * 360.0)));
    const sharp = Math.min(3.0, meta["dpdt_max"]! / 5.0e9);
    let knock = zeros(n);
    for (const [bq, f0, gn] of this.knock) {
      const r = bq.process(exc), k = gn * (1.0 + sharp * (f0 / 2000.0) ** 1.1);
      knock = map(knock, (v, i) => v + r[i]! * k);
    }
    const kComb = meta["dpdt_max"]! / this.ref_dpdt;
    const combustion = map(N["knock"]!.apply(knock), v => v * kComb);

    // ---- mechanical impulses ----
    const pair = ([p, q2]: [Biquad, Biquad], x: Arr, g: number): Arr => {
      const a = p.process(x), b = q2.process(x);
      return map(a, (v, i) => v + g * b[i]!);
    };
    const tk = pair(this.tick, this.sample("valve", theta), 0.6);
    const ij = pair(this.injr, this.sample("inj", theta), 0.5);
    const sl = pair(this.slapr, this.sample("slap", theta), 0.7);
    const a_tick = (Math.max(meta["v_seating"]!, 1e-6) / this.ref_vseat) ** 2;
    const a_slap = (Math.max(meta["skirt_clr"]!, 1e-9) / 30e-6) ** 0.6;
    const nt = N["tick"]!.apply(tk), nj = N["inj"]!.apply(ij), ns = N["slap"]!.apply(sl);
    const ks = 0.9 * a_slap;
    const mech = map(nt, (v, i) => a_tick * v + 0.75 * nj[i]! + ks * ns[i]!);

    // ---- turbocharger ----
    let turbo: Arr;
    if (s.turbo.enabled && meta["turbo_rpm"]! > 1000.0) {
      const tr = meta["turbo_rpm"]!;
      const f_shaft = map(spd, v => tr * (0.35 + 0.65 * v) / 60.0);
      const twoPi = 2 * Math.PI;
      const cs = cumsum(map(f_shaft, v => v / fs));
      const ph = map(cs, v => this.ph_t + twoPi * v);
      this.ph_t = pymod(ph[n - 1]!, twoPi);
      let whine = zeros(n);
      const mf = mean(f_shaft);
      for (const [kk, amp] of [[1, 1.0], [2, 0.45], [3, 0.22]] as const) {
        if (kk * mf < 0.45 * fs) whine = map(whine, (v, i) => v + amp * Math.sin(kk * ph[i]! + 0.7 * kk));
      }
      const blades = s.turbo.comp_blades;
      const f_bp = map(f_shaft, v => v * blades);
      const cb = cumsum(map(f_bp, v => v / fs));
      const ph_bp = map(cb, v => this.ph_bp + twoPi * v);
      this.ph_bp = pymod(ph_bp[n - 1]!, twoPi);
      if (mean(f_bp) < 0.42 * fs) whine = map(whine, (v, i) => v + 0.30 * Math.sin(ph_bp[i]!));
      const wh = N["whoosh"]!.apply(this.whoosh_bp.process(this.n_whoosh.take(n)));
      const boost = meta["boost"]!;
      const yt = map(whine, (v, i) => 0.55 * v + 0.45 * wh[i]!);
      const kT = (tr / this.ref_turbo) ** 2, rb = this.ref_boost;
      // FINDING-022: the boost term after the normalisation
      turbo = map(N["turbo"]!.apply(yt), (v, i) => v * kT * Math.max((boost - 1.0) * spd[i]! ** 2, 0.0) / rb);
    } else {
      turbo = zeros(n);
    }

    // ---- gear train (locked to the crank) ----
    let gear = zeros(n);
    const f_crank = map(rpm_s, r => r / 60.0);
    for (const [teeth, ratio, amp] of [[s.crank_gear_teeth, 1.0, 1.0], [s.cam_gear_teeth, 0.5, 0.7],
                                       [s.injpump_gear_teeth, 0.5, 0.5]] as const) {
      if (mean(map(f_crank, v => teeth * v * ratio)) < 0.45 * fs) {
        const c = 2 * Math.PI * teeth * ratio;
        gear = map(gear, (v, i) => {
          const ph_g = c * theta_u[i]! / 360.0;
          return v + amp * (Math.sin(ph_g) + 0.35 * Math.sin(2 * ph_g + 1.1));
        });
      }
    }
    const kG = 0.3 + 0.7 * meta["load"]!;
    const gearOut = map(N["gear"]!.apply(gear), v => v * kG);

    // ---- rumble: boundary-friction noise, firing-modulated ----
    const rum = this.rumble_bp.process(this.n_rumble.take(n));
    const kR = (Math.max(meta["Pb"]!, 1e-9) / this.ref_Pb) ** 0.5;
    const rumble = map(N["rumble"]!.apply(map(rum, (v, i) => v * (0.6 + 0.4 * Math.abs(dp[i]!)))), v => v * kR);

    // ---- the microphone ----
    const out: Record<Part, Arr> = { exhaust, intake, combustion, mech, turbo, gear: gearOut, rumble };
    const m = this.mic;
    let mix = zeros(n);
    for (const [key, gn] of Object.entries(m.gains) as [Part, number][]) {
      const p = out[key];
      mix = map(mix, (v, i) => v + gn * p[i]!);
    }
    mix = this.out_lp.process(mix);
    mix = this.out_hp.process(mix);
    const dist = Math.max(1.0, m.distance_m) ** 0.55;
    mix = map(mix, v => v / dist);
    const taps = this.rev.taps(mix, this.rev_taps);
    if (m.reverb > 0.0) {
      let r = zeros(n);
      taps.forEach((t, k) => { const g = this.rev_gains[k]!; r = map(r, (v, i) => v + g * t[i]!); });
      const rl = this.rev_lp.process(r);
      mix = map(mix, (v, i) => v + m.reverb * rl[i]!);
    }
    this.last_parts = out;
    const th11 = Math.tanh(1.1);
    return map(mix, v => Math.tanh(1.1 * (v * SPL_CAL)) / th11);
  }
}
