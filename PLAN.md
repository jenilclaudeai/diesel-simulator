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
grid on an M2 MacBook. Options are in `reviews/PROPOSAL-grid-build.md`.
The ETA (option A) shipped in #88; the rest is **deferred by the owner until
this version is complete** (2026-10-05). *(Was: "(mostly a misleading ETA;
the build is ~18 min on a laptop). Options and a recommendation are in …,
for the owner's decision. It may revise ADR-014 and add a phone path.")*

**The exit: REVIEW-007.** The Android check (2026-10-05, Galaxy S9+) found
4 bugs. B-01 and B-02 are fixed on the live site (#88), along with B-04's
Stop and ETA; B-03 was a browser extension. One item remains (M-1): the
owner re-checks on the phone and confirms the sound and smoothness. *(Was:
"Open: the exit criterion itself. The owner did the Android check … and
found a few bugs, to be listed in a shared Google Sheet. Phase 5 exits once
they are fixed (REVIEW-007).")*

---

## Phase 6 — Expert mode

Lazy-loads Pyodide. Full spec editing across all nine dataclasses, grouped by
physical subsystem rather than class name. Live 2D schematics (OPEN-E).
Grid-invalidation banner with rebuild progress.

Analysis pages: curve, map, cycle (p–V log-log, p–θ, HRR, valve lift), sweep,
durability. Economy and BSFC shown anywhere are steady-state figures and are
labelled so (FINDING-009). Durability's `health` is **life consumed**
(0 = new), not remaining health (FINDING-019).

**Plan for decision:** `reviews/PROPOSAL-phase6.md` (2026-10-05).
Measured:
- the bridge already takes spec `overrides` (173 fields in the nine
  dataclasses);
- curve (Dyno) and map (Grid) exist;
- cycle, sweep and durability need bridge calls;
- durability costs ~7.5 min per 1,000 h in the browser.

Recommended: PLAN's full scope, staged as two stacks (bridge, cycle page and
editor first; then schematics, the banner, sweep and durability).

**Decided 2026-10-05: option B (ADR-015). Done 2026-10-06: REVIEW-008**,
the exit review, on the stack #89–#99 (waiting to merge).
- `/spec`: every field, in 7 subsystem groups, with ADR-009's four live
  schematics.
- Its edits are solved on every analysis page, with an "out of date"
  banner, and an edited engine can be built drivable.
- `/cycle`, `/sweep` and `/durability`, each checked against native Python
  in a browser.
- The review found and fixed four MAJORs: CI's Pyodide job red since #91,
  the Dyno BSFC unlabelled, edited engines not drivable, and a CI timeout
  too tight for the grown suite.
- Open, all MINOR:
  - edits live in memory until Phase 7's project file (m-3);
  - the sweep's stated resolution (m-1);
  - Expert mode is unchecked on a phone (m-6).

---

## Phase 7 — Environment and projects

Country/season presets → ambient temperature, pressure, altitude, fuel cetane
and cold-flow. "Very close, not perfect" is the accepted bar. Humidity affects
NOx and is **not** in the solver today — either add it or state its absence.

Project save/load as JSON (OPEN-C).

**Decided 2026-10-07 (ADR-016, from `reviews/PROPOSAL-phase7.md`):**
- Weather reaches Drive and Enjoy through a per-engine torque-correction
  table, measured within 1.15% of converged solves *(before #107;
  20.3% on today's code, mostly FINDING-026, so it is re-measured after
  the fix)*. **Built 2026-10-09, shape A3** (every cell × 8 airs): all ten
  grids carry one. Each table's held-out Leh check is 0.3–2.8%, except
  single10 at 7.2% (FINDING-027) and hd_i6 at 4.7% (a smoke-limit knee).
  The place is picked on `/drive` and on `/enjoy`'s start screen; custom
  engines build their table in the browser.
- The ECU knows absolute pressure (MAP boost target, smoke map on absolute
  pressure) on the common-rail engines; the mechanical single stays
  uncompensated.
- Humidity: ISO 8178's K_H on reported NOx (a stated correction, not a
  cycle effect). *(Built 2026-10-08 as 40 CFR 1065.670's form, normalised
  to ISO's 10.71 g/kg: humidity-only, so intake temperature isn't counted
  twice. ADR-016 addendum.)*
- Cold-flow: below the fuel's CFPP, fuel flow is capped in the live loop.
  *(Built 2026-10-10 with a fuel picker on `/drive` and `/enjoy`, the
  owner's choice: sold here, summer, winter or arctic. Summer diesel in
  Rovaniemi won't start; ADR-016 addendum.)*
- Five real-place presets, numbers shown and editable.
- Projects: saved and opened on `/spec`; `/drive` and `/enjoy` can open
  them. *(Built 2026-10-10: version 1 holds the engine's edits plus a
  "Drive with" box on `/spec` (gearbox, place, fuel), the owner's choice.
  Old spec files still open. An edited engine drives once its grid is
  built in that browser. ADR-016 addendum.)*
- Build order: presets, environment on the solving pages, the ECU, the
  Drive table, humidity, cold-flow, projects. (REVIEW-008 m-3, keeping
  `/spec` edits across a reload, shipped first in #103.)

---

## P08 — An automatic that shifts on demand (the owner's request, 2026-10-12)

The owner's Feat Prop P08: shift on demanded torque, upshifting early when
there is torque to spare, and keep today's power schedule at full pedal.
The owner asked to continue with it, so it comes before Phase 8. Measured
and prototyped in `reviews/PROPOSAL-P08.md`: today's gear burns 3–43%
more than the least-fuel gear below 110 km/h on the cars. The
recommendation (C4) is a fuel-map choice among the gears that can supply
the pedal's power with a reserve. **Decided 2026-10-12 (ADR-017):** C4, all
automatic boxes, half pedal never later than today. *(Was: "Not decided;
nothing built.")* **Built 2026-10-12** on `feat/p08-shift-schedule`: all
12 car cruises in the least-fuel gear, full pedal identical to today. **Merged and live** (#123, 2026-10-12).

## P09 — more knocking at high altitude (the owner's request, priority 2)

Measured 2026-10-14 in `reviews/PROPOSAL-P09.md` (FINDING-029). The
solver lengthens the delay at altitude, but its knock mostly falls (the
0.72 premix cap, and a premixed burn that slows with φ). The live loop
plays the sea-level sound at every place. A scratch fix (V1) turns the
trend the right way, with torque and fuel within 0.6%. Even so, after P10
the change is 0.0–0.4 dB at the mics: not audible. Recommended: record it
now, and fix the physics at the next rebuild, with FINDING-028's solver
fix. ~~**Not decided; nothing built.**~~
**Decided (ADR-019).** The owner chose C, for a modern CRDi at Leh and a
cold start, staged, with a cold-start model (2026-10-14), and the synth's
gain k = 4 by ear (2026-10-15). **Built** on `feat/p09-knock`:
- stage 1, the numerics: FINDING-028 option B, the burn integrated over
  each step, the knock from the burn law (FINDING-029);
- stage 2: the burn law, a true cold start with a chamber warm-up in the
  live loop, the knock in the weather table, and the synth's gain.

**Waiting on** the rebuild of the ten grids with their weather tables
(started 2026-10-14 22:01 UTC, about 8 h or more), then CI, then the PR.

## P10 — a deeper, bassier diesel sound (the owner's request, 2026-10-13)

Measured in `reviews/PROPOSAL-P10.md`: the exhaust (the low firing pulse)
is 0.2–1.6% of the default mic's mix; clicks and combustion modes dominate.
Feasible; recommended: rebalance the mix plus a muffler low-pass, judged by
ear on A/B pairs first. **Not decided; nothing built.**
**2026-10-14:** the owner listens on a phone speaker, at the cabin and intake
mics. The "muffler" piece was wrong: the bright idle exhaust is a numerical
zig-zag in the solver's idle port flows (FINDING-028), so B is now the
zig-zag averaged out in the synth plus the rebalance. A/B/C listening files
sent (`tools/p10_ab.py`). ~~**Waiting on the owner's ear.**~~
**Decided 2026-10-14 (ADR-018):** B, loudness matched at a cruise, FINDING-028
option C. **Built** on `feat/p10-sound`: the balance and trims in
`acoustics.py`/`livesound.py`/`synth.ts`, the grids re-stamped, two new
tests. **Merged and live** (#128, 2026-10-14 08:10 UTC; CI 9 of 9).
~~Waiting on the owner's ear on the phone.~~ **The owner listened and
accepted it** (full pedal "is little louder. But fine I guess"). Left for later: FINDING-028's solver fix
(option B), at the next rebuild.

## P13 — build a drivable grid faster, front end unchanged (the owner's request, 2026-10-15)

Measured in `reviews/PROPOSAL-P13.md` on P09's code. A drivable grid is now
~73% weather table (the browser build includes it by default): crdi15 58 min
natively, ~1.4–1.8 h in a browser. Options: **N** a one-command native script
for a custom engine, then Import grid (no solver change); **B** stop converged
solves once settled, rule R2 (×1.9, torque ≤ 0.02% of full load, one rebuild);
**C** hoist two constants in `thermo.py` (×1.08, bit-identical). Recommended N
now, B + C after #131. ~~**Not decided; nothing built.** Two questions for the
owner.~~ **Decided 2026-10-16: both, N first.** N built (#132); B + C on
`feat/p13-early-stop`. **All merged:** N (#132, 2026-10-18), B + C (#133, 2026-10-19; rule R5,
ADR-020).

**Next proposal, from FINDING-031 (the owner, 2026-10-16):** a cold-start ECU in the
live loop (fast idle when cold, the pedal's fuel raised to cover the extra
friction), so light pedal moves the car from a cold start. At 0 °C, 20% pedal
doesn't move it today, on `main` too.

---

## Phase 8 — Polish and host

~~GitHub Pages.~~ Done early, 2026-10-04 (#85), for the Phase 5 phone check:
https://jenilclaudeai.github.io/diesel-simulator/, published from `main`.
~~Metric/imperial toggle.~~ **Built 2026-10-19** (`feat/phase8-units`): the owner's choice, Metric / US / UK on the driver pages only (Enjoy, Drive and their place notes; the engineering pages stay SI), kept per browser beside the place and the fuel. Accessibility: gauges need text
alternatives, and warnings must not be encoded in colour alone.
**Accessibility built 2026-10-13** (`feat/phase8-a11y`): measured with
axe-core on every page (7 clean) and by hand on Enjoy's dash; the dials
speak in rpm and km/h, a lit warning lamp is 4.87:1, the redline and the
derate mark differ by shape. Unlit lamps stay dim (the owner's choice).
**Merged and live** (#125, 2026-10-12 UTC).
~~Vibration on phones in `/enjoy` (the owner's Feat Prop P01, ADR-016),
patterned on firing frequency and load; Android Chrome only.~~ **Built 2026-10-19** (`feat/p01-vibration`): the owner's choice, events (start, stall,
gear change, the limiter) plus a shake while idling or lugging, on by default with a
switch. The Vibration API has no strength and a phone's motor can't follow a
4-cylinder's 27 Hz idle firing, so the shake pulses at the firing rate only up to
12 Hz (the single) and is a light buzz above it. **The feel is the owner's to judge on
the phone.** **Widened 2026-10-21** (`fix/p01-driving-vibration`): the owner, on the
S9+, felt the events and the idle but expected it while driving. The owner's choice
"follows load": the shake runs whenever the engine does, its on-time per 50 ms 15 + 20
× pedal (idle 20, was 12; lugging 35, was 25), and a Test button with a note on the
start screen (Chrome on Android stays still on Mute, with no error).

**Random roads (the owner's P06, tiers 1–2, ADR-016 addendum,
2026-10-08):** a seeded random route the engine feels (hills, surfaces as
rolling resistance, headwind, altitude through Phase 7's weather table), a
2D "road ahead" strip, speed breakers as a slow zone plus a jolt (no
suspension, stated), and goals on a route. One PRNG in Python and TS, so
the live fixture holds. Its own proposal comes after Phase 7 step 4, and
places the build in the order.

---

## Deliberately out of scope for v1

Tyre model and grip limit (ADR-002) · suspension, weight transfer, chassis ·
backend, accounts, payments, telemetry collection · multiplayer · 3D models.

### v2, after v1 (the owner's Feat Prop list, ADR-016)

In the owner's priority order (1 is highest):
1. **P04, grid builds on a backend** (priority 1). `PROPOSAL-grid-build.md`
   already weighs a build server.
2. **P02, Google sign-in** (2).
3. **P03, free and paid roles** (3) and **P05, grid builds on AWS Lambda**
   (3). Lambda's 15-minute limit means one invocation per cell, which
   ADR-014's pieces already allow.
4. **P06 tier 3, drawn traffic and scenery** (P06 is priority 2; its tiers
   1–2, random roads and goals, are v1). Needs a renderer, near the
   out-of-scope 3D models; needs no server.

Each reopens ADR-003's static hosting, so each needs its own proposal.

---

## Sequencing rule

Phases 1–3 must be correct before anything is made pretty. A beautiful
dashboard on a lying solver is worse than no dashboard, because it is
persuasive.
