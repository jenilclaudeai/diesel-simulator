"""
One cell of the real-time (rpm x load) grid.

This is the single implementation shared by native Python (play.py) and the
browser (Pyodide, via the SolverPort worker). Keeping it in the package, not in
play.py, is what makes "a grid built in the browser matches one built natively"
checkable at all -- there is only one piece of code to agree with.

Deliberately free of scipy, termios and multiprocessing, so it runs under a
numpy-only Pyodide.
"""
import numpy as np

from .acoustics import EngineSound
from .engine import DieselEngine

# FINDING-011: the grid was solved at n_cycles=6 on one engine iterated
# sequentially -- worst -10.06% against a fresh-engine n_cycles=9 reference,
# errors changing sign across the map.
GRID_CYCLES = 9

# crank-angle sources the runtime needs, kept as float32
SOURCE_KEYS = ("exh_flow", "int_flow", "dpdth", "inj", "valve", "slap")


def solve_cell(spec, rpm, load, n_cycles=GRID_CYCLES, fs=44100):
    """
    Solve one grid cell on a FRESH engine and return (sources, perf).

    Fresh per cell because nothing else isolates a solve: Turbocharger keeps
    shaft speed (n_rpm) and VGT position (vgt_pos) as instance state across
    operating_point calls, and warm_start=False resets only the gas state --
    measured 3.89% off after high-rpm history even with the flag off. This
    also matches exactly how the regression suite's golden values are made.

    `spec` is an EngineSpec object, not a preset name, so rating overrides
    travel with it and nothing depends on a preset registry.
    """
    eng = DieselEngine(spec=spec)
    op = eng.operating_point(float(rpm), load=float(load), n_cycles=n_cycles)
    snd = EngineSound(eng.spec, fs=fs)
    snd.wear = eng.wear
    sd = snd.build_sources(op)
    src = {k: np.asarray(sd[k], dtype=np.float32) for k in SOURCE_KEYS}
    src["_meta"] = sd["_meta"]
    perf = dict(
        torque=op.torque, power=op.power, fuel_mg=op.fuel_mg,
        boost=op.boost_pr, turbo_rpm=op.turbo_rpm,
        afr=op.cycle.afr, soot=op.soot_g_h, nox=op.nox_g_kwh,
        egr=op.egr_pct, T_exh=op.T_exh, p_max=op.p_max,
        bsfc=op.bsfc, fmep=op.fmep, dpdt=op.cycle.dpdtheta_max,
        fuel_kg_h=op.fuel_kg_h,
        # q_wall_frac is heat-to-wall divided by fuel energy, so at zero
        # fuelling it is 0/0 and the solver's 1e-9 floor turns it into a huge
        # number. Clamp it or the coolant node gets a nonsense heat input at
        # low load.
        q_wall=float(np.clip(op.cycle.q_wall_frac, 0.05, 0.45)))
    return src, perf
