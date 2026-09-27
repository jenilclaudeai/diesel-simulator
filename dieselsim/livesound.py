"""
livesound.py -- the engine sound, synthesised block by block in real time.

The streaming form of acoustics.EngineSound.render (the offline reference):
the same sources, filters, physical source levels (FINDINGs 003, 004, 017)
and microphone mixes, computed in blocks of BLOCK samples with every filter
and delay line carrying its state, so it can run inside an audio callback
(play.py) or an AudioWorklet (web/physics/src/audio -- the TypeScript port,
held to this file sample for sample).

What cannot stream is replaced by its causal equivalent, stated here:
  * render() normalises each source's SHAPE by the std of the whole render;
    here a one-pole mean-square tracker per source (time constant NORM_TAU)
    does it, seeded from the first block.
  * render() divides the rumble's firing modulation by its maximum over the
    render; here by the maximum over the 720-degree source waveform, which
    is known in advance.
  * noise comes from a fixed Gaussian table filled by a 32-bit generator
    (mulberry32 + Box-Muller) instead of numpy's -- identical in TypeScript
    -- read by three independent cursors.

FINDING-021: play.py's LiveSound was an older copy of the acoustics model
that never received FINDINGs 003, 004 and 017; this replaces it.

Pure mode (PURE = True, or no scipy) runs every recurrence as a Python loop
in one fixed operation order -- the reference the TypeScript port matches.
Otherwise scipy.signal.lfilter runs the same recurrences, ~1e-15 apart.
numpy only at import.
"""
from __future__ import annotations

import cmath
import math

import numpy as np

from .acoustics import C_AIR_STP, MICS, SPL_CAL

FS = 44100
BLOCK = 128                 # the AudioWorklet render quantum
NORM_TAU = 0.3              # s, the shape-normalisation trackers
SRC_TAU = 0.05              # s, source waveforms glide to a new operating point
NOISE_N = 1 << 18           # Gaussian table: ~6 s at 44.1 kHz per cursor
SOURCE_KEYS = ("exh_flow", "int_flow", "dpdth", "inj", "valve", "slap")
PURE = False


def _scipy_signal():
    if PURE:
        return None
    try:
        from scipy import signal
        return signal
    except ImportError:      # numpy-only runtimes: the pure recurrences
        return None


# ==========================================================================
# Butterworth design without scipy: analog prototype, band transform,
# bilinear transform, second-order sections (scipy.signal.butter's method).
# ==========================================================================
def butter_sos(order, wn, kind):
    """wn normalised to Nyquist (a pair for "band"). Returns [(b, a), ...]."""
    poles = [cmath.exp(1j * math.pi * (2 * k + order + 1) / (2 * order)) for k in range(order)]
    zeros, gain = [], 1.0
    warp = lambda w: 4.0 * math.tan(math.pi * w / 2.0)   # noqa: E731  (fs = 2)
    if kind == "low":
        wo = warp(wn)
        poles = [p * wo for p in poles]
        gain = wo ** order
    elif kind == "high":
        wo = warp(wn)
        prod = 1.0 + 0j
        for p in poles:
            prod *= -p
        gain = (1.0 / prod).real
        poles = [wo / p for p in poles]
        zeros = [0j] * order
    elif kind == "band":
        w1, w2 = warp(wn[0]), warp(wn[1])
        bw, wo = w2 - w1, math.sqrt(w1 * w2)
        new = []
        for p in poles:
            h = p * bw / 2.0
            r = cmath.sqrt(h * h - wo * wo)
            new += [h + r, h - r]
        poles = new
        zeros = [0j] * order
        gain = bw ** order
    else:
        raise ValueError(kind)
    # bilinear transform, fs = 2
    num, den = 1.0 + 0j, 1.0 + 0j
    for z in zeros:
        num *= 4.0 - z
    for p in poles:
        den *= 4.0 - p
    gain *= (num / den).real
    zd = [(4.0 + z) / (4.0 - z) for z in zeros] + [-1.0 + 0j] * (len(poles) - len(zeros))
    pd = [(4.0 + p) / (4.0 - p) for p in poles]
    # sections: one per conjugate pair (upper half plane), plus a real pole
    upper = sorted((p for p in pd if p.imag > 1e-12), key=lambda p: abs(p))
    real = [p for p in pd if abs(p.imag) <= 1e-12]
    zr = sorted((z.real for z in zd), reverse=True)     # +1 (highpass) before -1 (lowpass)
    sos = []
    for p in upper:
        z1, z2 = zr.pop(0), zr.pop(0)
        sos.append(([1.0, -(z1 + z2), z1 * z2], [1.0, -2.0 * p.real, abs(p) ** 2]))
    for p in real:
        z1 = zr.pop(0)
        sos.append(([1.0, -z1, 0.0], [1.0, -p.real, 0.0]))
    b0, a0 = sos[0]
    sos[0] = ([gain * c for c in b0], a0)
    return sos


def resonator_ba(f0, Q, gain=1.0, fs=FS):
    """acoustics._resonator's damped structural mode."""
    f0 = min(f0, 0.45 * fs)
    r = math.exp(-math.pi * f0 / (Q * fs))
    th = 2 * math.pi * f0 / fs
    return [gain * (1 - r), 0.0, -gain * (1 - r) * r], [1.0, -2 * r * math.cos(th), r * r]


def peak_ba(f0, Q, gain_db, fs=FS):
    """acoustics._biquad_peak."""
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * math.pi * f0 / fs
    alpha = math.sin(w0) / (2 * Q)
    b = [1 + alpha * A, -2 * math.cos(w0), 1 - alpha * A]
    a = [1 + alpha / A, -2 * math.cos(w0), 1 - alpha / A]
    return [c / a[0] for c in b], [c / a[0] for c in a]


# ==========================================================================
# streaming filters
# ==========================================================================
class Biquad:
    """Transposed direct form II, state carried between blocks:
        y  = b0 x + z1
        z1 = b1 x + z2 - a1 y
        z2 = b2 x - a2 y
    (scipy.signal.lfilter's recurrence)."""

    def __init__(self, b, a):
        self.b0, self.b1, self.b2 = (float(v) for v in b)
        self.a1, self.a2 = float(a[1]), float(a[2])
        self.z1 = self.z2 = 0.0

    def process(self, x):
        sig = _scipy_signal()
        if sig is not None:
            y, zf = sig.lfilter([self.b0, self.b1, self.b2], [1.0, self.a1, self.a2], x,
                                zi=[self.z1, self.z2])
            self.z1, self.z2 = float(zf[0]), float(zf[1])
            return y
        b0, b1, b2, a1, a2 = self.b0, self.b1, self.b2, self.a1, self.a2
        z1, z2 = self.z1, self.z2
        y = np.empty(len(x))
        for n, xn in enumerate(x.tolist()):
            yn = b0 * xn + z1
            z1 = b1 * xn + z2 - a1 * yn
            z2 = b2 * xn - a2 * yn
            y[n] = yn
        self.z1, self.z2 = z1, z2
        return y


class Chain:
    """A cascade of biquads (a Butterworth filter's sections)."""

    def __init__(self, sos):
        self.st = [Biquad(b, a) for b, a in sos]

    def process(self, x):
        for s in self.st:
            x = s.process(x)
        return x


def butter(kind, cutoff, order, fs=FS):
    """acoustics._lowpass / _highpass / _bandpass's clamps and design."""
    ny = 0.5 * fs
    if kind == "band":
        lo = max(20.0, min(cutoff[0], 0.9 * ny))
        hi = max(lo * 1.05, min(cutoff[1], 0.95 * ny))
        return Chain(butter_sos(order, (lo / ny, hi / ny), "band"))
    if kind == "low":
        return Chain(butter_sos(order, min(cutoff, 0.95 * ny) / ny, "low"))
    return Chain(butter_sos(order, max(5.0, min(cutoff, 0.9 * ny)) / ny, "high"))


class Comb:
    """acoustics._comb_waveguide, streaming: a pipe with a reflecting end and
    a one-pole wall loss per bounce."""

    def __init__(self, delay_s, refl, fs=FS, a_lp=0.55):
        self.D = max(1, int(round(delay_s * fs)))
        self.buf = [0.0] * self.D
        self.idx = 0
        self.lp = 0.0
        self.refl, self.a_lp = refl, a_lp

    def process(self, x):
        buf, D, refl, a = self.buf, self.D, self.refl, self.a_lp
        idx, lp = self.idx, self.lp
        y = np.empty(len(x))
        for n, xn in enumerate(x.tolist()):
            d = buf[idx]
            lp = a * lp + (1.0 - a) * d
            yn = xn + refl * lp
            buf[idx] = yn
            idx += 1
            if idx == D:
                idx = 0
            y[n] = yn
        self.idx, self.lp = idx, lp
        return y


class Norm:
    """Causal shape normalisation: y / rms, with the mean square tracked by a
    one-pole filter over blocks (seeded from the first block)."""

    def __init__(self, n=BLOCK, fs=FS, tau=NORM_TAU):
        self.beta = min(1.0, n / (tau * fs))
        self.ms = -1.0

    def __call__(self, y):
        m = float(np.dot(y, y)) / len(y)
        self.ms = m if self.ms < 0.0 else self.ms + self.beta * (m - self.ms)
        return y / (math.sqrt(self.ms) + 1e-12)


class Delay:
    """A tapped delay line for the cabin/exterior reverb."""

    def __init__(self, n):
        self.buf = np.zeros(n)

    def taps(self, x, delays):
        z = np.concatenate([self.buf, x])
        n = len(x)
        out = [z[len(self.buf) - d:len(self.buf) - d + n] for d in delays]
        self.buf = z[-len(self.buf):]
        return out


# ==========================================================================
# noise
# ==========================================================================
def noise_table(seed=12345, n=NOISE_N):
    """Gaussian table from mulberry32 + Box-Muller: the same bits in Python
    and TypeScript (32-bit integer arithmetic, then libm)."""
    s = seed & 0xFFFFFFFF
    out = np.empty(n)

    def u32():
        nonlocal s
        s = (s + 0x6D2B79F5) & 0xFFFFFFFF
        t = s
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return (t ^ (t >> 14)) & 0xFFFFFFFF
    for i in range(0, n, 2):
        u1 = (u32() + 0.5) / 4294967296.0
        u2 = (u32() + 0.5) / 4294967296.0
        r = math.sqrt(-2.0 * math.log(u1))
        out[i] = r * math.cos(2.0 * math.pi * u2)
        out[i + 1] = r * math.sin(2.0 * math.pi * u2)
    return out


class NoiseCursor:
    def __init__(self, table, start):
        self.t, self.i = table, start % len(table)

    def take(self, n):
        idx = (self.i + np.arange(n)) % len(self.t)
        self.i = (self.i + n) % len(self.t)
        return self.t[idx]


# ==========================================================================
# the synthesiser
# ==========================================================================
class LiveSynth:
    """
    One engine's sound, BLOCK samples at a time.

    set_sources(src): the operating point's crank-angle source waveforms
    (SOURCE_KEYS, each on the 0.5-degree grid) and its "_meta" scalars; the
    current set glides to it with time constant SRC_TAU.
    block(rpm, live): the next BLOCK samples at `rpm` (ramped from the last
    block's), with live values from the real-time loop -- boost, turbo_rpm,
    load, Pb (boundary friction power) and skirt_clr (skirt film) -- that
    override the grid's meta, so a cold engine sounds cold (ADR-011).
    """

    def __init__(self, spec, mic="exterior_7m", fs=FS, noise_seed=12345, dtheta=0.5):
        self.spec, self.fs, self.dtheta = spec, fs, dtheta
        self.n_src = int(round(720.0 / dtheta))
        g = spec.geom
        rated = max(getattr(spec, "rated_rpm", 2000.0), 1.0)
        pr = 2.2 if spec.turbo.enabled else 1.0
        # acoustics.EngineSound's physical reference levels (FINDING-004)
        self.ref_mdot = max(g.displacement * (rated / 120.0) * 1.19 * 1.15 * pr, 1e-6)
        self.ref_Pb = max(0.5 * 1.1e5 * g.displacement * (rated / 120.0), 1.0)
        self.ref_dpdt, self.ref_vseat, self.ref_turbo = 5.0e9, 0.10, 1.2e5
        table = noise_table(noise_seed)
        self.n_hiss = NoiseCursor(table, 0)
        self.n_whoosh = NoiseCursor(table, NOISE_N // 3)
        self.n_rumble = NoiseCursor(table, 2 * NOISE_N // 3)
        self.src = None
        self.target = None
        self.theta = 0.0          # crank angle, unwrapped [deg]
        self.rpm = None
        self.ph_t = self.ph_bp = 0.0
        self._build(mic)

    # ---- the signal chain (acoustics.EngineSound.render's, streaming) ----
    def _build(self, mic):
        s, fs = self.spec, self.fs
        a = s.air
        V_m = max(a.muffler_volume, 1e-4)
        self.exh_lp = butter("low", 900.0 * (0.02 / V_m) ** 0.25, 2)
        self.exh_hp = butter("high", 35.0, 1)
        self.exh_turb = butter("low", 1400.0, 1) if s.turbo.enabled else None
        self.exh_comb = None          # built on the first block: its delay follows T_exh
        self.exh_peaks = None
        self.int_comb = Comb(4.0 * a.runner_length_int / C_AIR_STP, -0.45)
        A_n, L_n, V_b = a.airbox_neck_area, a.airbox_neck_len, a.airbox_volume
        f_h = C_AIR_STP / (2 * math.pi) * math.sqrt(
            A_n / max(V_b * (L_n + 0.85 * math.sqrt(A_n / math.pi)), 1e-9))
        self.int_helm = Biquad(*resonator_ba(max(f_h, 25.0), 3.5, 2.0))
        self.hiss_bp = butter("band", (700.0, 6500.0), 2)
        self.knock = [(Biquad(*resonator_ba(f0, Q, 1.0)), f0, gn) for f0, Q, gn in
                      ((680.0, 11.0, 1.00), (1450.0, 14.0, 0.72), (2350.0, 16.0, 0.55),
                       (3600.0, 18.0, 0.42), (5200.0, 20.0, 0.26))]
        self.tick = (Biquad(*resonator_ba(3100.0, 26.0)), Biquad(*resonator_ba(5400.0, 30.0)))
        self.injr = (Biquad(*resonator_ba(4200.0, 34.0)), Biquad(*resonator_ba(6800.0, 36.0)))
        self.slapr = (Biquad(*resonator_ba(900.0, 9.0)), Biquad(*resonator_ba(1750.0, 12.0)))
        self.whoosh_bp = butter("band", (1200.0, 9000.0), 2)
        self.rumble_bp = butter("band", (40.0, 480.0), 2)
        self.norm = {k: Norm() for k in ("exh", "int", "hiss", "exc", "knock", "tick", "inj", "slap",
                                         "whoosh", "turbo", "gear", "rumble")}
        self.set_mic(mic)

    def set_mic(self, mic):
        m = MICS[mic]
        self.mic = m
        self.out_lp = butter("low", m.lp_hz, 3)
        self.out_hp = butter("high", m.hp_hz, 2)
        self.rev_taps = [int(d * self.fs) for d in (0.021, 0.037, 0.053, 0.079)]
        self.rev_gains = (0.42, 0.33, 0.26, 0.18)
        self.rev = Delay(max(self.rev_taps))
        self.rev_lp = butter("low", 2500.0, 1)

    def set_sources(self, src):
        t = {k: np.asarray(src[k], dtype=float) for k in SOURCE_KEYS}
        t["_meta"] = dict(src["_meta"])
        self.target = t
        if self.src is None:
            self.src = {k: v.copy() for k, v in t.items() if k != "_meta"}
            self.src["_meta"] = dict(t["_meta"])

    def _glide(self):
        a = min(1.0, BLOCK / (SRC_TAU * self.fs))
        for k in SOURCE_KEYS:
            self.src[k] = self.src[k] + a * (self.target[k] - self.src[k])
        m, tm = self.src["_meta"], self.target["_meta"]
        for k, v in tm.items():
            m[k] = m[k] + a * (v - m[k])

    def _sample(self, name, theta):
        s = self.src[name]
        u = theta / self.dtheta
        i = np.floor(u).astype(np.int64)
        f = u - i
        i %= self.n_src
        j = (i + 1) % self.n_src
        return s[i] + (s[j] - s[i]) * f

    # ------------------------------------------------------------------
    def block(self, rpm, live=None, running=True):
        """The next BLOCK samples. `live`: boost, turbo_rpm, load, Pb,
        skirt_clr from the real-time loop (each optional)."""
        n, fs, s = BLOCK, self.fs, self.spec
        self._glide()
        meta = dict(self.src["_meta"])
        meta.update(live or {})
        r0 = self.rpm if self.rpm is not None else rpm
        self.rpm = rpm
        k = np.arange(1, n + 1, dtype=float)
        rpm_s = np.maximum(r0 + (rpm - r0) * k / n, 50.0)          # ramped across the block
        theta_u = self.theta + np.cumsum(6.0 * rpm_s / fs)
        self.theta = float(theta_u[-1]) % (720.0 * 3600.0)       # keep it bounded, gear phase continuous
        theta = theta_u % 720.0
        if not running:
            return np.zeros(n)
        spd = rpm_s / max(meta["rpm"], 1.0)
        out = {}

        # ---- exhaust ----
        c_exh = math.sqrt(1.4 * 287.0 * max(meta["T_exh"], 400.0))
        if self.exh_comb is None:
            self.exh_comb = Comb(2.0 * s.air.exhaust_pipe_length / c_exh, -0.62)
            f_hx = c_exh / (2.0 * max(s.air.muffler_length, 0.25))
            self.exh_peaks = [Biquad(*peak_ba(min(kk * f_hx, 0.4 * fs), 2.2, -14.0)) for kk in (1, 3)]
            self._exh_q0 = None
        q = self._sample("exh_flow", theta) * spd
        prev = self._exh_q0 if self._exh_q0 is not None else q[0]
        dq = np.diff(np.concatenate(([prev], q))) * fs
        self._exh_q0 = float(q[-1])
        y = self.exh_comb.process(dq)
        y = self.exh_lp.process(y)
        for b in self.exh_peaks:
            y = b.process(y)
        y = self.exh_hp.process(y)
        if self.exh_turb is not None:
            y = self.exh_turb.process(y)
        out["exhaust"] = self.norm["exh"](y) * (meta["mdot_air"] / self.ref_mdot) ** 1.5

        # ---- intake ----
        qi = self._sample("int_flow", theta) * spd
        prev = getattr(self, "_int_q0", None)
        dqi = np.diff(np.concatenate(([qi[0] if prev is None else prev], qi))) * fs
        self._int_q0 = float(qi[-1])
        y = self.int_comb.process(dqi)
        y = self.int_helm.process(y) + 0.5 * y
        hiss = self.hiss_bp.process(self.n_hiss.take(n))
        hiss = hiss * (meta["mdot_air"] * spd ** 1.5) ** 1.5 * 4.0
        out["intake"] = self.norm["int"](y) + 0.45 * self.norm["hiss"](hiss)

        # ---- combustion ----
        exc = self.norm["exc"](self._sample("dpdth", theta) * (rpm_s / 60.0 * 360.0))
        sharp = min(3.0, meta["dpdt_max"] / 5.0e9)
        knock = np.zeros(n)
        for bq, f0, gn in self.knock:
            knock = knock + bq.process(exc) * (gn * (1.0 + sharp * (f0 / 2000.0) ** 1.1))
        out["combustion"] = self.norm["knock"](knock) * (meta["dpdt_max"] / self.ref_dpdt)

        # ---- mechanical impulses ----
        tk = self._sample("valve", theta)
        tk = self.tick[0].process(tk) + 0.6 * self.tick[1].process(tk)
        ij = self._sample("inj", theta)
        ij = self.injr[0].process(ij) + 0.5 * self.injr[1].process(ij)
        sl = self._sample("slap", theta)
        sl = self.slapr[0].process(sl) + 0.7 * self.slapr[1].process(sl)
        a_tick = (max(meta["v_seating"], 1e-6) / self.ref_vseat) ** 2
        a_slap = (max(meta["skirt_clr"], 1e-9) / 30e-6) ** 0.6
        out["mech"] = (a_tick * self.norm["tick"](tk) + 0.75 * self.norm["inj"](ij)
                       + 0.9 * a_slap * self.norm["slap"](sl))

        # ---- turbocharger ----
        if s.turbo.enabled and meta["turbo_rpm"] > 1000.0:
            f_shaft = meta["turbo_rpm"] * (0.35 + 0.65 * spd) / 60.0
            ph = self.ph_t + 2 * math.pi * np.cumsum(f_shaft / fs)
            self.ph_t = float(ph[-1]) % (2 * math.pi)
            whine = np.zeros(n)
            for kk, amp in ((1, 1.0), (2, 0.45), (3, 0.22)):
                if kk * float(np.mean(f_shaft)) < 0.45 * fs:
                    whine = whine + amp * np.sin(kk * ph + 0.7 * kk)
            f_bp = f_shaft * s.turbo.comp_blades
            ph_bp = self.ph_bp + 2 * math.pi * np.cumsum(f_bp / fs)
            self.ph_bp = float(ph_bp[-1]) % (2 * math.pi)
            if float(np.mean(f_bp)) < 0.42 * fs:
                whine = whine + 0.30 * np.sin(ph_bp)
            wh = self.norm["whoosh"](self.whoosh_bp.process(self.n_whoosh.take(n)))
            amp = np.maximum((meta["boost"] - 1.0) * spd ** 2, 0.0)
            y = (0.55 * whine + 0.45 * wh) * amp
            out["turbo"] = self.norm["turbo"](y) * (meta["turbo_rpm"] / self.ref_turbo) ** 2
        else:
            out["turbo"] = np.zeros(n)

        # ---- gear train (locked to the crank) ----
        gear = np.zeros(n)
        f_crank = rpm_s / 60.0
        for teeth, ratio, amp in ((s.crank_gear_teeth, 1.0, 1.0), (s.cam_gear_teeth, 0.5, 0.7),
                                  (s.injpump_gear_teeth, 0.5, 0.5)):
            if float(np.mean(teeth * f_crank * ratio)) < 0.45 * fs:
                ph_g = 2 * math.pi * teeth * ratio * theta_u / 360.0
                gear = gear + amp * (np.sin(ph_g) + 0.35 * np.sin(2 * ph_g + 1.1))
        out["gear"] = self.norm["gear"](gear) * (0.3 + 0.7 * meta["load"])

        # ---- rumble: boundary-friction noise, firing-modulated ----
        rum = self.rumble_bp.process(self.n_rumble.take(n))
        # render() also divides this by its maximum; ahead of a Norm, a
        # constant scale changes nothing (a mutant removing it is equivalent)
        firing = 0.6 + 0.4 * np.abs(self._sample("dpdth", theta))
        out["rumble"] = self.norm["rumble"](rum * firing) * (max(meta["Pb"], 1e-9) / self.ref_Pb) ** 0.5

        # ---- the microphone ----
        m = self.mic
        y = np.zeros(n)
        for key, gn in m.gains.items():
            y = y + gn * out[key]
        y = self.out_lp.process(y)
        y = self.out_hp.process(y)
        y = y / max(1.0, m.distance_m) ** 0.55
        taps = self.rev.taps(y, self.rev_taps)
        if m.reverb > 0.0:
            r = np.zeros(n)
            for t, g_ in zip(taps, self.rev_gains):
                r = r + g_ * t
            y = y + m.reverb * self.rev_lp.process(r)
        self.last_parts = out
        return np.tanh(1.1 * (y * SPL_CAL)) / math.tanh(1.1)
