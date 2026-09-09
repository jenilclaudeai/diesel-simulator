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

GOLDEN = {
    ("crdi15", 1800, 0.6): dict(torque=124.894, bsfc=263.50, pmax=107.23),
    ("crdi15", 3000, 1.0): dict(torque=220.004, bsfc=215.09, pmax=147.40),
    ("hd_i6", 1700, 1.0): dict(torque=2308.265, bsfc=214.58, pmax=173.68),
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
    FINDING-001: premix_fraction is pinned at its 0.02 floor because the
    Watson correlation returns a negative value at modern common-rail
    ignition delays.

    This test flips to UNEXPECTED PASS when the correlation is replaced.
    """
    vals = []
    for T in (273.0, 363.0):
        eng = DieselEngine(preset="crdi15")
        eng.T_coolant = T
        eng._apply_thermal_state()
        vals.append(eng.operating_point(
            1800, load=0.6, n_cycles=9).cycle.premix_fraction)
    pinned = abs(vals[1] - vals[0]) < 1e-9 and abs(vals[0] - 0.02) < 1e-9
    known("premix_fraction responds to coolant temperature", pinned,
          f"pinned at {vals[0]:.4f} across 273-363K (FINDING-001)")


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
    known("cold start sharpens dp/dtheta audibly", rise < 0.15,
          f"cold is only {100 * rise:+.1f}% sharper (FINDING-001)")


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


def main():
    for fn in (test_golden_points, test_n_cycles_convergence,
               test_premix_responds_to_temperature,
               test_cold_start_sharpens_dpdtheta,
               test_no_pilot_double_count):
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
