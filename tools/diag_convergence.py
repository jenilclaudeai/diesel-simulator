"""
Does an operating point converge, or does it sit in a limit cycle?

FINDING-013 found crdi15 at 1650 rpm full load swinging 211.6-237.9 N.m with
no trend from 6 to 40 cycles. The per-cycle trace shows the VGT vanes
slamming between their clamps with an 8-cycle period. The suspect is
`spool_accel`: CycleSolver.run() advances the turbo shaft AND the VGT
integral controller 14x faster than real time on every cycle but the last
two, while the manifold pressures the controller reads fill at real time.

Modes (native Python, multiprocessing):

  --map     every preset x 6 speeds x 4 loads, n_cycles=40 on a fresh
            engine: boost at the end of each cycle of the FINAL solve, and
            its spread over cycles 30..37 (accelerated, well past start-up).
            A converged point has ~0 spread; a limit cycle does not.
  --accel   crdi15 1650 rpm full-load fuel, EGR off: the same spread with
            spool_accel = 14 (shipped), 8, 4, 2, 1, each run for the same
            simulated turbo time, plus the final torque.

  --candidates  candidate fixes, applied from outside the solver by
            wrapping Turbocharger.step, scored against a converged reference
            (spool_accel = 1 for ~534 cycles). Each candidate changes only the
            accelerated cycles; real-time (1x) behaviour is untouched:
              shipped  shaft 14x, controller 14x
              C1       shaft 14x, controller 1x
              C2       both ramp 14x -> 1x geometrically over the accelerated cycles
              C3       shaft 14x, controller capped at 2x
              C4       both 4x

Diagnostic only; changes nothing.
Run:  python3 tools/diag_convergence.py --map | --accel | --candidates
"""
import os
import sys
from functools import partial
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dieselsim.engine import DieselEngine  # noqa: E402

PRESETS = ("crdi15", "crdi_1p5", "hd_i6", "ld_i4", "single")
LOADS = (0.25, 0.5, 0.75, 1.0)


def boost_per_cycle(eng, n, **op_kw):
    """Run one operating point; return (op, boost at the end of each cycle of
    the final cycle.run() call). Earlier calls -- the torque limiter's
    calibration on a capped preset -- are discarded."""
    steps = eng.cycle.n
    log = []
    real_step, real_run = eng.turbo.step, eng.cycle.run

    def step(*a, **k):
        r = real_step(*a, **k)
        log.append(a[3] / a[1])            # p_intake / p_amb
        return r

    def run(*a, **k):
        log.clear()
        return real_run(*a, **k)

    eng.turbo.step, eng.cycle.run = step, run
    op = eng.operating_point(n_cycles=n, **op_kw)
    assert len(log) == n * steps, (len(log), n * steps)
    return op, [log[(c + 1) * steps - 1] for c in range(n)]


def spread(b, lo, hi):
    w = b[lo:hi]
    m = sum(w) / len(w)
    return 100.0 * (max(w) - min(w)) / m


def _map_point(job):
    preset, rpm, load = job
    eng = DieselEngine(preset=preset)
    if not eng.spec.turbo.enabled:
        # no turbo loop, nothing to oscillate: report the same metric anyway
        pass
    op, b = boost_per_cycle(eng, 40, rpm=rpm, load=load)
    return preset, rpm, load, spread(b, 30, 38), op.torque, eng.turbo.vgt_pos


def map_all():
    jobs = []
    for p in PRESETS:
        s = DieselEngine(preset=p).spec
        for i in range(6):
            rpm = round((s.idle_rpm + (s.rated_rpm - s.idle_rpm) * i / 5) / 50) * 50
            jobs += [(p, rpm, ld) for ld in LOADS]
    with Pool(max(1, (os.cpu_count() or 2) - 2)) as pool:
        res = pool.map(_map_point, jobs)
    print("boost spread over cycles 30..37 of a 40-cycle solve, % of mean "
          "(fresh engine per point)")
    print(f"{'preset':9} {'rpm':>5} " + " ".join(f"{'load ' + str(ld):>10}" for ld in LOADS))
    bad = 0
    for p in PRESETS:
        for rpm in sorted({r[1] for r in res if r[0] == p}):
            cells = [next(r for r in res if r[:3] == (p, rpm, ld)) for ld in LOADS]
            bad += sum(c[3] > 1.0 for c in cells)
            print(f"{p:9} {rpm:5d} " + " ".join(
                f"{c[3]:9.2f}{'*' if c[3] > 1.0 else ' '}" for c in cells))
    print(f"\n* spread > 1 %: {bad} of {len(res)} points")


def _accel_point(job):
    accel, n, F = job
    eng = DieselEngine(preset="crdi15")
    eng.cycle.run = partial(eng.cycle.run, spool_accel=accel)
    op, b = boost_per_cycle(eng, n, rpm=1650, fuel_mg=F, egr=0.0)
    # the last 8 accelerated cycles (the final two always run at 1x)
    return accel, n, spread(b, n - 10, n - 2), op.torque, b[-3]


def accel_sweep():
    F = 48.85   # the limiter's fuelling at crdi15 1650 rpm (FINDING-013)
    # same simulated turbo time as 40 cycles at 14x (38 x 14 = 532 cycle-times)
    jobs = [(a, 2 + max(10, round(38 * 14 / a))) for a in (14, 8, 4, 2, 1)]
    with Pool(max(1, (os.cpu_count() or 2) - 2)) as pool:
        res = pool.map(_accel_point, [(a, n, F) for a, n in jobs])
    print(f"crdi15 1650 rpm, F = {F} mg, EGR 0, fresh engine")
    print(f"{'accel':>5} {'n':>4} {'spread%':>8} {'boost':>6} {'torque':>7}")
    for a, n, sp, T, b in res:
        print(f"{a:5d} {n:4d} {sp:8.2f} {b:6.3f} {T:7.2f}")


SHIPPED = 14.0


def _ramp(c, n):
    k = n - 2                                  # accelerated cycles
    if c >= k:
        return 1.0
    return SHIPPED ** (1.0 - c / max(k - 1, 1)) if k > 1 else SHIPPED


CANDIDATES = {
    # name: (shaft accel(c, n), controller accel(c, n)); c < n - 2 only
    "shipped": (lambda c, n: SHIPPED, lambda c, n: SHIPPED),
    "C1": (lambda c, n: SHIPPED, lambda c, n: 1.0),
    "C2": (_ramp, _ramp),
    "C3": (lambda c, n: SHIPPED, lambda c, n: min(SHIPPED, 2.0)),
    "C4": (lambda c, n: 4.0, lambda c, n: 4.0),
}


def apply_candidate(eng, name, n):
    """Wrap eng.turbo.step so the final cycle.run() uses the candidate's
    shaft and controller acceleration. Applies to every cycle.run() call
    (the limiter's calibration too), keyed on the call's own cycle index."""
    shaft_a, ctrl_a = CANDIDATES[name]
    steps = eng.cycle.n
    t = eng.turbo
    real_step, real_run = t.step, eng.cycle.run
    st = {"i": 0, "n": n}

    def run(*a, **k):
        st["i"], st["n"] = 0, k.get("n_cycles", n)
        return real_run(*a, **k)

    def step(dt, p_amb, T_amb, p_int, *rest):
        m = st["n"]
        c = st["i"] // steps
        st["i"] += 1
        shipped = SHIPPED if c < m - 2 else 1.0
        dt0 = dt / shipped
        sa = shaft_a(c, m) if c < m - 2 else 1.0
        ca = ctrl_a(c, m) if c < m - 2 else 1.0
        v0 = t.vgt_pos
        r = real_step(dt0 * sa, p_amb, T_amb, p_int, *rest)
        if t.s.vgt and ca != sa:
            bt = rest[-1] if rest else None
            tgt = bt if bt else t.s.wastegate_pset
            err = p_int / max(p_amb, 1e4) - tgt
            t.vgt_pos = min(1.0, max(t.s.vgt_min_frac, v0 + 2.5 * err * dt0 * ca))
        return r

    t.step, eng.cycle.run = step, run


def _cand_point(job):
    name, preset, rpm, load, flim, n = job
    eng = DieselEngine(preset=preset)
    # Same fuelling and schedules for every candidate: pre-seed the limiter
    # cache so fuel_limit() returns the shipped calibration's value without
    # re-running the calibration under the candidate (capped presets only).
    if eng.torque_cap(rpm) is not None:
        eng._torque_cal[int(round(rpm / 25.0))] = (1.0, 0.0, flim)
    if name == "reference":
        eng.cycle.run = partial(eng.cycle.run, spool_accel=1.0)
        op, b = boost_per_cycle(eng, n, rpm=rpm, fuel_mg=load * flim)
        return name, preset, rpm, load, n, op.torque, spread(b, n - 22, n - 2)
    apply_candidate(eng, name, n)
    op = eng.operating_point(rpm, fuel_mg=load * flim, n_cycles=n)
    return name, preset, rpm, load, n, op.torque, None


CAND_POINTS = (  # preset, rpm, load -- the worst limit cycles in --map, plus
    ("crdi15", 1450, 1.0),     # points that already converge (controls)
    ("crdi15", 2100, 0.75),
    ("crdi15", 4000, 0.25),
    ("crdi_1p5", 2100, 0.5),
    ("crdi_1p5", 3350, 0.25),
    ("hd_i6", 1100, 1.0),
    ("hd_i6", 1300, 1.0),      # control
    ("ld_i4", 2100, 0.5),      # control
    ("crdi15", 800, 1.0),      # control
)


def candidates():
    pts = [(p, r, ld, DieselEngine(preset=p).fuel_limit(r)) for p, r, ld in CAND_POINTS]
    jobs = [("reference", p, r, ld, f, 534) for p, r, ld, f in pts]
    jobs += [(c, p, r, ld, f, n) for c in CANDIDATES for p, r, ld, f in pts for n in (9, 12)]
    with Pool(max(1, (os.cpu_count() or 2) - 2)) as pool:
        res = pool.map(_cand_point, jobs)
    ref = {(p, r, ld): (T, sp) for c, p, r, ld, n, T, sp in res if c == "reference"}
    print("torque error vs converged reference (spool_accel 1, 534 cycles), %")
    cols = [f"{p[:6]}@{r}/{ld}" for p, r, ld, _ in pts]
    print(f"{'':12} " + " ".join(f"{c:>15}" for c in cols) + f" {'worst':>7} {'rms':>6}")
    print(f"{'reference':12} " + " ".join(f"{ref[k[:3]][0]:15.2f}" for k in pts))
    print(f"{'ref spread%':12} " + " ".join(f"{ref[k[:3]][1]:15.3f}" for k in pts))
    for c in CANDIDATES:
        for n in (9, 12):
            errs = []
            for p, r, ld, _ in pts:
                T = next(T for cc, pp, rr, ll, nn, T, _ in res if (cc, pp, rr, ll, nn) == (c, p, r, ld, n))
                errs.append(100 * (T - ref[(p, r, ld)][0]) / ref[(p, r, ld)][0])
            rms = (sum(e * e for e in errs) / len(errs)) ** 0.5
            print(f"{c + ' n=' + str(n):12} " + " ".join(f"{e:+15.2f}" for e in errs)
                  + f" {max(errs, key=abs):+7.2f} {rms:6.2f}")


if __name__ == "__main__":
    if "--candidates" in sys.argv:
        candidates()
        sys.exit()
    if "--accel" in sys.argv:
        accel_sweep()
    else:
        map_all()
