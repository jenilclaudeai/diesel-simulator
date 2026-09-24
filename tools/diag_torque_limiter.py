"""
Known bug #3 -- the torque limiter's residual error.

For every preset with a rating cap, at speeds across the capped range, on a
FRESH engine per measurement (so no turbo or manifold state leaks between
points -- see known bug #5):

  eval_N     operating_point(rpm, load=1, n_cycles=N): what a dyno pull
             reports. N = 8 is the calibration's own convergence, 9 is what
             the web app and grid use, 12 is closer to converged.
  F          the fuel the limiter chose for the cap.
  load_cal   F / fuel_limit_raw: the load the EGR, boost-target and SOI
             schedules see while calibrating (fuel_limit returns the raw
             limit while _calibrating is set).
  T_calcond  torque at F, 8 cycles, with the calibration's schedules.
  T_evalcond torque at F, 8 cycles, with the evaluation's schedules
             (load_est = 1, because F IS fuel_limit once calibrated).

  T_egrfix   as T_calcond, but with EGR forced to its full-load value, so
             only the boost-target and SOI schedules still see load_cal.
  air_lim    the limiter hit its own air ceiling (fuel_for_torque returned
             f_max because the cap was out of reach): a shortfall there is
             the engine running out of air, not limiter error.

So, all at 8 cycles on fresh engines:
  fit error        = T_calcond  - cap   (the secant fit, plus fresh-vs-warm)
  conditions bias  = T_evalcond - T_calcond
    of which EGR   = T_egrfix   - T_calcond
and convergence    = eval_9 - eval_8.

Diagnostic only; changes nothing. Native Python (uses multiprocessing).
Run:  python3 tools/diag_torque_limiter.py
      python3 tools/diag_torque_limiter.py --egr-sweep   (needs the first run's JSON)

--egr-sweep: EGR command vs the EGR fraction actually delivered, at the
limiter's own fuelling for crdi15 at 1650 rpm, with the calibration's boost and
SOI schedules. cycle.py opens the valve to 25 % of full area on the first step
for ANY positive command, so a tiny command is suspected of delivering far
more EGR than it asks for.
"""
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dieselsim.engine import DieselEngine  # noqa: E402

PRESETS = ("crdi15", "crdi_1p5")
RPMS = (1250, 1500, 1650, 1800, 2050, 2250, 2500, 2750, 2900, 3350, 3750, 4000, 4200)


def measure(job):
    preset, rpm = job
    out = {"preset": preset, "rpm": rpm}
    for n in (8, 9, 12):
        eng = DieselEngine(preset=preset)
        op = eng.operating_point(rpm, load=1.0, n_cycles=n)
        out[f"eval_{n}"] = op.torque
        if n == 8:
            out["cap"] = eng.torque_cap(rpm)
            out["F"] = op.fuel_mg
            out["raw"] = eng.fuel_limit_raw(rpm)
            a, b, f_cap = eng._torque_cal[int(round(rpm / 25.0))]
            out["air_lim"] = bool(op.fuel_mg >= f_cap * (1 - 1e-9))
    F = out["F"]
    # calibration's schedules: load_est = F / fuel_limit_raw
    eng = DieselEngine(preset=preset)
    eng._calibrating = True
    out["T_calcond"] = eng.operating_point(rpm, fuel_mg=F, n_cycles=8).torque
    out["egr_cal"] = eng.egr_schedule(rpm, F / out["raw"])
    out["egr_eval"] = eng.egr_schedule(rpm, 1.0)
    eng = DieselEngine(preset=preset)
    eng._calibrating = True
    out["T_egrfix"] = eng.operating_point(rpm, fuel_mg=F, n_cycles=8,
                                          egr=out["egr_eval"]).torque
    # evaluation's schedules: load_est = 1
    eng = DieselEngine(preset=preset)
    eng._torque_cal[int(round(rpm / 25.0))] = (1.0, 0.0, F)   # fuel_limit -> F
    out["load_eval"] = F / eng.fuel_limit(rpm)
    out["T_evalcond"] = eng.operating_point(rpm, fuel_mg=F, n_cycles=8).torque
    out["load_cal"] = F / out["raw"]
    return out


def _egr_point(job):
    rpm, F, cmd, n = job
    eng = DieselEngine(preset="crdi15")
    eng._calibrating = True
    op = eng.operating_point(rpm, fuel_mg=F, n_cycles=n, egr=cmd)
    return {"cmd": cmd, "n": n, "egr_pct": op.egr_pct, "torque": op.torque,
            "boost_pr": op.boost_pr}


def egr_sweep(rpm=1650):
    here = os.path.dirname(__file__)
    rows = json.load(open(os.path.join(here, "..", "out", "diag_torque_limiter.json")))
    F = next(r["F"] for r in rows if r["preset"] == "crdi15" and r["rpm"] == rpm)
    emax = DieselEngine(preset="crdi15").spec.air.egr_max_fraction
    jobs = [(rpm, F, c, n) for n in (9, 20, 40)
            for c in (0.0, 0.001, 0.02, 0.1, 0.2, 0.3)]
    with Pool(max(1, (os.cpu_count() or 2) - 2)) as pool:
        res = pool.map(_egr_point, jobs)
    print(f"crdi15 {rpm} rpm, F = {F:.2f} mg, egr_max_fraction = {emax}")
    print(f"{'cmd':>6} {'n':>3} {'target%':>8} {'actual%':>8} {'torque':>7} {'boost':>6}")
    for r in res:
        print(f"{r['cmd']:6.3f} {r['n']:3d} {100 * r['cmd'] * emax:8.2f} {r['egr_pct']:8.2f}"
              f" {r['torque']:7.1f} {r['boost_pr']:6.3f}")


def converge(rpm=1650):
    """--converge: torque vs n_cycles at the limiter's fuelling, EGR off, on
    fresh engines -- does the point settle, drift, or cycle?"""
    here = os.path.dirname(__file__)
    rows = json.load(open(os.path.join(here, "..", "out", "diag_torque_limiter.json")))
    out = []
    for preset in PRESETS:
        F = next(r["F"] for r in rows if r["preset"] == preset and r["rpm"] == rpm)
        jobs = [(preset, rpm, F, n) for n in (6, 8, 9, 10, 12, 16, 20, 25, 30, 40)]
        with Pool(max(1, (os.cpu_count() or 2) - 2)) as pool:
            res = pool.map(_conv_point, jobs)
        print(f"{preset} {rpm} rpm, F = {F:.2f} mg, EGR 0, fresh engine per n")
        for n, T, b in res:
            print(f"  n={n:3d}  torque {T:7.2f}  boost {b:6.3f}")


def _conv_point(job):
    preset, rpm, F, n = job
    op = DieselEngine(preset=preset).operating_point(rpm, fuel_mg=F, n_cycles=n, egr=0.0)
    return n, op.torque, op.boost_pr


def trace(preset, rpm, F, n=40):
    """--trace: VGT position, shaft speed and boost at the end of every cycle
    of one solve, with the min/max vane position within the cycle."""
    eng = DieselEngine(preset=preset)
    steps = eng.cycle.n
    log = []
    real_step = eng.turbo.step

    def step(*a, **k):
        r = real_step(*a, **k)
        log.append((eng.turbo.vgt_pos, eng.turbo.n_rpm, a[3] / a[1]))
        return r

    eng.turbo.step = step
    # operating_point() on a capped preset first runs the limiter calibration
    # (three 8-cycle solves, via fuel_limit() for load_est); keep only the
    # steps of the final solve
    real_run = eng.cycle.run

    def run(*a, **k):
        log.clear()
        return real_run(*a, **k)

    eng.cycle.run = run
    op = eng.operating_point(rpm, fuel_mg=F, n_cycles=n, egr=0.0)
    assert len(log) == n * steps, (len(log), n * steps)
    vmin = eng.spec.turbo.vgt_min_frac
    print(f"{preset} {rpm} rpm, F = {F:.2f} mg, EGR 0, n = {n}; vgt clamps "
          f"[{vmin}, 1.0]; final torque {op.torque:.2f}")
    print(f"{'cyc':>4} {'vgt_end':>8} {'vgt_min':>8} {'vgt_max':>8} {'turbo_rpm':>10} {'boost':>6}")
    for c in range(n):
        seg = log[c * steps:(c + 1) * steps]
        v = [x[0] for x in seg]
        print(f"{c:4d} {v[-1]:8.3f} {min(v):8.3f} {max(v):8.3f} {seg[-1][1]:10.0f} {seg[-1][2]:6.3f}")


class _OldCalibration(DieselEngine):
    """The limiter as it was before FINDING-013 item 1: calibration solves
    see load_est = f / fuel_limit_raw instead of 1."""
    def operating_point(self, *a, **k):
        if self._calibrating and k.get("load_est") == 1.0:
            k["load_est"] = None
        return super().operating_point(*a, **k)


def _conv_limiter(job):
    variant, preset, rpm = job
    cls = _OldCalibration if variant == "before" else DieselEngine
    eng = cls(preset=preset)
    eng.converged_mode = True
    op = eng.operating_point(rpm, load=1.0)
    return variant, preset, rpm, eng.torque_cap(rpm), op.torque, op.egr_pct


def converged_limiter():
    """--converged: the limiter's residual with every solve converged (real
    time, CONVERGED_CYCLES), before and after calibrating under the
    evaluation's schedules (FINDING-013 item 1)."""
    rpms = (1250, 1650, 2050, 2500, 2900, 3350, 4000)
    jobs = [(v, p, r) for v in ("before", "after") for p in PRESETS for r in rpms]
    with Pool(max(1, (os.cpu_count() or 2) - 2)) as pool:
        res = pool.map(_conv_limiter, jobs)
    print(f"converged ({DieselEngine.CONVERGED_CYCLES} cycles, real time): torque vs cap, %")
    print(f"{'preset':9} {'rpm':>5} {'cap':>6} {'before':>8} {'after':>8}")
    for p in PRESETS:
        for r in rpms:
            b = next(x for x in res if x[:3] == ("before", p, r))
            a = next(x for x in res if x[:3] == ("after", p, r))
            c = b[3]
            print(f"{p:9} {r:5d} {c:6.1f} {100 * (b[4] - c) / c:+8.2f} {100 * (a[4] - c) / c:+8.2f}")


def _pull_point(job):
    mode, preset, rpm = job
    eng = DieselEngine(preset=preset)
    eng.converged_mode = (mode == "converged")
    return mode, preset, rpm, eng.operating_point(rpm, load=1.0, n_cycles=9).torque


def dyno_pull():
    """--pull: every preset's 10-point full-load pull as the web app runs it
    (fresh engine, load 1, n_cycles 9) against converged mode."""
    from dieselsim.config import PRESETS as ALL
    jobs = []
    for p in sorted(ALL):
        s = DieselEngine(preset=p).spec
        rpms = [round((s.idle_rpm + (s.max_rpm - s.idle_rpm) * i / 9) / 50) * 50 for i in range(10)]
        jobs += [(m, p, r) for m in ("fast", "converged") for r in rpms]
    with Pool(max(1, (os.cpu_count() or 2) - 2)) as pool:
        res = pool.map(_pull_point, jobs)
    print("dyno pull, fast (web app) vs converged: torque N.m, error %")
    for p in sorted(ALL):
        rows = sorted({x[2] for x in res if x[1] == p})
        errs = []
        for r in rows:
            f = next(x[3] for x in res if x[:3] == ("fast", p, r))
            c = next(x[3] for x in res if x[:3] == ("converged", p, r))
            e = 100 * (f - c) / abs(c) if abs(c) > 1.0 else float("nan")
            errs.append((abs(e) if e == e else 0.0, r, f, c, e))
            print(f"  {p:9} {r:5d}  fast {f:8.2f}  converged {c:8.2f}  {e:+7.2f}%")
        w = max(errs)
        print(f"  {p}: worst {w[4]:+.2f}% at {w[1]} rpm")


def main():
    jobs = [(p, r) for p in PRESETS for r in RPMS]
    with Pool(max(1, (os.cpu_count() or 2) - 2)) as pool:
        rows = pool.map(measure, jobs)
    pct = lambda x, cap: 100.0 * (x - cap) / cap
    print(f"{'preset':9} {'rpm':>5} {'cap':>6} {'e8%':>6} {'e9%':>6} {'e12%':>6}"
          f" {'fit%':>6} {'cond%':>6} {'egr%':>6} {'conv%':>6} {'load_cal':>8} {'egr_cal':>7} air")
    for r in rows:
        c = r["cap"]
        print(f"{r['preset']:9} {r['rpm']:5d} {c:6.1f} {pct(r['eval_8'], c):+6.2f}"
              f" {pct(r['eval_9'], c):+6.2f} {pct(r['eval_12'], c):+6.2f}"
              f" {pct(r['T_calcond'], c):+6.2f} {100 * (r['T_evalcond'] - r['T_calcond']) / c:+6.2f}"
              f" {100 * (r['T_egrfix'] - r['T_calcond']) / c:+6.2f}"
              f" {100 * (r['eval_9'] - r['eval_8']) / c:+6.2f}"
              f" {r['load_cal']:8.3f} {r['egr_cal']:7.4f} {'AIR' if r['air_lim'] else ''}")
    with open(os.path.join(os.path.dirname(__file__), "..", "out", "diag_torque_limiter.json"), "w") as f:
        json.dump(rows, f, indent=1)


if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "out"), exist_ok=True)
    if "--converged" in sys.argv:
        converged_limiter()
    elif "--pull" in sys.argv:
        dyno_pull()
    elif "--trace" in sys.argv:
        rows = json.load(open(os.path.join(os.path.dirname(__file__), "..", "out",
                                           "diag_torque_limiter.json")))
        for preset in PRESETS:
            trace(preset, 1650, next(r["F"] for r in rows
                                     if r["preset"] == preset and r["rpm"] == 1650))
    elif "--converge" in sys.argv:
        converge()
    elif "--egr-sweep" in sys.argv:
        egr_sweep()
    else:
        main()
