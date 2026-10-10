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
# Re-baselined 2026-09-30 for REVIEW-003 m-5 (hd_i6's ramps have their own
# height, 1.25 x the lash, and run 3x slower, in front of the unchanged main
# event). The lift above the ramp is exactly as it was; the valves clear
# their lash on the gentle ramp 4.8 (intake) and 7.1 (exhaust) crank degrees
# earlier, at very small lift:
#   hd_i6  1700/1.0  torque 2313.377 -> 2313.603 (+0.0098%), bsfc 214.101 -> 214.080, p_max 178.837 -> 178.839
# (A first design narrowed the flank instead, losing 14-17% of hd_i6's
# lift-area; it was replaced before any baseline moved.)
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
    ("hd_i6", 1700, 1.0): dict(torque=2313.603180, bsfc=214.080003, pmax=178.839201),
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
    junction): 572.7 W; cam-time-base mutant 588.9 W, 2.8% apart.
    Re-pinned for REVIEW-003 m-5 (hd_i6's ramps 3x slower, their own
    height): 560.4 W; cam-time-base mutant (inertia and roller speeds at cam
    speed) 585.8 W, 4.5% apart."""
    shares = {}
    for preset, rpm, load in (("hd_i6", 1400, 0.6), ("single", 2000, 0.8)):
        f = DieselEngine(preset=preset).operating_point(rpm, load=load, n_cycles=9).friction
        shares[preset] = f["Pb_valvetrain"] / f["P_valvetrain"]
        if preset == "hd_i6":
            check("hd_i6 valvetrain friction power (crank time base)",
                  f["P_valvetrain"], 560.4, 0.01)
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


def test_cold_slap_follows_clearance():
    """FINDING-023 option A: slap reads the running skirt clearance, which a
    cold engine opens (an aluminium piston shrinks more than its iron bore),
    instead of the skirt film, which sat on its 0.32 x clearance cap in every
    cold cell. Checked at each place the synth's input is made: the formula
    (warm reference, a hand value at 273 K, falling with temperature, the
    floor); EngineSound.build_sources; grid.solve_cell's cold cell; and the
    live loop's sound_inputs(), whose prebuilt-grid part SKIPs without one."""
    from dieselsim.acoustics import (ALPHA_BORE, ALPHA_PISTON, EngineSound,
                                     running_skirt_clearance as clr)
    from dieselsim.grid import solve_cell
    eng = DieselEngine(preset="crdi15")
    c, b = eng.wear.eff_skirt_clearance(), eng.spec.geom.bore
    # by hand: the piston moves 0.72 K and the liner mean 0.55*0.88 + 0.45*0.95
    # per K of coolant (_apply_thermal_state)
    hand = c + b * 88.0 * (ALPHA_PISTON * 0.72 - ALPHA_BORE * (0.55 * 0.88 + 0.45 * 0.95))
    Ts = [250.0 + 5.0 * k for k in range(31)]
    falls = all(clr(c, b, t1) > clr(c, b, t2) for t1, t2 in zip(Ts, Ts[1:]))
    parts = {"warm reference is c_ref": clr(c, b, 361.0) == c,
             "273 K by hand": abs(clr(c, b, 273.0) / hand - 1.0) < 1e-12,
             "falls with temperature": falls,
             "floored at c_ref / 4": clr(c, b, 900.0) == 0.25 * c}
    op = eng.operating_point(800.0, load=0.2, n_cycles=9)
    snd = EngineSound(eng.spec)
    snd.wear = eng.wear
    warm = snd.build_sources(op)["_meta"]["skirt_clr"]
    snd.T_coolant = 273.0
    cold = snd.build_sources(op)["_meta"]["skirt_clr"]
    parts["build_sources reads it"] = warm == c and cold == clr(c, b, 273.0)
    src, _ = solve_cell(eng.spec, 800.0, 0.2, T_coolant=273.0)
    parts["a cold grid cell carries it"] = src["_meta"]["skirt_clr"] == clr(c, b, 273.0)
    note = f"crdi15: {c * 1e6:.1f} um warm, {clr(c, b, 273.0) * 1e6:.1f} um at 273 K (by hand {hand * 1e6:.1f})"
    if not _no_prebuilt_grids("the live loop sends the running clearance"):
        from dieselsim.live import LiveEngine
        live = LiveEngine(_prebuilt_grid("crdi15"), "crdi15")
        got = {}
        for T in (273.0, 361.0):
            live.T_coolant, live.T_oil = T, T
            live._update_friction()
            got[T] = live.sound_inputs()["skirt_clr"]
        parts["the live loop sends it"] = got[273.0] == clr(c, b, 273.0) and got[361.0] == c
        note += f"; live cold/warm {got[273.0] / got[361.0]:.3f}x"
    bad = [k for k, ok in parts.items() if not ok]
    check("slap follows the running skirt clearance (FINDING-023)", float(len(bad)), 0.0, 0.0,
          (f"failed: {', '.join(bad)}; " if bad else f"{len(parts)} of {len(parts)} parts; ") + note)


def test_grid_benchmark_schedule():
    """tools/bench_grid.py (the hardware benchmark): its estimate schedules a
    build as build_live_grids.py runs one -- the rows, then the warm cells,
    then the cold cells, a pool.map each, ceil(n / workers) waves -- and its
    quick mode samples rows over the whole grid and every load. SKIPs where
    tools/ is absent (the Pyodide harness). Parts:
    - 8 rows of 100 s, 48 warm cells of 20 s, 48 cold of 22 s on 6 workers:
      2 x 100 + 8 x 20 + 8 x 22 = 536 s; on 1 worker 800 + 960 + 1056;
    - phases don't overlap (a worker idle at the end of the rows waits);
    - row samples are spread evenly, ends included, never repeated;
    - load samples visit all six loads before repeating one."""
    import importlib.util
    tool = os.path.join(os.path.dirname(__file__), "..", "tools", "bench_grid.py")
    if not os.path.exists(tool):
        RESULTS.append(("SKIP", "grid benchmark's schedule", None, None, "tools/ not present (Pyodide harness)"))
        return
    spec_ = importlib.util.spec_from_file_location("bench_grid", tool)
    b = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(b)
    parts = {
        "6 workers: 536 s": b.estimate_build_seconds(100.0, 20.0, 22.0, 6) == 536.0,
        "1 worker: 2816 s": b.estimate_build_seconds(100.0, 20.0, 22.0, 1) == 800.0 + 960.0 + 1056.0,
        "7 workers: 2 + 7 + 7 waves (phases don't overlap)": b.estimate_build_seconds(100.0, 20.0, 22.0, 7)
        == 2 * 100.0 + 7 * 20.0 + 7 * 22.0,
        "rows spread, ends included": b.sample_rows(8, 6) == [0, 1, 3, 4, 6, 7] and b.sample_rows(8, 1) == [4]
        and b.sample_rows(8, 12) == list(range(8)),
        "loads: all six before a repeat": sorted(b.sample_loads(6, 6)) == list(range(6))
        and b.sample_loads(6, 8)[6:] == b.sample_loads(6, 6)[:2],
        "the native pool is the build tool's": b.native_workers() == min(6, os.cpu_count() or 1),
    }
    bad = [k for k, ok in parts.items() if not ok]
    check("grid benchmark's schedule (tools/bench_grid.py)", float(len(bad)), 0.0, 0.0,
          (f"failed: {', '.join(bad)}" if bad else f"{len(parts)} of {len(parts)} parts"))


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
    under 550 um lash). Every preset's ramps must clear its lash -- and,
    since REVIEW-003 m-5, every roster engine's: builder.py gave its 12.7 L
    truck the default 6 % ramp, 113 um under 550 um of lash, and this test
    only looked at the presets, so roster A shipped with it (0.65 m/s at idle)."""
    from dieselsim.config import PRESETS
    engines = {key: DieselEngine(preset=key) for key in sorted(PRESETS)}
    engines.update(_roster_engines())
    bad = []
    for key, eng in engines.items():
        cyc = eng.cycle
        for cam, which in ((cyc.cam_int, "intake"), (cyc.cam_exh, "exhaust")):
            if cam.lash > 0.0 and cam.h_ramp < cam.lash:
                bad.append(f"{key} {which}: ramp {cam.h_ramp * 1e6:.0f} um < lash {cam.lash * 1e6:.0f} um")
    check("closing ramps clear the lash on every preset and roster engine", float(len(bad)), 0.0, 0.0,
          "; ".join(bad) or f"{len(engines)} engines")


def _roster_engines():
    """The roster engines, built from engines/*.json without registering them
    as presets (so other tests' sorted(PRESETS) loops are unaffected); {} when
    engines/ is absent (Pyodide)."""
    import json
    from dieselsim.builder import from_dict
    out = {}
    for key in ROSTER:
        path = os.path.join(ENGINES_DIR, f"{key}.json")
        if os.path.exists(path):
            with open(path) as fh:
                out[key] = DieselEngine(spec=from_dict(json.load(fh)))
    return out


def test_ramps_have_their_own_height():
    """REVIEW-003 m-5: with the ramp ending where the flank reaches it, ramp
    height and speed were one parameter (speed ~ sqrt(height)), so the ramps
    tall enough to clear large lash ran at 0.074-0.083 mm per cam degree on
    hd_i6 and tick dominated. Every engine with lash now has ramps 1.25 x its
    lash tall, the exhaust's at 0.025 mm per cam degree (0.5%); above the
    ramp height its lift is the main event's raised cosine exactly, so the
    breathing is unchanged (a first design narrowed that flank instead and
    lost 10-17% of the valves' lift-area); it seats at the ramp's own
    measured slope (1%); and doubling ramp_fraction at the same height
    halves the speed without moving the height."""
    import numpy as np
    from dieselsim.kinematics import RAMP_SPEED, Cam
    th = np.arange(0.0, 720.0, 0.01)
    engines = {k: DieselEngine(preset=k) for k in ("hd_i6", "single")}
    engines.update({k: e for k, e in _roster_engines().items() if e.spec.valves.lash_exhaust > 0.0})
    bad, notes = [], []
    for key, eng in engines.items():
        vt = eng.spec.valves
        for cam, which, ev in ((eng.cycle.cam_int, "intake", (vt.ivo_deg, vt.ivc_deg)),
                               (eng.cycle.cam_exh, "exhaust", (vt.evo_deg, vt.evc_deg))):
            tag = f"{key} {which}"
            if abs(cam.h_ramp / (1.25 * cam.lash) - 1.0) > 1e-12:
                bad.append(f"{tag} height {cam.h_ramp * 1e6:.0f} um")
            speed = cam.h_ramp / (0.5 * cam.ramp * cam.dur / 2.0)      # m per cam degree
            if which == "exhaust":
                notes.append(f"{key} {speed * 1e3:.4f} mm/cam-deg")
                if abs(speed / RAMP_SPEED - 1.0) > 0.005:
                    bad.append(f"{tag} speed {speed * 1e3:.4f} mm/cam-deg")
            L, v = cam.cam_lift(th), np.abs(cam.dlift_dtheta(th))
            u = ((th - ev[0]) % 720.0) / cam.dur                # phase in the main event
            above = (u <= 1.0) & (L >= cam.h_ramp)
            main = cam.lift_max * np.sin(np.pi * u[above]) ** 2
            if not above.any() or float(np.max(np.abs(L[above] - main))) > 1e-15:
                bad.append(f"{tag} lift above the ramp is not the main event")
            slope = float(np.median(v[(L > 1e-9) & (L < 0.9 * cam.h_ramp)]))
            if abs(cam.seating_velocity(1.0) / slope - 1.0) > 0.01:
                bad.append(f"{tag} seats at {cam.seating_velocity(1.0):.4g}, ramp slope {slope:.4g}")
    cam = engines["hd_i6"].cycle.cam_exh
    twice = Cam(cam.open_deg, cam.close_deg, cam.lift_max, cam.lash, 2.0 * cam.ramp, ramp_height=cam.ramp_height)
    if twice.h_ramp != cam.h_ramp or abs(twice.seating_velocity(1.0) / cam.seating_velocity(1.0) - 0.5) > 1e-12:
        bad.append("height not independent of ramp_fraction")
    check("ramps have their own height: 1.25 x lash, 0.025 mm per cam degree, main event unchanged (REVIEW-003 m-5)",
          float(len(bad)), 0.0, 0.0, "; ".join(bad) or f"{len(engines)} engines; exhaust " + ", ".join(notes))


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
    # off = Cam(cam.open_deg, cam.close_deg, cam.lift_max, lash=2.0 * cam.h_ramp, ramp=cam.ramp)
    # (was: since REVIEW-003 m-5 hd_i6's ramp has its own height, and without
    # it this cam would be the old profile, whose 3.6 mm ramp holds the lash)
    off = Cam(cam.open_deg, cam.close_deg, cam.lift_max, lash=2.0 * cam.h_ramp, ramp=cam.ramp,
              ramp_height=cam.ramp_height)
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
    cannot change a cell only if the cell's solve never imports it (checked
    statically: first written with a subprocess, which Pyodide lacks)."""
    import hashlib
    import shutil
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
        for name in bridge.GRID_HASH_EXCLUDES:
            with open(os.path.join(cp, name), "a") as fh:
                fh.write("\n# edit\n")
        live_edit = gh(cp)
        with open(os.path.join(cp, "engine.py"), "a") as fh:
            fh.write("\n# edit\n")
        engine_edit = gh(cp)
    # every package module the cell solve can import, statically (imports
    # inside functions included) -- no subprocess, which Pyodide lacks
    import ast
    # (builder.py too: a roster or custom grid's spec is made by it)
    loaded, todo = set(), ["grid.py", "acoustics.py", "builder.py"]
    while todo:
        name = todo.pop()
        if name in loaded or not os.path.exists(os.path.join(pkg, name)):
            continue
        loaded.add(name)
        with open(os.path.join(pkg, name)) as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level == 1 and node.module:
                    todo.append(node.module.split(".")[0] + ".py")
                elif node.level == 1:
                    todo += [a.name + ".py" for a in node.names]
                elif node.module and node.module.startswith("dieselsim."):
                    todo.append(node.module.split(".")[1] + ".py")
            elif isinstance(node, ast.Import):
                todo += [a.name.split(".")[1] + ".py" for a in node.names if a.name.startswith("dieselsim.")]
    leaked = sorted(loaded & set(bridge.GRID_HASH_EXCLUDES))
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


def test_intake_and_boost_levels_carry_physics():
    """FINDING-022, fixed with option A (the owner's decision): in
    acoustics.render -- and so in the faithful streaming port -- the intake
    hiss was scaled by its mass flow and the next line divided it out, and
    the turbo's boost term went the same way: doubling the mass flow moved
    the intake by 0.0000%, doubling the boost moved the turbo by 0.0000%
    (this test's first form was a known defect saying so). The intake now
    carries the exhaust's law, (mdot/mdot_ref)^1.5, and the boost term sits
    after the normalisation. Each must move its part by more than 1%.
    Measured on the streaming synth, which runs without scipy."""
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
    check("intake level carries mass flow, turbo level carries boost (FINDING-022)",
          1.0 if min(i, t) > 0.01 else 0.0, 1.0, 0.0,
          f"mass flow x2 -> intake {100 * i:+.1f}%, boost x2 -> turbo {100 * t:+.1f}%")


_GRIDS = {}
GRID_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "app", "public", "grids")


def _no_prebuilt_grids(name):
    """SKIP a test on the prebuilt grids where they are absent: the Pyodide
    harness copies only the package and the tests (tools/pyodide), and its
    job exists to prove the solver runs unmodified, not to re-read data files."""
    if os.path.isdir(GRID_DIR):
        return False
    RESULTS.append(("SKIP", name, None, None, "prebuilt grids not present (Pyodide harness)"))
    return True


def _prebuilt_grid(key):
    """A prebuilt grid (web/app/public/grids/<key>.json) as live.Adr011Grid."""
    if key not in _GRIDS:
        import json
        from dieselsim.live import Adr011Grid
        with open(os.path.join(GRID_DIR, f"{key}.json")) as fh:
            _GRIDS[key] = Adr011Grid.from_json(json.load(fh))
    return _GRIDS[key]


def test_grid_sources_warm_and_cold():
    """Phase 4: every prebuilt grid carries each cell's acoustic sources,
    warm and cold, and none is silent or non-finite (the dead-signal
    pattern, checked where it would hide); blend_sources on a node returns
    that node's cell exactly; and a cold cell's skirt film -- FINDING-017's
    stand-in for slap clearance -- is never thinner than the warm one's.
    (First written as "thicker": false in 115 of 240 cells, where both sit
    on the film's clamp. That clamp is FINDING-023, recorded below.)
    Since FINDING-023 option A the slap input is the running clearance:
    every cold cell's is the warm one's opened by the cold (the same factor
    in every cell of a grid), and none sits on the old film cap."""
    if _no_prebuilt_grids("prebuilt grids carry warm and cold sound sources"):
        return
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
    # was known("the slap input (skirt film) is off its clamp in cold cells
    # (FINDING-023)", pinned["cold"] == cells, ...): 240 of 240 cold cells on it
    check("the slap input opens in every cold cell, off the old film cap (FINDING-023)",
          1.0 if (min(ratio) > 1.3 and pinned["cold"] == 0 and pinned["warm"] == 0) else 0.0, 1.0, 0.0,
          f"cold/warm {min(ratio):.3f}..{max(ratio):.3f} over {cells} cells; on 0.32 x clearance: "
          f"{pinned['cold']} cold, {pinned['warm']} warm")


def test_live_sound_follows_the_engine():
    """Phase 4: the synth follows the live loop's friction (ADR-011). On the
    prebuilt crdi15 grid at idle, one LiveEngine with its oil at 361 K and
    one at 273 K, both with the coolant at 361 K -- so the grid's blend is
    identical, and only sound_inputs() (the live friction) can tell them
    apart -- each feed LiveSynth. Cold oil must move the rumble (boundary
    friction power). First written as cold oil AND coolant, where the grid's
    own cold cells could produce the difference without the live path; and
    asserting the slap moved too, which FINDING-023's clamp prevents."""
    if _no_prebuilt_grids("the live synth follows the live friction"):
        return
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


ENGINES_DIR = os.path.join(os.path.dirname(__file__), "..", "engines")
ROSTER = ("hatch15", "crdi22", "truck127", "v8hd", "single10")   # Enjoy mode, roster B (ADR-012)


def test_custom_engine_json():
    """ADR-014: a custom engine is the roster's JSON plus "vehicle". The
    builder ignores "vehicle" (the same engine with or without it); a grid
    file that records its engine JSON is rebuilt from it, not from a preset
    of the same name; and every vehicle key but the fallback names its own
    vehicle (a typo would silently get the tractor, which the build tool and
    the app refuse)."""
    import dataclasses
    import json
    from dieselsim.builder import from_dict
    from dieselsim.live import VEHICLE_KEYS, Vehicle
    d = {"name": "2.0 L four", "displacement": 2.0, "n_cyl": 4, "rated_rpm": 4000,
         "peak_torque": 320, "peak_power": 103, "plateau": [1750, 2500]}
    same = dataclasses.asdict(from_dict(dict(d, vehicle="crdi15"))) == dataclasses.asdict(from_dict(d))
    names = {k: Vehicle(k).name for k in VEHICLE_KEYS}
    fallback = Vehicle("no such vehicle").name
    distinct = (len(set(names.values())) == len(VEHICLE_KEYS) and names["tractor"] == fallback
                and all(n != fallback for k, n in names.items() if k != "tractor"))
    parts = {"builder ignores vehicle": same, "every vehicle key is its own vehicle": distinct}
    if not _no_prebuilt_grids("a grid file is rebuilt from its own engine JSON"):
        from dieselsim.live import Adr011Grid
        with open(os.path.join(os.path.dirname(__file__), "..", "web", "app", "public", "grids", "hatch15.json")) as fh:
            gj = json.load(fh)
        gj.update(preset="crdi15", engine_json=dict(d, vehicle="crdi15"))   # a preset name that is NOT its engine
        parts["grid built from its engine JSON"] = Adr011Grid.from_json(gj).spec.name == "2.0 L four"
        # Phase 6: an edited engine's grid (the spec editor's "Drive it") records its base preset and edits
        del gj["engine_json"]
        gj.update(preset="crdi15-edited", base="crdi15", overrides={"geom.compression_ratio": 18.0, "idle_rpm": 900.0})
        es = Adr011Grid.from_json(gj).spec
        parts["an edited engine's grid rebuilt from its base and edits"] = (
            es.geom.compression_ratio == 18.0 and es.idle_rpm == 900.0 and es.name == Adr011Grid.from_json(
                dict(gj, preset="crdi15", base=None)).spec.name)
    bad = [k for k, ok in parts.items() if not ok]
    check("custom engine JSON: vehicle kept apart, grids rebuilt from their own JSON (ADR-014)",
          float(len(bad)), 0.0, 0.0, (f"failed: {', '.join(bad)}" if bad else f"{len(parts)} of {len(parts)} parts")
          + f"; vehicles {', '.join(f'{k}={v}' for k, v in names.items())}")


def test_describe_engine():
    """ADR-014 step 2: the bridge describes an engine for the UI without a
    solve. A preset reads as runtime_info's preset_info says; a custom engine
    reports the builder's own idle and max rpm (not a copy of its rules in
    TypeScript) and the brochure numbers it was asked for; numbers the
    builder rejects are an invalid request, not a crash."""
    import json
    from dieselsim import bridge
    from dieselsim.builder import from_dict
    d = {"name": "2.0 L four", "displacement": 2.0, "n_cyl": 4, "rated_rpm": 4000,
         "peak_torque": 320, "peak_power": 103, "plateau": [1750, 2500], "vehicle": "crdi15"}
    preset = json.loads(bridge.describe_engine(json.dumps({"engine": {"preset": "crdi15"}})))
    info = json.loads(bridge.runtime_info())["preset_info"]["crdi15"]
    custom = json.loads(bridge.describe_engine(json.dumps({"engine": {"headline": d}})))
    spec = from_dict(d)
    try:
        bridge.describe_engine(json.dumps({"engine": {"headline": dict(d, n_cyl="four")}}))
        rejected = "accepted"
    except bridge.RequestError as e:
        rejected = f"RequestError: {e}"
    except Exception as e:                       # noqa: BLE001
        rejected = f"{type(e).__name__}: {e}"
    parts = {"preset as preset_info": all(preset[k] == v for k, v in info.items()),
             "custom: builder's idle/max rpm": (custom["idle_rpm"], custom["max_rpm"]) == (float(spec.idle_rpm), float(spec.max_rpm)),
             "custom: requested numbers": custom.get("requested") == {"peak_torque": 320.0, "peak_power_kw": 103.0,
                                                                      "plateau": [1750.0, 2500.0]},
             "bad numbers are an invalid request": rejected.startswith("RequestError")}
    bad = [k for k, ok in parts.items() if not ok]
    check("describe_engine for the UI (ADR-014)", float(len(bad)), 0.0, 0.0,
          (f"failed: {', '.join(bad)}; " if bad else f"{len(parts)} of {len(parts)} parts; ")
          + f"custom idle {custom['idle_rpm']:.0f} / max {custom['max_rpm']:.0f} rpm; bad numbers: {rejected[:80]}")


def test_solve_cycle():
    """Phase 6 (ADR-015): the cycle page's traces. They must be the solver's
    own arrays, exactly; p must be paired with V (FINDING-008's trap, in
    another form); the events must be the spec's; n_cycles stays >= 9; and a
    NaN must fail at the boundary rather than reach the browser's JSON.parse.

    The pairing check: the trapezoid loop integral of p dV over one
    cylinder's displacement against imep_net. They are not equal: the solver
    integrates p (at the step's start) times the analytic dV/dtheta, and at
    1 degree a sharp combustion peak moves the answer by the rule alone
    (measured 2026-10-05: trapezoid 0.961 / 0.975 / 0.996 of imep_net on
    single / crdi15 / hd_i6; left-point 1.047 on single). So 5% is the
    bound, and the same integral with p shifted 90 degrees must miss by far,
    or the check couldn't tell. (A 360-degree shift is invisible to it: V
    repeats every revolution.)"""
    import json
    import numpy as np
    from dieselsim import bridge
    from dieselsim.config import PRESETS
    from dieselsim.engine import DieselEngine
    key, rpm, load = "crdi15", 2000.0, 0.6
    r = json.loads(bridge.solve_cycle(json.dumps({"engine": {"preset": key}, "rpm": rpm, "load": load})))
    op = DieselEngine(spec=PRESETS[key]()).operating_point(rpm, load=load, n_cycles=9)
    tr = op.cycle.traces
    same = all(np.array_equal(np.array(r[k]), np.asarray(v, dtype=float)) for k, v in (
        ("theta", tr.theta), ("V", tr.V), ("p", tr.p[0]), ("p_motored", tr.p_motored[0]), ("T", tr.T[0]),
        ("hrr", tr.hrr[0]), ("lift_int", tr.valve_lift_int), ("lift_exh", tr.valve_lift_exh),
        ("p_int_manifold", tr.p_int_manifold), ("p_exh_manifold", tr.p_exh_manifold)))
    p, V = np.array(r["p"]), np.array(r["V"])
    dV, Vd, im = np.roll(V, -1) - V, V.max() - V.min(), r["summary"]["imep_net"]
    loop = lambda pp: float(np.sum(0.5 * (pp + np.roll(pp, -1)) * dV) / Vd / im)  # noqa: E731
    paired, shifted = loop(p), loop(np.roll(p, 90))
    vt = PRESETS[key]().valves
    events = (r["events"]["ivo"], r["events"]["ivc"], r["events"]["evo"], r["events"]["evc"]) == \
        (vt.ivo_deg, vt.ivc_deg, vt.evo_deg, vt.evc_deg)
    try:
        bridge.solve_cycle(json.dumps({"engine": {"preset": key}, "rpm": rpm, "load": load, "n_cycles": 6}))
        floor = "accepted"
    except bridge.RequestError:
        floor = "refused"
    try:
        bridge._finite_deep({"summary": {"x": 1.0}, "p": [1.0, float("nan")]}, "t")
        nan = "passed through"
    except ArithmeticError as e:
        nan = str(e)
    parts = {"the solver's own traces, exactly": same,
             "p paired with V (within 5% of imep_net)": abs(paired - 1.0) <= 0.05,
             "and a 90-degree shift misses by far": abs(shifted - 1.0) > 0.5,
             "valve events are the spec's": events,
             "cylinder 1's phase is 0": r["cylinder_phase_deg"] == 0.0,
             "n_cycles below 9 refused": floor == "refused",
             "a NaN deep in a trace fails at the boundary": "p[1]" in nan}
    bad = [k for k, ok in parts.items() if not ok]
    check("solve_cycle: the cycle page's traces (ADR-015)", float(len(bad)), 0.0, 0.0,
          (f"failed: {', '.join(bad)}; " if bad else f"{len(parts)} of {len(parts)} parts; ")
          + f"loop/imep {paired:.4f}, shifted 90 deg {shifted:.3f}; p_max {max(p) / 1e5:.1f} bar")


def test_mfb50_counts_combustion_before_tdc():
    """FINDING-024: MFB50 accumulated heat release from firing TDC (0), so
    combustion before TDC (at 700-719) was counted last and MFB50 came out
    late: 7 deg on `single`, which releases 41% of its heat before TDC.
    Synthetic: equal heat in the 20 deg before and the 20 deg after TDC puts
    the half at -1 (the last degree before TDC); the old code said +19.
    Real: on `single` the solver's MFB50 equals an independent computation
    from the traces, accumulated from gas-exchange TDC."""
    import json
    import types
    import numpy as np
    from dieselsim import bridge
    from dieselsim.cycle import CycleSolver
    ns = types.SimpleNamespace(n=720, theta=np.arange(720.0))
    hrr = np.zeros(720)
    hrr[700:720] = 1.0
    hrr[0:20] = 1.0
    synthetic = CycleSolver.mfb50(ns, hrr, 1.0)
    r = json.loads(bridge.solve_cycle(json.dumps({"engine": {"preset": "single"}, "rpm": 2000, "load": 0.5})))
    h, th = np.array(r["hrr"]), np.array(r["theta"])
    rel = np.where(th > 360, th - 720, th)
    order = np.argsort(rel, kind="stable")
    c = np.cumsum(h[order])
    independent = float(rel[order][int(np.searchsorted(c, 0.5 * c[-1]))])
    solver = r["summary"]["mfb50"]
    ok = synthetic == -1.0 and solver == independent
    check("MFB50 counts combustion before TDC (FINDING-024)", 0.0 if ok else 1.0, 0.0, 0.0,
          f"synthetic {synthetic:+.0f} (want -1; the old code: +19); single 2000/0.5: solver {solver:+.1f}, "
          f"independent {independent:+.1f}")


def test_durability_steps():
    """Phase 6 (ADR-015): a durability run stepped from the browser, block by
    block (bridge.durability_start / _next / _stop over
    DieselEngine.durability_blocks), logs exactly what durability_run logs;
    a finished or replaced run is gone; stop frees it."""
    import json
    from dieselsim import bridge
    from dieselsim.engine import DieselEngine
    req = {"engine": {"preset": "crdi15"}, "hours": 150, "step_h": 50}
    ref = DieselEngine(preset="crdi15").durability_run(150.0, step_h=50.0, verbose=False)
    s = json.loads(bridge.durability_start(json.dumps(req)))
    rows, done, calls = [], False, 0
    while not done and calls < 10:
        r = json.loads(bridge.durability_next(json.dumps({"id": s["id"]})))
        rows += r["rows"]
        done = r["done"]
        calls += 1
    same = len(rows) == len(ref) and all(
        set(a) == set(b) and all(repr(float(a[k])) == repr(float(b[k])) for k in a) for a, b in zip(rows, ref))
    try:
        bridge.durability_next(json.dumps({"id": s["id"]}))
        gone = False
    except bridge.RequestError:
        gone = True
    first = json.loads(bridge.durability_start(json.dumps(req)))["id"]
    second = json.loads(bridge.durability_start(json.dumps(dict(req, hours=100))))["id"]
    try:
        bridge.durability_next(json.dumps({"id": first}))
        replaced = first == second
    except bridge.RequestError:
        replaced = True
    stop1 = json.loads(bridge.durability_stop(json.dumps({"id": second})))["stopped"]
    stop2 = json.loads(bridge.durability_stop(json.dumps({"id": second})))["stopped"]
    parts = {"stepped rows equal durability_run's log, exactly": same,
             "a finished run is gone": gone, "a new start replaces the old run": replaced,
             "stop frees it once": stop1 and not stop2}
    bad = [k for k, ok in parts.items() if not ok]
    check("durability stepped from the browser (ADR-015)", float(len(bad)), 0.0, 0.0,
          (f"failed: {', '.join(bad)}; " if bad else f"{len(parts)} of {len(parts)} parts; ")
          + f"{len(rows)} rows in {calls} calls; life consumed after {rows[-1]['hours']:.0f} h: "
          f"{rows[-1]['health']:.3f}%" if rows else "no rows")


def test_spec_editor_schema():
    """Phase 6 (ADR-015): the spec editor's data. The committed schema
    (web/app/src/app/spec/spec-schema.json, tools/spec_schema.py) is current;
    describe_spec returns exactly its paths, in order, with overrides applied;
    and every editable field (number, int, bool) round-trips through
    `overrides`: set to its own value, the spec is unchanged, so every path
    the editor sends is one the bridge accepts. Where tools/ is absent (the
    Pyodide harness copies only the package and the tests), the schema's two
    parts are left out, and the result says so."""
    import importlib.util
    import json
    import os
    from dieselsim import bridge
    root = os.path.join(os.path.dirname(__file__), "..")
    tool_file = os.path.join(root, "tools", "spec_schema.py")
    d = json.loads(bridge.describe_spec(json.dumps({"engine": {"preset": "crdi15",
                                                               "overrides": {"geom.compression_ratio": 17.0}}})))
    cr = next(f["value"] for f in d["fields"] if f["path"] == "geom.compression_ratio") == 17.0
    editable = {f["path"]: f["value"] for f in d["fields"] if f["type"] in ("number", "int", "bool")}
    again = json.loads(bridge.describe_spec(json.dumps({"engine": {"preset": "crdi15", "overrides": editable}})))
    roundtrip = again["fields"] == d["fields"]
    parts = {"an override shows in describe_spec": cr, "every editable field round-trips through overrides": roundtrip}
    note = ""
    if os.path.isfile(tool_file):
        spec_ = importlib.util.spec_from_file_location("spec_schema", tool_file)
        tool = importlib.util.module_from_spec(spec_)
        spec_.loader.exec_module(tool)
        with open(tool.OUT) as fh:
            committed = json.load(fh)
        parts["the committed schema is current"] = committed == tool.schema()
        parts["describe_spec has the schema's paths, in order"] = \
            [f["path"] for f in d["fields"]] == [r["path"] for r in committed]
    else:
        note = "; the schema's 2 parts left out (tools/ not present, Pyodide harness)"
    bad = [k for k, ok in parts.items() if not ok]
    check("spec editor: schema and describe_spec (ADR-015)", float(len(bad)), 0.0, 0.0,
          (f"failed: {', '.join(bad)}; " if bad else f"{len(parts)} of {len(parts)} parts; ")
          + f"{len(d['fields'])} fields, {len(editable)} editable" + note)


def test_accuracy_table_is_for_this_build():
    """The Dyno page's accuracy note (web/app/src/app/dyno/accuracy.ts,
    FINDING-013) shows its measured figures only when ACCURACY_SOLVER is the
    running build's grid hash. Re-stamping the grids without it (session 6,
    FINDING-024) turned every engine's note into 'not measured' and nothing
    noticed. So: the table names this build, the same hash the shipped grids
    carry. After a change that can move torque, re-measure
    (tools/diag_torque_limiter.py --write-accuracy); after one that can't,
    re-stamp it with the grids (tools/restamp_grids.py). SKIP where web/app
    is absent (the Pyodide harness copies only the package and the tests)."""
    import json
    import os
    import re
    from dieselsim import bridge
    root = os.path.join(os.path.dirname(__file__), "..")
    table_file = os.path.join(root, "web", "app", "src", "app", "dyno", "accuracy.ts")
    if not os.path.isfile(table_file):
        RESULTS.append(("SKIP", "the Dyno page's accuracy table is for this solver build", None, None,
                        "web/app not present (Pyodide harness)"))
        return
    with open(table_file) as fh:
        m = re.search(r"ACCURACY_SOLVER = '([0-9a-f]{64})'", fh.read())
    table = m.group(1) if m else ""
    with open(os.path.join(root, "web", "app", "public", "grids", "crdi15.json")) as fh:
        grids = json.load(fh)["grid_hash"]
    h = bridge.grid_hash()
    check("the Dyno page's accuracy table is for this solver build", 0.0 if table == h == grids else 1.0, 0.0, 0.0,
          f"table {table[:12]}, grids {grids[:12]}, this build {h[:12]}")


def test_compressor_map():
    """ADR-009's compressor-map schematic (Phase 6, ADR-015): bridge.compressor_map
    is the solver's own Compressor, and solve_cycle's operating point sits on it.
    The point lies on the speed line at its own u (Compressor.solve at its PR
    gives its corrected flow); every surge point has zero surge margin; each
    speed line starts on the choke line at PR 1; no turbo, no map and no point."""
    import json
    from dieselsim import bridge
    from dieselsim.config import PRESETS
    from dieselsim.turbo import Compressor, P_REF, T_REF
    spec = PRESETS["crdi15"]()
    comp = Compressor(spec.turbo)
    m = json.loads(bridge.compressor_map(json.dumps({"engine": {"preset": "crdi15"}})))
    op = json.loads(bridge.solve_cycle(json.dumps({"engine": {"preset": "crdi15"}, "rpm": 2700, "load": 0.6})))["compressor"]
    m_line = comp.solve(op["u"] * spec.turbo.n_corr_ref, op["pr"], P_REF, T_REF)[0]
    on_line = abs(m_line - op["m_corr"]) <= 1e-9 * max(op["m_corr"], 1e-9)
    surge_ok = len(m["surge"]) == len(m["lines"]) and all(
        abs(comp.solve(s_["u"] * spec.turbo.n_corr_ref, s_["pr"], P_REF, T_REF)[3]) < 2e-3 for s_ in m["surge"])
    choke_ok = all(abs(line["m"][0] - ch["m"]) <= 1e-12 and line["pr"][0] == 1.0 for line, ch in zip(m["lines"], m["choke"]))
    na_map = json.loads(bridge.compressor_map(json.dumps({"engine": {"preset": "single"}})))
    na_op = json.loads(bridge.solve_cycle(json.dumps({"engine": {"preset": "single"}, "rpm": 2000, "load": 0.5})))["compressor"]
    parts = {"the operating point is on its own speed line": on_line, "surge points have zero margin": surge_ok,
             "speed lines start on the choke line": choke_ok, "no turbo: no map, no point": na_map == {"enabled": False} and na_op is None}
    bad = [k for k, ok in parts.items() if not ok]
    check("compressor map is the solver's own (ADR-009)", float(len(bad)), 0.0, 0.0,
          (f"failed: {', '.join(bad)}; " if bad else f"{len(parts)} of {len(parts)} parts; ")
          + f"crdi15 2700/0.6 at PR {op['pr']:.2f}, {op['m_corr']:.4f} kg/s corrected, u {op['u']:.3f}, surge margin {op['surge_margin']:.2f}")


def test_spec_ambient_reaches_the_solve():
    """FINDING-025: the spec's ambient (thermal.ambient_p / ambient_T, primary
    fields in the spec editor) reached no solve. operating_point took fixed
    defaults, 101325 Pa and 298 K, and no caller passed the spec's, so a
    3000 m edit on /spec left all 8 Dyno outputs bit-identical. Now the
    defaults are the spec's, except in the fuel-limit chain's calibration,
    which stays at the rating's air (engine.RATING_P_AMB / _T_AMB). A first
    fix calibrated at the spec's ambient too, and half load at 2000 m then
    got 13.5% more fuel and 4.6% more torque. Parts:
    - the default spec through the bridge equals an explicit 101325 Pa / 298 K
      solve exactly (the fix changes nothing at standard ambient);
    - 70 kPa in the spec moves the solve the way thin air does (less air: AFR
      down 10% or more; NOx and soot up);
    - 318 K in the spec makes the exhaust hotter;
    - a spec at 70 kPa equals the standard engine told p_amb=70 kPa
      explicitly (the rating is calibrated in the same air either way);
    - half load at 79.5 kPa gets standard's fuel, and less torque;
    - solve_cycle's compressor point reads its inlet temperature from the spec."""
    import json
    from dieselsim import bridge
    from dieselsim.config import PRESETS
    from dieselsim.engine import DieselEngine

    def point(overrides=None):
        eng = {"preset": "crdi15"}
        if overrides:
            eng["overrides"] = overrides
        return json.loads(bridge.solve_point(json.dumps({"engine": eng, "rpm": 2500, "load": 1.0, "n_cycles": 9})))

    base = point()
    op = DieselEngine(spec=PRESETS["crdi15"]()).operating_point(2500, load=1.0, n_cycles=9,
                                                                p_amb=101325.0, T_amb=298.0)
    thin = point({"thermal.ambient_p": 70000.0})
    hot = point({"thermal.ambient_T": 318.0})
    explicit = DieselEngine(spec=PRESETS["crdi15"]()).operating_point(2500, load=1.0, n_cycles=9, p_amb=70000.0)

    def half(p):
        s = PRESETS["crdi15"]()
        s.thermal.ambient_p = p
        return DieselEngine(spec=s).operating_point(1500, load=0.5, n_cycles=9)
    half_sl, half_2k = half(101325.0), half(79500.0)

    def comp(T):
        eng = {"preset": "crdi15", "overrides": {"thermal.ambient_T": T}} if T else {"preset": "crdi15"}
        return json.loads(bridge.solve_cycle(json.dumps({"engine": eng, "rpm": 2700, "load": 0.6})))["compressor"]
    c298, c318 = comp(None), comp(318.0)
    parts = {
        "default spec equals explicit 101325 Pa / 298 K": base["torque"] == op.torque and base["bsfc"] == op.bsfc
        and base["afr"] == op.cycle.afr,
        "70 kPa: AFR down >= 10%, NOx and soot up": thin["afr"] <= 0.9 * base["afr"]
        and thin["nox_g_kwh"] > base["nox_g_kwh"] and thin["soot_g_kwh"] > base["soot_g_kwh"],
        "318 K: exhaust hotter": hot["T_exh"] > base["T_exh"] + 5.0,
        "spec 70 kPa equals explicit p_amb 70 kPa": thin["torque"] == explicit.torque and thin["afr"] == explicit.cycle.afr,
        "half load at 79.5 kPa: standard's fuel, less torque": half_2k.fuel_mg == half_sl.fuel_mg
        and half_2k.torque < half_sl.torque,
        "compressor point at the spec's inlet T": c318 is not None and c298 is not None
        and abs(c318["T_in"] - 318.0) < 1e-9 and abs(c298["T_in"] - 298.0) < 1e-9,
    }
    bad = [k for k, ok in parts.items() if not ok]
    check("spec ambient reaches the solve (FINDING-025)", float(len(bad)), 0.0, 0.0,
          (f"failed: {', '.join(bad)}; " if bad else f"{len(parts)} of {len(parts)} parts; ")
          + f"crdi15 2500/1.0: AFR {base['afr']:.1f} -> {thin['afr']:.1f} at 70 kPa, "
          + f"T_exh {base['T_exh']:.0f} -> {hot['T_exh']:.0f} K at 318 K, torque {base['torque']:.1f} -> {thin['torque']:.1f} N.m; "
          + f"1500/0.5 at 79.5 kPa: {half_2k.fuel_mg:.2f} mg (standard {half_sl.fuel_mg:.2f}), "
          + f"{half_sl.torque:.1f} -> {half_2k.torque:.1f} N.m")


def test_environment_presets_reach_the_solve():
    """Phase 7 (ADR-016): five real places, each the air and the fuel sold
    there. FINDING-025's lesson: a field is only real if a solve moves when
    it changes, so each preset is solved, not just listed. Parts:
    - altitude to pressure matches the ICAO standard atmosphere (3500 m is
      658 hPa in the published table; sea level is 101325 Pa exactly);
    - the standard preset's humidity is ISO 8178's reference, 10.71 g/kg;
    - the standard preset solves bit-identically to no preset;
    - every other preset moves the solve, the physical way: the plateau's
      thin air cuts AFR by 10% or more, the arctic morning's dense air
      gives more torque, the desert's heat a hotter exhaust;
    - runtime_info carries all five, with the same overrides."""
    import json
    from dieselsim import bridge
    from dieselsim.environment import ENVIRONMENTS, H_REF, humidity_ratio, pressure_at

    def solve(ov):
        eng = {"preset": "crdi15", **({"overrides": ov} if ov else {})}
        return json.loads(bridge.solve_point(json.dumps({"engine": eng, "rpm": 2500, "load": 1.0, "n_cycles": 9})))

    E = ENVIRONMENTS
    none, std = solve(None), solve(E["standard"].overrides())
    r = {k: solve(E[k].overrides()) for k in ("plateau", "winter", "desert", "tropics")}
    info = json.loads(bridge.runtime_info()).get("environments", [])   # missing: a part fails, not a KeyError
    h_std = humidity_ratio(E["standard"].T_amb, E["standard"].p_amb, E["standard"].rh_pct)
    # the fuel half of a preset: cetane alone, in standard air, must move the solve too
    cn40, cn55 = solve({"inj.cetane_number": 40.0}), solve({"inj.cetane_number": 55.0})
    moved = [k for k, v in r.items() if any(v[q] != std[q] for q in ("torque", "afr", "T_exh", "nox_g_kwh"))]
    parts = {
        "ICAO pressure: 101325 Pa at 0 m, 658 hPa at 3500 m": pressure_at(0.0) == 101325.0
        and abs(pressure_at(3500.0) / 65800.0 - 1.0) < 0.002,
        "standard humidity is ISO 8178's 10.71 g/kg": abs(h_std - H_REF) < 0.02,
        "standard preset solves identically to none": std == none,
        "every other preset moves the solve": len(moved) == 4,
        "plateau: AFR down >= 10%": r["plateau"]["afr"] <= 0.9 * std["afr"],
        "arctic morning: more torque": r["winter"]["torque"] > std["torque"],
        "desert: hotter exhaust": r["desert"]["T_exh"] > std["T_exh"] + 5.0,
        "each fuel preset sets its cetane": all(e.overrides().get("inj.cetane_number") == e.cetane
                                                for e in E.values() if e.cetane is not None),
        "cetane alone moves the solve (40 -> 55: less NOx)": cn55["nox_g_kwh"] < cn40["nox_g_kwh"],
        "runtime_info carries the five, same overrides": [e["key"] for e in info] == list(E)
        and all(e["overrides"] == E[e["key"]].overrides() for e in info),
    }
    bad = [k for k, ok in parts.items() if not ok]
    check("environment presets reach the solve (ADR-016)", float(len(bad)), 0.0, 0.0,
          (f"failed: {', '.join(bad)}; " if bad else f"{len(parts)} of {len(parts)} parts; ")
          + f"crdi15 2500/1.0 torque {std['torque']:.1f} N.m: plateau {r['plateau']['torque']:.1f} (AFR {std['afr']:.1f} -> "
          + f"{r['plateau']['afr']:.1f}), arctic {r['winter']['torque']:.1f}, desert {r['desert']['torque']:.1f} "
          + f"(T_exh {std['T_exh']:.0f} -> {r['desert']['T_exh']:.0f} K), tropics {r['tropics']['torque']:.1f}; "
          + f"3500 m = {pressure_at(3500.0) / 100:.1f} hPa")


def test_modern_ecu_knows_absolute_pressure():
    """ADR-016 item 2: a modern ECU (spec.ecu_modern) knows absolute pressure.
    Off the rating's air its boost target is the rating's absolute pressure,
    capped at the compressor's map limit, and its smoke limiter caps each
    cycle's fuel at the trapped air / afr_limit. A mechanical pump
    (ecu_modern False) is uncompensated: same pedal, same fuel. At the
    rating's air the two are identical, by construction (the grids were
    re-stamped on that, with an old-vs-new A/B on every engine). Fast solves,
    9 cycles, except the light-load pair (converged). Parts:
    - at the rating's air, modern and mechanical solve identically;
    - mechanical at Leh (65.8 kPa): the rating's fuel, uncompensated;
    - modern at Leh, crdi15 full load: the turbo holds more boost pressure,
      so more torque and leaner than mechanical;
    - modern at Leh, hatch15 full load (a small turbo): the smoke limiter
      holds AFR at its limit, where mechanical runs rich, and delivers less
      fuel than commanded;
    - modern at 90 kPa, crdi15 light load: boost pressure within 5% of sea
      level's (absolute target). The pressure-ratio target let it fall with
      ambient, and light load gained 8.2% torque in thin air (PROPOSAL-phase7
      measurement 3)."""
    from dieselsim import bridge
    from dieselsim.builder import from_dict
    from dieselsim.engine import DieselEngine
    LEH = (65764.0, 293.15)
    # engines/hatch15.json, inlined so the test runs under Pyodide too (which has no engines/)
    HATCH15 = {"name": "1.5 L four, 115 ps", "displacement": 1.5, "n_cyl": 4, "rated_rpm": 4000,
               "peak_torque": 260, "peak_power": 85, "plateau": [2000, 2750], "boost_map_rise": 0.12, "afr_limit": 16.0}

    def op(key, rpm, load, air=None, modern=None, afr_limit=None, converged=False):
        s = from_dict(HATCH15) if key == "hatch15" else bridge._resolve_spec({"preset": key})
        if afr_limit is not None:
            s.afr_limit = afr_limit
        if air:
            s.thermal.ambient_p, s.thermal.ambient_T = air
        if modern is not None:
            s.ecu_modern = modern
        e = DieselEngine(spec=s)
        return e.operating_point(rpm, load=load, converged=True) if converged else e.operating_point(rpm, load=load, n_cycles=9)

    # afr_limit 35: a limiter that acted at the rating's air would bind here (AFR ~29), so a lost gate shows
    std_m, std_x = op("crdi15", 2500, 1.0, modern=True, afr_limit=35.0), op("crdi15", 2500, 1.0, modern=False, afr_limit=35.0)
    std_n = op("crdi15", 2500, 1.0, modern=False)          # the pedal's fuel at the normal afr_limit
    leh_m, leh_x = op("crdi15", 2500, 1.0, LEH, True), op("crdi15", 2500, 1.0, LEH, False)
    hat_m, hat_x = op("hatch15", 2000, 1.0, LEH, True), op("hatch15", 2000, 1.0, LEH, False)
    hat_cmd = op("hatch15", 2000, 1.0, modern=True).fuel_mg      # the pedal's fuel, at the rating's air
    # converged: at light load a fast solve's boost hasn't settled (FINDING-013), and a 5% band can't tell
    # the two targets apart there (measured: 234 -> 228 kPa without the absolute target, 229 with it)
    lite_std = op("crdi15", 2800, 0.3, converged=True)
    lite_90 = op("crdi15", 2800, 0.3, (90000.0, 283.0), True, converged=True)
    afr_lim = HATCH15["afr_limit"]
    parts = {
        "rating's air (afr_limit 35, where a limiter would bind): modern and mechanical identical": (std_m.torque, std_m.fuel_mg, std_m.cycle.afr)
        == (std_x.torque, std_x.fuel_mg, std_x.cycle.afr),
        "mechanical at Leh: the rating's fuel": leh_x.fuel_mg == std_n.fuel_mg,
        "modern at Leh: more boost, torque and air than mechanical": leh_m.cycle.p_intake > 1.1 * leh_x.cycle.p_intake
        and leh_m.torque > leh_x.torque and leh_m.cycle.afr > leh_x.cycle.afr,
        "modern at Leh: boost ratio within the compressor's map limit (+5%)":
        leh_m.cycle.p_intake / LEH[0] <= 1.05 * bridge._resolve_spec({"preset": "crdi15"}).turbo.pr_max_ref,
        "modern at Leh, small turbo: AFR held at the limit (within 5%), mechanical rich":
        0.99 * afr_lim <= hat_m.cycle.afr <= 1.05 * afr_lim
        and hat_x.cycle.afr < 0.97 * afr_lim and hat_m.fuel_mg < 0.95 * hat_cmd,
        "modern at 90 kPa, light load: boost pressure held (absolute target)":
        abs(lite_90.cycle.p_intake / lite_std.cycle.p_intake - 1.0) < 0.05,
    }
    bad = [k for k, ok in parts.items() if not ok]
    check("modern ECU knows absolute pressure (ADR-016)", float(len(bad)), 0.0, 0.0,
          (f"failed: {', '.join(bad)}; " if bad else f"{len(parts)} of {len(parts)} parts; ")
          + f"crdi15 2500/1.0 at Leh: modern {leh_m.torque:.1f} N.m, MAP {leh_m.cycle.p_intake / 1e3:.0f} kPa, AFR {leh_m.cycle.afr:.1f}; "
          + f"mechanical {leh_x.torque:.1f}, {leh_x.cycle.p_intake / 1e3:.0f} kPa, AFR {leh_x.cycle.afr:.1f}; "
          + f"hatch15 2000/1.0 at Leh: AFR {hat_m.cycle.afr:.2f} (limit {afr_lim}; mechanical {hat_x.cycle.afr:.2f}), "
          + f"fuel {hat_m.fuel_mg:.1f} of {hat_cmd:.1f} mg; crdi15 2800/0.3 MAP {lite_std.cycle.p_intake / 1e3:.0f} -> "
          + f"{lite_90.cycle.p_intake / 1e3:.0f} kPa at 90 kPa")


def test_modern_cap_holds_with_egr_on():
    """FINDING-026: off the rating's air the modern ECU caps its boost target at
    the compressor's map limit, and the cap must hold for the target the VGT
    actually chases. cycle.run raises the target for EGR, so a cap applied
    before that raise left part load with EGR on chasing a ratio above the
    limit: the vanes jammed on their minimum, exhaust back-pressure reached
    5-6 bar, and crdi15 at Leh lost 30% torque at 4057/0.6 (-75% at 0.2).
    test_modern_ecu_knows_absolute_pressure checks the limit only at full
    load, where EGR is zero, so it passed. crdi15, Leh, converged (a fast
    solve's boost hasn't settled at part load, FINDING-013). Parts:
    - 4057/0.2 and 4057/0.6: the achieved pressure ratio within the limit (+1%);
    - 4057/0.6: the ratio reaches the limit (-2%), where the absolute target
      exceeds it (a cap divided twice by the raise passed without this part);
    - 4057/0.2: the vanes off their minimum;
    - 4057/0.6: torque within 10% of standard air's."""
    from dieselsim import bridge
    from dieselsim.engine import DieselEngine
    LEH = (65764.0, 293.15)

    def op(load, air=None):
        s = bridge._resolve_spec({"preset": "crdi15"})
        if air:
            s.thermal.ambient_p, s.thermal.ambient_T = air
        e = DieselEngine(spec=s)
        return e, e.operating_point(4057.0, load=load, converged=True)

    spec = bridge._resolve_spec({"preset": "crdi15"})
    pr_max, vgt_min = spec.turbo.pr_max_ref, spec.turbo.vgt_min_frac
    (_, std6), (_, leh6), (e2, leh2) = op(0.6), op(0.6, LEH), op(0.2, LEH)
    parts = {
        "4057/0.2 at Leh: pressure ratio within the limit": leh2.boost_pr <= 1.01 * pr_max,
        "4057/0.6 at Leh: pressure ratio within the limit": leh6.boost_pr <= 1.01 * pr_max,
        # the absolute target exceeds the limit here, so the cap binds: an over-cap shows as boost below it
        "4057/0.6 at Leh: pressure ratio reaches the limit (-2%)": leh6.boost_pr >= 0.98 * pr_max,
        "4057/0.2 at Leh: vanes off their minimum": e2.turbo.vgt_pos > vgt_min + 0.02,
        "4057/0.6 at Leh: torque within 10% of standard air's": leh6.torque > 0.9 * std6.torque,
    }
    bad = [k for k, ok in parts.items() if not ok]
    check("modern ECU's cap holds with EGR on (FINDING-026)", float(len(bad)), 0.0, 0.0,
          (f"failed: {', '.join(bad)}; " if bad else f"{len(parts)} of {len(parts)} parts; ")
          + f"limit {pr_max:.2f}: PR {leh2.boost_pr:.2f} (0.2), {leh6.boost_pr:.2f} (0.6); "
          + f"vanes {e2.turbo.vgt_pos:.3f} (min {vgt_min:.2f}); "
          + f"torque at 0.6 {leh6.torque:.1f} vs {std6.torque:.1f} N.m; "
          + f"exhaust {leh2.cycle.p_exhaust / 1e5:.2f} / {leh6.cycle.p_exhaust / 1e5:.2f} bar")


def test_live_grid_pieces_match_the_shipped_grid():
    """ADR-014 step 3: a browser worker builds a drivable grid from the
    bridge's pieces, and tools/build_live_grids.py now builds with the same
    ones. A cell solved through bridge.live_cell, on the shipped crdi15
    grid's own row fuel, must equal that grid's cell (perf, pressure trace,
    sources), warm and cold; and the plan's axes must be the grid's.
    (The refactored tool also rebuilt a 2 x 2 custom grid identical to the
    old code's, 0 of 24 fields differing.)
    First written as exact equality: it held on the Mac that built the
    grids and failed on CI's Linux (perf and sources differ, the trace does
    not) -- floating point across platforms, which the golden points allow
    for with GOLDEN_TOL. Now held to GOLDEN_TOL, the worst difference said."""
    if _no_prebuilt_grids("bridge pieces match the shipped grid"):
        return
    import json
    from dieselsim import bridge
    with open(os.path.join(os.path.dirname(__file__), "..", "web", "app", "public", "grids", "crdi15.json")) as fh:
        g = json.load(fh)
    plan = json.loads(bridge.live_grid_plan(json.dumps({"engine": {"preset": "crdi15"}})))
    import base64
    import numpy as np
    i, j = 2, 3
    bad, worst = [], [0.0, ""]

    def near(a, b, what):
        # numbers relative, float32 arrays (base64) relative to their peak
        if isinstance(a, str):
            x, y = (np.frombuffer(base64.b64decode(v), dtype="<f4").astype(float) for v in (a, b))
            if x.shape != y.shape:
                return False
            r = float(np.max(np.abs(x - y)) / max(float(np.max(np.abs(y))), 1e-30)) if x.size else 0.0
        else:
            r = abs(a - b) / max(abs(b), 1e-12) if abs(a - b) > 1e-15 else 0.0
        if r > worst[0]:
            worst[0], worst[1] = r, what
        return r <= GOLDEN_TOL

    def same(a, b, what):
        if isinstance(a, dict):
            return a.keys() == b.keys() and all(same(a[k], b[k], f"{what}.{k}") for k in a)
        return near(a, b, what)
    if plan["rpms"] != g["rpms"] or plan["loads"] != g["loads"]:
        bad.append("plan axes")
    for cold, sfx in ((False, ""), (True, "_cold")):
        c = json.loads(bridge.live_cell(json.dumps({"engine": {"preset": "crdi15"}, "rpm": g["rpms"][i],
                                                    "load": g["loads"][j], "fuel_limit": g["fuel_limits"][i],
                                                    "cold": cold})))
        if not same(c["perf"], g["perf" + sfx][i][j], f"perf{sfx}"):
            bad.append(f"perf{sfx}")
        if not same(c["p_cyl_f32"], g["p_cyl" + sfx + "_f32"][i][j], f"p_cyl{sfx}"):
            bad.append(f"p_cyl{sfx}")
        if not (same(c["src_f32"], g["src" + sfx + "_f32"][i][j], f"src{sfx}")
                and same(c["meta"], g["src_meta" + sfx][i][j], f"meta{sfx}")):
            bad.append(f"sources{sfx}")
    check("a cell built from the bridge's pieces equals the shipped grid's (ADR-014 step 3)", float(len(bad)), 0.0, 0.0,
          (f"differ beyond {GOLDEN_TOL}: {', '.join(bad)}; " if bad else f"crdi15 cell [{i}][{j}], warm and cold: ")
          + f"worst difference {worst[0]:.2e} at {worst[1] or '-'}")


def test_na_engines_idle_on_a_converter():
    """Roster B: the torque converter was sized from a 19 bar BMEP for every
    engine, so the 1.0 L naturally aspirated single got one sized for
    159 N.m against its 58 and, in "Auto", was dragged to the loop's floor
    (60 rpm) at a cold start. Sized by aspiration (8 bar NA), it must hold
    within 15% of idle for 3 s, warm-up not counted. Known, recorded: the dev
    preset `single` still sags on the same tractor's converter, its idle
    (1000 rpm) high against the 1800 rpm stall -- the exact fix sizes the
    converter from the engine's own full-load torque at stall."""
    if _no_prebuilt_grids("NA engines idle on a converter"):
        return
    import json
    from dieselsim.builder import from_dict
    from dieselsim.live import Adr011Grid, LiveEngine
    grids = os.path.join(os.path.dirname(__file__), "..", "web", "app", "public", "grids")

    def idle_after(key, spec=None):
        with open(os.path.join(grids, f"{key}.json")) as fh:
            g = Adr011Grid.from_json(json.load(fh), spec=spec)
        e = LiveEngine(g, key, trans="tc")
        for _ in range(180):
            e.step(1 / 60)
        return e.rpm, e.spec.idle_rpm
    with open(os.path.join(ENGINES_DIR, "single10.json")) as fh:
        r, idle = idle_after("single10", from_dict(json.load(fh)))
    check("an NA single holds its idle on a torque converter (roster B)", 1.0 if r > 0.85 * idle else 0.0, 1.0, 0.0,
          f"single10 at {r:.0f} rpm after 3 s (idle {idle:.0f}); with the 19 bar sizing it fell to 60")
    r2, idle2 = idle_after("single")
    known("the dev single sags on the tractor's converter (sized by a BMEP proxy, not its own torque)",
          r2 < 0.9 * idle2, f"single at {r2:.0f} rpm after 3 s (idle {idle2:.0f})")


def test_roster_engines_make_their_numbers():
    """ADR-008/012: each Enjoy roster engine, built by builder.py from its
    engines/<key>.json brochure, still delivers it: at the start of its
    torque plateau at least 95% of the rating cap (the low end is where the
    builder falls short: 77-85% before tuning), and at rated speed within 3%
    of its brochure power. Fresh engine per point. The full verify() record
    is in engines/ROSTER.md. SKIP where engines/ is absent (Pyodide)."""
    import json
    if not os.path.isdir(ENGINES_DIR):
        RESULTS.append(("SKIP", "roster engines make their numbers", None, None, "engines/ not present"))
        return
    from dieselsim.builder import load_engine_dir
    load_engine_dir(ENGINES_DIR)
    notes, ok = [], True
    for key in ROSTER:
        with open(os.path.join(ENGINES_DIR, f"{key}.json")) as fh:
            d = json.load(fh)
        lo = float(d["plateau"][0])
        e = DieselEngine(preset=key)
        T = e.operating_point(lo, load=1.0, n_cycles=9).torque
        frac = T / e.torque_cap(lo)
        P = DieselEngine(preset=key).operating_point(float(d["rated_rpm"]), load=1.0, n_cycles=9).power / 1e3
        good = frac >= 0.95 and abs(P / d["peak_power"] - 1.0) <= 0.03
        ok = ok and good
        notes.append(f"{key} {100 * frac:.1f}% at {lo:.0f} rpm, {P:.1f}/{d['peak_power']} kW")
    check("roster engines make their brochure numbers (ADR-008/012)", 1.0 if ok else 0.0, 1.0, 0.0, "; ".join(notes))


def test_roster_grids_match_their_engine_files():
    """A roster grid depends on engines/<key>.json, which the grid hash
    (dieselsim/ only) does not cover: build_live_grids records the file's
    sha256, and it must still match, or a retuned engine drives a stale grid
    unnoticed. SKIP where the grids or engines/ are absent (Pyodide)."""
    import hashlib
    import json
    if _no_prebuilt_grids("roster grids match their engine files") or not os.path.isdir(ENGINES_DIR):
        return
    bad = []
    for key in ROSTER:
        with open(os.path.join(GRID_DIR, f"{key}.json")) as fh:
            recorded = json.load(fh).get("engine_file_sha256")
        with open(os.path.join(ENGINES_DIR, f"{key}.json"), "rb") as fh:
            now = hashlib.sha256(fh.read()).hexdigest()
        if recorded != now:
            bad.append(f"{key} ({'none recorded' if recorded is None else recorded[:12]} vs {now[:12]})")
    check("roster grids were built from the current engine files", 1.0 if not bad else 0.0, 1.0, 0.0,
          f"stale: {', '.join(bad)}" if bad else f"{len(ROSTER)} of {len(ROSTER)} match")


def main():
    for fn in (test_accuracy_table_is_for_this_build, test_compressor_map,
               test_golden_points, test_n_cycles_convergence,
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
               test_cold_slap_follows_clearance,
               test_ramps_have_their_own_height,
               test_custom_engine_json,
               test_describe_engine, test_solve_cycle, test_mfb50_counts_combustion_before_tdc, test_durability_steps,
               test_spec_editor_schema, test_spec_ambient_reaches_the_solve, test_environment_presets_reach_the_solve, test_modern_ecu_knows_absolute_pressure,
               test_modern_cap_holds_with_egr_on,
               test_live_grid_pieces_match_the_shipped_grid,
               test_na_engines_idle_on_a_converter,
               test_flat_tappet_wears_more_than_roller,
               test_closing_ramps_clear_the_lash,
               test_cam_wear_calibration,
               test_cell_friction_from_trace,
               test_cold_solve_is_path_independent,
               test_cam_lift_is_continuous,
               test_seating_on_ramp_is_ramp_speed, test_grid_benchmark_schedule,
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
               test_intake_and_boost_levels_carry_physics,
               test_grid_sources_warm_and_cold,
               test_live_sound_follows_the_engine,
               test_roster_engines_make_their_numbers,
               test_roster_grids_match_their_engine_files):
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
