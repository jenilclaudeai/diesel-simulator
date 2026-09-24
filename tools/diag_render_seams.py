"""
Known bug #10: seams in EngineSound.render_transient().

render_transient() renders a transient in chunks of `blend` seconds, each an
independent render() call, and joins them with a 20 ms equal-power
cross-fade. Two things are measured, both with the SAME operating point in
every chunk, so anything found is caused by the chunking itself, not by a
change of operating point:

  1. duration: each cross-fade overlaps 20 ms and removes it, so the output
     should be shorter than the log by 20 ms per chunk boundary, and each
     later chunk sits earlier than the rpm trajectory it was rendered for.
  2. firing regularity at the seams: render() integrates crank angle from 0
     on every call, so every chunk restarts at crank angle 0. Firing events
     are found as peaks of the signal envelope; intervals that span a chunk
     boundary are compared with the nominal firing interval and with the
     intervals everywhere else. A single uninterrupted render of the same
     point is the control.

Diagnostic only. Needs scipy (acoustics uses scipy.signal).
Run:  python3 tools/diag_render_seams.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dieselsim.acoustics import EngineSound  # noqa: E402
from dieselsim.engine import DieselEngine  # noqa: E402

PRESET, RPM, LOAD = "crdi15", 1400.0, 0.6
DUR, BLEND = 2.0, 0.25


def envelope(y, fs, win_s=0.002):
    k = max(1, int(win_s * fs))
    return np.sqrt(np.convolve(y * y, np.ones(k) / k, mode="same"))


def firing_times(y, fs, period):
    from scipy.signal import find_peaks
    env = envelope(y, fs)
    pk, _ = find_peaks(env, distance=int(0.7 * period * fs),
                       prominence=0.2 * float(np.percentile(env, 95)))
    return pk / fs


def main():
    eng = DieselEngine(preset=PRESET)
    op = eng.operating_point(RPM, load=LOAD, n_cycles=9)
    snd = EngineSound(eng.spec)
    snd.wear = eng.wear
    fs = snd.fs
    period = 120.0 / RPM / eng.spec.geom.n_cyl       # s between firings, 4-stroke

    # a transient log whose every entry is the same point
    times = np.arange(0.0, DUR + 1e-9, 0.02)
    log = [dict(t=float(t), rpm=RPM, op=op) for t in times]
    src = snd.build_sources(op)

    snd._rng = np.random.default_rng(7)
    single, _ = snd.render(op, duration=DUR, sources=src)
    snd._rng = np.random.default_rng(7)
    chunked = snd.render_transient(eng, log, blend=BLEND)

    n_bound = int(np.ceil(DUR / max(BLEND, 0.15))) - 1
    print(f"{PRESET} {RPM:.0f} rpm / {LOAD}: same operating point in every chunk, "
          f"blend {BLEND} s, fs {fs}")
    print(f"1. duration: log {DUR:.3f} s, single render {len(single) / fs:.3f} s, "
          f"render_transient {len(chunked) / fs:.3f} s "
          f"({1000 * (DUR - len(chunked) / fs):.1f} ms short over {n_bound} boundaries)")

    # boundaries as placed in the OUTPUT: each join overlaps xf samples
    xf = int(0.02 * fs)
    step = int(max(BLEND, 0.15) * fs)
    bounds = [(k + 1) * step - (k + 1) * xf + xf // 2 for k in range(n_bound)]

    print(f"2. firing intervals (nominal {1000 * period:.2f} ms):")
    # the control is judged at the same boundary times: if it shows no
    # elevation there, the metric measures seams and not where it looks
    for name, y, bnd in (("single render (control)", single, bounds),
                         ("render_transient", chunked, bounds)):
        ft = firing_times(y, fs, period)
        iv = np.diff(ft)
        near = np.zeros(len(iv), dtype=bool)
        for b in bnd:
            near |= (ft[:-1] <= b / fs + 0.01) & (ft[1:] >= b / fs - 0.01)
        dev = 100.0 * np.abs(iv - period) / period
        far = dev[~near]
        line = (f"   {name:24} {len(ft)} firings; away from seams: "
                f"median dev {np.median(far):.1f}%, max {far.max():.1f}%")
        if near.any():
            line += (f"; across seams: median dev {np.median(dev[near]):.1f}%, "
                     f"max {dev[near].max():.1f}% ({near.sum()} intervals)")
        print(line)


if __name__ == "__main__":
    main()
