"""
acoustics.py -- engine sound synthesised from the simulated physics.

Nothing here is a sample library or a lookup table.  Every source is driven
by a quantity the solver already computed:

    exhaust note      <- mdot through the exhaust valve, through a 1-D
                         waveguide (delay + open-end reflection) and a
                         reactive muffler
    intake roar       <- mdot through the intake valve, through the runner
                         quarter-wave and the airbox Helmholtz resonator
    diesel clatter    <- dp/dtheta exciting the block/head structural modes
    injector tick     <- the commanded injection events
    valvetrain tick   <- seating velocity from the cam ramp (grows with lash)
    piston slap       <- thrust reversal of the con-rod side force
    turbo whine       <- shaft order of the live turbocharger speed
    gear whine        <- tooth-mesh frequency of the timing gear train
    mechanical rumble <- boundary-friction power, firing-modulated

Synthesis is done in the CRANK-ANGLE domain and then resampled through the
instantaneous engine speed, so pitch tracks rpm exactly and transients
(spool-up, gear changes, load steps) sound right without any pitch-shifting.
"""
from __future__ import annotations

import math
import wave
from dataclasses import dataclass, field

import numpy as np
from scipy import signal

C_AIR_STP = 343.0
RHO_AIR = 1.20


# ==========================================================================
# small DSP helpers
# ==========================================================================
def _biquad_peak(f0, Q, gain_db, fs):
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * math.pi * f0 / fs
    alpha = math.sin(w0) / (2 * Q)
    b = [1 + alpha * A, -2 * math.cos(w0), 1 - alpha * A]
    a = [1 + alpha / A, -2 * math.cos(w0), 1 - alpha / A]
    return np.array(b) / a[0], np.array(a) / a[0]


def _resonator(x, f0, Q, fs, gain=1.0):
    """Damped structural mode: 2-pole resonator excited by x."""
    f0 = min(f0, 0.45 * fs)
    r = math.exp(-math.pi * f0 / (Q * fs))
    theta = 2 * math.pi * f0 / fs
    b = [gain * (1 - r), 0.0, -gain * (1 - r) * r]
    a = [1.0, -2 * r * math.cos(theta), r * r]
    return signal.lfilter(b, a, x)


def _bandpass(x, lo, hi, fs, order=2):
    ny = 0.5 * fs
    lo = max(20.0, min(lo, 0.9 * ny))
    hi = max(lo * 1.05, min(hi, 0.95 * ny))
    sos = signal.butter(order, [lo / ny, hi / ny], btype="band", output="sos")
    return signal.sosfilt(sos, x)


def _lowpass(x, fc, fs, order=2):
    ny = 0.5 * fs
    sos = signal.butter(order, min(fc, 0.95 * ny) / ny, btype="low",
                        output="sos")
    return signal.sosfilt(sos, x)


def _highpass(x, fc, fs, order=2):
    ny = 0.5 * fs
    sos = signal.butter(order, max(5.0, min(fc, 0.9 * ny)) / ny,
                        btype="high", output="sos")
    return signal.sosfilt(sos, x)


def _comb_waveguide(x, delay_s, refl, fs, n_bounce=1):
    """
    Feedback comb = a pipe of length L with a reflecting end.
    delay_s = 2L/c (there and back).  refl < 0 for an open end.
    A one-pole loss models the wall/thermal damping per bounce.
    """
    D = max(1, int(round(delay_s * fs)))
    y = np.zeros_like(x)
    buf = np.zeros(D)
    idx = 0
    lp = 0.0
    a_lp = 0.55          # per-bounce high-frequency loss
    for n in range(len(x)):
        d = buf[idx]
        lp = a_lp * lp + (1.0 - a_lp) * d
        y[n] = x[n] + refl * lp
        buf[idx] = y[n]
        idx = (idx + 1) % D
    return y


def _softclip(x, drive=1.0):
    return np.tanh(drive * x) / math.tanh(drive)


# ==========================================================================
@dataclass
class MicPosition:
    """A listening position = a mix of the sources plus a transfer function."""
    name: str
    gains: dict = field(default_factory=dict)
    lp_hz: float = 20000.0
    hp_hz: float = 20.0
    distance_m: float = 1.0
    reverb: float = 0.0


MICS = {
    "exhaust_tip": MicPosition(
        "exhaust_tip",
        dict(exhaust=1.00, intake=0.05, combustion=0.16, mech=0.10,
             turbo=0.10, gear=0.03, rumble=0.20),
        lp_hz=5200, hp_hz=28, distance_m=0.5),
    "intake": MicPosition(
        "intake",
        dict(exhaust=0.10, intake=1.00, combustion=0.18, mech=0.12,
             turbo=0.55, gear=0.05, rumble=0.15),
        lp_hz=7500, hp_hz=45, distance_m=0.4),
    "engine_bay": MicPosition(
        "engine_bay",
        dict(exhaust=0.30, intake=0.35, combustion=1.00, mech=0.95,
             turbo=0.45, gear=0.55, rumble=0.55),
        lp_hz=11000, hp_hz=55, distance_m=0.8),
    "cabin": MicPosition(
        "cabin",
        dict(exhaust=0.38, intake=0.20, combustion=0.42, mech=0.22,
             turbo=0.20, gear=0.14, rumble=0.60),
        lp_hz=1900, hp_hz=32, distance_m=2.0, reverb=0.25),
    "exterior_7m": MicPosition(
        "exterior_7m",
        dict(exhaust=0.85, intake=0.30, combustion=0.55, mech=0.35,
             turbo=0.30, gear=0.22, rumble=0.35),
        lp_hz=6500, hp_hz=60, distance_m=7.0, reverb=0.35),
}


# ==========================================================================
class EngineSound:
    """
    Build the crank-angle-domain source waveforms once per operating point,
    then render them along an arbitrary rpm/load trajectory.
    """

    def __init__(self, spec, fs: int = 44100, dtheta: float = 0.5):
        self.spec = spec
        self.fs = fs
        self.dtheta = dtheta
        self.grid = np.arange(0.0, 720.0, dtheta)
        self._rng = np.random.default_rng(12345)
        self.wear = None          # attach a WearModel to hear the engine age

    # ------------------------------------------------------------------ #
    # crank-angle-domain source construction
    # ------------------------------------------------------------------ #
    def _phase_sum(self, y_1cyl: np.ndarray, theta_src: np.ndarray):
        """Resample one cylinder's trace onto the grid and sum the firing order."""
        g = self.spec.geom
        base = np.interp(self.grid, theta_src, y_1cyl, period=720.0)
        out = np.zeros_like(base)
        for i in range(g.n_cyl):
            out += np.interp((self.grid - g.phase_deg(i)) % 720.0,
                             self.grid, base, period=720.0)
        return out

    def build_sources(self, op) -> dict:
        """
        Returns a dict of 720-degree-periodic waveforms, one per physical
        source, plus the scalar tone parameters.
        """
        spec, g = self.spec, self.spec.geom
        cyc = op.cycle
        th = cyc.traces.theta
        src = {}

        # ---- 1. exhaust port mass flow --------------------------------
        mdot_e = np.clip(cyc.traces.mdot_exh[0], 0.0, None)
        src["exh_flow"] = self._phase_sum(mdot_e, th)

        # ---- 2. intake port mass flow ---------------------------------
        mdot_i = np.clip(cyc.traces.mdot_int[0], 0.0, None)
        src["int_flow"] = self._phase_sum(mdot_i, th)

        # ---- 3. combustion: dp/dtheta ---------------------------------
        p1 = cyc.traces.p[0]
        dpdth = np.gradient(p1, th[1] - th[0])
        src["dpdth"] = self._phase_sum(dpdth, th)

        # ---- 4. injector events ---------------------------------------
        ev = []
        tr = cyc.traces
        if spec.inj.pilot_enabled:
            ev.append(((tr.pilot_soi_deg) % 720.0, 0.55))
        ev.append((tr.soi_deg % 720.0, 1.0))
        ev.append(((tr.soi_deg + tr.inj_dur_main_deg) % 720.0, 0.7))
        src["inj"] = self._impulses(ev, n_cyl=g.n_cyl)

        # ---- 5. valve seating ------------------------------------------
        vt = spec.valves
        # Impact energy goes as the square of seating velocity, and lash
        # growth adds free travel before the ramp catches the valve -- which
        # is exactly why a worn engine ticks louder.
        w_int = self.spec.geom  # (alias kept for readability below)
        lash_i = self.wear_lash("intake")
        lash_e = self.wear_lash("exhaust")
        f_i = (1.0 + lash_i / max(vt.lash_intake, 1e-5)) ** 1.5
        f_e = (1.0 + lash_e / max(vt.lash_exhaust, 1e-5)) ** 1.5
        ev = [(vt.ivc_deg % 720.0, 1.00 * f_i),
              (vt.evc_deg % 720.0, 0.85 * f_e),
              (vt.ivo_deg % 720.0, 0.35 * f_i),
              (vt.evo_deg % 720.0, 0.45 * f_e)]
        src["valve"] = self._impulses(ev, n_cyl=g.n_cyl)

        # ---- 6. piston slap (thrust reversal) --------------------------
        sc_th = np.radians(th)
        om = 2.0 * math.pi * op.rpm / 60.0
        # signed side force
        try:
            from .kinematics import SliderCrank
            sc = SliderCrank(g)
            acc = sc.piston_accel(sc_th, om)
            beta = sc.beta(sc_th)
            F_ax = (p1 - 1.05e5) * g.piston_area - g.recip_mass * acc
            S = -F_ax * np.tan(beta)
        except Exception:
            S = np.zeros_like(p1)
        sg = np.sign(S)
        cross = np.where(np.diff(sg) != 0)[0]
        ev = []
        for k in cross:
            amp = abs(S[min(k + 3, len(S) - 1)] - S[max(k - 3, 0)])
            ev.append((th[k] % 720.0, amp))
        if ev:
            mx = max(a for _, a in ev)
            ev = [(t, a / mx) for t, a in ev if a > 0.12 * mx]
        src["slap"] = self._impulses(ev, n_cyl=g.n_cyl)

        # ---- scalar tone parameters ------------------------------------
        src["_meta"] = dict(
            rpm=op.rpm,
            turbo_rpm=op.turbo_rpm,
            mdot_air=op.air_kg_s,
            boost=op.boost_pr,
            dpdt_max=float(np.max(np.abs(dpdth))) * op.rpm * 6.0,
            p_max=op.p_max,
            T_exh=op.T_exh,
            load=op.bmep / 2.3e6,
            v_seating=op.friction.get("v_seating", 1.0),
            Pb=sum(op.friction.get(k, 0.0) for k in
                   ("Pb_rings", "Pb_skirt", "Pb_rods", "Pb_mains", "Pb_pin")),
            skirt_clr=op.friction.get("h_skirt", 40e-6),
        )
        return src

    def wear_lash(self, which: str) -> float:
        """Lash growth [m] if a wear model has been attached, else 0."""
        w = getattr(self, "wear", None)
        if w is None:
            return 0.0
        return (w.state.lash_growth_int if which == "intake"
                else w.state.lash_growth_exh)

    def _impulses(self, events, n_cyl: int, width_deg: float = 1.2):
        """Place short raised-cosine impulses at the given crank angles,
        repeated for every cylinder in the firing order."""
        g = self.spec.geom
        y = np.zeros_like(self.grid)
        # A mechanical strike is a half-sine contact force pulse.  Sample the
        # OPEN interval (0,1): a closed raised cosine on only 2-3 points is
        # identically zero, which silently deletes the whole source.
        w = max(4, int(round(width_deg / self.dtheta)) + 1)
        u = (np.arange(w) + 0.5) / w
        win = np.sin(math.pi * u) * np.exp(-2.2 * u)
        win /= win.max()
        for ang, amp in events:
            for i in range(n_cyl):
                a = (ang + g.phase_deg(i)) % 720.0
                k = int(a / self.dtheta) % len(y)
                for j in range(w):
                    y[(k + j) % len(y)] += amp * win[j]
        return y

    # ------------------------------------------------------------------ #
    # rendering
    # ------------------------------------------------------------------ #
    def render(self, op, duration: float = 3.0, mic: str = "exterior_7m",
               rpm_traj=None, sources: dict = None, seed: int = None):
        """
        Render `duration` seconds.  `rpm_traj` may be a callable t -> rpm to
        sweep the engine; the crank phase is integrated from it so the pitch
        is exact.
        """
        fs = self.fs
        n = int(duration * fs)
        t = np.arange(n) / fs
        src = sources or self.build_sources(op)
        meta = src["_meta"]
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        rpm = np.full(n, meta["rpm"]) if rpm_traj is None else \
            np.array([float(rpm_traj(x)) for x in t])
        rpm = np.maximum(rpm, 50.0)
        # crank phase [deg], 720 per 4-stroke cycle
        theta = np.cumsum(6.0 * rpm / fs) % 720.0

        def sample(name):
            return np.interp(theta, self.grid, src[name], period=720.0)

        spd = rpm / max(meta["rpm"], 1.0)          # flow scaling with speed

        out = {}

        # ---------------- exhaust ------------------------------------
        s = self.spec
        q = sample("exh_flow") * spd
        # monopole radiation: p ~ rho * dQ/dt
        dq = np.diff(q, prepend=q[0]) * fs
        c_exh = math.sqrt(1.4 * 287.0 * max(meta["T_exh"], 400.0))
        L_pipe = s.air.exhaust_pipe_length
        y = _comb_waveguide(dq, 2.0 * L_pipe / c_exh, -0.62, fs)
        # reactive muffler: expansion chamber -> lowpass + notch train
        V_m = max(s.air.muffler_volume, 1e-4)
        f_hx = c_exh / (2.0 * max(s.air.muffler_length, 0.25))
        y = _lowpass(y, 900.0 * (0.02 / V_m) ** 0.25, fs, order=2)
        for k in (1, 3):
            b, a = _biquad_peak(min(k * f_hx, 0.4 * fs), 2.2, -14.0, fs)
            y = signal.lfilter(b, a, y)
        y = _highpass(y, 35.0, fs, order=1)
        # turbine takes the sharpest edges out of the pulse
        if s.turbo.enabled:
            y = _lowpass(y, 1400.0, fs, order=1)
        out["exhaust"] = y / (np.std(y) + 1e-12)

        # ---------------- intake -------------------------------------
        qi = sample("int_flow") * spd
        dqi = np.diff(qi, prepend=qi[0]) * fs
        L_run = s.air.runner_length_int
        y = _comb_waveguide(dqi, 4.0 * L_run / C_AIR_STP, -0.45, fs)
        # airbox Helmholtz
        A_n, L_n, V_b = (s.air.airbox_neck_area, s.air.airbox_neck_len,
                         s.air.airbox_volume)
        f_h = C_AIR_STP / (2 * math.pi) * math.sqrt(
            A_n / max(V_b * (L_n + 0.85 * math.sqrt(A_n / math.pi)), 1e-9))
        y = _resonator(y, max(f_h, 25.0), 3.5, fs, gain=2.0) + 0.5 * y
        # filter / throttle hiss: turbulent broadband ~ mdot^3
        hiss = self._rng.standard_normal(n)
        hiss = _bandpass(hiss, 700.0, 6500.0, fs, order=2)
        hiss *= (meta["mdot_air"] * spd ** 1.5) ** 1.5 * 4.0
        y = y / (np.std(y) + 1e-12) + 0.45 * hiss / (np.std(hiss) + 1e-12)
        out["intake"] = y

        # ---------------- combustion / diesel clatter ------------------
        exc = sample("dpdth") * (rpm / 60.0 * 360.0)     # -> dp/dt
        exc = exc / (np.std(exc) + 1e-12)
        knock = np.zeros(n)
        # block / head structural modes.  Higher peak dp/dt excites the
        # high-frequency modes far more strongly -- that is diesel knock.
        sharp = min(3.0, meta["dpdt_max"] / 6.0e6)
        for f0, Q, gn in ((680.0, 11.0, 1.00), (1450.0, 14.0, 0.72),
                          (2350.0, 16.0, 0.55), (3600.0, 18.0, 0.42),
                          (5200.0, 20.0, 0.26)):
            w = gn * (1.0 + sharp * (f0 / 2000.0) ** 1.1)
            knock += _resonator(exc, f0, Q, fs, gain=w)
        out["combustion"] = knock / (np.std(knock) + 1e-12)

        # ---------------- mechanical impulses --------------------------
        tick = sample("valve") * (meta["v_seating"] / 1.2) ** 1.5
        tick = _resonator(tick, 3100.0, 26.0, fs, 1.0) + \
            0.6 * _resonator(tick, 5400.0, 30.0, fs, 1.0)
        inj = sample("inj")
        inj = _resonator(inj, 4200.0, 34.0, fs, 1.0) + \
            0.5 * _resonator(inj, 6800.0, 36.0, fs, 1.0)
        slap = sample("slap") * (meta["skirt_clr"] / 30e-6) ** 0.6
        slap = _resonator(slap, 900.0, 9.0, fs, 1.0) + \
            0.7 * _resonator(slap, 1750.0, 12.0, fs, 1.0)
        mech = (tick / (np.std(tick) + 1e-12)
                + 0.75 * inj / (np.std(inj) + 1e-12)
                + 0.9 * slap / (np.std(slap) + 1e-12))
        out["mech"] = mech / (np.std(mech) + 1e-12)

        # ---------------- turbocharger ---------------------------------
        if s.turbo.enabled and meta["turbo_rpm"] > 1000.0:
            n_t = meta["turbo_rpm"] * (0.35 + 0.65 * spd)
            f_shaft = n_t / 60.0
            ph = 2 * math.pi * np.cumsum(f_shaft / fs)
            whine = np.zeros(n)
            for k, a in ((1, 1.0), (2, 0.45), (3, 0.22)):
                if k * float(np.mean(f_shaft)) < 0.45 * fs:
                    whine += a * np.sin(k * ph + 0.7 * k)
            # blade passing is real but usually ultrasonic -- keep it only
            # if it lands below Nyquist
            f_bp = f_shaft * s.turbo.comp_blades
            if float(np.mean(f_bp)) < 0.42 * fs:
                whine += 0.30 * np.sin(2 * math.pi * np.cumsum(f_bp / fs))
            whoosh = _bandpass(self._rng.standard_normal(n), 1200.0, 9000.0,
                               fs, 2)
            amp = (meta["boost"] - 1.0) * spd ** 2
            y = (0.55 * whine + 0.45 * whoosh /
                 (np.std(whoosh) + 1e-12)) * np.maximum(amp, 0.0)
            out["turbo"] = y / (np.std(y) + 1e-12)
        else:
            out["turbo"] = np.zeros(n)

        # ---------------- gear train -----------------------------------
        gear = np.zeros(n)
        f_crank = rpm / 60.0
        for teeth, ratio, amp in ((s.crank_gear_teeth, 1.0, 1.0),
                                  (s.cam_gear_teeth, 0.5, 0.7),
                                  (s.injpump_gear_teeth, 0.5, 0.5)):
            f_mesh = teeth * f_crank * ratio
            if float(np.mean(f_mesh)) < 0.45 * fs:
                ph = 2 * math.pi * np.cumsum(f_mesh / fs)
                gear += amp * (np.sin(ph) + 0.35 * np.sin(2 * ph + 1.1))
        out["gear"] = gear / (np.std(gear) + 1e-12) * (0.3 + 0.7 * meta["load"])

        # ---------------- broadband mechanical rumble ------------------
        rum = _bandpass(self._rng.standard_normal(n), 40.0, 480.0, fs, 2)
        firing = 0.6 + 0.4 * np.abs(sample("dpdth"))
        firing /= (np.max(firing) + 1e-12)
        rum = rum * firing
        out["rumble"] = rum / (np.std(rum) + 1e-12)

        # ---------------- mix at the microphone ------------------------
        m = MICS[mic]
        y = np.zeros(n)
        for k, gn in m.gains.items():
            y += gn * out[k]
        y = _lowpass(y, m.lp_hz, fs, order=3)
        y = _highpass(y, m.hp_hz, fs, order=2)
        y /= max(1.0, m.distance_m) ** 0.55
        if m.reverb > 0.0:
            y = y + m.reverb * self._cheap_reverb(y)
        # overall level tracks bmep and speed the way a real engine does
        lvl = (0.25 + 0.75 * min(1.6, meta["load"])) * (0.45 + 0.55 * spd)
        y = _softclip(y / (np.std(y) + 1e-12) * 0.22 * lvl, 1.1)
        return y, out

    def _cheap_reverb(self, x):
        fs = self.fs
        y = np.zeros_like(x)
        for d, g in ((0.021, 0.42), (0.037, 0.33), (0.053, 0.26),
                     (0.079, 0.18)):
            D = int(d * fs)
            z = np.zeros_like(x)
            z[D:] = x[:-D]
            y += g * z
        return _lowpass(y, 2500.0, fs, order=1)

    # ------------------------------------------------------------------ #
    def render_transient(self, engine, log, mic: str = "exterior_7m",
                         blend: float = 0.35):
        """
        Render a transient run produced by DieselEngine.transient().
        The source set is rebuilt every `blend` seconds and cross-faded, so
        turbo spool, smoke limit and load change are audible.
        """
        fs = self.fs
        times = np.array([r["t"] for r in log])
        rpms = np.array([r["rpm"] for r in log])
        dur = float(times[-1])
        rpm_of_t = lambda x: float(np.interp(x, times, rpms))
        step = max(blend, 0.15)
        chunks = []
        t0 = 0.0
        while t0 < dur:
            t1 = min(dur, t0 + step)
            k = int(np.searchsorted(times, 0.5 * (t0 + t1)))
            k = min(k, len(log) - 1)
            op = log[k]["op"]
            y, _ = self.render(op, duration=(t1 - t0), mic=mic,
                               rpm_traj=lambda x, o=t0: rpm_of_t(o + x))
            chunks.append(y)
            t0 = t1
        # equal-power cross-fade between chunks
        xf = int(0.02 * fs)
        out = chunks[0]
        for c in chunks[1:]:
            if len(out) > xf and len(c) > xf:
                w = np.linspace(0, 1, xf)
                tail = out[-xf:] * np.cos(w * math.pi / 2) + \
                    c[:xf] * np.sin(w * math.pi / 2)
                out = np.concatenate([out[:-xf], tail, c[xf:]])
            else:
                out = np.concatenate([out, c])
        return out

    # ------------------------------------------------------------------ #
    @staticmethod
    def write_wav(path: str, y: np.ndarray, fs: int = 44100,
                  stereo: bool = True):
        y = np.asarray(y, dtype=np.float64)
        pk = np.max(np.abs(y)) + 1e-12
        y = y / pk * 0.89
        if stereo:
            # tiny Haas spread so it is not a point source
            d = int(0.0009 * fs)
            r = np.concatenate([np.zeros(d), y[:-d]]) * 0.94
            data = np.stack([y, r], axis=1)
        else:
            data = y[:, None]
        pcm = (data * 32767.0).astype("<i2")
        with wave.open(path, "wb") as w:
            w.setnchannels(data.shape[1])
            w.setsampwidth(2)
            w.setframerate(fs)
            w.writeframes(pcm.tobytes())
        return path

    # ------------------------------------------------------------------ #
    def spectrum(self, y, nfft: int = 8192):
        f, P = signal.welch(y, self.fs, nperseg=min(nfft, len(y)))
        return f, 10.0 * np.log10(P + 1e-20)
