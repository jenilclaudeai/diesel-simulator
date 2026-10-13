"""P10 (reviews/PROPOSAL-P10.md). Usage: python3 tools/p10_sound_split.py . crdi15 800 0.05 [mic]
Per source: its share of the mix's power, and how much of it is below 250 Hz; the firing harmonics' levels."""
import os, sys
import numpy as np
REPO = sys.argv[1]; sys.path.insert(0, REPO)
from dieselsim.builder import load_engine_dir
load_engine_dir(os.path.join(REPO, "engines"))
from dieselsim.engine import DieselEngine
from dieselsim.acoustics import EngineSound, MICS
from dieselsim import livesound as LS
preset, rpm, load = sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
mic = sys.argv[5] if len(sys.argv) > 5 else "exterior_7m"
eng = DieselEngine(preset=preset); s = eng.spec
op = eng.operating_point(rpm, load=load, n_cycles=9)
src = EngineSound(s).build_sources(op)
syn = LS.LiveSynth(s, mic); syn.set_sources(src)
ys, acc = [], {}
for i in range(int(3.0 * LS.FS / LS.BLOCK)):
    ys.append(syn.block(rpm))
    if i * LS.BLOCK >= LS.FS:
        for k, v in syn.last_parts.items(): acc.setdefault(k, []).append(v)
y = np.concatenate(ys)[LS.FS:]
seg = 1 << 15
f = np.fft.rfftfreq(seg, 1 / LS.FS)
def psd(x):
    P = np.zeros(seg // 2 + 1)
    for k in range(0, len(x) - seg + 1, seg // 2):
        P += np.abs(np.fft.rfft(x[k:k + seg] * np.hanning(seg))) ** 2
    return P
g = MICS[mic].gains
tot = sum(psd(np.concatenate(v)).sum() * g.get(k, 1) ** 2 for k, v in acc.items())
print(f"{preset} {rpm:.0f} rpm load {load} [{mic}] mic gains {g}")
for k, v in acc.items():
    x = np.concatenate(v); P = psd(x)
    print(f"  {k:11s} share (x mic gain^2, before the mic filters) = {P.sum()*g.get(k,1)**2/tot*100:6.1f}% of mix;  below 250 Hz: {P[f<250].sum()/P.sum()*100:5.1f}% of itself; centroid {(f*P).sum()/P.sum():5.0f} Hz")
P = psd(y); ff = rpm / 60 * s.geom.n_cyl / 2
ref = P.max()
print("  firing harmonics, dB below the mix's strongest bin: " + ", ".join(
    f"{h*ff:.0f} Hz {10*np.log10(P[(f>h*ff-2)&(f<h*ff+2)].max()/ref):+.0f}" for h in range(1, 7)))
print(f"  strongest bin: {f[np.argmax(P)]:.0f} Hz")
