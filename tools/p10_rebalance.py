"""P10 (reviews/PROPOSAL-P10.md). Usage: python3 tools/p10_rebalance.py . crdi15
What-if, in memory only (nothing in the repo changes): the exterior mic's gains rebalanced;
the centroid, the share below 250 Hz and the RMS."""
import os, sys, dataclasses
import numpy as np
REPO = sys.argv[1]; sys.path.insert(0, REPO)
from dieselsim.builder import load_engine_dir
load_engine_dir(os.path.join(REPO, "engines"))
from dieselsim.engine import DieselEngine
from dieselsim.acoustics import EngineSound
from dieselsim import acoustics as A, livesound as LS
preset = sys.argv[2]
eng = DieselEngine(preset=preset); s = eng.spec
base = A.MICS["exterior_7m"]
seg = 1 << 14; f = np.fft.rfftfreq(seg, 1 / LS.FS)
def run(src, rpm, gains):
    LS.MICS["exterior_7m"] = dataclasses.replace(base, gains=gains)
    syn = LS.LiveSynth(s, "exterior_7m"); syn.set_sources(src)
    y = np.concatenate([syn.block(rpm) for _ in range(int(3 * LS.FS / LS.BLOCK))])[LS.FS:]
    P = np.zeros(seg // 2 + 1)
    for k in range(0, len(y) - seg + 1, seg // 2):
        P += np.abs(np.fft.rfft(y[k:k + seg] * np.hanning(seg))) ** 2
    return (f * P).sum() / P.sum(), P[f < 250].sum() / P.sum() * 100, np.sqrt(np.mean(y ** 2))
for rpm, load in ((800, 0.05), (2000, 0.3)):
    src = EngineSound(s).build_sources(eng.operating_point(rpm, load=load, n_cycles=9))
    for name, k_exh, k_mech, k_comb in (("today", 1, 1, 1), ("exhaust x10", 10, 1, 1), ("exhaust x10, mech /3", 10, 1/3, 1),
                                        ("exhaust x10, mech /3, comb /2", 10, 1/3, 0.5)):
        g = dict(base.gains); g["exhaust"] *= k_exh; g["mech"] *= k_mech; g["combustion"] *= k_comb
        c, low, rms = run(src, rpm, g)
        print(f"{preset} {rpm} rpm {name:30s}: centroid {c:5.0f} Hz, below 250 Hz {low:4.1f}%, rms {rms:.3f}")
