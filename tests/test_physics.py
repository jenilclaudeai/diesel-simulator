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
# was 0.5% -- these come from a deterministic solver, so anything larger
# means a real change. (Now GOLDEN_TOL = 1e-5; see the end of this block.)
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
#
# Re-baselined 2026-09-25 for FINDING-013 item 1 (both crdi15 points; hd_i6
# is uncapped and unchanged). The torque limiter's calibration now runs with
# the full-load schedules it is judged under. The old calibration ran with
# EGR on, and at 9 cycles the EGR loop delivers 2-3x its target, so it needed
# ~11% more fuel to reach the rating cap: calibrated fuel at 1800 rpm, default
# 361 K coolant, fell 48.02 -> 42.59 mg. "Load 0.6" is 60% of that, hence 1800/0.6:
#   torque 124.391 -> 111.718 (-10.2%), bsfc 265.40 -> 262.10, p_max 110.78 -> 104.72.
# At 3000/1.0 the cap is 218.06 N.m (map): 219.675 (+0.74% over it) ->
# 216.858 (-0.55%); bsfc 214.70 -> 214.64; p_max 151.98 -> 153.13.
#
# Re-baselined again 2026-09-25 for FINDING-016: start of combustion is now
# resolved within the crank step instead of snapping to the end of it, so
# ignition lands up to a step earlier. Everything moves a little:
#   crdi15 1800/0.6  torque 111.718 -> 111.696, bsfc 262.10 -> 261.88, p_max 104.72 -> 104.78
#   crdi15 3000/1.0  torque 216.858 -> 216.892, bsfc 214.64 -> 214.56, p_max 153.13 -> 152.23
#   hd_i6  1700/1.0  torque 2313.331 -> 2313.401, bsfc 214.11 -> 214.10, p_max 178.53 -> 178.84
# hd_i6 still reproduces the documented 2310 N.m and stays in the 160-200 bar band.
#
# Correction (session 5): hd_i6 1700/1.0 had already moved on main before the
# next change -- PR #37 raised hd_i6's closing ramps (FINDING-017 item 2) and
# the golden was not re-baselined, because the move sat inside the 0.5%
# tolerance: torque 2313.401 -> 2311.359 (-0.09%), bsfc 214.10 -> 214.29,
# p_max 178.84 -> 178.17. Measured on clean main 16f37cd; my miss in #37.
#
# Re-baselined 2026-09-26 for FINDING-013 item 2: the EGR valve starts at
# 0.14 x command instead of 25 % open. crdi15 1800/0.6 only (the other two
# are full load, EGR off, bit-identical). Against a converged solve at the
# same fuel (torque 125.278, bsfc 233.46, p_max 144.19, EGR 9.08 %):
#   torque 111.696 -> 122.628 (error -10.8% -> -2.1%), bsfc 261.88 -> 238.51,
#   p_max 104.78 -> 129.99, delivered EGR 16.64% -> 9.96% (target 9.20%).
#
# Re-baselined 2026-09-26 for FINDING-018 (cam lift no longer steps where the
# ramps meet the flank; flank and ramp heights kept). All inside tolerance,
# re-baselined anyway so the next change starts from exact values:
#   crdi15 1800/0.6  torque 122.628 -> 122.580, bsfc 238.51 -> 238.52, p_max 129.99 -> 130.05
#   crdi15 3000/1.0  torque 216.892 -> 216.888, bsfc 214.56 -> 214.55, p_max 152.23 -> 152.27
#   hd_i6  1700/1.0  torque 2311.359 -> 2313.377, bsfc 214.29 -> 214.10, p_max 178.17 -> 178.84
# hd_i6 still reproduces the documented 2310 N.m and stays in the 160-200 bar band.
#
# Tolerance tightened 0.5% -> 1e-5 at the Phase 1 exit (REVIEW-003), values
# now stored to 9 significant figures. 0.5% let PR #37's -0.09% move pass
# unrecorded. 1e-5 is the SolverPort's bound for the same reason: the
# limiter's warm-started calibration chain amplifies a ~1e-10 platform
# difference to ~1e-6 (Pyodide/numpy 2.4.6 vs native/numpy 2.1.0: 4.9e-8 at
# crdi15 1800/0.6).
GOLDEN_TOL = 1e-5
GOLDEN = {
    ("crdi15", 1800, 0.6): dict(torque=122.580341, bsfc=238.524968, pmax=130.046491),
    ("crdi15", 3000, 1.0): dict(torque=216.888323, bsfc=214.552248, pmax=152.273735),
    ("hd_i6", 1700, 1.0): dict(torque=2313.377013, bsfc=214.100932, pmax=178.836788),
}


def test_golden_points():
    for (preset, rpm, load), exp in GOLDEN.items():
        eng = DieselEngine(preset=preset)
        op = eng.operating_point(rpm, load=load, n_cycles=9)
        tag = f"{preset}@{rpm}/{load}"
        check(f"{tag} torque", op.torque, exp["torque"], GOLDEN_TOL)
        check(f"{tag} bsfc", op.bsfc, exp["bsfc"], GOLDEN_TOL)
        check(f"{tag} p_max", op.p_max / 1e5, exp["pmax"], GOLDEN_TOL)
        if (preset, rpm, load) == ("crdi15", 1800, 0.6):
            # FINDING-013 item 2: with the valve starting 25 % open for any
            # command a 9-cycle solve delivered 16.6 % against a 9.2 % target
            target = 100.0 * eng.egr_schedule(rpm, load) * eng.spec.air.egr_max_fraction
            check(f"{tag} delivered EGR within 25% of target ({target:.2f}%)",
                  1.0 if abs(op.egr_pct / target - 1.0) < 0.25 else 0.0, 1.0, 0.0,
                  f"delivered {op.egr_pct:.2f}% vs target {target:.2f}%")


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
    swing = (vals[0] - vals[1]) / max(vals[1], 1e-9)
    # FINDING-016: the old "> 20%" came from the ignition delay jumping a
    # whole 1-deg crank step. With ignition resolved within the step the real
    # response here is +2.9% (cold premix 0.1657 vs warm 0.1611, each engine
    # on its own calibrated fuel; +6.5% at fixed fuel). The window catches
    # both regressions: a delay stuck in one bin gave cold BELOW warm
    # (0.1839 vs 0.1886), a whole-step jump gave +67%.
    check("premix responds to coolant T",
          1.0 if 0.0 < swing < 0.15 else 0.0, 1.0, 0.0,
          f"cold {vals[0]:.4f} vs warm {vals[1]:.4f}, swing {100 * swing:+.1f}% "
          f"(must be cold > warm, under 15%)")


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
    # FINDING-016: the real response here is +2.4% (the old "> 8%" was a
    # whole-step ignition jump, +13.6%). Cold must be sharper, by less than
    # a step jump would make it; test_ignition_delay_resolved guards the
    # delay itself.
    check("combustion dp/dtheta responds to coolant T",
          1.0 if 0.0 < rise < 0.08 else 0.0, 1.0, 0.0,
          f"cold is {100 * rise:+.1f}% sharper (must be > 0, under 8%)")


def test_ignition_delay_resolved():
    """FINDING-016: the main ignition delay responds to coolant temperature
    by a fraction of a crank step (0.112 deg, 273 vs 363 K, crdi15
    1800/0.6). Quantised to the step it read either 0 (both in one bin) or
    a whole degree (a bin jump); the window rejects both."""
    d = []
    for T in (273.0, 363.0):
        eng = DieselEngine(preset="crdi15")
        eng.T_coolant = T
        eng._apply_thermal_state()
        d.append(eng.operating_point(1800, load=0.6, n_cycles=9).cycle.ign_delay_deg)
    diff = d[0] - d[1]
    check("ignition delay resolved within the step",
          1.0 if 0.05 < diff < 0.5 else 0.0, 1.0, 0.0,
          f"cold {d[0]:.4f} vs warm {d[1]:.4f} deg, difference {diff:.4f} "
          f"(must be 0.05-0.5 deg)")


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


def test_unsettled_cell_is_period_averaged():
    """FINDING-013: a converged-mode cell whose last cycles have not settled
    is averaged over whole oscillation periods and flagged. Synthetic: a
    21-cycle sawtooth in IMEP (the shape measured at crdi_1p5 1450/0.5),
    ending mid-ramp, so the last cycle alone is well off the mean."""
    import math
    from types import SimpleNamespace
    from dieselsim.grid import oscillation_period, settle_or_average
    import random
    random.seed(3)
    checks = {
        "constant": oscillation_period([5.0] * 120) == 0,
        "noise": oscillation_period([random.gauss(0, 1) for _ in range(120)]) == 0,
        "decay": oscillation_period([math.exp(-i / 30) for i in range(120)]) == 0,
        "sine 17": oscillation_period([math.sin(2 * math.pi * i / 17) for i in range(120)]) == 17,
        "sawtooth 21 on a ramp": oscillation_period([(i % 21) / 21 + 0.01 * i for i in range(120)]) == 21,
    }
    spec = DieselEngine(preset="crdi15").spec
    imep = [1.0e6 * (1.0 + 0.1 * ((i % 21) / 21 - 0.5)) for i in range(200)][:-7]
    means = [dict(imep_net=v, work=v, boost=2.0) for v in imep]
    op = SimpleNamespace(cycle=SimpleNamespace(converged=False, cycle_means=means),
                         torque=100.0, power=100.0 * 2 * math.pi * 2000 / 60,
                         rpm=2000.0, bsfc=220.0)
    over, flags = settle_or_average(op, spec)
    true_mean = sum(imep[-21:]) / 21                    # mean over one whole period
    dT_expected = (true_mean - imep[-1]) * spec.geom.displacement / (4 * math.pi)
    checks["flagged unsettled, period 21"] = flags["settled"] == 0.0 and flags["osc_period"] == 21.0
    checks["torque averaged over whole periods"] = abs(over["torque"] - (100.0 + dT_expected)) < 1e-6 * abs(dT_expected)
    op.cycle.converged = True
    checks["settled cell untouched"] = settle_or_average(op, spec) == ({}, dict(settled=1.0, osc_period=0.0, osc_spread=0.0))
    bad = [k for k, v in checks.items() if not v]
    check("unsettled cell period-averaged and flagged", float(len(bad)), 0.0, 0.0,
          ", ".join(bad) or f"{len(checks)} checks")


def test_seeded_fuel_limit_is_exact():
    """A seeded fuel limit (shared across a converged grid row) must come back
    exactly, whatever the rating cap -- an earlier version routed it through
    the calibration cache and returned min(cap in N.m, fuel in mg)."""
    eng = DieselEngine(preset="single")
    eng.spec.torque_limit = 10.0                 # a cap numerically below the fuel
    eng.seed_fuel_limit(2000.0, 40.0)
    check("seeded fuel limit returned exactly", eng.fuel_limit(2000.0), 40.0, 1e-12)


def test_ignition_delay_converges_in_resolution():
    """FINDING-016: resolved within the step, the main ignition delay at the
    solver's 1-deg step agrees with a 0.25-deg solve (measured 0.007 deg
    against 0.1 deg). The start clip -- the first increment covers only the
    part of the step after SOI -- is what makes the absolute value agree;
    without it the delay reads early by a fraction of a step."""
    d = []
    for dth in (1.0, 0.25):
        eng = DieselEngine(preset="crdi15", dtheta=dth)
        eng.seed_fuel_limit(1800.0, 42.59)      # same fuel at both resolutions
        d.append(eng.operating_point(1800, load=0.6, n_cycles=9).cycle.ign_delay_deg)
    check("ignition delay converges in crank resolution",
          1.0 if abs(d[0] - d[1]) < 0.03 else 0.0, 1.0, 0.0,
          f"1 deg {d[0]:.4f} vs 0.25 deg {d[1]:.4f} (must agree within 0.03 deg)")


def test_cam_film_and_time_base():
    """FINDING-015: the cam film was ~780x too thick (pressure-viscosity
    counted twice) so cam boundary friction -- the wear path -- was 1e-5 to
    1e-8 of valvetrain friction; and follower velocity / inertia used cam
    speed on crank-angle derivatives. Boundary share must now be material,
    and hd_i6's valvetrain friction power sits where the crank time base
    puts it (563.5 W; 585.2 W on the cam time base).

    Re-pinned 2026-09-26 for FINDING-013 item 2: 1400/0.6 runs with EGR, and
    the EGR valve's new start changes the cylinder pressure the exhaust valve
    opens against: 577.8 W crank time base, 597.2 W with the cam time base
    mutated back (velocity, roller slip and inertia), still 3.4% apart.
    Re-pinned for FINDING-018 (no lift step, so no inertia spike at the
    junction): 572.7 W; cam-time-base mutant 588.9 W, 2.8% apart."""
    shares = {}
    for preset, rpm, load in (("hd_i6", 1400, 0.6), ("single", 2000, 0.8)):
        f = DieselEngine(preset=preset).operating_point(rpm, load=load, n_cycles=9).friction
        shares[preset] = f["Pb_valvetrain"] / f["P_valvetrain"]
        if preset == "hd_i6":
            check("hd_i6 valvetrain friction power (crank time base)",
                  f["P_valvetrain"], 572.7, 0.01)
    check("cam boundary friction is a material share of valvetrain friction",
          1.0 if min(shares.values()) > 1e-2 else 0.0, 1.0, 0.0,
          ", ".join(f"{k} {v:.3f}" for k, v in shares.items()) + " (must exceed 0.01)")


def test_render_transient_has_no_seams():
    """FINDING-014: render_transient restarted crank angle at 0 in every
    chunk (firing intervals across seams off 13% median, 29% max) and each
    cross-fade deleted 20 ms (2.00 s rendered as 1.86 s). Same operating
    point in every chunk, so any seam is the chunking's. Needs scipy, which
    Pyodide does not have: reported SKIP there, not PASS."""
    import importlib.util
    if importlib.util.find_spec("scipy") is None:
        RESULTS.append(("SKIP", "render_transient has no seams", None, None,
                        "scipy unavailable (acoustics renders with it)"))
        return
    import numpy as np
    from scipy.signal import find_peaks
    from dieselsim.acoustics import EngineSound
    eng = DieselEngine(preset="crdi15")
    op = eng.operating_point(1400.0, load=0.6, n_cycles=9)
    snd = EngineSound(eng.spec)
    snd.wear = eng.wear
    fs, dur, blend = snd.fs, 2.0, 0.25
    log = [dict(t=float(t), rpm=1400.0, op=op) for t in np.arange(0.0, dur + 1e-9, 0.02)]
    y = snd.render_transient(eng, log, blend=blend)
    period = 120.0 / 1400.0 / eng.spec.geom.n_cyl
    k = int(0.002 * fs)
    env = np.sqrt(np.convolve(y * y, np.ones(k) / k, mode="same"))
    pk, _ = find_peaks(env, distance=int(0.7 * period * fs),
                       prominence=0.2 * float(np.percentile(env, 95)))
    ft = pk / fs
    xf = int(0.02 * fs)
    bounds = [((i + 1) * int(round(blend * fs)) + xf // 2) / fs for i in range(int(dur / blend) - 1)]
    dev = [abs(b - a - period) / period for a, b in zip(ft[:-1], ft[1:])
           if any(a <= x + 0.01 and b >= x - 0.01 for x in bounds)]
    ok_len = len(y) == int(round(dur * fs))
    ok_seam = bool(dev) and max(dev) < 0.05
    check("render_transient has no seams", 1.0 if ok_len and ok_seam else 0.0, 1.0, 0.0,
          f"length {len(y) / fs:.3f} s of {dur:.3f}; worst firing interval across "
          f"{len(dev)} seam intervals {100 * max(dev or [1]):.1f}% (must be < 5%)")


def test_theta_global_axis():
    """FINDING-008 option D: CycleTraces.theta_global[c] gives the engine
    angle of cylinder c's local samples. (1) Peak pressure read on it is
    spread by the firing order (every cylinder peaks at the same LOCAL
    angle). (2) It matches the solver's storage: cylinder c's sample at local
    index (k + phase_idx[c]) % n carries global step k -- which pins the
    sign; an even-fire engine's peak spread alone cannot, since its phase
    set is symmetric under negation."""
    import numpy as np
    bad = []
    for preset, rpm in (("hd_i6", 1400), ("crdi15", 1800)):
        eng = DieselEngine(preset=preset)
        tr = eng.operating_point(rpm, load=1.0, n_cycles=9).cycle.traces
        nc, n = tr.p.shape
        peaks = sorted(float(tr.theta_global[c][int(np.argmax(tr.p[c]))]) for c in range(nc))
        gaps = np.diff(peaks + [peaks[0] + 720.0])
        if np.max(np.abs(gaps - 720.0 / nc)) > 2.0:
            bad.append(f"{preset} peak gaps {np.round(gaps, 1).tolist()}")
        k = np.arange(n)
        for c in range(nc):
            kk = (k + eng.cycle.phase_idx[c]) % n
            if np.max(np.abs(((tr.theta_global[c][kk] - tr.theta[k] + 360.0) % 720.0) - 360.0)) > 1e-9:
                bad.append(f"{preset} cyl {c} disagrees with the storage convention")
                break
    check("theta_global spreads cylinders by firing order and matches storage",
          float(len(bad)), 0.0, 0.0, "; ".join(bad) or "hd_i6 and crdi15")


def test_mech_levels_carry_physics():
    """FINDING-017: tick and slap were each divided by their own std, so
    their seating and clearance scaling never reached the output (doubling
    the slap input changed it by 3.6e-11). Now each carries its own level.
    Needs scipy; SKIP where it is missing (Pyodide)."""
    import importlib.util
    if importlib.util.find_spec("scipy") is None:
        RESULTS.append(("SKIP", "mechanical sound levels carry physics", None, None,
                        "scipy unavailable (acoustics renders with it)"))
        return
    import numpy as np
    from dieselsim.acoustics import EngineSound
    eng = DieselEngine(preset="crdi15")
    op = eng.operating_point(1800.0, load=0.6, n_cycles=9)
    snd = EngineSound(eng.spec)
    snd.wear = eng.wear
    src = snd.build_sources(op)

    def mech_rms(key, k):
        s2 = dict(src)
        s2["_meta"] = dict(src["_meta"])
        s2["_meta"][key] *= k
        m = snd.render(op, duration=1.0, sources=s2, seed=5)[1]["mech"]
        return float(np.sqrt(np.mean(m ** 2)))

    base = mech_rms("skirt_clr", 1.0)
    slap = mech_rms("skirt_clr", 2.0) / base - 1.0
    tick = mech_rms("v_seating", 2.0) / base - 1.0
    # The bar was +5%. FINDING-018 doubled the ramp speed, so tick carries 4x
    # the energy and slap's share of the sub-mix shrank: slap x2 now moves it
    # +4.5%. The defect this guards against moved it 3.6e-11; removing the
    # slap level (mutation) gives +0.0%. A 1% bar still separates them.
    check("mechanical sound levels carry physics",
          1.0 if slap > 0.01 and tick > 0.01 else 0.0, 1.0, 0.0,
          f"slap input x2 -> mech {100 * slap:+.1f}%, seating x2 -> mech {100 * tick:+.1f}% "
          f"(each must exceed +1%)")


def test_flat_tappet_wears_more_than_roller():
    """FINDING-015 item 2: with the flat-faced follower's own sliding and
    entrainment speeds, a flat tappet's cam boundary power per cylinder is
    far above a roller's (measured: single 215 W vs hd_i6 4.6 W per
    cylinder, ~46x). With the follower's lift velocity standing in for both
    speeds it was ~4.6x."""
    pb = {}
    for preset, rpm, load in (("single", 2000, 0.8), ("hd_i6", 1400, 0.6)):
        eng = DieselEngine(preset=preset)
        f = eng.operating_point(rpm, load=load, n_cycles=9).friction
        pb[preset] = f["Pb_valvetrain"] / eng.spec.geom.n_cyl
    ratio = pb["single"] / max(pb["hd_i6"], 1e-12)
    # the entrainment half of the fix moves single's boundary power ~6%
    # (228 W with the old entrainment speed) but not the ratio: pin it
    # 215.1 W when pinned; PR #37's ramp raise moved it to 217.3 W unrecorded
    # (inside the 2%); FINDING-018's continuous profile puts it at 215.3 W
    check("single cam boundary power (flat-tappet entrainment)", pb["single"], 215.3, 0.02)
    check("flat tappet cam boundary power >> roller's (per cylinder)",
          1.0 if ratio > 10.0 else 0.0, 1.0, 0.0,
          f"single {pb['single']:.1f} W vs hd_i6 {pb['hd_i6']:.2f} W per cylinder, "
          f"{ratio:.0f}x (must exceed 10x)")


def test_closing_ramps_clear_the_lash():
    """FINDING-017 item 2: a closing ramp shorter than the lash lands the
    valve on the steep flank (hd_i6 seated at 0.91 m/s with a 106 um ramp
    under 550 um lash). Every preset's ramps must clear its lash."""
    from dieselsim.config import PRESETS
    bad = []
    for key in sorted(PRESETS):
        cyc = DieselEngine(preset=key).cycle
        for cam, which in ((cyc.cam_int, "intake"), (cyc.cam_exh, "exhaust")):
            if cam.lash > 0.0 and cam.h_ramp < cam.lash:
                bad.append(f"{key} {which}: ramp {cam.h_ramp * 1e6:.0f} um < lash {cam.lash * 1e6:.0f} um")
    check("closing ramps clear the lash on every preset", float(len(bad)), 0.0, 0.0,
          "; ".join(bad) or f"{len(PRESETS)} presets")


def test_cam_wear_calibration():
    """FINDING-015: K_ARCHARD["cam"] is calibrated to the owner's
    service-interval target -- the flat-tappet single, default duty cycle,
    grows 150 um of exhaust lash in 2000 h (measured 149.8 um). A design
    choice, stated as one; this pins it. Re-fitted for FINDING-018 (the
    continuous cam profile gave 147.8 um at 2.17e-7): 2.20e-7, 149.8 um."""
    eng = DieselEngine(preset="single")
    eng.durability_run(2000.0, verbose=False)
    check("single exhaust lash growth at 2000 h (calibration target 150 um)",
          eng.wear.state.lash_growth_exh * 1e6, 150.0, 0.05)


def test_cell_friction_from_trace():
    """ADR-011: grid cells store cylinder 1's pressure trace (p_cyl) and the
    real-time loop evaluates friction from it at the live oil state. From the
    stored trace (resampled to the 0.5-deg source grid, float32) friction
    must match the cell's own (measured -0.008%) and, with cold oil, a full
    cold solve (+0.070%) -- oil never touches the trace."""
    from dieselsim.acoustics import EngineSound
    from dieselsim.grid import solve_cell, cell_friction
    spec = DieselEngine(preset="crdi15").spec
    src, perf = solve_cell(spec, 1800.0, 0.6)
    grid = EngineSound(spec).grid
    own = DieselEngine(preset="crdi15").operating_point(1800, load=0.6, n_cycles=9).fmep
    same = cell_friction(DieselEngine(preset="crdi15"), 1800.0, src["p_cyl"], grid,
                         perf["fuel_mg"], perf["p_rail"])["fmep"]
    cold_eng = DieselEngine(preset="crdi15")
    cold_eng.oil.cond.T_oil = 273.0
    cold = cell_friction(cold_eng, 1800.0, src["p_cyl"], grid, perf["fuel_mg"], perf["p_rail"])["fmep"]
    ref = DieselEngine(preset="crdi15")
    ref.oil.cond.T_oil = 273.0
    ref.seed_fuel_limit(1800.0, perf["fuel_mg"] / 0.6)
    full_cold = ref.operating_point(1800, fuel_mg=perf["fuel_mg"], n_cycles=9).fmep
    check("cell friction from stored trace (same state)", same, own, 0.002)
    # FINDING-011: a grid cell is a fresh-engine n_cycles=9 solve; the old
    # shared-engine build was off by up to -10.06%
    check("grid cell torque equals a fresh-engine solve (FINDING-011)", perf["torque"],
          DieselEngine(preset="crdi15").operating_point(1800, load=0.6, n_cycles=9).torque, 1e-12)
    check("cell friction from stored trace (cold oil vs full cold solve)", cold, full_cold, 0.002)


def test_cold_solve_is_path_independent():
    """Bug #5: warm_start=False reset only the gas state; the turbo kept its
    shaft speed and VGT position (+0.54% at 2000 rpm after a 4000 rpm solve,
    seeded fuel), and the limiter's calibration chain warm-started from
    whatever came before (-0.16% more, unseeded). A cold solve after any
    history must now equal a fresh engine's, bit for bit."""
    def solve(history):
        e = DieselEngine(preset="crdi15")
        if history:
            e.operating_point(4000.0, load=1.0, n_cycles=9)
        return e.operating_point(2000.0, load=0.6, n_cycles=9, warm_start=False).torque
    fresh, after = solve(False), solve(True)
    check("cold solve after history equals a fresh engine", after, fresh, 1e-12,
          f"fresh {fresh:.9f} vs after 4000 rpm {after:.9f}")


def test_cam_lift_is_continuous():
    """FINDING-018: the ramps ended at h_r = sin^2(pi r/2) while the flank
    they joined started at sin^2(pi r), about 4x higher, so valve lift
    stepped at both junctions (0.026 of peak lift at ramp 0.06, 0.16 --
    2.0 mm -- on hd_i6). On a 0.01-deg grid no sample-to-sample change may
    exceed 1e-3 of peak lift (smooth flanks reach ~2e-4); and the seating
    velocity must be the profile's own ramp speed (lash-free crdi15)."""
    import numpy as np
    from dieselsim.config import PRESETS
    th = np.arange(0.0, 720.0, 0.01)
    worst, where = 0.0, ""
    for key in sorted(PRESETS):
        cyc = DieselEngine(preset=key).cycle
        for cam, which in ((cyc.cam_int, "intake"), (cyc.cam_exh, "exhaust")):
            step = float(np.max(np.abs(np.diff(cam.cam_lift(th))))) / cam.lift_max
            if step > worst:
                worst, where = step, f"{key} {which}"
    check("cam lift has no step (max change per 0.01 deg / peak lift < 1e-3)",
          1.0 if worst < 1e-3 else 0.0, 1.0, 0.0, f"worst {worst:.2e} at {where}")
    cam = DieselEngine(preset="crdi15").cycle.cam_exh
    L, v = cam.cam_lift(th), np.abs(cam.dlift_dtheta(th))
    on_ramp = (L > 1e-9) & (L < 0.9 * cam.h_ramp)
    check("seating velocity is the profile's ramp speed (crdi15 exhaust, no lash)",
          cam.seating_velocity(1.0), float(np.median(v[on_ramp])), 0.01)


def test_seating_on_ramp_is_ramp_speed():
    """FINDING-017 follow-up (task #27): with the lash inside the closing ramp
    the valve seats at the ramp's own speed. The lash penalty
    (1 + 2.2 lash / h_ramp) applied there too -- x2.74 on hd_i6's exhaust
    (550 um lash, 697 um ramp). Off the ramp (lash taller than the ramp) the
    penalty stays, by the owner's decision."""
    import math
    import numpy as np
    from dieselsim.kinematics import Cam
    cam = DieselEngine(preset="hd_i6").cycle.cam_exh
    th = np.arange(0.0, 720.0, 0.01)
    L, v = cam.cam_lift(th), np.abs(cam.dlift_dtheta(th))
    ramp_speed = float(np.median(v[(L > 1e-9) & (L < 0.9 * cam.h_ramp)]))
    check("hd_i6 exhaust seats at its ramp speed (lash within the ramp)",
          cam.seating_velocity(1.0), ramp_speed, 0.01,
          f"lash {cam.lash * 1e6:.0f} um, ramp {cam.h_ramp * 1e6:.0f} um")
    off = Cam(cam.open_deg, cam.close_deg, cam.lift_max, lash=2.0 * cam.h_ramp, ramp=cam.ramp)
    check("lash above the ramp keeps the penalty", off.seating_velocity(1.0),
          ramp_speed * (1.0 + 2.2 * 2.0), 0.01)


def test_pressure_and_temperature_limits():
    """FINDING-010 / known bug #2: the fuel limiter had no peak-pressure or
    exhaust-temperature bound. With each limit set below hd_i6's full-load
    point at 1700 rpm (179 bar, 895 K), full demand must come back within
    2% of it (the limit is found at the calibration's 8 cycles, judged at
    9) with less torque; and limits that do not bind must leave a solve
    bit-identical (the check solve restores gas and turbo state)."""
    free = DieselEngine(preset="hd_i6")
    free.spec.p_max_limit = free.spec.T_exh_limit = 0.0
    ref = free.operating_point(1700.0, load=1.0, n_cycles=9)
    for field, value, attr, scale, unit in (("p_max_limit", 160e5, "p_max", 1e-5, "bar"),
                                            ("T_exh_limit", 850.0, "T_exh", 1.0, "K")):
        e = DieselEngine(preset="hd_i6")
        e.spec.p_max_limit = e.spec.T_exh_limit = 0.0
        setattr(e.spec, field, value)
        op = e.operating_point(1700.0, load=1.0, n_cycles=9)
        got, lim = getattr(op, attr) * scale, value * scale
        check(f"{field} bounds full demand (hd_i6 1700 rpm)",
              1.0 if got <= 1.02 * lim and op.torque < ref.torque else 0.0, 1.0, 0.0,
              f"{attr} {getattr(ref, attr) * scale:.1f} -> {got:.1f} {unit} (limit {lim:.0f}), "
              f"torque {ref.torque:.0f} -> {op.torque:.0f} N.m, "
              f"reason {e.pressure_temperature_limit(1700.0, e.fuel_limit_raw(1700.0))[1]}")
    on = DieselEngine(preset="crdi15").operating_point(1800.0, load=0.6, n_cycles=9).torque
    off_eng = DieselEngine(preset="crdi15")
    off_eng.spec.p_max_limit = off_eng.spec.T_exh_limit = 0.0
    off = off_eng.operating_point(1800.0, load=0.6, n_cycles=9).torque
    check("limits that do not bind leave the solve bit-identical (crdi15 1800/0.6)",
          on, off, 1e-12)


def test_durability_solves_are_converged_enough():
    """FINDING-019: durability_run solved every mode at n_cycles=6, which
    known bug #1 measured as unconverged; over 2000 h that moved crdi15's
    logged rated torque 3.8%. No solve it makes may use fewer than 9."""
    eng = DieselEngine(preset="single")
    seen = []
    orig = eng.operating_point

    def spy(*a, **kw):
        # the limiter's own calibration runs at cal_cycles (8, a recorded
        # decision -- see engine.py); only durability_run's solves count
        if not eng._calibrating:
            seen.append(kw.get("n_cycles", 10))
        return orig(*a, **kw)
    eng.operating_point = spy
    eng.durability_run(50.0, verbose=False)
    check("durability_run solves at n_cycles >= 9",
          1.0 if seen and min(seen) >= 9 else 0.0, 1.0, 0.0,
          f"{len(seen)} solves, n_cycles {sorted(set(seen))}")


def test_calibration_cache_is_consistent():
    """FINDING-007 (BUG-8): fuel_for_torque's cache clipped against a lower
    ceiling than its calibration, so the same call returned 61.31 mg cold and
    55.97 mg warm (-8.71%). A warm call must return the cold call's fuel."""
    eng = DieselEngine(preset="crdi15")
    cold = eng.fuel_for_torque(1800.0, 286.6)
    warm = eng.fuel_for_torque(1800.0, 286.6)
    check("fuel_for_torque: warm cache returns the cold calibration (BUG-8)", warm, cold, 1e-12,
          f"{cold:.4f} mg cold, {warm:.4f} mg warm")


def test_ring_film_field_responds():
    """FINDING-006: the ring film minimum sits on its 12 nm clamp at the
    reversals in every condition, so it is exposed as h_ring_tdc; the
    mid-stroke film h_ring_mid is the one that responds. It must move with
    load, and h_ring_tdc stays the clamp."""
    lo = DieselEngine(preset="crdi15").operating_point(1800.0, load=0.2, n_cycles=9)
    hi = DieselEngine(preset="crdi15").operating_point(1800.0, load=0.9, n_cycles=9)
    moved = abs(hi.h_ring_mid / lo.h_ring_mid - 1.0)
    check("h_ring_mid responds to load (FINDING-006)", 1.0 if moved > 0.01 else 0.0, 1.0, 0.0,
          f"load 0.2 {lo.h_ring_mid * 1e9:.1f} nm vs 0.9 {hi.h_ring_mid * 1e9:.1f} nm ({100 * moved:.1f}%); "
          f"h_ring_tdc {lo.h_ring_tdc * 1e9:.1f} / {hi.h_ring_tdc * 1e9:.1f} nm")


def test_source_levels_carry_physics():
    """FINDING-004: every source was normalised to unit level, so load and
    temperature changed timbre but not loudness. Exhaust now scales as
    (mass flow)^1.5 and combustion as dp/dt: doubling each input must scale
    its source exactly 2^1.5 and 2. Needs scipy; SKIP without."""
    import importlib.util
    if importlib.util.find_spec("scipy") is None:
        RESULTS.append(("SKIP", "exhaust and combustion levels carry physics", None, None,
                        "scipy unavailable (acoustics renders with it)"))
        return
    import numpy as np
    from dieselsim.acoustics import EngineSound
    eng = DieselEngine(preset="crdi15")
    op = eng.operating_point(1800.0, load=0.6, n_cycles=9)
    snd = EngineSound(eng.spec)
    snd.wear = eng.wear
    src = snd.build_sources(op)

    def rms(key, k, part):
        s2 = dict(src)
        s2["_meta"] = dict(src["_meta"])
        s2["_meta"][key] *= k
        y = snd.render(op, duration=0.5, sources=s2, seed=5)[1][part]
        return float(np.sqrt(np.mean(y ** 2)))
    check("exhaust level x mass flow^1.5 (FINDING-004)",
          rms("mdot_air", 2.0, "exhaust") / rms("mdot_air", 1.0, "exhaust"), 2.0 ** 1.5, 1e-6)
    check("combustion level x dp/dt (FINDING-004)",
          rms("dpdt_max", 2.0, "combustion") / rms("dpdt_max", 1.0, "combustion"), 2.0, 1e-6)


def _toy_live(trans, motoring=False):
    """A LiveEngine on a synthetic 2 x 2 grid -- enough for controls, no solve.
    motoring=True gives torque = -15 + 230 x load N.m, so an engine off the
    throttle brakes the car as a real one does."""
    from dieselsim.live import LiveEngine, PerfGrid
    spec = DieselEngine(preset="crdi15").spec
    def cell(load):
        tq = -15.0 + 230.0 * load if motoring else 100.0
        return dict(torque=tq, power=20e3, fuel_kg_h=0.3 + 12.0 * load, boost=1.0 + 1.2 * load,
                    turbo_rpm=9e4, afr=25.0, q_wall=0.2)
    perf = [[cell(0.0), cell(1.0)], [cell(0.0), cell(1.0)]]
    return LiveEngine(PerfGrid(spec, [spec.idle_rpm, spec.max_rpm], [0.0, 1.0], perf), "crdi15", trans=trans)


def test_lockup_key_by_transmission():
    """Bug #6: the "l" key toggled a lock-up flag a DCT never reads, silently.
    Now in dieselsim.live.handle_key (moved from play.py's terminal loop so it
    can be tested): on a torque converter it toggles lock-up; on a DCT it
    changes nothing and says why."""
    from dieselsim.live import handle_key
    tc, dct = _toy_live("tc"), _toy_live("dct")
    handle_key(tc, "l")
    before = dct.dl.lock_allowed
    handle_key(dct, "l")
    ok = (tc.dl.lock_allowed is False and tc.hint == "lockup blocked"
          and dct.dl.lock_allowed == before and "DCT" in dct.hint and dct.hint_t > 0)
    check("lock-up key: toggles on a converter, explains itself on a DCT (bug #6)",
          1.0 if ok else 0.0, 1.0, 0.0, f"tc: {tc.hint!r}; dct: {dct.hint!r}")


def _manual_moving(assist=False):
    """A manual crdi15 on the toy grid, launched in 1st and rolling with the
    clutch clamped: pedal floored, lever into 1st, pedal released, throttle."""
    from dieselsim.live import handle_key, pedal_return
    live = _toy_live("manual")
    handle_key(live, "z"); handle_key(live, "z")          # pedal to the floor
    handle_key(live, ".")                                 # neutral -> 1st
    if assist:
        handle_key(live, "a")
    live.throttle = 0.5
    for _ in range(360):                                  # 6 s: pedal returns, car moves
        pedal_return(live, 1 / 60)
        live.step(1 / 60)
    return live


def test_manual_gearbox():
    """Phase 3 manual box: the lever will not move without the clutch; braking
    to a stop in gear with the clutch up stalls the engine; it restarts only
    with the clutch down (or in neutral); with the auto-clutch the same stop
    -- even braking with the throttle feathered -- does not stall."""
    from dieselsim.live import handle_key, pedal_return
    live = _manual_moving()
    moving = live.dl.v > 1.0 and live.dl.tc.engaged and not live.dl.gb.neutral
    g0 = live.dl.gb.gear
    handle_key(live, ".")                                 # no clutch: refused
    refused = live.dl.gb.gear == g0 and "clutch" in live.hint
    live.dl.clutch_pedal = 1.0
    handle_key(live, ".")
    accepted = live.dl.gb.gear == g0 + 1
    handle_key(live, ",")
    live.dl.clutch_pedal = 0.0
    live.throttle = 0.0
    for _ in range(600):                                  # brake hard to a stop, clutch up
        live.dl.brake = 1.0
        live.step(1 / 60)
    stalled = live.stalled and live.rpm == 0.0 and live.fuel_kg_h == 0.0
    handle_key(live, "i")
    still = live.stalled
    live.dl.clutch_pedal = 1.0
    handle_key(live, "i")
    restarted = not live.stalled and live.rpm == live.spec.idle_rpm
    a = _manual_moving(assist=True)
    # braking with the throttle feathered (0.1): the stopped-car rule that
    # opens the clutch needs the throttle off, so only the anti-stall rule
    # (open below 0.85 x idle) can save the engine here
    a.throttle = 0.1
    for _ in range(600):
        a.dl.brake = 1.0
        a.step(1 / 60)
    assisted = not a.stalled and a.rpm > 0.8 * a.spec.idle_rpm
    ok = moving and refused and accepted and stalled and still and restarted and assisted
    check("manual box: clutch to shift, stall on a stop in gear, clutch to restart, assist does not stall",
          1.0 if ok else 0.0, 1.0, 0.0,
          f"moving {moving}, refused {refused}, accepted {accepted}, stalled {stalled}, "
          f"restart refused {still}, restarted {restarted}, assist no stall {assisted} "
          f"(assisted rpm {a.rpm:.0f})")


def _coast_down(trans):
    """Coast from 100 km/h in top gear with a light brake to 5 km/h; returns
    per-frame (accel m/s^2, gear) and the lock-up torque into the box."""
    import math
    live = _toy_live(trans, motoring=True)
    gb, dl = live.dl.gb, live.dl
    dl.v = 100 / 3.6
    for k in range(gb.n - 1, -1, -1):
        gb.gear = gb.gear_from = k
        if dl.w_out_at_input() * 60 / (2 * math.pi) > 1.05 * live.spec.idle_rpm:
            break
    dl.w_in = dl.w_out_at_input()
    live.rpm = dl.w_in * 60 / (2 * math.pi)
    rows, locked_T, vp = [], [], dl.v
    for _ in range(3600):
        live.throttle, dl.brake = 0.0, 0.08
        live.step(1 / 60)
        rows.append(((dl.v - vp) * 60, gb.gear))
        vp = dl.v
        if dl.lockup:
            locked_T.append(abs(dl.T_turb))
        if dl.v < 5 / 3.6:
            break
    return rows, locked_T


def _worst_overshoot(rows):
    """Largest excursion of the deceleration, within 1 s of a shift, beyond
    both the steady value before and the steady value after it."""
    import statistics
    worst = 0.0
    for i in range(1, len(rows)):
        if rows[i][1] != rows[i - 1][1] and i + 120 < len(rows):
            before = statistics.median(r[0] for r in rows[max(0, i - 60):max(1, i - 5)])
            after = statistics.median(r[0] for r in rows[i + 60:i + 120])
            lo, hi = min(before, after), max(before, after)
            worst = max(worst, max(max(lo - r[0], r[0] - hi, 0.0) for r in rows[i:i + 60]))
    return worst


def test_lockup_and_coast_downshifts():
    """FINDING-020 / bug #11: the converter's lock-up was a spring integrated
    explicitly at h*C/J = 17 (stable below 2) -- every locked frame sat on its
    4500 N.m clamp, and coast downshifts re-locked as 1 g jolts. Now a clutch
    (slip-engaged, then rigid), and coast downshifts stretch both shift
    phases. On a coast-down from 100 km/h no locked frame may reach the
    clamp, and no downshift may overshoot the steady deceleration by more
    than 2 m/s^2 (converter or dual clutch)."""
    rows_tc, locked = _coast_down("tc")
    rows_dct, _ = _coast_down("dct")
    at_clamp = sum(1 for t in locked if t > 4400.0)
    o_tc, o_dct = _worst_overshoot(rows_tc), _worst_overshoot(rows_dct)
    check("lock-up never at its clamp; coast downshifts within 2 m/s^2 (FINDING-020, bug #11)",
          1.0 if locked and at_clamp == 0 and o_tc < 2.0 and o_dct < 2.0 else 0.0, 1.0, 0.0,
          f"locked {len(locked)} frames, {at_clamp} at the clamp; worst overshoot tc {o_tc:.2f}, dct {o_dct:.2f} m/s^2")


def _toy_adr011_grid():
    """A 2 x 2 ADR-011 grid with synthetic pressure traces (polytropic
    compression/expansion, a pressure rise that grows with load and falls
    when cold) and perf built through grid.cell_friction at the engine's
    default warm state (oil 373 K, coolant 361 K) -- small enough for the
    suite, faithful enough to test the plumbing."""
    import numpy as np
    from dieselsim.grid import cell_friction
    from dieselsim.kinematics import SliderCrank
    from dieselsim.live import Adr011Grid
    spec = DieselEngine(preset="crdi15").spec
    sc = SliderCrank(spec.geom)
    deg = np.arange(0.0, 720.0, 0.5)
    V = sc.volume(np.radians(deg - 360.0))
    Vmax = float(V.max())
    def trace(load, cold):
        p = 1.4e5 * (Vmax / V) ** 1.35
        burn = np.exp(-((deg - 372.0) / 18.0) ** 2) * (35e5 * load) * (0.94 if cold else 1.0)
        return np.where((deg > 180) & (deg < 540), p + burn, 1.2e5).astype("<f4")
    rpms, loads = [spec.idle_rpm, spec.max_rpm], [0.0, 1.0]
    def cells(cold):
        perf, traces = [], []
        for r in rpms:
            prow, trow = [], []
            for l in loads:
                tr = trace(l, cold)
                fr = cell_friction(DieselEngine(preset="crdi15"), r, tr.astype(float), deg, 30.0 * l, 1.2e8)
                ind = 30.0 + 190.0 * l - (8.0 if cold else 0.0)
                k = spec.geom.displacement / (4.0 * np.pi)
                prow.append(dict(torque=ind - fr["fmep"] * k, fmep=fr["fmep"], fuel_mg=30.0 * l, p_rail=1.2e8,
                                 boost=1.0 + 1.2 * l, turbo_rpm=9e4, fuel_kg_h=0.3 + 12.0 * l, afr=25.0,
                                 q_wall=0.2))
                trow.append(tr)
            perf.append(prow)
            traces.append(trow)
        return perf, traces
    pw, tw = cells(False)
    pc, tc = cells(True)
    return Adr011Grid(spec, rpms, loads, pw, tw, deg, pc, tc, 361.0, 273.0)


def test_adr011_live_friction():
    """ADR-011 in the live loop (Phase 3): friction is evaluated live from
    the cells' pressure traces at the live oil and coolant state.
    - at the warm state on a cell, the live friction is the cell's own
      (the plumbing -- blending, walls, oil, torque conversion -- adds nothing)
    - cold coolant alone raises it through the walls (x > 1.05), and cold oil
      on top of that raises it again (x > 1.3 beyond the walls, at 298 K)
    - the oil node warms the oil while the engine runs
    - at the cold endpoint the grid's performance is the cold cells'."""
    from dieselsim.live import LiveEngine
    g = _toy_adr011_grid()
    live = LiveEngine(g, "crdi15", trans="tc")
    live.T_coolant, live.T_oil, live.rpm, live.load_eff = 361.0, 373.0, g.rpms[1], g.loads[1]
    live._update_friction()
    own = abs(live.fmep_live / g.perf[1][1]["fmep"] - 1.0)
    warm = live.T_fric
    live.T_coolant, live.T_oil = 298.0, 373.0           # cold coolant only: the walls
    live._update_friction()
    walls = live.T_fric / warm
    live.T_coolant, live.T_oil = 298.0, 298.0
    live._update_friction()
    ratio = live.T_fric / warm
    cold_ok = abs(g.blend_perf_T(g.rpms[0], g.loads[1], 273.0)["torque"] / g.perf_cold[0][1]["torque"] - 1.0)
    run = LiveEngine(g, "crdi15", trans="tc")
    T0 = run.T_oil
    for _ in range(1800):
        run.throttle = 0.6
        run.step(1 / 60)
    warmed = run.T_oil - T0
    oil_extra = ratio / walls                             # what the oil adds beyond the walls
    ok = own < 1e-9 and walls > 1.05 and oil_extra > 1.3 and warmed > 2.0 and cold_ok < 1e-12
    check("ADR-011 live friction: own cell exact warm, higher cold, oil warms, cold endpoint",
          1.0 if ok else 0.0, 1.0, 0.0,
          f"own-cell diff {own:.1e}; cold coolant only x{walls:.2f}, cold oil on top x{oil_extra:.2f}; "
          f"oil +{warmed:.1f} K in 30 s; "
          f"cold endpoint diff {cold_ok:.1e}")


def test_grid_hash_ignores_the_live_loop():
    """Prebuilt grids are keyed on bridge.grid_hash(): the package sources
    without the real-time loop and its synth (live.py, livesound.py), which
    consume grids but cannot change a cell. Editing either must leave it
    unchanged; editing any other file must change it. Checked on a copy of
    the package, so nothing on disk is touched. And an excluded file really
    cannot change a cell only if the cell's solve never imports it."""
    import hashlib
    import shutil
    import subprocess
    import tempfile
    from dieselsim import bridge
    pkg = os.path.join(os.path.dirname(__file__), "..", "dieselsim")

    def gh(folder):
        h = hashlib.sha256()
        for name in sorted(f for f in os.listdir(folder)
                           if f.endswith(".py") and f not in bridge.GRID_HASH_EXCLUDES):
            with open(os.path.join(folder, name), "rb") as fh:
                h.update(name.encode() + b"\0" + fh.read() + b"\0")
        return h.hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        cp = os.path.join(tmp, "dieselsim")
        shutil.copytree(pkg, cp, ignore=shutil.ignore_patterns("__pycache__"))
        base = gh(cp)
        same_as_bridge = base == bridge.grid_hash()
        for name in ("live.py", "livesound.py"):
            with open(os.path.join(cp, name), "a") as fh:
                fh.write("\n# edit\n")
        live_edit = gh(cp)
        with open(os.path.join(cp, "engine.py"), "a") as fh:
            fh.write("\n# edit\n")
        engine_edit = gh(cp)
    probe = ("import sys; import dieselsim.grid, dieselsim.acoustics; "
             "print(' '.join(m.split('.')[1] + '.py' for m in sys.modules if m.startswith('dieselsim.')))")
    loaded = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                            cwd=os.path.join(pkg, "..")).stdout.split()
    leaked = sorted(set(loaded) & set(bridge.GRID_HASH_EXCLUDES))
    ok = same_as_bridge and live_edit == base and engine_edit != base and bool(loaded) and not leaked
    check("grid hash: live-loop and synth edits keep it, solver edits change it", 1.0 if ok else 0.0, 1.0, 0.0,
          f"matches bridge {same_as_bridge}, {'/'.join(bridge.GRID_HASH_EXCLUDES)} edits keep {live_edit == base}, "
          f"engine.py edit changes {engine_edit != base}, excluded files the cell solve imports: {leaked or 'none'}"
          f" (of {len(loaded)} loaded)")


_HD_SRC = {}


def _hd_i6_sources():
    """hd_i6 at 1400 rpm / 0.6 and its acoustic sources, solved once."""
    if not _HD_SRC:
        from dieselsim.acoustics import EngineSound
        eng = DieselEngine(preset="hd_i6")
        op = eng.operating_point(1400.0, load=0.6, n_cycles=9)
        _HD_SRC.update(eng=eng, op=op, es=EngineSound(eng.spec))
        _HD_SRC["src"] = _HD_SRC["es"].build_sources(op)
    return _HD_SRC


def _stream(spec, src, secs, rpm=1400.0, mic="exterior_7m", parts=False):
    from dieselsim import livesound as LS
    syn = LS.LiveSynth(spec, mic)
    syn.set_sources(src)
    ys, acc = [], {}
    for i in range(int(secs * LS.FS / LS.BLOCK)):
        ys.append(syn.block(rpm))
        if parts and i * LS.BLOCK >= LS.FS:
            for k, v in syn.last_parts.items():
                acc.setdefault(k, []).append(v)
    import numpy as np
    return np.concatenate(ys), {k: np.concatenate(v) for k, v in acc.items()}


def test_livesound_firing_peaks_and_sources():
    """Phase 4 exit criterion, on the streaming synth (dieselsim/livesound.py):
    an I6 at 1400 rpm peaks at its firing frequency and harmonics, 70/140/210
    Hz (each > 15 dB over its surroundings), and every source is non-silent.
    numpy only, so it runs under Pyodide too."""
    import numpy as np
    d = _hd_i6_sources()
    y, parts = _stream(d["eng"].spec, d["src"], 3.0, parts=True)
    y = y[44100:]
    seg = 1 << 15
    P = np.zeros(seg // 2 + 1)
    for k in range(0, len(y) - seg + 1, seg // 2):
        P += np.abs(np.fft.rfft(y[k:k + seg] * np.hanning(seg))) ** 2
    f = np.fft.rfftfreq(seg, 1 / 44100)
    peaks = []
    for h in (70.0, 140.0, 210.0):
        band = (f > h - 3) & (f < h + 3)
        side = ((f > h - 15) & (f < h - 6)) | ((f > h + 6) & (f < h + 15))
        peaks.append(10 * np.log10(P[band].max() / np.median(P[side])))
    rms = {k: float(np.sqrt(np.mean(v ** 2))) for k, v in parts.items()}
    silent = [k for k, v in rms.items() if v < 1e-3 * max(rms.values())]
    check("sound: I6 at 1400 rpm peaks at 70/140/210 Hz, every source audible",
          1.0 if min(peaks) > 15.0 and not silent else 0.0, 1.0, 0.0,
          f"peaks {', '.join(f'{p:+.1f}' for p in peaks)} dB; silent sources {silent or 'none'} of {len(rms)}")


def test_livesound_carries_physics():
    """FINDING-021: play.py's LiveSound ignored the physics its sources carry
    -- doubling the slap input, the exhaust mass flow or the valve seating
    speed changed its output by 0.0000%. The streaming synth that replaces
    it must respond to each, in the source it feeds (> 1% RMS)."""
    import numpy as np
    d = _hd_i6_sources()
    # each input is judged on the source it feeds: on hd_i6 the valve tick is
    # 13x the slap, so slap x2 moves the whole exterior mix only ~0.2%
    feeds = {"skirt_clr": "mech", "mdot_air": "exhaust", "v_seating": "mech"}
    # and even inside "mech" the tick outweighs the slap (the sound-design
    # question left for the owner's ears), so slap is tested with the
    # seating speed turned down to 1% in both runs
    rms = lambda parts, k: float(np.sqrt(np.mean(parts[k] ** 2)))  # noqa: E731

    def run(key, factor):
        s2 = dict(d["src"])
        s2["_meta"] = dict(d["src"]["_meta"])
        if key == "skirt_clr":
            s2["_meta"]["v_seating"] *= 0.01
        s2["_meta"][key] *= factor
        return _stream(d["eng"].spec, s2, 1.5, parts=True)[1]
    moved = {k: rms(run(k, 2.0), part) / rms(run(k, 1.0), part) - 1.0 for k, part in feeds.items()}
    check("sound carries physics: slap, exhaust flow and seating each move it (FINDING-021)",
          1.0 if min(abs(v) for v in moved.values()) > 0.01 else 0.0, 1.0, 0.0,
          ", ".join(f"{k} x2 -> {feeds[k]} {100 * v:+.1f}%" for k, v in moved.items()))


def test_livesound_matches_render():
    """The streaming synth against acoustics.EngineSound.render, the offline
    reference (ADR-004: spectral): its Butterworth design matches scipy's
    response, its pure and scipy paths agree, and at a steady operating
    point every source's level is within 3% of render's, and the
    third-octave spectrum within 1.5 dB -- the mix's, and each source's
    shape over its bands within 30 dB of its strongest (the mix alone hid a
    stale combustion sharpness; below -30 dB lie inter-harmonic floors and
    the trackers' block-step sidebands). Needs scipy; SKIP without."""
    import importlib.util
    if importlib.util.find_spec("scipy") is None:
        RESULTS.append(("SKIP", "streaming sound matches the offline render", None, None,
                        "scipy unavailable"))
        return
    import numpy as np
    from scipy import signal
    from dieselsim import livesound as LS
    worst = 0.0
    for kind, order, wn in (("low", 1, 0.06), ("low", 3, 0.3), ("high", 2, 0.0027), ("band", 2, (0.0317, 0.295))):
        w = np.linspace(1e-4, np.pi * 0.999, 2000)
        _, h_ref = signal.sosfreqz(signal.butter(order, wn, btype=kind, output="sos"), worN=w)
        h = np.ones_like(h_ref)
        for b, a in LS.butter_sos(order, wn, kind):
            h *= signal.freqz(b, a, worN=w)[1]
        worst = max(worst, float(np.max(np.abs(h - h_ref)) / np.max(np.abs(h_ref))))
    d = _hd_i6_sources()
    LS.PURE = True
    y_pure = _stream(d["eng"].spec, d["src"], 0.3)[0]
    LS.PURE = False
    y_fast = _stream(d["eng"].spec, d["src"], 0.3)[0]
    paths = float(np.max(np.abs(y_pure - y_fast)))
    y_s, parts = _stream(d["eng"].spec, d["src"], 4.0, parts=True)
    y_s = y_s[44100:]
    y_r, parts_r = d["es"].render(d["op"], duration=3.0, mic="exterior_7m", sources=d["src"], seed=5)
    lvl = {k: float(np.sqrt(np.mean(parts[k] ** 2)) / (np.sqrt(np.mean(parts_r[k] ** 2)) + 1e-30)) for k in parts_r}
    def bands(y):
        f, P = signal.welch(y, 44100, nperseg=8192)
        e = 25.0 * 2 ** (np.arange(0, 30) / 3.0)
        return np.array([P[(f >= lo) & (f < hi)].sum() for lo, hi in zip(e[:-1], e[1:])])
    bs, br = bands(y_s), bands(y_r)
    m = br > 1e-6 * br.max()
    db = np.abs(10 * np.log10(bs[m] / br[m]))
    shape = {}
    for k in parts_r:
        a, b = bands(parts[k]), bands(parts_r[k])
        a, b = a / a.sum(), b / b.sum()
        mk = b > 1e-3 * b.max()
        shape[k] = float(np.abs(10 * np.log10(a[mk] / b[mk])).max())
    worst_shape = max(shape, key=shape.get)
    worst_lvl = max(abs(v - 1.0) for v in lvl.values())
    ok = (worst < 1e-9 and paths < 1e-9 and worst_lvl < 0.03 and float(db.max()) < 1.5
          and shape[worst_shape] < 1.5)
    check("streaming sound matches the offline render (filters, paths, levels, spectrum)", 1.0 if ok else 0.0, 1.0, 0.0,
          f"filter response {worst:.1e}; pure vs scipy {paths:.1e}; worst source level {100 * worst_lvl:.1f}% off; "
          f"worst third-octave {float(db.max()):.2f} dB over {int(m.sum())} bands; "
          f"worst source shape {shape[worst_shape]:.2f} dB ({worst_shape})")


def test_intake_and_boost_levels_are_normalised_away():
    """FINDING-022 (known defect): in acoustics.render -- and so in the
    faithful streaming port -- the intake hiss is scaled by its mass flow,
    (mdot * spd^1.5)^1.5, and the next line divides it by its own std, and
    the intake source carries no other level; the turbo's boost term goes
    the same way. Doubling the mass flow moves the intake by 0.0000%, and
    doubling the boost moves the turbo by 0.0000%. Left in place for the
    owner's listening review (Phase 4: port faithfully, decide by ear).
    Measured on the streaming synth, which runs without scipy; render()
    gives the same 0.0000% (reviews/FINDING-022.md)."""
    import copy
    import numpy as np
    d = _hd_i6_sources()
    rms = lambda y: float(np.sqrt(np.mean(np.asarray(y, float) ** 2)))  # noqa: E731
    base = _stream(d["eng"].spec, d["src"], 1.3, parts=True)[1]

    def part(key, name):
        src = copy.deepcopy(d["src"])
        src["_meta"][key] *= 2.0
        return rms(_stream(d["eng"].spec, src, 1.3, parts=True)[1][name]) / rms(base[name]) - 1.0
    i, t = part("mdot_air", "intake"), part("boost", "turbo")
    known("intake level carries mass flow, turbo level carries boost (FINDING-022)",
          abs(i) < 1e-6 and abs(t) < 1e-6,
          f"mass flow x2 -> intake {100 * i:+.4f}%, boost x2 -> turbo {100 * t:+.4f}%")


_GRIDS = {}


def _prebuilt_grid(key):
    """A prebuilt grid (web/app/public/grids/<key>.json) as live.Adr011Grid."""
    if key not in _GRIDS:
        import json
        from dieselsim.live import Adr011Grid
        path = os.path.join(os.path.dirname(__file__), "..", "web", "app", "public", "grids", f"{key}.json")
        with open(path) as fh:
            _GRIDS[key] = Adr011Grid.from_json(json.load(fh))
    return _GRIDS[key]


def test_grid_sources_warm_and_cold():
    """Phase 4: every prebuilt grid carries each cell's acoustic sources,
    warm and cold, and none is silent or non-finite (the dead-signal
    pattern, checked where it would hide); blend_sources on a node returns
    that node's cell exactly; and a cold cell's skirt film -- FINDING-017's
    stand-in for slap clearance -- is never thinner than the warm one's.
    (First written as "thicker": false in 115 of 240 cells, where both sit
    on the film's clamp. That clamp is FINDING-023, recorded below.)"""
    import numpy as np
    from dieselsim.config import PRESETS
    from dieselsim.livesound import SOURCE_KEYS
    bad, n, ratio, off, cmp, pinned, twins = [], 0, [], 0, 0, {"warm": 0, "cold": 0}, 0
    for key in sorted(PRESETS):
        g = _prebuilt_grid(key)
        for tag, S in (("warm", g.src), ("cold", g.src_cold)):
            for i, row in enumerate(S):
                for j, c in enumerate(row):
                    for k in SOURCE_KEYS:
                        n += 1
                        if not (np.all(np.isfinite(c[k])) and float(np.max(np.abs(c[k]))) > 0.0):
                            bad.append(f"{key} {tag}[{i}][{j}].{k}")
                    if not all(np.isfinite(v) for v in c["_meta"].values()):
                        bad.append(f"{key} {tag}[{i}][{j}]._meta")
        ratio += [g.src_cold[i][j]["_meta"]["skirt_clr"] / g.src[i][j]["_meta"]["skirt_clr"]
                  for i in range(len(g.rpms)) for j in range(len(g.loads))]
        # a cold cell is its own solve: its combustion waveform is never the warm one's
        twins += sum(np.array_equal(g.src_cold[i][j]["dpdth"], g.src[i][j]["dpdth"])
                     for i in range(len(g.rpms)) for j in range(len(g.loads)))
        # the film's upper clamp is 0.32 x the skirt clearance (lubrication.skirt_film_thickness)
        top = 0.32 * DieselEngine(preset=key).wear.eff_skirt_clearance()
        for tag, S in (("warm", g.src), ("cold", g.src_cold)):
            pinned[tag] += sum(abs(c["_meta"]["skirt_clr"] / top - 1.0) < 1e-9 for row in S for c in row)
        for i, j in ((0, 0), (len(g.rpms) - 1, len(g.loads) - 1), (3, 2)):
            for T, S in ((g.T_warm, g.src), (g.T_cold, g.src_cold)):
                b = g.blend_sources(g.rpms[i], g.loads[j], T)
                for k in SOURCE_KEYS:
                    off += int(np.count_nonzero(b[k] != S[i][j][k]))
                    cmp += b[k].size
                off += sum(b["_meta"][k] != S[i][j]["_meta"][k] for k in b["_meta"])
                cmp += len(b["_meta"])
    ok = not bad and off == 0 and min(ratio) >= 1.0 - 1e-12 and twins == 0
    check("prebuilt grids carry warm and cold sound sources, none silent (Phase 4)", 1.0 if ok else 0.0, 1.0, 0.0,
          f"silent or non-finite: {len(bad)} of {n} waveforms {bad[:3] or ''}; node blends: {off} of {cmp} values "
          f"differ; cold/warm skirt film {min(ratio):.2f}..{max(ratio):.2f} over {len(ratio)} cells; "
          f"cold combustion identical to warm in {twins}")
    cells = len(ratio)
    known("the slap input (skirt film) is off its clamp in cold cells (FINDING-023)",
          pinned["cold"] == cells,
          f"on 0.32 x clearance: {pinned['cold']} of {cells} cold cells, {pinned['warm']} of {cells} warm")


def test_live_sound_follows_the_engine():
    """Phase 4: the synth follows the live loop's friction (ADR-011). On the
    prebuilt crdi15 grid at idle, one LiveEngine with its oil at 361 K and
    one at 273 K, both with the coolant at 361 K -- so the grid's blend is
    identical, and only sound_inputs() (the live friction) can tell them
    apart -- each feed LiveSynth. Cold oil must move the rumble (boundary
    friction power). First written as cold oil AND coolant, where the grid's
    own cold cells could produce the difference without the live path; and
    asserting the slap moved too, which FINDING-023's clamp prevents."""
    import numpy as np
    from dieselsim import livesound as LS
    from dieselsim.live import LiveEngine
    g = _prebuilt_grid("crdi15")

    def run(T_oil):
        live = LiveEngine(g, "crdi15")
        live.T_coolant, live.T_oil = 361.0, T_oil
        live._update_friction()
        inp = live.sound_inputs()
        syn = LS.LiveSynth(g.spec)
        syn.set_sources(g.blend_sources(live.rpm, live.load_eff, live.T_coolant))
        acc = {}
        for b in range(int(1.2 * LS.FS / LS.BLOCK)):
            syn.block(live.rpm, inp)
            if b * LS.BLOCK >= 0.6 * LS.FS:
                for k, v in syn.last_parts.items():
                    acc.setdefault(k, []).append(v)
        return inp, {k: float(np.sqrt(np.mean(np.concatenate(v) ** 2))) for k, v in acc.items()}
    ic, rc = run(273.0)
    iw, rw = run(361.0)
    moved = {k: rc[k] / rw[k] - 1.0 for k in ("mech", "rumble", "combustion")}
    ok = abs(moved["rumble"]) > 0.01
    check("the live synth follows the live friction: cold oil (Phase 4)", 1.0 if ok else 0.0, 1.0, 0.0,
          "oil 273 vs 361 K, coolant 361 K, idle: " + ", ".join(f"{k} {100 * v:+.1f}%" for k, v in moved.items())
          + f"; skirt film {ic.get('skirt_clr', 0.0) / iw.get('skirt_clr', 1.0):.2f}x, "
          + f"boundary power {ic.get('Pb', 0.0) / iw.get('Pb', 1.0):.2f}x" + ("" if "Pb" in ic else " (no live friction sent)"))


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
               test_converged_flag_is_honest,
               test_unsettled_cell_is_period_averaged,
               test_seeded_fuel_limit_is_exact,
               test_ignition_delay_resolved,
               test_ignition_delay_converges_in_resolution,
               test_cam_film_and_time_base,
               test_render_transient_has_no_seams,
               test_theta_global_axis,
               test_mech_levels_carry_physics,
               test_flat_tappet_wears_more_than_roller,
               test_closing_ramps_clear_the_lash,
               test_cam_wear_calibration,
               test_cell_friction_from_trace,
               test_cold_solve_is_path_independent,
               test_cam_lift_is_continuous,
               test_seating_on_ramp_is_ramp_speed,
               test_pressure_and_temperature_limits,
               test_durability_solves_are_converged_enough,
               test_calibration_cache_is_consistent,
               test_ring_film_field_responds,
               test_source_levels_carry_physics,
               test_lockup_key_by_transmission,
               test_manual_gearbox,
               test_lockup_and_coast_downshifts,
               test_adr011_live_friction,
               test_grid_hash_ignores_the_live_loop,
               test_livesound_firing_peaks_and_sources,
               test_livesound_carries_physics,
               test_livesound_matches_render,
               test_intake_and_boost_levels_are_normalised_away,
               test_grid_sources_warm_and_cold,
               test_live_sound_follows_the_engine):
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
    # a SKIP (a check that cannot run here, e.g. no scipy under Pyodide) is
    # not a pass; it used to be counted as one
    n_skip = sum(1 for r in RESULTS if r[0] == "SKIP")
    print(f"\n{len(RESULTS) - fails - n_known - n_unexp - n_skip} passed, "
          f"{fails} failed, {n_known} known defects, "
          f"{n_unexp} unexpected passes"
          + (f", {n_skip} skipped" if n_skip else ""))
    if n_unexp:
        print("An UNEXPECTED PASS means a known defect is fixed. "
              "Promote it to a real assertion.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
