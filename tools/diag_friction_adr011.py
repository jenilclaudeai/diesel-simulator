"""
ADR-011 measurements: how should the real-time loop get friction?

  --surface  FMEP over oil x coolant temperature (converged, fuel fixed):
             how many oil-viscosity nodes a piecewise-linear surface needs,
             and whether coolant separates additively.
  --trace    friction evaluated from a pressure trace solved at a DIFFERENT
             oil temperature, against a full solve: if oil state never
             touches the trace, trace-based friction is exact.
  --timing   one friction.evaluate() call, and where its time goes.

Run:  python3 tools/diag_friction_adr011.py --surface | --trace | --timing
"""
import json
import math
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dieselsim.engine import DieselEngine  # noqa: E402

POINTS = (("crdi15", 1800, 0.6), ("crdi15", 2500, 0.3), ("hd_i6", 1400, 0.6))
OIL = (273.0, 278.0, 283.0, 293.0, 303.0, 318.0, 333.0, 348.0, 363.0)
COOL = (273.0, 318.0, 363.0)


def _warm_fuel(pt):
    e = DieselEngine(preset=pt[0])
    e.converged_mode = True
    return pt, e.fuel_limit(float(pt[1]))


def _surface_job(a):
    pt, f, To, Tc = a
    p, r, l = pt
    e = DieselEngine(preset=p)
    e.converged_mode = True
    e.seed_fuel_limit(float(r), f)
    e.T_coolant = Tc
    e._apply_thermal_state()
    e.oil.cond.T_oil = To
    op = e.operating_point(float(r), fuel_mg=l * f)
    return pt, To, Tc, op.fmep / 1e5, e.oil.viscosity(To)


def surface():
    with Pool(max(1, (os.cpu_count() or 2) - 2)) as pool:
        fl = dict(pool.map(_warm_fuel, POINTS))
        res = pool.map(_surface_job, [(pt, fl[pt], To, Tc) for pt in POINTS for Tc in COOL for To in OIL])
    F = {(pt, To, Tc): f for pt, To, Tc, f, mu in res}
    MU = {To: mu for pt, To, Tc, f, mu in res if pt == POINTS[0]}
    print("FMEP piecewise-linear in oil viscosity, k nodes even in log viscosity; worst error elsewhere")
    for k in (2, 3, 4, 5):
        lm = np.linspace(math.log(MU[OIL[0]]), math.log(MU[OIL[-1]]), k)
        nd = sorted({min(OIL, key=lambda T: abs(math.log(MU[T]) - v)) for v in lm}, key=lambda T: MU[T])
        worst = max(abs(float(np.interp(MU[T], [MU[n] for n in nd], [F[(pt, n, Tc)] for n in nd]))
                        / F[(pt, T, Tc)] - 1)
                    for pt in POINTS for Tc in COOL for T in OIL if T not in nd)
        print(f"  k={k} nodes {[int(T) for T in sorted(nd)]} K: worst {100 * worst:.2f}%")
    worst = max(abs((F[(pt, T, 363.0)] + F[(pt, 363.0, Tc)] - F[(pt, 363.0, 363.0)]) / F[(pt, T, Tc)] - 1)
                for pt in POINTS for Tc in COOL for T in OIL)
    print(f"coolant additively separable? worst error {100 * worst:.2f}%")


def _trace_job(pt):
    p, r, l = pt
    w = DieselEngine(preset=p)
    w.converged_mode = True
    f = w.fuel_limit(float(r))
    out = []
    for Ts, Te in ((273.0, 363.0), (363.0, 273.0), (303.0, 333.0)):
        a = DieselEngine(preset=p)
        a.converged_mode = True
        a.seed_fuel_limit(float(r), f)
        a.oil.cond.T_oil = Ts
        opa = a.operating_point(float(r), fuel_mg=l * f)
        a.oil.cond.T_oil = Te
        fr = a.friction.evaluate(opa.cycle.traces.theta, opa.cycle.traces.p[0], float(r), a.oil, a.wear,
                                 fuel_mg=l * f, p_rail=opa.cycle.rail_pressure)
        b = DieselEngine(preset=p)
        b.converged_mode = True
        b.seed_fuel_limit(float(r), f)
        b.oil.cond.T_oil = Te
        opb = b.operating_point(float(r), fuel_mg=l * f)
        out.append((Ts, Te, fr["fmep"] / 1e5, opb.fmep / 1e5, opa.cycle.imep_net, opb.cycle.imep_net))
    return pt, out


def trace():
    with Pool(3) as pool:
        for pt, rows in pool.map(_trace_job, POINTS):
            for Ts, Te, ft, ff, ia, ib in rows:
                print(f"{pt[0]} {pt[1]}/{pt[2]}  trace at oil {Ts:.0f} K, friction at {Te:.0f} K: "
                      f"FMEP {ft:.4f} vs full {ff:.4f} ({100 * (ft / ff - 1):+.3f}%); "
                      f"IMEP differs {100 * (ia / ib - 1):+.3f}%")


def timing():
    import cProfile
    import io
    import pstats
    e = DieselEngine(preset="crdi15")
    op = e.operating_point(1800, load=0.6, n_cycles=9)
    tr = op.cycle.traces
    call = lambda: e.friction.evaluate(tr.theta, tr.p[0], 1800.0, e.oil, e.wear,
                                       fuel_mg=op.fuel_mg, p_rail=op.cycle.rail_pressure)
    t = time.perf_counter()
    for _ in range(50):
        call()
    print(f"friction.evaluate: {1e3 * (time.perf_counter() - t) / 50:.2f} ms per call (native Python)")
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(10):
        call()
    pr.disable()
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("tottime").print_stats(3)
    print(s.getvalue()[:1200])


if __name__ == "__main__":
    {"--surface": surface, "--trace": trace, "--timing": timing}.get(
        next((a for a in sys.argv[1:] if a.startswith("--")), "--trace"), trace)()
