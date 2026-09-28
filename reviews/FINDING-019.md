# FINDING-019 — the aged `crdi15`'s torque gain is a fast-path artifact, not a wear bug; `durability_run` solved at 6 cycles

**Opened by:** FINDING-015's "observed, not investigated" note: `crdi15` makes
+3.6% torque after 2000 h, and `hd_i6` makes −1.9%.
**Lens:** PHY2 (lead), QA2
**Status:** investigated. No wear-model bug. One clear bug fixed (`durability_run`'s cycle count).
**Reproduce:** `out/aged.py`, `out/aged_attr.py`, `out/aged_conv.py` (not committed; summarised below)

---

## Measured on the current tree

This tree includes PRs #40–#44. `crdi15`, default duty cycle, 2000 h. Every
row compares against a new engine at the same point, n_cycles 9.

| engine | 1800 / 1.0 | 1800 / 0.6 | 3000 / 1.0 |
|---|---|---|---|
| aged engine as `durability_run` leaves it | +2.47% | +2.20% | −0.25% |
| new engine + aged wear only | +2.46% | +2.74% | −0.23% |
| new engine + aged thermal state only (coolant 364.5 K, oil 388.2 K) | −0.01% | +0.14% | −0.00% |
| new engine + aged oil condition only | +0.01% | −0.07% | −0.00% |

The "+3.6%" from session 4 is not reproduced exactly. The tree has changed
since (EGR start, cam profile), and the measurement then was not recorded.
The size and sign are the same. It is the **wear**, not the thermal or oil
state.

## Which wear

Each group applied alone, and removed alone, at 1800/1.0:

| group | alone | all but it |
|---|---|---|
| cylinder kit (bore, rings, skirt) | −2.40% | −0.03% |
| bearings | −2.40% | −0.00% |
| valvetrain (cam, lash, seat) | −2.40% | +0.01% |
| injector (coking, spray) | −3.07% | +0.37% |
| **turbo (shaft wear, fouling)** | **+0.34%** | **−2.99%** |

(The "alone" column is relative to the fully aged engine.) Turbo fouling
(compressor 2.5%, turbine 4.2% efficiency loss) produces the whole gain.
Everything else, applied alone, costs torque, as it should. The route is the
fuel limiter: calibrated full-load fuel is 42.53 mg new and 44.30 mg with a
fouled turbo.

## Why: the limiter calibrates on unconverged solves

At 1800 rpm `crdi15`'s torque cap (220.6 N·m) is out of reach at 8 cycles, so
the limiter falls back to the fuel the measured air allows. That measurement
comes from the unconverged VGT loop (FINDING-013 item 3), which responds to a
less efficient turbo in the wrong direction. Converged, the effect vanishes:

| 1800 / 1.0 | fast (n 9, cal 8) | converged (200 cycles, real time) |
|---|---|---|
| new | 205.59 N·m, fuel 42.53 mg | 219.90 N·m, fuel 43.87 mg |
| fouled turbo only | 211.36 (+2.81%), 44.30 mg | 220.03 (+0.06%), 44.39 mg |
| fully aged | 210.65 (+2.46%), 44.14 mg | 219.72 (**−0.08%**), 44.23 mg |

Converged, the aged engine holds its rating using 0.8% more fuel. That is what
a torque-structured ECU does. **No wear-model bug.** The fast-path artifact
belongs to item 3 (Phase 3).

## A clear bug on the way: `durability_run` at 6 cycles

`durability_run` solved every duty-cycle mode at `n_cycles=6`. Known bug #1
measured that as unconverged, and the project's rule is ≥ 9. Over 2000 h,
6 vs 9:

| preset | exhaust lash | bore wear | ring gap | logged rated torque |
|---|---|---|---|---|
| `single` | 149.90 → 149.90 µm | identical | identical | identical |
| `crdi15` | 1.78 → 1.79 µm | 1.905 → 1.856 µm | 6.987 → 6.796 µm | **192.02 → 199.26 N·m (+3.8%)** |
| `hd_i6` | 6.67 → 6.87 µm | 1.355 → 1.374 µm | 4.585 → 4.657 µm | 2236.6 → 2225.9 N·m |

Fixed to 9. The owner's cam-wear calibration engine (`single`) is unchanged
(149.90 µm), so `K_ARCHARD` needs no re-fit. A durability run costs about
1.5× the time. `demo.py`'s sweep also used 6 and now uses 9.

Test `test_durability_solves_are_converged_enough`: during a 50 h run, no
solve made by `durability_run` itself uses fewer than 9 cycles. The limiter's
calibration keeps its recorded `cal_cycles = 8`. Mutation: restoring 6 fails
it. The unmutated baseline passes. Suite 46 passed, 0 failed, 2 known.

## Noted, not changed

- `durability_run` never calls `reset_torque_cal()`, although
  `fuel_for_torque`'s docstring says to after wear. An aged engine keeps the
  fuel map it was calibrated with when new. That is defensible as "the ECU was
  calibrated once", so it is not a clear bug. It is a choice worth recording.
- Its log's `health` reads 0.9–1.7% after 2000 h. That is correct:
  `overall_health()` returns **life consumed** (0 = new, 100 = due for
  overhaul), as its docstring says. The name reads the other way round, so the
  UI should label it "life used".
