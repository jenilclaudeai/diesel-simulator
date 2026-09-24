#!/usr/bin/env python3
"""
Physics regression suite.

Dependency-free on purpose -- runs with `python3 tests/test_physics.py`,
no pytest required, so it works in any container that can already import
dieselsim.

Two kinds of test here:

  PASS tests  -- lock numbers that are currently correct. If one of these
                 fails, something regressed and you need to explain why
                 before merging.

  KNOWN tests -- encode a defect that is diagnosed but not yet fixed. These
                 report KNOWN, not FAIL. When the defect is fixed the test
                 flips to UNEXPECTED PASS, which is the signal to promote it
                 to a PASS test and delete the note.

Exit code is non-zero only on a real FAIL.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dieselsim.engine import DieselEngine  # noqa: E402

RESULTS = []


def check(name, actual, expected, rel_tol, note=""):
    ok = abs(actual - expected) <= rel_tol * abs(expected)
    RESULTS.append(("PASS" if ok else "FAIL", name, actual, expected, note))
    return ok


def known(name, cond, note):
    """Records a diagnosed defect. Not a failure."""
    RESULTS.append(("KNOWN" if cond else "UNEXPECTED PASS",
                    name, None, None, note))


# --------------------------------------------------------------------- #
# Golden operating points
#
# Captured 2026-09-08 on the pre-fix tree and confirmed bit-identical after
# removing the double-counted pilot multiplier (FINDING-001 P-1). Tolerance
# is 0.5% -- these come from a deterministic solver, so anything larger
# means a real change.
#
# hd_i6 @ 1700 rpm reproduces the 2310 N.m peak torque in
# PROJECT_CONTEXT.md section 1.5.
# --------------------------------------------------------------------- #

# Re-baselined 2026-09-08 after FINDING-001 P-2 replaced the Watson premixed-
# fraction correlation with premix = tau / dur_main. Torque and BSFC moved
# under 1%; p_max rose ~3% everywhere, which is the physically expected
# direction (more premixed burn -> sharper, higher peak). hd_i6 p_max goes
# 173.7 -> 178.5 bar, still inside the 160-200 bar band in
# PROJECT_CONTEXT.md section 1.5, and hd_i6 torque still reproduces the
# documented 2310 N.m.
GOLDEN = {
    ("crdi15", 1800, 0.6): dict(torque=124.391, bsfc=265.40, pmax=110.78),
    ("crdi15", 3000, 1.0): dict(torque=219.675, bsfc=214.70, pmax=151.98),
    ("hd_i6", 1700, 1.0): dict(torque=2313.331, bsfc=214.11, pmax=178.53),
}


def test_golden_points():
    for (preset, rpm, load), exp in GOLDEN.items():
        eng = DieselEngine(preset=preset)
        op = eng.operating_point(rpm, load=load, n_cycles=9)
        tag = f"{preset}@{rpm}/{load}"
        check(f"{tag} torque", op.torque, exp["torque"], 0.005)
        check(f"{tag} bsfc", op.bsfc, exp["bsfc"], 0.005)
        check(f"{tag} p_max", op.p_max / 1e5, exp["pmax"], 0.005)


def test_n_cycles_convergence():
    """Known bug #1: results at n_cycles=6 run a few percent light."""
    eng = DieselEngine(preset="crdi15")
    t6 = eng.operating_point(1800, load=0.6, n_cycles=6).torque
    eng = DieselEngine(preset="crdi15")
    t12 = eng.operating_point(1800, load=0.6, n_cycles=12).torque
    drift = abs(t12 - t6) / t12
    known("n_cycles=6 not converged", drift > 0.005,
          f"drift {100 * drift:.2f}% vs n_cycles=12 -- use >=9 (bug #1)")


def test_premix_responds_to_temperature():
    """
    Promoted to a real assertion 2026-09-08. FINDING-001 P-2 replaced the
    Watson correlation with premix = tau / dur_main, so the premixed
    fraction now responds to charge temperature instead of sitting pinned
    at its 0.02 floor. Guards against regression.
    """
    vals = []
    for T in (273.0, 363.0):
        eng = DieselEngine(preset="crdi15")
        eng.T_coolant = T
        eng._apply_thermal_state()
        vals.append(eng.operating_point(
            1800, load=0.6, n_cycles=9).cycle.premix_fraction)
    swing = abs(vals[0] - vals[1]) / max(vals[1], 1e-9)
    check("premix responds to coolant T", 1.0 if swing > 0.20 else 0.0, 1.0,
          0.0, f"cold {vals[0]:.4f} vs warm {vals[1]:.4f}, swing "
               f"{100 * swing:.0f}% (must exceed 20%)")


def test_cold_start_sharpens_dpdtheta():
    """
    A cold diesel should rattle: colder walls -> longer delay -> bigger
    premixed spike -> sharper dp/dtheta. PROJECT_CONTEXT section 1.4 claims
    this. Downstream of FINDING-001, the effect is present but far too
    small to hear. Threshold of 15% is a judgement call, not a measurement.
    """
    vals = []
    for T in (273.0, 363.0):
        eng = DieselEngine(preset="crdi15")
        eng.T_coolant = T
        eng._apply_thermal_state()
        vals.append(eng.operating_point(
            1800, load=0.6, n_cycles=9).cycle.dpdtheta_max)
    cold, warm = vals
    rise = (cold - warm) / warm
    known("cold start sharpens whole-cycle dp/dtheta", rise < 0.15,
          f"raw dp/dtheta only {100 * rise:+.1f}% -- expected, it is "
          f"compression-dominated (FINDING-002); use dpdtheta_comb")


def test_combustion_dpdtheta_responds():
    """
    FINDING-002: dpdtheta_max peaks ~10 deg before ignition, so it measures
    compression. dpdtheta_comb subtracts the motored trace and leaves the
    rise combustion actually caused, which does respond to temperature.
    """
    vals = []
    for T in (273.0, 363.0):
        eng = DieselEngine(preset="crdi15")
        eng.T_coolant = T
        eng._apply_thermal_state()
        vals.append(eng.operating_point(
            1800, load=0.6, n_cycles=9).cycle.dpdtheta_comb)
    rise = (vals[0] - vals[1]) / vals[1]
    check("combustion dp/dtheta responds to coolant T",
          1.0 if rise > 0.08 else 0.0, 1.0, 0.0,
          f"cold is {100 * rise:+.1f}% sharper (must exceed 8%)")


def test_sharp_not_clamped():
    """
    FINDING-003: the clatter high-mode weight was min(3.0, dpdt_max/6.0e6)
    with dpdt_max around 5e9, so it sat pinned at its ceiling for every
    engine at every operating point.
    """
    src = os.path.join(os.path.dirname(__file__), "..",
                       "dieselsim", "acoustics.py")
    with open(src) as fh:
        body = fh.read()
    check("sharp divisor rescaled",
          0.0 if 'dpdt_max"] / 6.0e6' in body else 1.0, 1.0, 0.0,
          "6.0e6 pins sharp at its 3.0 ceiling")


def test_transient_stalls_cleanly():
    """
    FINDING-012: lugging below stall used to return nan in the log and then
    crash three frames downstream, because the 150 rpm floor sat inside the
    solver's failure region and max(nan, floor) is nan. It must now stop with
    stalled=True and no non-finite values.
    """
    import math
    import warnings
    warnings.filterwarnings("ignore")
    eng = DieselEngine(preset="crdi15")
    log = eng.transient(1.0, lambda t: 0.2, lambda t, rpm: 60.0,
                        dt=0.02, n_cycles=3)
    finite = all(math.isfinite(e["rpm"]) for e in log)
    check("transient stall is clean",
          1.0 if (finite and log[-1]["stalled"]) else 0.0, 1.0, 0.0,
          f"{len(log)} steps, stalled={log[-1]['stalled']}, "
          f"all finite={finite}")


def test_package_is_numpy_only_at_import():
    """
    ADR-001: the browser runs the solver under a numpy-only Pyodide, and the
    real-time grid must build there too. That holds only while no module in
    dieselsim/ imports scipy at MODULE level -- acoustics.py used to, which
    made the whole grid path unimportable in the browser even though no scipy
    code ran. Imports inside functions, or the _LazySignal shim, are fine.

    Static rather than a subprocess test, because this suite also runs under
    Pyodide (tools/pyodide), where subprocesses do not exist.
    """
    import ast
    pkg = os.path.join(os.path.dirname(__file__), "..", "dieselsim")
    offenders = []
    for fn in sorted(os.listdir(pkg)):
        if not fn.endswith(".py"):
            continue
        with open(os.path.join(pkg, fn)) as fh:
            tree = ast.parse(fh.read())
        for node in tree.body:                      # module level only
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any(n.split(".")[0] == "scipy" for n in names):
                offenders.append(f"{fn}:{node.lineno}")
    check("no module-level scipy import in dieselsim/",
          0.0 if offenders else 1.0, 1.0, 0.0,
          ", ".join(offenders) if offenders else "numpy-only at import")


def test_override_typo_rejected():
    """
    batch._apply used a bare setattr, so "turbo.turbin_area_eff" silently
    created a new attribute and a sweep reported 'no effect'. Overrides are
    now validated: unknown paths, type mismatches and non-finite values raise.
    """
    from dieselsim.config import PRESETS
    from dieselsim.overrides import OverrideError, apply_overrides
    caught = 0
    for bad in ({"turbo.turbin_area_eff": 1.0},      # typo
                {"afr_limit": "18"},                  # wrong type
                {"afr_limit": float("nan")}):         # non-finite
        try:
            apply_overrides(PRESETS["crdi15"](), bad)
        except OverrideError:
            caught += 1
    spec = apply_overrides(PRESETS["crdi15"](), {"turbo.turbine_area_eff": 5e-4})
    ok = caught == 3 and spec.turbo.turbine_area_eff == 5e-4
    check("bad overrides rejected, good ones applied", 1.0 if ok else 0.0,
          1.0, 0.0, f"{caught}/3 rejected")


def test_registered_preset_not_aliased():
    """
    builder.register stored `lambda s=spec: s`, so every lookup returned the
    same object and a mutation -- a rating override, an edit -- leaked into
    every later lookup. Fatal in a long-lived browser worker. Each lookup must
    now be an independent copy, like the built-in factories.
    """
    from dieselsim.builder import register
    from dieselsim.config import PRESETS
    register("_alias_probe", PRESETS["crdi15"]())
    a = PRESETS["_alias_probe"]()
    a.torque_limit = 123.0
    leaked = PRESETS["_alias_probe"]().torque_limit == 123.0
    del PRESETS["_alias_probe"]
    check("registered presets are independent copies",
          0.0 if leaked else 1.0, 1.0, 0.0,
          "mutation leaked" if leaked else "no leak")


def test_no_pilot_double_count():
    """
    FINDING-001 P-1: the pilot's suppression of premixed burn must be
    applied once, through the ignition delay, not again as a multiplier.
    Guards against reintroduction.
    """
    src = os.path.join(os.path.dirname(__file__), "..",
                       "dieselsim", "cycle.py")
    with open(src) as fh:
        body = fh.read()
    check("no pilot multiplier on premix",
          0.0 if "0.55 * f_pilot" in body else 1.0, 1.0, 0.0,
          "reintroducing the 0.55 multiplier double-counts the pilot")


def test_runtime_info_describes_every_preset():
    """
    The web app labels engines and chooses the dyno rpm range from
    runtime_info()["preset_info"] without solving anything. Every preset
    must be described, and the description must agree with the spec: a
    unit slip here (m^3 vs L) or a swapped rpm field draws a wrong sweep
    with no error. Displacement is cross-checked against bore and stroke,
    not against the property the bridge itself reads.
    """
    import json
    import math
    from dieselsim import bridge
    from dieselsim.config import PRESETS
    info = json.loads(bridge.runtime_info())
    described = info.get("preset_info", {})
    problems = []
    if sorted(described) != sorted(info["presets"]):
        problems.append(f"described {sorted(described)} != presets {sorted(info['presets'])}")
    for key in info["presets"]:
        d = described.get(key)
        if d is None:
            continue
        spec = PRESETS[key]()
        g = spec.geom
        for f in ("idle_rpm", "rated_rpm", "max_rpm"):
            if d[f] != float(getattr(spec, f)):
                problems.append(f"{key}: {f} {d[f]} vs spec {getattr(spec, f)}")
        disp_l = math.pi / 4 * g.bore ** 2 * g.stroke * g.n_cyl * 1000.0
        if abs(d["displacement_l"] - disp_l) > 1e-9 * disp_l:
            problems.append(f"{key}: {d['displacement_l']} L vs {disp_l} L from bore/stroke")
        if d["n_cyl"] != g.n_cyl:
            problems.append(f"{key}: n_cyl {d['n_cyl']} vs {g.n_cyl}")
        if not 0 < d["idle_rpm"] < d["rated_rpm"] <= d["max_rpm"]:
            problems.append(f"{key}: rpm order idle {d['idle_rpm']} rated {d['rated_rpm']} max {d['max_rpm']}")
        if not d["name"]:
            problems.append(f"{key}: empty name")
    check("runtime_info describes every preset", 0.0 if problems else 1.0,
          1.0, 0.0, "; ".join(problems) or f"{len(described)} presets")


def test_limiter_calibrates_under_evaluation_schedules():
    """FINDING-013 item 1: every torque-limiter calibration solve must run
    with the full-load schedules (load_est=1) its result is judged under.
    Before the fix they saw f / fuel_limit_raw -- EGR on across part of the
    plateau -- and the limiter overshot its cap by up to +5.5%."""
    eng = DieselEngine(preset="crdi15")
    seen = []
    real = eng.operating_point

    def spy(*a, **k):
        if eng._calibrating:
            seen.append(k.get("load_est"))
        return real(*a, **k)

    eng.operating_point = spy
    eng.fuel_limit(2500.0)                      # capped speed: calibrates
    bad = [x for x in seen if x != 1.0]
    check("limiter calibration uses load_est=1",
          0.0 if (seen and not bad) else 1.0, 0.0, 0.0,
          f"{len(seen)} calibration solves, load_est {sorted(set(map(str, seen)))}")


def test_converged_flag_is_honest():
    """FINDING-013: CycleResult.converged was set True on every solve without
    checking. A fixed-count fast solve establishes nothing, so it must say
    False; converged mode must run at real time for CONVERGED_CYCLES."""
    op = DieselEngine(preset="single").operating_point(2000, load=0.8, n_cycles=6)
    check("fast solve does not claim convergence", float(op.cycle.converged),
          0.0, 0.0)
    eng = DieselEngine(preset="single")
    eng.converged_mode = True
    seen = {}
    real_run = eng.cycle.run

    def run(*a, **k):
        seen.update(k)
        return real_run(*a, **k)

    eng.cycle.run = run
    eng.operating_point(2000, load=0.8, n_cycles=6)
    check("converged mode runs CONVERGED_CYCLES at real time",
          0.0 if (seen.get("n_cycles") == eng.CONVERGED_CYCLES
                  and seen.get("spool_accel") == 1.0) else 1.0, 0.0, 0.0,
          f"n_cycles {seen.get('n_cycles')}, spool_accel {seen.get('spool_accel')}")


def main():
    for fn in (test_golden_points, test_n_cycles_convergence,
               test_premix_responds_to_temperature,
               test_cold_start_sharpens_dpdtheta,
               test_combustion_dpdtheta_responds,
               test_sharp_not_clamped,
               test_transient_stalls_cleanly,
               test_package_is_numpy_only_at_import,
               test_override_typo_rejected,
               test_registered_preset_not_aliased,
               test_no_pilot_double_count,
               test_runtime_info_describes_every_preset,
               test_limiter_calibrates_under_evaluation_schedules,
               test_converged_flag_is_honest):
        try:
            fn()
        except Exception as exc:                       # noqa: BLE001
            RESULTS.append(("FAIL", fn.__name__, None, None, repr(exc)))

    width = max(len(r[1]) for r in RESULTS) + 2
    fails = 0
    for status, name, actual, expected, note in RESULTS:
        line = f"{status:16s} {name:{width}s}"
        if actual is not None:
            line += f" got {actual:12.4f} want {expected:12.4f}"
        if note:
            line += f"  {note}"
        print(line)
        if status == "FAIL":
            fails += 1

    n_known = sum(1 for r in RESULTS if r[0] == "KNOWN")
    n_unexp = sum(1 for r in RESULTS if r[0] == "UNEXPECTED PASS")
    print(f"\n{len(RESULTS) - fails - n_known - n_unexp} passed, "
          f"{fails} failed, {n_known} known defects, "
          f"{n_unexp} unexpected passes")
    if n_unexp:
        print("An UNEXPECTED PASS means a known defect is fixed. "
              "Promote it to a real assertion.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
