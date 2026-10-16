"""P09 listening round: the knock at altitude and on a cold start, at several playback gains.

    python3 tools/p09_listen.py OUTDIR [preset ...]          (default: crdi15 hatch15)

One WAV per engine and mic (cabin, intake). Each holds four sections, one per gain exponent k
(livesound.KNOCK_GAIN_EXP: 0 = the physics alone, then 3, 5, 8), and each section plays the engine at idle:
warm at sea level, a cold start at sea level, warm at Leh (3500 m, 20 C), and a cold start at Leh, 3 s each.
A cold start: every chamber wall, the coolant and the oil at the air's temperature (engine.cold_start_walls),
as the grid's cold cells and the live loop's first minute. Leh: the solver at Leh's air. The synth gets the
case's knock against warm sea level's (dpdt_max / dpdt_ref), as the live loop sends it.

Unlike tools/p10_ab.py the segments are NOT level-matched: the loudness change is the point. Each file has
one scale (its peak to 0.95). Prints each segment's level against the file's first, in dB.
"""
import os
import sys
import wave

import numpy as np

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, REPO)
from dieselsim.builder import load_engine_dir  # noqa: E402
load_engine_dir(os.path.join(REPO, "engines"))
from dieselsim.config import PRESETS  # noqa: E402
from dieselsim.engine import DieselEngine  # noqa: E402
from dieselsim.acoustics import EngineSound  # noqa: E402
from dieselsim.environment import pressure_at  # noqa: E402
from dieselsim import livesound as LS  # noqa: E402

GAINS = (0.0, 3.0, 5.0, 8.0)
CASES = (("warm, sea level", 101325.0, 298.0, False), ("cold start, sea level", 101325.0, 298.0, True),
         ("warm, Leh", pressure_at(3500.0), 293.15, False), ("cold start, Leh", pressure_at(3500.0), 293.15, True))


def sources(key, p, T, cold):
    spec = PRESETS[key]()
    spec.thermal.ambient_p, spec.thermal.ambient_T = p, T
    eng = DieselEngine(spec=spec)
    if cold:
        eng.cold_start_walls(T)
        eng.oil.cond.T_oil = T
    rpm = float(spec.idle_rpm)
    op = eng.operating_point(rpm, load=0.05, n_cycles=9)
    es = EngineSound(eng.spec)
    es.wear, es.T_coolant = eng.wear, eng.T_coolant
    return eng.spec, rpm, es.build_sources(op)


def play(spec, src, rpm, mic, live, secs=3.0, warm=1.0):
    syn = LS.LiveSynth(spec, mic)
    syn.set_sources(src)
    n = int((secs + warm) * LS.FS / LS.BLOCK)
    return np.concatenate([syn.block(rpm, live) for _ in range(n)])[int(warm * LS.FS):]


def fade(y, ms=25):
    n = int(ms * LS.FS / 1000)
    w = np.ones(len(y))
    w[:n] = np.linspace(0, 1, n)
    w[-n:] = np.linspace(1, 0, n)
    return y * w


def main():
    out = sys.argv[1]
    presets = sys.argv[2:] or ["crdi15", "hatch15"]
    os.makedirs(out, exist_ok=True)
    k_was = LS.KNOCK_GAIN_EXP
    try:
        for key in presets:
            solved = [sources(key, p, T, cold) for _, p, T, cold in CASES]
            ref = solved[0][2]["_meta"]["dpdt_max"]
            for mic in ("cabin", "intake"):
                pieces, rms0, t = [], None, 0.0
                for k in GAINS:
                    LS.KNOCK_GAIN_EXP = k
                    for (label, *_), (spec, rpm, src) in zip(CASES, solved):
                        live = {"dpdt_max": src["_meta"]["dpdt_max"], "dpdt_ref": ref}
                        y = play(spec, src, rpm, mic, live)
                        rms = float(np.sqrt(np.mean(y ** 2)))
                        rms0 = rms0 or rms
                        print(f"{key} {mic:6s} k={k:3.0f}  {label:22s} {t:5.1f}-{t + 3:5.1f} s  knock x{live['dpdt_max'] / ref:4.2f}"
                              f"  level {20 * np.log10(rms / rms0):+5.1f} dB", flush=True)
                        pieces += [fade(y), np.zeros(int(0.5 * LS.FS))]
                        t += 3.5
                    pieces.append(np.zeros(int(1.0 * LS.FS)))
                    t += 1.0
                y = np.concatenate(pieces)
                y = y * (0.95 / max(float(np.abs(y).max()), 1e-9))
                path = os.path.join(out, f"p09_{key}_{mic}.wav")
                with wave.open(path, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(LS.FS)
                    w.writeframes((y * 32767).astype("<i2").tobytes())
                print("wrote", path, f"{len(y) / LS.FS:.0f} s", flush=True)
    finally:
        LS.KNOCK_GAIN_EXP = k_was


if __name__ == "__main__":
    main()
