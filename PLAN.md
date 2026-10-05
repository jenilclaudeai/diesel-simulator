# Build Plan

Target: a browser-based diesel engine simulator for enthusiasts. Standalone
Angular frontend, no backend in v1. Architecture decisions are in
`DECISIONS.md`; live state is in `STATUS.md`.

**Governing principle:** the physics is the product. The UI's job is to not lie
about it. Where the simulation is approximate, say so in the UI rather than
presenting an approximation as truth.

---

## Phase 0 — Foundations *(done)*

Establish the repo so any future session can be rebuilt from it rather than
from a pasted context document.

- [x] Vendor `dieselsim` into the repo
- [x] Confirm the solver runs and produces sane numbers
- [x] `PLAN.md`, `DECISIONS.md`, `STATUS.md` committed
- [x] Resolve OPEN-A, C, D, E (ADR-006 to ADR-009)

**Exit criteria:** a new session can read three files and know exactly where
the project stands.

---

## Phase 1 — Physics truth pass

Fix the known bugs **before** anything is built on top of them. Building a UI
on a solver with a 2× fuel-consumption error means every economy figure shipped
is wrong, and the UI gets blamed.

### 1a. Cheap fixes

| Bug | Fix |
|---|---|
| #1 `n_cycles=6` not converged | raise default to ≥9; audit call sites |
| #6 `l` key dead in DCT | `lock_allowed` only read in `_step_tc` |
| #12 grade small-angle form | use `sin θ`, add `cos θ` to rolling resistance |
| #8 unknown-provenance code | audit AFR-headroom block in `fuel_for_torque`, duplicate `cal_cycles`, and the `compact_crdi_i4` / `crdi_1p5` entries |

### 1b. Diagnosis first, then fix

- **#4 — light-load fuel understated ~2×.** Trace `fuel_kg_h` at low load
  against the grid's `fuel_mg` before changing anything. Could be a unit slip,
  could be the limiter. Cannot be scoped until measured.
- **#9 — worn-vs-new audio pair suspect.** The worn engine reported *lower*
  blow-by than new and zero lash growth. Points at wear state not reaching the
  acoustics object.

### 1c. Design work

- **#2 — fuelling is open-loop on rpm, not closed on measured boost.** A better
  turbo currently does not raise torque, which an enthusiast will immediately
  notice and call out. Naive closure is unstable: collapses to 148 N·m at
  1500 rpm, runs away to 33 bar BMEP at 2500. Needs a rate-limited boost
  follower with a stability argument, not a gain guess.
- **#3** is a symptom of #2, not a separate bug. Expect it to resolve with it.
- **#7 — cold combustion.** Resolved by ADR-006: two grids, cold and warm,
  interpolated on coolant temperature. Doubles grid build time.

### 1d. Deferred, documented

#5 (path dependence — `batch.py` already avoids it), #10 (`render_transient`
seams), #11 (coast downshift calibration).

**Exit criteria:** every fixed bug has a regression test. Validation table in
`PROJECT_CONTEXT.md` §1.5 still holds. No number moves without an explanation.

### Outcome (session 5, 2026-09-26) — see REVIEW-003

The plan above is kept as written. What actually happened, per bug:

- [x] #1 — measured (10.8% at 6 cycles); defaults ≥ 9; the last 6-cycle call
  sites (`durability_run`, `demo.py`) fixed in FINDING-019.
- [x] #2 — the instability did not reproduce (FINDING-010). The real gap, no
  p_max / T_exh limit, was fixed in PR #44.
- [x] #3 — not only a symptom of #2: the limiter was calibrated under the wrong
  schedules (FINDING-013 item 1, fixed). The part-load EGR start (item 2) was
  also fixed, in PR #40.
- [x] #4 — the claim, not the solver: the gap is ~29%, not 2× (FINDING-009).
  The economy figure is a **steady-state** figure. Any page that shows it must
  say so (a Phase 5/6 requirement, below). Recalibrating needs part-load data
  we don't have.
- [x] #5 — fixed after all (PR #41): `warm_start=False` isolates a solve.
- [x] #6, #8 (FINDING-007), #9 (FINDINGs 004/005/015/017), #10 (FINDING-014),
  #12 (already correct) — done.
- [x] #7 — resolved by **ADR-011** (friction live from each cell's pressure
  trace; combustion from a cold/warm pair). The ADR-006 line above is
  superseded.
- [x] New on the way: FINDINGs 016 (ignition quantised to the crank step),
  018 (cam lift stepped 4× at the ramp junctions) and 019 (aged-engine torque,
  a fast-path artifact).
- **Deferred to Phase 3, by the owner's decision:** FINDING-013 item 3 (the
  fast path's VGT/EGR loops do not converge in 9 cycles; limit cycle at
  `crdi15`) and #11 (coast downshift). Until then: converge offline, state the
  accuracy online (the dyno page does).
- **Moved to Phase 4's exit criteria, by the owner's decision:** the by-ear
  sign-off of every audio change since FINDING-004.

Exit criteria, checked:

- [x] Every fixed bug has a regression test. The table is in REVIEW-003. One
  exception is recorded there: bug #6 lives in `play.py`'s interactive
  terminal loop and is carried to Phase 3's port.
- [x] Validation table still holds: 12 of 12 rows in band on this tree
  (`tools/validate_table.py`). The 12,000 h paragraph under it did not, and is
  corrected in place.
- [x] No number moved without an explanation: every re-baseline is written up
  next to the golden it moved, in `tests/test_physics.py`.

---

## Phase 2 — Solver port and fixture harness

- [x] `SolverPort` interface — one seam, Pyodide behind it (ADR-001, ADR-010; #11)
- [x] Pyodide in a Web Worker; **verify scipy submodule availability first**
  (not needed: the solver is numpy-only, and scipy is never imported; #9)
- [x] Grid build with real progress reporting, cached in IndexedDB, keyed by
  preset **and** spec hash (cache #12; the `/grid` page with per-cell
  progress, #48)
- [x] Golden-fixture generator (ADR-004) + CI (#47: kinematics and thermo
  ported, the friction fixture ready for Phase 3)

**Exit criteria:** a grid built in-browser matches one built by native Python
within tolerance.

- [x] Met (REVIEW-004): `crdi15`'s full 8 × 6 grid built in headless Chrome
  through the app's worker matches native in 816 of 816 values, worst 8.7e-7
  against a 1e-5 tolerance. CI job `web-grid-e2e` checks it on every PR.

---

## Phase 3 — Real-time loop in TypeScript

Port from `play.py`: `LiveEngine`, `Driveline`, `Gearbox`, `TorqueConverter`,
`LaunchClutch`, cooling stack, trip computer. Fixed 60 Hz in a worker,
decoupled from render rate.

New work: **manual gearbox** with clutch (does not exist in `play.py`).

### Traps carried forward from the Python original

- Shift capacity must be **latched from slip at phase entry**. Recomputing from
  live slip makes the excess shrink as the error shrinks → exponential decay →
  the shift never completes and hits the abort timer.
- The input shaft `w_in` is a **state**, not a function of road speed. Getting
  this wrong previously teleported road speed and manufactured ~700 kW of
  kinetic energy from nowhere.
- A torque converter is specified by **stall speed**, not rated speed.
- Never step the sim from an event handler. Fixed rate or the flywheel
  integration goes wrong.

Carried in from Phase 1 (owner's decision): FINDING-013 item 3 (the fast
path's VGT/EGR loops do not converge in 9 cycles, with a limit cycle at
`crdi15`; its part-load error is 13.5% RMS against converged, see FINDING-013),
known bug #11 (coast downshift calibration), and a test for bug #6's key
handling once the loop is ported.

**Exit criteria:** differential tests green; a 60-second drive in TS matches
the same drive in Python within tolerance.

### Outcome (session 5, 2026-09-27) — see REVIEW-005

- [x] The loop ported: `play.py`'s real-time classes were moved into
  `dieselsim/live.py` bit-identically, then ported to `web/physics/src/live`
  with Python's field names (#51, #52).
- [x] Fixed 60 Hz in a Web Worker, decoupled from rendering: the `/drive`
  page (#57).
- [x] Manual gearbox with a clutch pedal and an auto-clutch assist (#53).
- [x] Carried items:
  - FINDING-013 item 3: prebuilt converged grids for the presets (#56);
  - bug #11: root cause FINDING-020, the lock-up's numerical instability (#54);
  - bug #6: tested (#51);
  - ADR-011 step 2: friction live in the loop (#55).
- [x] Exit criterion 1: `web/physics` has 41 checks, all passing, with
  per-step agreement at worst 1.0e-14 and every event at the same step in 7
  fixture drives.
- [x] Exit criterion 2: the 60 s script through the drive page's worker in
  Chrome, on a prebuilt converged grid, matches native Python: 53 of 53
  events at the same frame, final values within 1.7e-16. Checked in CI.

---

## Phase 4 — Audio

TypeScript `AudioWorklet` port of `acoustics.py` (ADR-003). Crank-angle domain
synthesis resampled through instantaneous rpm, so pitch tracks rpm exactly and
a rev sweep needs no pitch-shifting.

Five mic positions. "Start engine" gesture button to satisfy autoplay policy.

**Exit criteria:** rendered audio at 1400 rpm on an I6 peaks at 70/140/210 Hz
(firing frequency and harmonics). Every source asserted non-silent — see the
`_impulses` note in ADR-003. **The owner has listened to, and signed off,**
every audio change since FINDING-004: physical levels, the warm/cold pair,
tick and slap scaling (FINDING-017), ramp-speed seating and the doubled ramp
speed (FINDING-018), and `hd_i6`'s tick dominance (13× its other mechanical
sources). Moved here from Phase 1 by the owner's decision.

**Status (2026-09-27, REVIEW-006):** built and measured, on the stack #59–#63.
- `dieselsim/livesound.py` is the streaming reference, and `play.py` uses
  it (FINDING-021).
- The grids carry warm and cold sources.
- The TypeScript synth matches it to 2.2e-13 of peak.
- The drive page plays it in an AudioWorklet (Sound on, five mics, Record
  WAV).
- Criteria 1 and 2 are met, and CI checks both.
- **Criterion 3 is met.** The owner signed off by ear on 2026-09-30 ("Yes
  it sounds right to me"; REVIEW-006). FINDING-022 was fixed first (#64).
  FINDING-023 (the slap input pinned on a clamp) stays open as a known
  defect, for later.
- *(Was: "Criterion 3, the owner's listening sign-off, is open.")*

---

## Phase 5 — Enjoy mode

Prebuilt grids, no Pyodide, no spec editing. Instant start.

Dashboard: tachometer, speedometer, gear indicator with **shift phase** (torque
phase / inertia phase — the sim models it and nothing else on the web shows
it), warning lamps, vitals, thermal stack, trip computer.

The trip computer's economy is a **steady-state** figure (FINDING-009: about
29% leaner than mixed real-world driving at a 90 km/h cruise). Label it that
way, and don't set it beside brochure consumption.

**Touch controls** (added 2026-09-30, ADR-012; measured missing on
2026-09-29):
- throttle on the right, brake on the left, pressed harder by sliding up;
- shift paddles in the top corners;
- a clutch for the manual.

A new **`/enjoy`** page; `/drive` stays for engineering. **Roster** (ADR-012,
resolving OPEN-F): A first (1.5 L hatchback, 2.2 L SUV, 12.7 L I6 truck),
then B (a 15 L V8 truck and an old NA single).

**Exit criteria:** loads and drives on a mid-range phone in landscape with
audio, without ever fetching Pyodide. Judged on a real mid-range Android
phone in Chrome (ADR-012).

### State (2026-10-05)

Built and merged (#72–#84):
- `/enjoy` with touch pedals, paddles, the dashboard and the steady-state
  trip computer;
- the whole roster, A and B: `hatch15`, `crdi22`, `truck127`, `v8hd` and
  `single10` (records in `engines/ROSTER.md`);
- FINDING-023's cold slap and the separate ramp height, which the owner is
  to judge by ear.

Also built, beyond the plan: custom engines from brochure numbers or JSON,
checked against their brochure and drivable, with grids built in the
browser or natively (ADR-014, #79–#82). That partly anticipates Phase 6
(spec editing) and Phase 7 (engine JSON).

**Custom-engine build times, measured on real devices (2026-10-05):** 5+
min for a grid on a Samsung phone, and an ETA of 2–3+ h for a drivable
grid on an M2 MacBook (mostly a misleading ETA; the build is ~18 min on a
laptop). Options and a recommendation are in `reviews/PROPOSAL-grid-build.md`,
for the owner's decision. It may revise ADR-014 (the browser build) and
add a phone path.

**Open: the exit criterion itself.** The owner did the Android check on the
live site (reported 2026-10-05; Phase 8's hosting was done early for it) and
found a few bugs, to be listed in a shared Google Sheet. Phase 5 exits once
they are fixed (REVIEW-007). *(Was: "Open: the exit criterion itself, the
owner's Android check, on the live site.")*

---

## Phase 6 — Expert mode

Lazy-loads Pyodide. Full spec editing across all nine dataclasses, grouped by
physical subsystem rather than class name. Live 2D schematics (OPEN-E).
Grid-invalidation banner with rebuild progress.

Analysis pages: curve, map, cycle (p–V log-log, p–θ, HRR, valve lift), sweep,
durability. Economy and BSFC shown anywhere are steady-state figures and are
labelled so (FINDING-009). Durability's `health` is **life consumed**
(0 = new), not remaining health (FINDING-019).

---

## Phase 7 — Environment and projects

Country/season presets → ambient temperature, pressure, altitude, fuel cetane
and cold-flow. "Very close, not perfect" is the accepted bar. Humidity affects
NOx and is **not** in the solver today — either add it or state its absence.

Project save/load as JSON (OPEN-C).

---

## Phase 8 — Polish and host

~~GitHub Pages.~~ Done early, 2026-10-04 (#85), for the Phase 5 phone check:
https://jenilclaudeai.github.io/diesel-simulator/, published from `main`.
Metric/imperial toggle. Accessibility: gauges need text
alternatives, and warnings must not be encoded in colour alone.

---

## Deliberately out of scope for v1

Tyre model and grip limit (ADR-002) · suspension, weight transfer, chassis ·
backend, accounts, payments, telemetry collection · multiplayer · 3D models.

---

## Sequencing rule

Phases 1–3 must be correct before anything is made pretty. A beautiful
dashboard on a lying solver is worse than no dashboard, because it is
persuasive.
