# REVIEW-005 — Phase 3 exit (real-time loop in TypeScript)

**Date:** 2026-09-27 (session 5, second part)
**Scope:** PLAN.md Phase 3, on the stack #51 → #58 (on top of #50, which lands Phases 1–2)
**Lenses run:** PM, LEAD, PHY2, SR1, SW1, SW2, QA1, QA2, USR1/2 (advisory)
**Reproduce:**
- `cd web/physics && npm test`
- `python3 tools/fixtures/gen_fixtures.py --check`
- `cd web/app && npm run build:pages && CHROME_PATH=… npm run e2e:drive`
- `python3 tests/test_physics.py`

---

## Summary

| Class | Count |
|---|---|
| BLOCK | 0 |
| MAJOR | 0 (REVIEW-003's M-1 is closed for the presets, below) |
| MINOR | 6 |
| NOTE | 3 |

**Phase 3 can exit** once the stack is merged. Both exit criteria are met, and
both are checked in CI.

---

## Exit criteria

**1. Differential tests green.** `web/physics` runs 41 checks, all passing:

| port | reference | agreement |
|---|---|---|
| kinematics, thermo (Phase 2) | fixtures | 3.6e-14 and 4.0e-16 |
| friction + lubrication (ADR-011) | `friction.json`, 6 cases × 27 quantities | **3.5e-13** |
| live loop, per step (from Python's exact state, 80 steps per drive) | `live.json`, 7 drives | worst **1.0e-14** (bound 1e-12) |
| live loop, terminal (free-running) | same | **every event at the same step** in all 7; final values within 2e-15 (bound 1e-6) |

The seven drives:
- `tc` and `dct`, 60 s each: launch, kickdown, coast, brake, grade, lock-up key, cruise, manual shifts, neutral;
- `dct_hot`: fan switching on and off, a 10% climb;
- `manual`: slipping launches, a refused shift, a stall, restarts, the auto-clutch;
- `adr011_cold` and `adr011_warm`: live friction from traces with the oil node, from cold and from warm;
- `tc_kickdown`: 6th → 4th.

`gen_fixtures.py --check` catches a physics change that wasn't regenerated.

**2. A 60-second drive in TypeScript matches the same drive in Python.** It
does so in Node (above), and **in a real browser**: `e2e/drive.e2e.mjs` runs
the 60 s script frame-exact through the drive page's own worker, on the
prebuilt converged `crdi15` grid, against `e2e/native_drive.py` on the same
grid. Result: **53 of 53 events at the same frame, final values within
1.7e-16.** The worker runs the minute in 1.6 s.

---

## The checklist

| PLAN item | done | where |
|---|---|---|
| port `LiveEngine`, `Driveline`, `Gearbox`, `TorqueConverter`, `LaunchClutch`, cooling stack, trip computer | yes: moved out of `play.py` into `dieselsim/live.py` bit-identically (0 of 180,000 values differ), then ported | #51, #52 |
| fixed 60 Hz in a worker, decoupled from render rate | yes: an accumulator in a Web Worker; measured 60 Hz in Chrome | #57 |
| manual gearbox with clutch (new) | yes, plus an auto-clutch assist (owner's decision); Python first, as the reference | #53 |
| trap: shift capacity latched at phase entry | kept; a mutant computing it from live slip is caught | #52 |
| trap: `w_in` is a state (the teleport) | kept; its mutant is equivalent in today's code (sync acts only while rigid, where `i_eff == gb.ratio()`), stated in #52 | #52 |
| trap: converter sized by stall speed | kept (unchanged code) | — |
| trap: never step from an event handler | yes: keys only set inputs, and the worker steps on its own clock | #57 |
| carried: FINDING-013 item 3 | presets drive **prebuilt converged grids** (owner's decision); browser-built grids stay fast with the caveat stated | #56 |
| carried: bug #11 | fixed; the root cause was FINDING-020 (below) | #54 |
| carried: a test for bug #6 | `test_lockup_key_by_transmission`, and the TypeScript key map is checked by the fixture's message log | #51 |
| carried: ADR-011 step 2 | friction live from the traces at the oil and coolant state; a cold engine drives cold (bug #7 closed in real time) | #55 |

---

## Findings of this phase

**FINDING-020 (fixed): the converter's lock-up was numerically unstable.**
It was a spring integrated explicitly at h·C/J = 17, where explicit Euler is
stable only below 2. Every locked frame sat on its ±4,500 N·m clamp, which is
CLAUDE.md's pattern exactly, and coast downshifts jolted at up to 1.3 g. It
had been in `play.py` all along. Lock-up is now a clutch (slip-engaged, then
rigid), and coast downshifts stretch both phases.

## Review findings

**m-1 (MINOR) — browser-built grids.** A custom engine's grid, built in the
browser, stays on the unconverged fast path, and it has no cold pair, so live
friction still follows the oil but combustion does not follow the coolant. The
drive page offers presets only, which all have prebuilt grids. The grid page
states the part-load caveat. *(LEAD, USR)*

**m-2 (MINOR) — the prebuilt grids cost 4 MiB and 57 minutes to rebuild after
a solver change.** They are keyed on `grid_hash()`, which excludes the live
loop, so tuning the loop doesn't trigger a rebuild. Staleness is **labelled on
the page, not enforced in CI**, the same policy as the dyno accuracy table.
*(SW1, PM)*

**m-3 (MINOR) — the converter's residual coast transient.** After a
downshift completes, the converter pulls the engine up to input speed: up to
1.5 m/s² on 2→1 at 17 km/h. That is real converter physics; a TCU would also
match engine speed, and that is not modelled. *(PHY2)*

**m-4 (MINOR) — a manual on a keyboard is hard.** The clutch returns over
1.4 s, a measured choice: at 0.9 s a launch at 0.4 throttle stalled. The
auto-clutch is there for keyboard drivers. Judge it by hand in Phase 5.
*(USR)*

**m-5 (MINOR) — the cost of live friction.** It takes 8.2 ms per evaluation in
Node (1,440 samples), at 10 Hz, so about 8% of a desktop core. Check on a
mid-range phone before Enjoy mode's exit. *(SW2)*

**m-6 (MINOR) — `play.py` still uses the old warm-baked grid** (no traces, no
cold pair). Its `EngineGrid` could adopt `Adr011Grid`. *(SW1)*

**N-1 — unsettled converged cells:** 32 of 480. `crdi_1p5` accounts for 23,
from its VGT/EGR limit cycle. They are period-averaged and flagged
(FINDING-013), and the page states the count. Fixing the fast path's
controllers was not attempted again; converging offline was the owner's
choice.

**N-2 — mistakes this phase, all corrected where they happened:**
- Two false alarms, both mine: I read m/s as km/h, and a quick check omitted
  the script's brake and keys. Each was caught before any change was made.
- A suite count written before the run finished (54 vs 53). Amended.
- A branch checkout removed just-committed grid files from the working tree.
  Restored from `HEAD` without touching uncommitted work.
- An e2e race that passed by luck once. Fixed by waiting for the gauges.
- Three test gaps found by their own mutants, each closed before commit: the
  anti-stall rule untested with the throttle off; the oil effect masked by the
  walls; four live-loop mutants that the first fixture let through.

**N-3 — what an enthusiast sees now:** `/drive`. A cold start feels cold: at
start, oil at 29 °C gives 2.69 bar of live FMEP. There are three gearboxes,
and a manual that stalls if you dump the clutch. Fuel figures are labelled as
coming from steady-state cells.

---

## Suite and accuracy on the final tree

Physics suite on this tree: **56 passed, 0 failed, 2 known defects, 0 unexpected passes** (with scipy).

Dyno accuracy table regenerated on physics build `848083b7b0ee` (`--pull`
then `--write-accuracy`). The rows are unchanged from REVIEW-004: nothing in
Phase 3 touched the dyno's solve, only the hash moved:
`crdi15` −5.84%, `crdi_1p5` −8.48%, `hd_i6` −3.35%, `ld_i4` −3.74%,
`single` 0.00%.
