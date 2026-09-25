"""
REVIEW-002 (ADR-006 reassessment): how an operating point responds to
temperature, and how well a two-grid (cold, warm) linear interpolation
reproduces it.

Converged solves (real time, 200 cycles) at fixed fuel -- the warm engine's
converged full-load fuel times the load, seeded so every temperature burns
the same fuel and only temperature changes. Three sweeps, 273-363 K:
  coolant   coolant swept, oil warm
  oil       oil swept, coolant warm
  both      oil and coolant together (a warm-up, idealised)

Run:  python3 tools/diag_cold_sensitivity.py
      python3 tools/diag_cold_sensitivity.py --visc   (which axis to interpolate friction on)
"""
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dieselsim.engine import DieselEngine  # noqa: E402

POINTS = (("crdi15", 1800, 0.6), ("crdi15", 2500, 0.3), ("hd_i6", 1400, 0.6))
TEMPS = (273.0, 293.0, 313.0, 333.0, 353.0, 363.0)
KEYS = ("torque", "fmep", "ign", "premix", "dpdth_c")


def warm_fuel(pt):
    p, r, l = pt
    e = DieselEngine(preset=p)
    e.converged_mode = True
    return pt, e.fuel_limit(float(r))


def job(a):
    (p, r, l), f_lim, mode, T = a
    e = DieselEngine(preset=p)
    e.converged_mode = True
    e.seed_fuel_limit(float(r), f_lim)
    warm_oil = e.oil.cond.T_oil
    if mode in ("coolant", "both"):
        e.T_coolant = T
        e._apply_thermal_state()
    e.oil.cond.T_oil = T if mode in ("oil", "both") else warm_oil
    op = e.operating_point(float(r), fuel_mg=l * f_lim)
    c = op.cycle
    return (p, r, l), mode, T, dict(torque=op.torque, fmep=op.fmep / 1e5, ign=c.ign_delay_deg,
                                    premix=c.premix_fraction, dpdth_c=c.dpdtheta_comb)


def main():
    with Pool(max(1, (os.cpu_count() or 2) - 2)) as pool:
        flim = dict(pool.map(warm_fuel, POINTS))
        jobs = [(pt, flim[pt], m, T) for pt in POINTS for m in ("coolant", "oil", "both") for T in TEMPS]
        res = pool.map(job, jobs)
    for pt in POINTS:
        print(f"\n{pt[0]} {pt[1]} rpm / {pt[2]}  (fixed fuel {pt[2] * flim[pt]:.2f} mg)")
        for m in ("coolant", "oil", "both"):
            rows = {T: v for q, mm, T, v in res if q == pt and mm == m}
            cold, warm = rows[TEMPS[0]], rows[TEMPS[-1]]
            print(f"  sweep {m:7}: " + "  ".join(
                f"{k} {100 * (cold[k] - warm[k]) / abs(warm[k]):+6.1f}%" for k in KEYS) + "   (273 K vs 363 K)")
            if m == "both":
                print("    two-grid linear interpolation error (273/363 endpoints):")
                for T in TEMPS[1:-1]:
                    x = (T - TEMPS[0]) / (TEMPS[-1] - TEMPS[0])
                    errs = []
                    for k in KEYS:
                        lin = cold[k] + x * (warm[k] - cold[k])
                        errs.append(f"{k} {100 * (lin - rows[T][k]) / abs(rows[T][k]):+6.1f}%")
                    print(f"      {T:.0f} K: " + "  ".join(errs))


if __name__ == "__main__" and "--visc" not in sys.argv:
    main()


def _visc_job(a):
    (p, r, l), f_lim, T = a
    e = DieselEngine(preset=p)
    e.converged_mode = True
    e.seed_fuel_limit(float(r), f_lim)
    e.oil.cond.T_oil = T
    op = e.operating_point(float(r), fuel_mg=l * f_lim)
    return (p, r, l), T, e.oil.viscosity(T), op.fmep / 1e5, op.torque


def viscosity_axis():
    """--visc: oil-only sweep. Is FMEP closer to linear in oil temperature,
    oil viscosity, or log viscosity? (Which axis a two-endpoint scheme
    should interpolate on.)"""
    import math
    temps = (273.0, 283.0, 293.0, 303.0, 313.0, 333.0, 363.0)
    pts = POINTS
    with Pool(max(1, (os.cpu_count() or 2) - 2)) as pool:
        flim = dict(pool.map(warm_fuel, pts))
        res = pool.map(_visc_job, [(pt, flim[pt], T) for pt in pts for T in temps])
    for pt in pts:
        rows = sorted((T, mu, f, tq) for q, T, mu, f, tq in res if q == pt)
        (T0, m0, f0, t0), (T1, m1, f1, t1) = rows[0], rows[-1]
        print(f"\n{pt[0]} {pt[1]}/{pt[2]}: FMEP linear interpolation error between 273 and 363 K, by axis")
        print(f"  {'T K':>5} {'visc mPa.s':>10} {'FMEP bar':>9} {'in T':>8} {'in visc':>8} {'in log visc':>11}")
        for T, mu, f, tq in rows:
            e = lambda x, x0, x1: 100 * ((f0 + (x - x0) / (x1 - x0) * (f1 - f0)) - f) / f
            print(f"  {T:5.0f} {1e3 * mu:10.2f} {f:9.3f} {e(T, T0, T1):+7.1f}% {e(mu, m0, m1):+7.1f}% "
                  f"{e(math.log(mu), math.log(m0), math.log(m1)):+10.1f}%")


if __name__ == "__main__" and "--visc" in sys.argv:
    viscosity_axis()
