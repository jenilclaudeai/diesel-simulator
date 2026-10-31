"""Do 3-, 5-cylinder and V6 builder engines sound through the live synth?
Solve 2000 rpm / 0.5 (9 cycles), build the sources, stream 1.5 s through
LiveSynth (pure, as the app's port is), and report rms, and the spectrum's
strongest peak below 400 Hz against the firing frequency n_cyl/2 * rpm/60.
usage: python3 p14_sound.py <repo>"""
import json, os, sys
sys.path.insert(0, sys.argv[1])
import numpy as np
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__))
C = {d['key']: d for d in json.load(open(os.path.join(HERE, 'p14_all.json')))}   # p14_mk_all.py
TUNE = {"mhawk75": {"boost_map_rise": 0.12, "afr_limit": 16.0}, "om642": {"boost_map_rise": 0.08, "afr_limit": 15.5}}
RPM = 2000.0


def run(key):
    from dieselsim.builder import from_dict
    from dieselsim.engine import DieselEngine
    from dieselsim.acoustics import EngineSound
    from dieselsim import livesound as LS
    d = {k: v for k, v in C[key].items() if k != "control"}
    d.update(TUNE.get(key, {}))
    eng = DieselEngine(spec=from_dict(d))
    op = eng.operating_point(RPM, load=0.5, n_cycles=9)
    src = EngineSound(eng.spec).build_sources(op)
    syn = LS.LiveSynth(eng.spec, "exterior_7m")
    syn.set_sources(src)
    y = np.concatenate([syn.block(RPM) for _ in range(int(1.5 * LS.FS / LS.BLOCK))])
    y = y[int(0.5 * LS.FS):]
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    f = np.fft.rfftfreq(len(y), 1.0 / LS.FS)
    band = (f > 20) & (f < 400)
    fpk = f[band][np.argmax(spec[band])]
    ffire = eng.spec.geom.n_cyl / 2.0 * RPM / 60.0
    return key, eng.spec.geom.n_cyl, bool(np.all(np.isfinite(y))), float(np.sqrt(np.mean(y ** 2))), float(fpk), ffire


if __name__ == "__main__":
    with Pool(5) as p:
        for k, n, fin, rms, fpk, ff in p.map(run, ["CTL_crdi22", "mhawk75", "revotorq105", "duratorq32", "om642"]):
            print(f"{k:12s} {n} cyl  finite {fin}  rms {rms:.4f}  peak <400 Hz at {fpk:6.1f} Hz  "
                  f"(firing {ff:5.1f} Hz, ratio {fpk / ff:.2f})")
