#!/usr/bin/env python3
"""
Dead-signal audit.

Four findings in a row shared one shape: a mechanism fully built, correctly
wired, and fed a quantity that is effectively zero or pinned against a clamp.
None of them raised an error. This script looks for others.

It solves a small matrix of operating points and flags any scalar output that:

  DEAD      exactly zero in every case
  FROZEN    identical in every case, to floating-point equality, despite
            conditions that should move it
  PINNED    identical across cases AND sitting on a suspiciously round value
            (a clamp bound)
  TINY      nonzero but below 1e-6 of a comparable sibling quantity

Run: python3 tools/audit_dead_signals.py
It is a diagnostic, not a test -- it reports, it does not fail.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dieselsim.engine import DieselEngine  # noqa: E402

# preset, rpm, load, coolant K, oil K -- deliberately spans cold/warm and
# light/heavy so anything condition-sensitive has a reason to move
MATRIX = [
    ("crdi15", 1800, 0.2, 363.0, 363.0),
    ("crdi15", 1800, 1.0, 363.0, 363.0),
    ("crdi15", 1800, 0.6, 273.0, 273.0),
    ("crdi15", 3000, 1.0, 363.0, 363.0),
    ("hd_i6", 1200, 0.4, 363.0, 363.0),
    ("hd_i6", 1700, 1.0, 363.0, 363.0),
    ("single", 2000, 0.8, 363.0, 363.0),
    ("ld_i4", 2500, 0.9, 363.0, 363.0),
]

# values that legitimately sit at a bound or are structurally constant
EXPECTED_CONSTANT = {
    "egr_pct", "egr_fraction", "egr_valve_area",   # EGR off unless commanded
    "converged",          # False unless a converged-mode solve settled (FINDING-013)
    "n_cycles_used",      # the requested count on the fast path (FINDING-013)
}


def collect(preset, rpm, load, T_cool, T_oil):
    eng = DieselEngine(preset=preset)
    eng.T_coolant = T_cool
    eng._apply_thermal_state()
    eng.oil.cond.T_oil = T_oil
    op = eng.operating_point(rpm, load=load, n_cycles=9, update_oil=False)

    vals = {}
    for obj, prefix in ((op, "op."), (op.cycle, "cyc.")):
        for k, v in vars(obj).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                vals[prefix + k] = float(v)
    for k, v in op.friction.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            vals["fric." + k] = float(v)
    return vals


def main():
    print(f"solving {len(MATRIX)} operating points...\n")
    rows = []
    for case in MATRIX:
        try:
            rows.append((case, collect(*case)))
        except Exception as exc:                       # noqa: BLE001
            print(f"  {case[0]} {case[1]}/{case[2]}: FAILED {exc!r}")
    if not rows:
        return 1

    keys = sorted(set.intersection(*(set(r[1]) for r in rows)))
    dead, frozen, tiny = [], [], []

    for k in keys:
        if k.split(".", 1)[1] in EXPECTED_CONSTANT:
            continue
        series = np.array([r[1][k] for r in rows])
        if np.all(series == 0.0):
            dead.append(k)
        elif np.all(series == series[0]):
            frozen.append((k, series[0]))

    # TINY: boundary powers that are negligible against their total sibling
    for k in keys:
        if not k.startswith("fric.Pb_"):
            continue
        tot = "fric.P_" + k[len("fric.Pb_"):]
        if tot not in keys:
            continue
        ratios = []
        for _, v in rows:
            if abs(v[tot]) > 1e-9:
                ratios.append(abs(v[k]) / abs(v[tot]))
        if ratios and max(ratios) < 1e-4:
            tiny.append((k, tot, max(ratios)))

    def head(t, n):
        print(f"\n{'=' * 68}\n{t}  ({n})\n{'=' * 68}")

    head("DEAD -- exactly zero in every case", len(dead))
    for k in dead:
        print(f"  {k}")
    if not dead:
        print("  none")

    head("FROZEN -- identical in every case despite varied conditions",
         len(frozen))
    for k, v in frozen:
        print(f"  {k:38s} = {v!r}")
    if not frozen:
        print("  none")

    head("TINY -- boundary power negligible vs its own total", len(tiny))
    for k, tot, r in tiny:
        print(f"  {k:26s} max |{k.split('.')[1]}/{tot.split('.')[1]}| "
              f"= {r:.3e}")
    if not tiny:
        print("  none")

    print(f"\n{len(keys)} scalars checked across {len(rows)} operating points.")
    print("DEAD and FROZEN are not automatically bugs -- some quantities are")
    print("legitimately constant. Each needs a judgement. TINY means a wear")
    print("or noise path that exists but cannot influence anything.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
