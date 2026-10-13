"""P10 (ADR-018): each mic's level trim, matched at a cruise.

    python3 tools/p10_trim.py TREE > levels.json                 # the synth's RMS per engine and mic
    python3 tools/p10_trim.py TREE --ref old_levels.json         # + the trim that matches old_levels

TREE is a checkout (its dieselsim/ and engines/). Run it on the tree before the balance changed, then on
the new tree with acoustics.MIC_TRIM all 1.0: each mic's trim is the median, over the Enjoy roster, of
old RMS / new RMS at half the rated rpm and 30% load, after 1 s of settling. The median, because
single10's exhaust outweighs everything else on it (its cabin ratio is 0.24 against 0.86-1.01).
"""
import json
import os
import sys

TREE = sys.argv[1]
sys.path.insert(0, TREE)
import numpy as np  # noqa: E402
from dieselsim.builder import load_engine_dir  # noqa: E402
load_engine_dir(os.path.join(TREE, "engines"))
from dieselsim.engine import DieselEngine  # noqa: E402
from dieselsim.acoustics import EngineSound, MICS  # noqa: E402
from dieselsim import livesound as LS  # noqa: E402

ROSTER = ("crdi15", "hatch15", "crdi22", "truck127", "v8hd", "single10")


def levels():
    out = {}
    for preset in ROSTER:
        eng = DieselEngine(preset=preset)
        rpm = 0.5 * eng.spec.rated_rpm
        src = EngineSound(eng.spec).build_sources(eng.operating_point(rpm, load=0.3, n_cycles=9))
        for mic in MICS:
            syn = LS.LiveSynth(eng.spec, mic)
            syn.set_sources(src)
            y = np.concatenate([syn.block(rpm) for _ in range(int(2.5 * LS.FS / LS.BLOCK))])[LS.FS:]
            out[f"{preset}/{mic}"] = float(np.sqrt(np.mean(y ** 2)))
        print(f"{preset} at {rpm:.0f} rpm, 30%: done", file=sys.stderr, flush=True)
    return out


def main():
    new = levels()
    if "--ref" not in sys.argv:
        print(json.dumps(new, indent=1))
        return
    ref = json.load(open(sys.argv[sys.argv.index("--ref") + 1]))
    for mic in MICS:
        r = [ref[f"{p}/{mic}"] / new[f"{p}/{mic}"] for p in ROSTER]
        q = sorted(r)
        g = 0.5 * (q[len(q) // 2 - 1] + q[len(q) // 2])
        print(f"{mic:12s} trim {g:.3f}   per engine: " + " ".join(f"{p} {x:.2f}" for p, x in zip(ROSTER, r)))


if __name__ == "__main__":
    main()
