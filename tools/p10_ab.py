"""P10 (reviews/PROPOSAL-P10.md): A/B/C listening files, in memory only (nothing in dieselsim/ changes).

Usage: python3 tools/p10_ab.py . OUTDIR [preset ...]      (default: crdi15 hatch15 crdi22)

One WAV per engine and mic (cabin, intake). For each of idle, 2000 rpm at 30% and 2500 rpm at full
pedal it plays A (today), B (the proposal) and C (B + a small-speaker bass peak), 3 s each, every
segment at the same RMS (LEVEL), so the ear compares the tone, not the loudness (and idle is audible
on a phone). Prints each segment's numbers, and its RMS as the synth made it.

B: the solver's port flows lose their step-locked zig-zag (a 2-degree moving average; FINDING-028),
then the mix is rebalanced: exhaust x8, mechanical clicks /3, combustion x0.6, intake hiss x0.4,
turbo x0.4. C: B + a +9 dB peak at 200 Hz (Q 0.8) on the output, a playback effect, not physics.
"""
import dataclasses
import os
import sys
import wave

import numpy as np

REPO = sys.argv[1]
sys.path.insert(0, REPO)
from dieselsim.builder import load_engine_dir  # noqa: E402
load_engine_dir(os.path.join(REPO, "engines"))
from dieselsim.engine import DieselEngine  # noqa: E402
from dieselsim.acoustics import EngineSound  # noqa: E402
from dieselsim import livesound as LS  # noqa: E402

B_GAINS = dict(exhaust=8.0, mech=1 / 3, combustion=0.6, turbo=0.4)
B_HISS = 0.4
C_EQ = (200.0, 0.8, 9.0)
LEVEL = 0.12                 # every segment's RMS in the file


def smooth2deg(x):
    """A 2-degree circular moving average on the 0.5-degree source grid: nulls the 1-degree solver's
    step-locked chatter (order 180 per rev) and its harmonics."""
    x = np.asarray(x, dtype=float)
    return (x + np.roll(x, 1) + np.roll(x, 2) + np.roll(x, 3)) / 4.0


class Variant(LS.LiveSynth):
    def __init__(self, spec, mic, smooth=False, k=None, hiss=1.0, eq=None):
        self._smooth, self._k, self._hiss, self._eq = smooth, dict(k or {}), hiss, eq
        super().__init__(spec, mic)

    def _build(self, mic):
        super()._build(mic)
        if self._hiss != 1.0:
            n0, f = self.norm["hiss"], self._hiss
            self.norm["hiss"] = lambda y: f * n0(y)

    def set_mic(self, mic):
        super().set_mic(mic)
        g = dict(self.mic.gains)
        for key, f in self._k.items():
            g[key] *= f
        self.mic = dataclasses.replace(self.mic, gains=g)
        if self._eq:
            eq, lp = LS.Biquad(*LS.peak_ba(*self._eq)), self.out_lp

            class Then:
                def process(self, x):
                    return eq.process(lp.process(x))
            self.out_lp = Then()

    def set_sources(self, src):
        if self._smooth:
            src = dict(src, exh_flow=smooth2deg(src["exh_flow"]), int_flow=smooth2deg(src["int_flow"]))
        super().set_sources(src)


VARIANTS = {"A": {}, "B": dict(smooth=True, k=B_GAINS, hiss=B_HISS),
            "C": dict(smooth=True, k=B_GAINS, hiss=B_HISS, eq=C_EQ)}


def render(spec, src, rpm, mic, secs=3.0, warm=1.0, **kw):
    syn = Variant(spec, mic, **kw)
    syn.set_sources(src)
    n = int((secs + warm) * LS.FS / LS.BLOCK)
    return np.concatenate([syn.block(rpm) for _ in range(n)])[int(warm * LS.FS):]


SEG = 1 << 14
F = np.fft.rfftfreq(SEG, 1 / LS.FS)


def metrics(y):
    P = np.zeros(SEG // 2 + 1)
    for k in range(0, len(y) - SEG + 1, SEG // 2):
        P += np.abs(np.fft.rfft(y[k:k + SEG] * np.hanning(SEG))) ** 2
    return (F * P).sum() / P.sum(), P[F < 250].sum() / P.sum() * 100, P[F >= 2000].sum() / P.sum() * 100


def fade(y, ms=25):
    n = int(ms * LS.FS / 1000)
    w = np.ones(len(y))
    w[:n] = np.linspace(0, 1, n)
    w[-n:] = np.linspace(1, 0, n)
    return y * w


def main():
    out = sys.argv[2]
    presets = sys.argv[3:] or ["crdi15", "hatch15", "crdi22"]
    os.makedirs(out, exist_ok=True)
    for preset in presets:
        eng = DieselEngine(preset=preset)
        spec = eng.spec
        idle = float(getattr(spec, "idle_rpm", 800.0) or 800.0)
        pts = ((idle, 0.05, "idle"), (2000.0, 0.3, "2000 rpm, 30%"), (2500.0, 1.0, "2500 rpm, full pedal"))
        srcs = [EngineSound(spec).build_sources(eng.operating_point(r, load=ld, n_cycles=9)) for r, ld, _ in pts]
        for mic in ("cabin", "intake"):
            pieces, t = [], 0.0
            for (rpm, _, label), src in zip(pts, srcs):
                for name, kw in VARIANTS.items():
                    y = render(spec, src, rpm, mic, **kw)
                    rms = float(np.sqrt(np.mean(y ** 2)))
                    c, lo, hi = metrics(y)
                    print(f"{preset} {mic:6s} {label:21s} {name}  {t:5.1f}-{t + 3:5.1f} s  centroid {c:5.0f} Hz  "
                          f"<250 Hz {lo:5.1f}%  >2 kHz {hi:5.1f}%  synth rms {rms:.3f}", flush=True)
                    pieces += [fade(y * LEVEL / rms), np.zeros(int(0.5 * LS.FS))]
                    t += 3.5
                pieces.append(np.zeros(int(0.7 * LS.FS)))
                t += 0.7
            y = np.concatenate(pieces)
            peak = float(np.abs(y).max())
            y = y / max(1.0, peak / 0.95)
            path = os.path.join(out, f"p10_{preset}_{mic}.wav")
            with wave.open(path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(LS.FS)
                w.writeframes((y * 32767).astype("<i2").tobytes())
            print("wrote", path, f"{len(y) / LS.FS:.1f} s, peak {peak:.2f}" + (" (scaled to 0.95)" if peak > 0.95 else ""), flush=True)


if __name__ == "__main__":
    main()
