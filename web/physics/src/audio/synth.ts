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
/** numpy.cumsum, sequential, into y. */
const cumsumInto = (a: Arr, y: Arr): void => {
  let s = 0.0;
  for (let i = 0; i < a.length; i++) { s = i === 0 ? a[0]! : s + a[i]!; y[i] = s; }
};
const mean = (a: Arr): number => { let s = 0.0; for (let i = 0; i < a.length; i++) s += a[i]!; return s / a.length; };
/** Python's float %: the sign of the divisor. */
const pymod = (x: number, m: number): number => { const r = x % m; return r !== 0 && (r < 0) !== (m < 0) ? r + m : r; };
const PARTS: readonly Part[] = ["exhaust", "intake", "combustion", "mech", "turbo", "gear", "rumble"];

/** Every buffer one block needs, allocated once: the audio thread must not
 *  allocate (garbage collection there is an audible glitch). */
class Scratch {
  private readonly n: number;
  constructor(n: number) { this.n = n; }
  private readonly pool = new Map<string, Arr>();
  get(name: string): Arr {
    let a = this.pool.get(name);
    if (!a) { a = new Float64Array(this.n); this.pool.set(name, a); }
    return a;
  }
}

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
  private readonly sc = new Scratch(BLOCK);
  private readonly meta: Record<string, number> = {};
  private readonly parts: Record<Part, Arr>;
  private readonly taps: Arr[];
  /** Each source's last block. Its arrays are reused by the next block. */
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
    this.parts = Object.fromEntries(PARTS.map(p => [p, new Float64Array(BLOCK)])) as Record<Part, Arr>;
    this.taps = [0, 1, 2, 3].map(() => new Float64Array(BLOCK));
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

  /** The operating point's sources; copied into buffers kept from the first
   *  call, so the 20 Hz updates allocate nothing. */
  setSources(src: Sources): void {
    const copy = (into: Sources | null): Sources => {
      const t = into ?? ({ _meta: {} } as Sources);
      for (const k of SOURCE_KEYS) {
        if (into && t[k].length === src[k].length) t[k].set(src[k]);
        else t[k] = Float64Array.from(src[k]);
      }
      for (const k in src._meta) t._meta[k] = src._meta[k]!;
      return t;
    };
    this.target = copy(this.target);
    if (this.src === null) this.src = copy(null);
  }

  private glide(): void {
    const a = Math.min(1.0, BLOCK / (SRC_TAU * this.fs));
    const s = this.src!, t = this.target!;
    for (const k of SOURCE_KEYS) {
      const x = s[k], y = t[k];
      for (let i = 0; i < x.length; i++) x[i] = x[i]! + a * (y[i]! - x[i]!);
    }
    for (const k in t._meta) s._meta[k] = s._meta[k]! + a * (t._meta[k]! - s._meta[k]!);
  }

  private sampleInto(name: SourceKey, theta: Arr, out: Arr): void {
    const s = this.src![name], n = this.n_src, dth = this.dtheta;
    for (let k = 0; k < theta.length; k++) {
      const u = theta[k]! / dth;
      let i = Math.floor(u);
      const f = u - i;
      i = ((i % n) + n) % n;
      const j = (i + 1) % n;
      out[k] = s[i]! + (s[j]! - s[i]!) * f;
    }
  }

  /** The next BLOCK samples. `live`: boost, turbo_rpm, load, Pb, skirt_clr,
   *  v_seating from the real-time loop (each optional). The returned array
   *  is reused by the next call: copy it out first. */
  block(rpm: number, live: Record<string, number> | null = null, running = true): Arr {
    const n = BLOCK, fs = this.fs, s = this.spec, sc = this.sc;
    this.glide();
    const meta = this.meta;
    for (const k in this.src!._meta) meta[k] = this.src!._meta[k]!;
    if (live) for (const k in live) meta[k] = live[k]!;
    const r0 = this.rpm ?? rpm;
    this.rpm = rpm;
    const rpm_s = sc.get("rpm_s"), inc = sc.get("inc"), S = sc.get("S"), theta_u = sc.get("theta_u"), theta = sc.get("theta");
    for (let i = 0; i < n; i++) rpm_s[i] = Math.max(r0 + (rpm - r0) * (i + 1) / n, 50.0);
    for (let i = 0; i < n; i++) inc[i] = 6.0 * rpm_s[i]! / fs;
    cumsumInto(inc, S);
    for (let i = 0; i < n; i++) theta_u[i] = this.theta + S[i]!;
    this.theta = pymod(theta_u[n - 1]!, 720.0 * 3600.0);
    for (let i = 0; i < n; i++) theta[i] = pymod(theta_u[i]!, 720.0);
    const out = sc.get("out");
    if (!running) { out.fill(0); return out; }
    const rpmRef = Math.max(meta["rpm"]!, 1.0);
    const spd = sc.get("spd");
    for (let i = 0; i < n; i++) spd[i] = rpm_s[i]! / rpmRef;
    const N = this.norm, P = this.parts;

    // ---- exhaust ----
    const c_exh = Math.sqrt(1.4 * 287.0 * Math.max(meta["T_exh"]!, 400.0));
    if (this.exh_comb === null) {
      this.exh_comb = new Comb(2.0 * s.air.exhaust_pipe_length / c_exh, -0.62);
      const f_hx = c_exh / (2.0 * Math.max(s.air.muffler_length, 0.25));
      this.exh_peaks = [1, 3].map(kk => new Biquad(peakBa(Math.min(kk * f_hx, 0.4 * fs), 2.2, -14.0)));
      this.exh_q0 = null;
    }
    const q = sc.get("q"), dq = sc.get("dq"), y = sc.get("y");
    this.sampleInto("exh_flow", theta, q);
    for (let i = 0; i < n; i++) q[i] = q[i]! * spd[i]!;
    let prev = this.exh_q0 ?? q[0]!;
    for (let i = 0; i < n; i++) dq[i] = (q[i]! - (i === 0 ? prev : q[i - 1]!)) * fs;
    this.exh_q0 = q[n - 1]!;
    this.exh_comb.processInto(dq, y);
    this.exh_lp.processInto(y, y);
    for (const b of this.exh_peaks) b.processInto(y, y);
    this.exh_hp.processInto(y, y);
    if (this.exh_turb) this.exh_turb.processInto(y, y);
    const kExh = (meta["mdot_air"]! / this.ref_mdot) ** 1.5;
    const exhaust = P.exhaust;
    N["exh"]!.applyInto(y, exhaust);
    for (let i = 0; i < n; i++) exhaust[i] = exhaust[i]! * kExh;

    // ---- intake ----
    const qi = sc.get("qi"), dqi = sc.get("dqi"), yc = sc.get("yc"), yh = sc.get("yh"), yi = sc.get("yi");
    this.sampleInto("int_flow", theta, qi);
    for (let i = 0; i < n; i++) qi[i] = qi[i]! * spd[i]!;
    prev = this.int_q0 ?? qi[0]!;
    for (let i = 0; i < n; i++) dqi[i] = (qi[i]! - (i === 0 ? prev : qi[i - 1]!)) * fs;
    this.int_q0 = qi[n - 1]!;
    this.int_comb.processInto(dqi, yc);
    this.int_helm.processInto(yc, yh);
    for (let i = 0; i < n; i++) yi[i] = yh[i]! + 0.5 * yc[i]!;
    const hiss = sc.get("hiss");
    this.n_hiss.takeInto(hiss);
    this.hiss_bp.processInto(hiss, hiss);
    const mdot = meta["mdot_air"]!;
    for (let i = 0; i < n; i++) hiss[i] = hiss[i]! * (mdot * spd[i]! ** 1.5) ** 1.5 * 4.0;
    const ni = sc.get("ni"), nh = sc.get("nh");
    N["int"]!.applyInto(yi, ni);
    N["hiss"]!.applyInto(hiss, nh);
    const kInt = (mdot / this.ref_mdot) ** 1.5;          // FINDING-022
    const intake = P.intake;
    for (let i = 0; i < n; i++) intake[i] = (ni[i]! + 0.45 * nh[i]!) * kInt;

    // ---- combustion ----
    const dp = sc.get("dp"), exc = sc.get("exc"), knock = sc.get("knock"), kr = sc.get("kr");
    this.sampleInto("dpdth", theta, dp);
    for (let i = 0; i < n; i++) exc[i] = dp[i]! * (rpm_s[i]! / 60.0 * 360.0);
    N["exc"]!.applyInto(exc, exc);
    const sharp = Math.min(3.0, meta["dpdt_max"]! / 5.0e9);
    knock.fill(0);
    for (const [bq, f0, gn] of this.knock) {
      bq.processInto(exc, kr);
      const k = gn * (1.0 + sharp * (f0 / 2000.0) ** 1.1);
      for (let i = 0; i < n; i++) knock[i] = knock[i]! + kr[i]! * k;
    }
    const kComb = meta["dpdt_max"]! / this.ref_dpdt;
    const combustion = P.combustion;
    N["knock"]!.applyInto(knock, combustion);
    for (let i = 0; i < n; i++) combustion[i] = combustion[i]! * kComb;

    // ---- mechanical impulses ----
    const pa = sc.get("pa"), pb = sc.get("pb");
    const pairInto = ([p, q2]: [Biquad, Biquad], x: Arr, g: number, into: Arr): void => {
      p.processInto(x, pa);
      q2.processInto(x, pb);
      for (let i = 0; i < n; i++) into[i] = pa[i]! + g * pb[i]!;
    };
    const src = sc.get("src"), tk = sc.get("tk"), ij = sc.get("ij"), sl = sc.get("sl");
    this.sampleInto("valve", theta, src); pairInto(this.tick, src, 0.6, tk);
    this.sampleInto("inj", theta, src); pairInto(this.injr, src, 0.5, ij);
    this.sampleInto("slap", theta, src); pairInto(this.slapr, src, 0.7, sl);
    const a_tick = (Math.max(meta["v_seating"]!, 1e-6) / this.ref_vseat) ** 2;
    const a_slap = (Math.max(meta["skirt_clr"]!, 1e-9) / 30e-6) ** 0.6;
    N["tick"]!.applyInto(tk, tk); N["inj"]!.applyInto(ij, ij); N["slap"]!.applyInto(sl, sl);
    const ks = 0.9 * a_slap;
    const mech = P.mech;
    for (let i = 0; i < n; i++) mech[i] = a_tick * tk[i]! + 0.75 * ij[i]! + ks * sl[i]!;

    // ---- turbocharger ----
    const turbo = P.turbo;
    if (s.turbo.enabled && meta["turbo_rpm"]! > 1000.0) {
      const tr = meta["turbo_rpm"]!;
      const f_shaft = sc.get("f_shaft"), cs = sc.get("cs"), ph = sc.get("ph"), whine = sc.get("whine");
      for (let i = 0; i < n; i++) f_shaft[i] = tr * (0.35 + 0.65 * spd[i]!) / 60.0;
      const twoPi = 2 * Math.PI;
      for (let i = 0; i < n; i++) inc[i] = f_shaft[i]! / fs;
      cumsumInto(inc, cs);
      for (let i = 0; i < n; i++) ph[i] = this.ph_t + twoPi * cs[i]!;
      this.ph_t = pymod(ph[n - 1]!, twoPi);
      whine.fill(0);
      const mf = mean(f_shaft);
      for (const [kk, amp] of [[1, 1.0], [2, 0.45], [3, 0.22]] as const) {
        if (kk * mf < 0.45 * fs) for (let i = 0; i < n; i++) whine[i] = whine[i]! + amp * Math.sin(kk * ph[i]! + 0.7 * kk);
      }
      const blades = s.turbo.comp_blades;
      const f_bp = sc.get("f_bp"), phb = sc.get("phb");
      for (let i = 0; i < n; i++) f_bp[i] = f_shaft[i]! * blades;
      for (let i = 0; i < n; i++) inc[i] = f_bp[i]! / fs;
      cumsumInto(inc, cs);
      for (let i = 0; i < n; i++) phb[i] = this.ph_bp + twoPi * cs[i]!;
      this.ph_bp = pymod(phb[n - 1]!, twoPi);
      if (mean(f_bp) < 0.42 * fs) for (let i = 0; i < n; i++) whine[i] = whine[i]! + 0.30 * Math.sin(phb[i]!);
      const wh = sc.get("wh");
      this.n_whoosh.takeInto(wh);
      this.whoosh_bp.processInto(wh, wh);
      N["whoosh"]!.applyInto(wh, wh);
      const boost = meta["boost"]!;
      for (let i = 0; i < n; i++) whine[i] = 0.55 * whine[i]! + 0.45 * wh[i]!;
      const kT = (tr / this.ref_turbo) ** 2, rb = this.ref_boost;
      // FINDING-022: the boost term after the normalisation
      N["turbo"]!.applyInto(whine, turbo);
      for (let i = 0; i < n; i++) turbo[i] = turbo[i]! * kT * Math.max((boost - 1.0) * spd[i]! ** 2, 0.0) / rb;
    } else {
      turbo.fill(0);
    }

    // ---- gear train (locked to the crank) ----
    const gear = sc.get("gear"), f_crank = sc.get("f_crank");
    gear.fill(0);
    for (let i = 0; i < n; i++) f_crank[i] = rpm_s[i]! / 60.0;
    for (const [teeth, ratio, amp] of [[s.crank_gear_teeth, 1.0, 1.0], [s.cam_gear_teeth, 0.5, 0.7],
                                       [s.injpump_gear_teeth, 0.5, 0.5]] as const) {
      for (let i = 0; i < n; i++) inc[i] = teeth * f_crank[i]! * ratio;
      if (mean(inc) < 0.45 * fs) {
        const c = 2 * Math.PI * teeth * ratio;
        for (let i = 0; i < n; i++) {
          const ph_g = c * theta_u[i]! / 360.0;
          gear[i] = gear[i]! + amp * (Math.sin(ph_g) + 0.35 * Math.sin(2 * ph_g + 1.1));
        }
      }
    }
    const kG = 0.3 + 0.7 * meta["load"]!;
    const gearOut = P.gear;
    N["gear"]!.applyInto(gear, gearOut);
    for (let i = 0; i < n; i++) gearOut[i] = gearOut[i]! * kG;

    // ---- rumble: boundary-friction noise, firing-modulated ----
    const rum = sc.get("rum");
    this.n_rumble.takeInto(rum);
    this.rumble_bp.processInto(rum, rum);
    const kR = (Math.max(meta["Pb"]!, 1e-9) / this.ref_Pb) ** 0.5;
    for (let i = 0; i < n; i++) rum[i] = rum[i]! * (0.6 + 0.4 * Math.abs(dp[i]!));
    const rumble = P.rumble;
    N["rumble"]!.applyInto(rum, rumble);
    for (let i = 0; i < n; i++) rumble[i] = rumble[i]! * kR;

    // ---- the microphone ----
    const m = this.mic, mix = sc.get("mix");
    mix.fill(0);
    for (const key in m.gains) {
      const gn = m.gains[key as Part], p = P[key as Part];
      for (let i = 0; i < n; i++) mix[i] = mix[i]! + gn * p[i]!;
    }
    this.out_lp.processInto(mix, mix);
    this.out_hp.processInto(mix, mix);
    const dist = Math.max(1.0, m.distance_m) ** 0.55;
    for (let i = 0; i < n; i++) mix[i] = mix[i]! / dist;
    this.rev.tapsInto(mix, this.rev_taps, this.taps);
    if (m.reverb > 0.0) {
      const r = sc.get("r");
      r.fill(0);
      this.taps.forEach((t, k) => { const g = this.rev_gains[k]!; for (let i = 0; i < n; i++) r[i] = r[i]! + g * t[i]!; });
      this.rev_lp.processInto(r, r);
      for (let i = 0; i < n; i++) mix[i] = mix[i]! + m.reverb * r[i]!;
    }
    this.last_parts = P;
    const th11 = Math.tanh(1.1);
    for (let i = 0; i < n; i++) out[i] = Math.tanh(1.1 * (mix[i]! * SPL_CAL)) / th11;
    return out;
  }
}
