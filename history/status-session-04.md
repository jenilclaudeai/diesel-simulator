# STATUS history: Session 4 (2026-09-25/26)

Moved verbatim from `STATUS.md` at `a57a6fd`, its lines 3277-3458, by step A1 of
`reviews/PROPOSAL-modularize.md` (2026-10-28). **This is history, not the present**:
`STATUS.md` is. Struck-through text and in-place corrections are as they were written.
`python3 tools/check_verbatim_move.py history/` proves the copy.

<!-- verbatim: STATUS.md@a57a6fd 3277-3458 -->
## Session 4, part 4 (2026-09-26)

Owner's decisions, applied as the stack #36 → #39:

- **#37 — ramps above lash** on `hd_i6` (ramp_fraction 0.155) and `single`
  (0.13): seating 0.81 → 0.45 and 0.39 → 0.25 m/s at 1500 rpm. `hd_i6`'s valve
  tick falls from ~41× to **13×** its loudest other source — still dominant;
  the on-ramp lash penalty in `seating_velocity()` and the `_ref_vseat`
  calibration are open judgements (FINDING-017).
- **#38 — cam wear calibrated**: `K_ARCHARD["cam"]` 3.2e-9 → 2.17e-7 so the
  flat-tappet `single` grows 150 µm of exhaust lash in 2000 h (the owner's
  service interval). Rollers ~17× slower. *Observed, not investigated:*
  `crdi15` gains 3.6% torque after 2000 h from the other (untouched) wear
  mechanisms — recalls bug #9.
- **#39 — ADR-011 step 1**: cells carry `p_cyl` and `perf.p_rail`;
  `grid.cell_friction()` evaluates friction from the stored trace at live
  oil/coolant state (matches the cell's own to −0.008%, a full cold solve to
  +0.070%). `GRID_FORMAT` 2, `CACHE_VERSION` 7.
- **Harness trap found:** Python's bytecode cache validates a source by its
  mtime (whole seconds) and size, so a same-length mutation restored within a
  second runs stale bytecode. Mutation runs now use
  `PYTHONDONTWRITEBYTECODE=1`. Earlier results were re-checked: a stale cache
  can make a mutant falsely *survive*, never falsely *caught*, and every
  surviving mutant reported this session changed the line's length.

---

## Session 4, part 3 (2026-09-25, later)

- **The listening pairs were finally rendered and sent to the owner**
  (`tools/render_ab.py`, WAVs in `out/listen/`): `crdi15` 1800/0.6 warm vs fully
  cold is now **+28% brighter, +3.5% louder** (before FINDING-004: +1% / −11%).
  **Awaiting the owner's ears.**
- **FINDING-017 (#31):** piston slap and valve tick lose their physical scaling
  inside the mechanical sub-mix (each divided by its own std — FINDING-004's
  pattern again; doubling the slap input changes the output by 3.6e-11), and
  `hd_i6` / `single` seat valves off the closing ramp (lash 550 / 250 µm above
  ramps of 106 / 69 µm), so `hd_i6`'s valve clatter is ~45× its other sources.
- **REVIEW-002 (#32):** ADR-006 reassessed with converged solves. The cold
  engine is an **oil** effect (FMEP +224–375%, torque −21–78%); coolant drives a
  small, linear combustion change. Two-grid linear interpolation in
  temperature errs up to +108% FMEP. **ADR-011 accepted by the owner:**
  friction computed live; indicated performance from a cold/warm coolant pair.
  Then measured how friction reaches the loop: a fitted FMEP(viscosity)
  surface needs ~6 viscosity nodes × a coolant axis for ~1%, while friction
  evaluated from each cell's stored pressure trace with the live oil state is
  **exact** (0.000% in 9/9; oil never touches the trace). Chosen:
  trace-based. Cost 44 ms per call in Python (94% the bearing eccentricity
  solve); ~ms as compiled JS — to confirm in the port.
- **#34 — FINDING-017 item 1 fixed:** tick, injector and slap carry their own
  physical levels. `crdi15`'s mechanical level ×2.3; warm/cold now +11%
  brighter cold. **`hd_i6` gets far brighter** — item 2 (lash above the ramp)
  now matters more. The updated pair 1 was re-sent to the owner.
- **#35 — FINDING-015 item 2 fixed:** flat-tappet kinematics, rolling
  entrainment, roughness-based film floor (measured inert). `single` cam
  boundary power 22.6 → 215 W, 8000 h lash growth ~1 → ~9 µm; flat tappet ~46×
  a roller per cylinder. **Wear-rate calibration target: owner to choose**
  (options in FINDING-015).

---

## Session 4, part 2 — autonomous stretch (2026-09-25)

The owner merged #15, #17, #18, #19, then asked for ~6 hours of independent
work, pre-deciding: unsettled offline cells are period-averaged and flagged;
goldens may be re-baselined on the PR branch with inline justification; the
e2e-in-CI, bug #10, FINDING-005 and FINDING-008 items may be picked up
(measurement and write-ups only for the physics ones). Nothing was merged —
the permission check blocks merging without review.

**What landed as PRs:**

- **#21 — converged offline solves + FINDING-013 item 1** (the main work).
  `DieselEngine.converged_mode`: real time, 200 cycles — validated on the
  120-point map: ≤ 0.36% everywhere a steady state exists (95th pct 0.11%).
  One point, `crdi_1p5` 1450/0.5, has no steady state even at real time (VGT
  and EGR integral controllers fight; 21-cycle sawtooth, ±7.5%); unsettled
  cells are period-averaged (all 5 within 0.20%) and flagged `settled = 0`.
  Item 1 (calibrate the limiter under the evaluation's schedules): with
  converged solves the plateau overshoot goes from **+3.0% to within ±0.3%**.
  `CycleResult.converged` no longer claims convergence it never checked.
  Goldens re-baselined for `crdi15` (1800/0.6 torque −10.2%: the old
  calibration's fuel limit was inflated by EGR over-delivery). **Two guards
  became KNOWN — see FINDING-016; a judgement to review.** SolverPort
  round-trip tolerance 1e-8 → 1e-5 (native vs Pyodide now 1.2e-6 here: the
  calibration's warm-started solves amplify platform differences through the
  VGT limit cycle — measured; ADR-001 addendum). `play.py --converged-grid`
  builds a converged grid: `crdi15` 8×6 in **544 s** vs 55 s fast (6
  workers). The dyno page states its own accuracy against converged solves,
  tied to the physics build it was measured on.
- **#23 — e2e in CI** (headless Chrome on the runner; 13/13 there). The e2e
  no longer passes silently without its native reference.
- **#24 — FINDING-014, bug #10 measured**: `render_transient` restarts crank
  phase at 0 every chunk (seam firing intervals off 13% median, 29% max) and
  each cross-fade deletes 20 ms (2.00 s renders as 1.86 s). No fix applied.
- **#25 — FINDING-015, FINDING-005 explained**: the cam film is ~780× too
  thick — pressure-viscosity counted twice (`mu_cam` at 500 MPa *and*
  Hamrock–Dowson's G) — plus two kinematic errors. Fixed, boundary power
  becomes plausible (flat tappet 215 W, roller 28 W) but the 8 nm film floor
  then binds. No fix applied.
- **#22 — FINDING-008 options** for the crank-angle contract (docs).
- **#20** stays a draft: the `steady_ctrl` experiment, kept as a record.

**Then the owner decided four fixes, all the recommended options, now a
stack on #21 (each PR shows only its own commits):**

- **#27 — FINDING-016 fixed**: start of combustion resolved within the crank
  step. Ignition delay at 1° agrees with 0.1° within 0.007° (was up to 1°);
  the two guards are real assertions again, thresholds re-derived from the
  physics; a direct delay guard and a resolution test added.
- **#28 — FINDING-015 items 1 and 3 fixed**: cam film at inlet viscosity, cam
  kinematics on crank speed. Cam boundary power single 5e-7 → 22.6 W, hd_i6
  4e-3 → 29.5 W; 8000 h lash growth ~0 → ~1 µm (modest, no runaway). The
  dead-signal audit's TINY list is now empty. Flat-tappet kinematics, a film
  floor and a wear calibration await a decision (proposal in FINDING-015).
- **#29 — FINDING-014 fixed**: `render_transient` continues crank phase and
  keeps its length (2.000 s for 2.000 s; seams indistinguishable from an
  uninterrupted render). The suite now counts SKIPs separately — it had been
  counting them as passes.
- **#30 — FINDING-008 option D**: `CycleTraces.theta_global`.

**Found on the way:** FINDING-016 — the FINDING-001/002 guards had been
passing on a single 1° jump of the main ignition delay. The real response at
`crdi15` 1800/0.6 is ~0.2° / ~10% premix over 90 K (measured at dθ = 0.1°),
quantised away by the solver's 1° step. *My first reading — "pinned, does not
respond", and a "correction" of REVIEW-001 — was wrong and is corrected in
place; REVIEW-001's "quantised to the crank step" was right.*

---

## Session 4 — the handoff had drifted again

Measured at the start of session 4 against `git log` and `gh pr list`:

- `STATUS.md` on `main` was still the **session-2** version (2026-09-09): "no
  frontend code exists yet", PRs #8–#12 "open". The session-3 rewrite existed
  but sat unmerged in PR #15 — so the failure `CLAUDE.md` warns about happened
  to the very file that fixes it. **Merge the STATUS update in the same session
  that writes it.**
- The session-3 text below already assumed the stack was open; by the time it
  was read, #8–#14 and #16 (`CLAUDE.md`) had all merged.
- The chart-axis fix (next action 2 in session 3) had been written and pushed
  as `fix/dyno-axis-ticks` with **no PR**, and its own commit message said
  `build:pages` and e2e had not been run.
- Sessions 1–3 ran in a Linux dev container; session 4 runs on a local Mac
  (macOS, Python 3.12). Container-specific notes under Housekeeping are marked
  as such rather than deleted.

### What session 4 did

- **PR #15** (this file) rebased onto `main` and brought up to date; CI 4/4
  green. **Merging it needs a human**: Claude Code's permission check blocks
  merging a PR without review. The rule above is therefore "the human merges
  the STATUS PR before the session ends".
- **PR #17 — the dyno axis fix**, verified end to end on the Mac:
  `ng test` 14 passed; `build:pages` builds; e2e **12 passed, 0 failed** in
  real Chrome, with 800 / 2900 / 4600 rpm matching native Python (87.3 /
  223.2 / −25.1 N·m); screenshot shows 250 / 100 tops, round labels, shared
  gridlines, zero aligned.
- **The surviving tie-break mutant was untested code, not dead code.**
  Disabling it changes 48,280 of 437,736 layouts (11%), never lowering either
  curve's fill (7,695 equal, 385 better, 0 worse). New test added; mutation
  3 of 5 caught against a passing baseline. The two survivors both reduce to
  "most intervals wins a tie", which chose identically to "nearest five" on
  every input — equivalent over the measured range, recorded as such, not as
  caught.
- **PR #18 — `web/app` in CI**, stacked on #17: `ng test` + `build:pages`.
  Dry-run in a fresh clone; a broken spec and a type error each exit 1.
  E2e is not in CI yet.
- **Found:** `web/app` does not build unless `web/solver` has had `npm ci`
  (it compiles `../solver/src` and needs the `pyodide` types) — TS2307
  otherwise. Undocumented until now; the CI job does both.
- **FINDING-013** (PR #19), from re-measuring bug #3 — see the Findings table.
  The largest item is not the limiter: `crdi15` at 1650 rpm full-load fuel
  oscillates 211.6–237.9 N·m from 6 to 40 cycles and never converges, so
  "use `n_cycles >= 9`" does not hold everywhere.
- **Found:** `NATIVE_REF` for the e2e check was undocumented, and without it
  the check compares nothing against native Python and still passes (9
  checks, not 11–12). How to produce it is under Tests below.

---

