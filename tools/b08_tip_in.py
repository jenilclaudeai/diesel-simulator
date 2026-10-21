"""B-08 ("sudden noise spikes": open the throttle, close it, open it again): the streaming synth
through a tip-out and tip-in on the live loop, coupled as the app couples them (the loop at 60 Hz,
the sources blended every 17 render quanta, as sound.worklet.ts does).

    python3 tools/b08_tip_in.py table [TREE]                     the six cases against a zero-lag reference
    python3 tools/b08_tip_in.py wav TREE OUT.wav preset mic case  three lifts, for listening

TREE is the repo whose dieselsim/ and grids are run (default: this one), so main's tree can be
measured with this tool. case: drive (Auto, 4th, 54 km/h, 60% pedal), neutral (manual box in
neutral, full pedal), brake (Auto, standing on the brake, 60%). Warm engine, standard air.

The reference replaces every shape tracker by the mean square of its own input averaged over a
centred 0.2 s Hann window: no lag, and at a steady point the trackers' normalisation (it agrees
there within 0.6 dB). Non-causal, so it can't ship: it is what the shape normalisation intends.
"synth over reference" is the synth's output over the reference's, in 100 ms windows: the worst
rise in the 1.5 s after the tip-in, the worst dip in the 1.5 s after the lift-off. Three passes
settle the cascade (the combustion trace's tracker feeds the knock's).
"""
import json
import math
import os
import sys
import wave
from multiprocessing import Pool

import numpy as np

CASES = (("crdi15", "exterior_7m", "drive", 3.0), ("crdi15", "exterior_7m", "neutral", 3.0),
         ("crdi15", "exterior_7m", "brake", 3.0), ("crdi15", "cabin", "drive", 1.0),
         ("hatch15", "cabin", "drive", 3.0), ("single", "exterior_7m", "neutral", 3.0))
DT = 1 / 60
STATE = {"table": None, "rec": None, "b": 0}


def _setup(tree):
    sys.path.insert(0, tree)
    from dieselsim.builder import load_engine_dir
    load_engine_dir(os.path.join(tree, "engines"))
    from dieselsim import livesound as LS
    for cls in [c for c in (getattr(LS, "Norm", None), getattr(LS, "CycleNorm", None)) if c is not None]:
        orig = cls.__call__

        def call(self, y, *a, orig=orig):
            STATE["rec"].setdefault(self._name, []).append(float(np.dot(y, y)) / len(y))
            if STATE["table"] is None:
                return orig(self, y, *a)
            return y / (math.sqrt(STATE["table"][self._name][STATE["b"]]) + 1e-12)
        cls.__call__ = call
    return LS


def drive(tree, key, mic, case, lifts, table=None):
    """lifts: [(t_off, t_on)] pedal-off intervals. Per-block output RMS, each tracker's input
    mean square, and the samples."""
    LS = _setup(tree)
    from dieselsim.live import Adr011Grid, LiveEngine, pedal_return
    with open(os.path.join(tree, "web/app/public/grids", f"{key}.json")) as fh:
        g = Adr011Grid.from_json(json.load(fh))
    live = LiveEngine(g, key, trans="manual" if case == "neutral" else "tc")
    live.T_coolant = live.T_chamber = live.T_oil = 361.0
    if case == "drive":
        v = 15.0
        live.dl.v = v
        live.dl.gb.gear = live.dl.gb.gear_from = 4
        live.dl.w_in = v / live.veh.r_wheel * live.veh.final * live.veh.gears[3]
        live.rpm = live.dl.w_in * 60.0 / (2.0 * math.pi)
    elif case == "brake":
        live.dl.brake = 1.0
    live._update_friction()
    pedal = 1.0 if case == "neutral" else 0.6
    syn = LS.LiveSynth(g.spec, mic)
    for k, nm in syn.norm.items():
        nm._name = k
    STATE.update(table=table, rec={})
    t_end = lifts[-1][1] + 4.0
    t_loop, Y, out = 0.0, [], []
    for b in range(int(t_end * LS.FS / LS.BLOCK)):
        STATE["b"] = b
        t = b * LS.BLOCK / LS.FS
        while t_loop <= t:
            live.throttle = 0.0 if any(t0 <= t_loop < t1 for t0, t1 in lifts) else pedal
            pedal_return(live, DT)
            live.step(DT)
            t_loop += DT
        if syn.src is None or b % 17 == 0:
            syn.set_sources(g.blend_sources(live.rpm, live.load_eff, live.T_chamber))
        y = syn.block(live.rpm, live.sound_inputs(), not live.stalled)
        Y.append(float(np.sqrt(np.mean(y ** 2))))
        out.append(y)
    return np.array(Y), {k: np.array(v) for k, v in STATE["rec"].items()}, np.concatenate(out), LS


def centred(m, half):
    w = np.hanning(2 * half + 1)
    w /= w.sum()
    return np.convolve(np.concatenate([np.full(half, m[0]), m, np.full(half, m[-1])]), w, mode="valid")


def one_case(arg):
    tree, (key, mic, case, off) = arg
    lifts = [(3.0, 3.0 + off)]
    Yc, rec, _, LS = drive(tree, key, mic, case, lifts)
    half = int(0.1 * LS.FS / LS.BLOCK)
    for _ in range(3):
        Yo, rec, _, _ = drive(tree, key, mic, case, lifts, {k: centred(v, half) for k, v in rec.items()})
    T = np.arange(len(Yc)) * LS.BLOCK / LS.FS
    W = int(0.1 * LS.FS / LS.BLOCK)

    def worst(lo, pick):
        idx = np.where((T >= lo) & (T < lo + 1.5))[0][:-W]
        v = [20 * math.log10(math.sqrt(np.mean(Yc[i:i + W] ** 2)) / math.sqrt(np.mean(Yo[i:i + W] ** 2)))
             for i in idx]
        return pick(v)
    ss = T > T[-1] - 1.0
    steady = 20 * math.log10(math.sqrt(np.mean(Yc[ss] ** 2)) / math.sqrt(np.mean(Yo[ss] ** 2)))
    return (f"{key:8s} {mic:11s} {case:7s} lift {off:.0f} s | tip-in {worst(3.0 + off, max):+5.1f} dB"
            f" | lift-off {worst(3.0, min):+5.1f} dB | steady {steady:+5.2f} dB")


def main():
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    if len(sys.argv) >= 2 and sys.argv[1] == "table":
        tree = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else here)
        print(f"{tree}: the synth's output over a zero-lag reference")
        with Pool(len(CASES)) as pool:
            for line in pool.map(one_case, [(tree, c) for c in CASES]):
                print(line)
    elif len(sys.argv) == 7 and sys.argv[1] == "wav":
        tree, path, key, mic, case = os.path.abspath(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]
        _, _, y, LS = drive(tree, key, mic, case, [(3.0, 6.0), (9.0, 10.0), (13.0, 15.0)])
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(LS.FS)
            w.writeframes((np.clip(y, -1.0, 1.0) * 0.9 * 32767).astype("<i2").tobytes())
        print(f"wrote {path}: {len(y) / LS.FS:.1f} s; pedal off 3-6 s, 9-10 s, 13-15 s")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
