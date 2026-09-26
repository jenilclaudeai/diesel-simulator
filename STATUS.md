# Status

**Updated:** 2026-09-26 (session 5: "complete Phases 1 and 2")
**Phase:** 1 and 2 **exit-ready** (REVIEW-003, REVIEW-004). Waiting on two things:
the owner merging the stack, and one decision (FINDING-018's fix option).
After that, Phase 3.
**Main:** everything through PR #39 is merged. Open, **one stack, merge in
order**, retargeting each child to `main` after its parent merges
(`gh pr edit <n> --base main`):

| PR | branch | what | needs |
|---|---|---|---|
| #40 | `fix/egr-start` | EGR valve starts at 0.14 × command (FINDING-013 item 2) | review |
| #41 | `fix/turbo-reset` | `warm_start=False` isolates a solve (bug #5) | review |
| #42 | `fix/cam-profile` | cam lift no longer steps 4× at the ramp junctions (FINDING-018), option C′ | **decision: confirm C′** (A/B/C measured in the finding) |
| #43 | `fix/seat-ramp` | valves seat at ramp speed when the lash is inside the ramp | review |
| #44 | `feat/pmax-texh-limits` | p_max and T_exh limits in the fuel limiter (bug #2) | review |
| #45 | `fix/aged-torque` | `durability_run` at 9 cycles; the aged-engine torque gain explained (FINDING-019) | review |
| #46 | `docs/phase1-exit` | Phase 1 exit: regression-test gaps closed, validation re-checked, goldens at 1e-5 (REVIEW-003) | review |
| #47 | `feat/golden-fixtures` | golden-fixture harness and first TypeScript ports (ADR-004) | review |
| #48 | `feat/browser-grid-e2e` | `/grid` page; a full grid built in Chrome matches native, cell for cell | review |
| #49 | `docs/phase2-exit` | accuracy table regenerated on the final tree; REVIEW-004; this file | review |

Read this first in a new session, then `PLAN.md`, then `DECISIONS.md`, then
`reviews/`. Those replace pasting a context document. `CLAUDE.md` says the same
for Claude Code sessions.

---

## Session 5 (2026-09-26) — Phases 1 and 2 completed

The owner asked for Phases 1 and 2 to be finished. Eight decisions were taken
up front, and all went with the recommended option: EGR starts from a target
estimate; add p_max + T_exh limits; fix the economy *claim*; seat at ramp
speed; reset the turbo too; move the by-ear audio sign-off to Phase 4;
leave the limit cycle for Phase 3; fix clear bugs.

**Phase 1 (#40–#46, REVIEW-003):**
- **EGR start (#40).** Delivered-EGR error vs converged 7.75 → 3.07 points;
  torque RMS 17.6% → 13.5%. One point got worse: `crdi15` 4000/0.25,
  −1% → −39%. That is the unconverged VGT loop, which the old over-open
  valve was masking (Phase 3).
- **Bug #5 (#41).** A cold solve after any history is bit-identical to a
  fresh engine.
- **FINDING-018 (#42), new.** Cam lift stepped 4× where the ramps meet the
  flank, 2.0 mm on `hd_i6`, since the first commit. Option C′ keeps breathing
  (≤ 0.1%) and the ramp heights, and doubles ramp speed (tick +6 dB). **Owner
  to confirm.**
- **Seating (#43).** `hd_i6` tick went from 75.7× to 13.0× its other
  mechanical sources. It stays dominant because its ramp is steep (Phase 4).
- **Limits (#44).** 100 of 100 points bit-identical with limits on vs off;
  they bind when set low. Cost: one extra solve per speed. A fuel-only p_max
  limit is severe, so it is set not to bind.
- **FINDING-019 (#45).** The aged-engine torque gain is turbo fouling acting
  through the limiter's unconverged calibration. Converged it is −0.08%, so
  there is no wear bug. `durability_run` solved at 6 cycles; now 9.
- **Exit (#46).**
  - Every fixed bug has a test (four gaps closed, mutation-tested). Bug #6,
    in `play.py`'s terminal loop, is carried to Phase 3.
  - Validation table: 12 of 12 rows in band. The 12,000 h paragraph did
    **not** hold and is corrected in place.
  - Goldens tightened 0.5% → 1e-5: PR #37 had moved one −0.09% unrecorded
    (my miss).
  - The "two fitted scalars" claim is corrected in place.

**Phase 2 (#47–#49, REVIEW-004):**
- **Golden fixtures (#47).** `tools/fixtures/gen_fixtures.py` plus the
  `web/physics` ports (kinematics 3.6e-14, thermo 4.0e-16). `--check` fails
  on stale fixtures. Finite differences are compared at their stencil's
  rounding bound (a new ADR-004 rule), and REVIEW-001 M-1 is resolved.
- **Browser grid (#48).** A full grid built in Chrome matches native in 816
  of 816 values, worst 8.7e-7. The second build comes from the cache in
  0.05 s. The build takes 487 s.
- **Accuracy table (#49).** Regenerated on the final physics build.

**Mistakes of mine this session, corrected where they happened:**
- Contaminated pool workers in the EGR comparison. Rerun; noted in
  FINDING-013.
- An option-C prototype with `min` for `max`. Caught by its own continuity
  output.
- Uncomputed ramp speeds and wrong PR numbers in draft docs. Fixed before
  commit.
- VE referenced to the wrong density in the validation tool.
- A comparator that let NaN be overwritten. Caught by its own self-test.
- A unit test that needed a generated file. Red in CI; fixed in #48.
- The dyno e2e timed out on CI after #44 made pulls longer. Fixed in #44 and
  merged up the stack.

**Owner, please:**
1. Confirm FINDING-018's option C′, or pick A, B or C, before #42 merges.
2. Merge #40 → #49 in order.
3. Listen when Phase 4 comes. That is now its exit criterion.

---

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

## Phase 2 — state

**ADR-001 is validated by measurement.** The unmodified solver runs under
Pyodide 314.0.7 (Python 3.14.2, numpy 2.4.6); the full regression suite passes
there, identical to native. Single-point results agree with native CPython to
~1e-10 relative. Warm, ~1.7× slower than native; ~3.4× on a fresh worker's
first solve. `scipy` is never imported.

**The grid builds under Pyodide too.** The grid cell lives in
`dieselsim/grid.py`, shared by native and browser; a cell built under Pyodide
matches native to 4.8e-10 (performance) and 99.81% bit-identical float32
sources. Phase 2's exit criterion is met at cell level — not yet at full-grid
level in a real browser. *(Session 5: now met at full-grid level in real
Chrome, 816 of 816 values within 8.7e-7, and checked in CI; #48, REVIEW-004.)*

**The SolverPort exists** (`web/solver/`, ADR-010, Accepted). Main-thread
client → real worker loop → Pyodide → unmodified dieselsim. Typed errors,
cancellation per grid cell.

**Grids are cached** (REVIEW-001 M-2, M-3 closed). Keyed on engine + a
fingerprint of the physics sources; a hit never boots Pyodide (0.4 ms vs 8.8 s).

**The first web page exists** (`web/app/`, Angular 22.1.7, zoneless, signals,
OnPush). A dyno pull: pick an engine, torque and power draw in as each point is
solved by Python in a worker. Build with `npm run build:pages` — a plain
`build` renders a blank page on GitHub Pages. 11 e2e browser checks.

**CI runs** (`.github/workflows/ci.yml`: native Python 3.10 + 3.12, the suite
under Pyodide, the SolverPort end to end) on every PR, including stacked ones.
The handoff believed it had never run; PR mergeable states show it had: #13
`clean`, #14 `unstable`. #14 was failing — see *Session 3* below.
**`web/app` is not in CI**: neither `build:pages` nor the e2e checks.
*(Since fixed: #18 and #23 added them, and session 5 added the fixtures
and full-grid jobs.)*

### Session 3 — PR #14 was red, and CI had said so

#14 made `RuntimeInfo.preset_info` required but did not update the
`FakeSolver` in `web/solver/test/cache.test.ts`, so `tsc` failed before any
test ran (`TS2741`). The parent branch passes 20/20. CI caught it; nobody could
read the result with the token in use. Fixed, and `preset_info` — which the
dyno page uses to label engines and choose its rpm sweep — now has a native
test that cross-checks displacement against bore and stroke and each rpm field
against the spec. Mutation-tested: 4 of 4 applied mutants caught (an initial
version let `rated_rpm = max_rpm` through; tightened).

## Where things stand

Architecture is decided (ADR-001 to ADR-010, with ADR-006 on hold). The Python
physics has been through a review pass that produced twelve findings, nine
fixes, a regression suite and a standing audit tool.

### The pattern that came out of it

Five of the first six findings share one shape: **a mechanism fully built, correctly
wired, and fed a quantity that is effectively zero or pinned against a clamp.
None raised an error.**

- `premix_fraction` sat on its 0.02 floor (FINDING-001)
- `sharp` sat on its 3.0 ceiling (FINDING-003)
- every acoustic amplitude was normalised away (FINDING-004)
- the roller-follower branch never accumulated boundary friction (FINDING-005)
- `h_min_ring` was always its 12 nm clamp (FINDING-006)

`tools/audit_dead_signals.py` exists to catch the sixth. **Run it after any
physics change, and port it alongside the solver** — the same failure in
TypeScript would be far harder to find, and Phase 3 ports the whole real-time
loop.

Latest audit: 102 scalars over 8 operating points — **0 dead, 2 frozen
(`fric.h_ring` and `op.h_ring_tdc`: one 12 nm clamp exposed twice), 1 tiny
(`Pb_valvetrain`)**. *(Session 4: this line said "1 frozen (the
now-honestly-named `h_ring_tdc`)"; the audit on unmodified `main` reports 2 —
a miscount, not a change.)*

---

## Findings

| # | Issue | Status |
|---|---|---|
| 001 | `premix_fraction` pinned; Watson correlation out of domain at modern common-rail delays | P-1 and P-2 fixed |
| 002 | `dp/dθ` peaks 10° *before* ignition, so it measures compression; clatter was driven by it | fixed |
| 003 | clatter high-mode weight pinned at its ceiling; divisor 3 orders of magnitude out | fixed |
| 004 | every physical amplitude discarded by two normalisation stages | fixed |
| 005 | roller-follower branch never accumulated `Pb_vt`; cam wear structurally impossible | fixed, **but insufficient** — the rest explained by FINDING-015 |
| 006 | `h_min_ring` always its clamp, and exposed as a headline field | fixed |
| 007 | bug #8 audit; `fuel_for_torque` returned 8.7% different fuel depending on cache warmth | fixed |
| 008 | `theta` indexes two references — per-cylinder local vs global engine angle | **fixed (option D, #30)**: `CycleTraces.theta_global`. *(Was: "documented; roll sign fixed".)* |
| 009 | bug #4 overstated — light-load gap is ~29%, not 2× | measured; no fix needed |
| 010 | bug #2 overstated — the loop converges; real gap is missing p_max/T_exh limits | **limits added (#44)** |
| 011 | the real-time grid was the least accurate part — worst −10.06% | **fixed** — per-cell fresh engines at `n_cycles=9`; now exact vs reference |
| 012 | `transient()` floor sat inside the solver's NaN region and could not catch NaN | **fixed** — stall detection; root cause as first recorded was wrong |
| 013 | bug #3 understated: limiter fitted with EGR on, judged with it off; EGR valve opens 25% for any command; `crdi15` never converges at 1650 rpm | item 1 fixed (#21); **item 2 fixed (#40)**; item 3 **deferred to Phase 3** (caveat online) |
| 014 | `render_transient`: crank phase restarts every chunk; each cross-fade deletes 20 ms (bug #10) | **fixed (#29)**. *(Was: "measured, not fixed — PR #24".)* |
| 015 | cam film ~780× too thick (pressure-viscosity counted twice) + two kinematic errors — why cam wear is negligible | **fixed (#28, #35); wear calibrated (#38)**. *(Was: "measured, not fixed — PR #25".)* |
| 016 | FINDING-001/002 guards rode a 1° ignition-delay step; the real response (~0.2° over 90 K) is quantised by the 1° crank step | **fixed** — PR #27 (ignition resolved within the step) |
| 017 | slap and tick normalised away in the mechanical sub-mix; mechanical-lash presets seat valves off the closing ramp | **fixed (#34, #37, #43)**; by-ear sign-off in Phase 4 |
| 018 | cam lift stepped 4× where the ramps meet the flank (2.0 mm on `hd_i6`), since the first commit | **fixed with option C′ (#42) — owner to confirm** |
| 019 | the aged `crdi15`'s torque gain | a fast-path artifact, not a wear bug; `durability_run` moved to 9 cycles (#45) |

### Still open inside those

- **FINDING-005 is not closed.** `Pb_valvetrain` is now nonzero but runs 1e-5
  to 1e-8 of total. The flat-tappet case is *lowest* at 3.9e-7 W — the case
  that should wear most. Cam wear is still negligible and lash still does not
  grow at 8000 h. Suspects: `sigma_cam`, or entrainment velocity at nose
  reversal. Untested. *(Session 4: measured — neither suspect is the main
  cause; the cam film is ~780× too thick. FINDING-015, PR #25.)*
- **FINDING-004 has not been listened to.** Every judgement was band ratios and
  RMS. It changes the character of every rendered sound. Four WAVs were
  produced for A/B; the warm-vs-cold pair at load 0.6 is the one that matters.

---

## Known bugs — status

| # | Issue | Status |
|---|---|---|
| 1 | `n_cycles=6` not converged | **measured 10.8% drift**, worse than documented; test added |
| 2 | Fuelling open-loop on rpm | **measured — loop converges, no instability.** Real gap was missing p_max/T_exh limits: **added (#44)**. FINDING-010 |
| 3 | Torque limiter ±3% | **re-measured in session 4 — understated.** At n=9: `crdi15` −4.3…+6.8%, `crdi_1p5` −0.9…+5.5%. Not only "a symptom of #1": a systematic EGR-schedule bias. FINDING-013. *(Was: "partly addressed by the FINDING-007 cache fix; re-measure".)* |
| 4 | Light-load fuel understated ~2× | **measured — does not reproduce at 2×; real gap ~29%.** FINDING-009. **Closed as a claim fix:** the economy is a steady-state figure, and pages must say so (PLAN Phases 5/6) |
| 5 | `operating_point` path-dependent | **fixed (#41)**: `warm_start=False` resets the turbo and the limiter's calibration starts cold; bit-identical to a fresh engine. *(Was: "root cause found — the API itself still leaks".)* |
| 6 | `l` key dead in DCT | **fixed** — now reports why instead of silently no-opping |
| 7 | No cold-temperature combustion | root-caused through FINDINGs 001–004 |
| 8 | Unknown-provenance code in `engine.py` | **closed** — FINDING-007; found a real cache bug |
| 9 | Worn-vs-new audio pair suspect | root-caused — FINDING-004 and 005 |
| 10 | `render_transient` seams | **measured (session 4)** — FINDING-014, PR #24: phase resets every chunk, and each cross-fade deletes 20 ms. *(Was: "still unmeasured — blocked by FINDING-012".)* |
| 11 | Coast downshift calibration | **fixed in Phase 3** — root cause was the lock-up clutch's numerical instability (FINDING-020); coast downshifts also stretch both phases. *(Was: "deferred to Phase 3".)* |
| 12 | Grade small-angle form | **already correct** — `atan`/`sin`/`cos` all present; entry was stale |

---

## Also found, not yet actioned

*(Session 5: all three items below are done. FINDING-008 is fixed with
`theta_global` (#30); ADR-006 is superseded by ADR-011; the fitted-scalars
claim is corrected in PROJECT_CONTEXT §1.3 (#46). Kept as history.)*

- **Trace arrays index two crank-angle references** — diagnosed as FINDING-008
  (per-cylinder local vs global engine angle). The fix is an API-contract
  decision. **Resolve before the Angular cycle page consumes traces.** Options
  written up in PR #22 (recommended: keep storage, add a per-cylinder
  `theta_global` axis, plus a firing-order guard test).
- **ADR-006 is on hold** and should be reassessed now that FINDINGs 001–004
  have changed the numbers it was decided on.
- **`SPL_CAL` and the 5.0e9 clatter divisor are chosen constants.** The package
  advertises exactly two fitted scalars (`NOX_CAL`, `SOOT_CAL`). That claim is
  no longer accurate; either derive the constants or update the claim.

---

## Tests

```
python3 tests/test_physics.py                    # top of the stack: 51 passed, 0 failed, 2 known with scipy; 47 + 3 skipped without
python3 tools/audit_dead_signals.py              # 0 dead, 2 frozen (the h_ring clamp, known), 0 tiny
python3 tools/validate_table.py [--aged]         # PROJECT_CONTEXT §1.5 re-check: 12 of 12 in band
python3 tools/fixtures/gen_fixtures.py --check   # golden fixtures current (regenerate without --check)
cd web/physics && npm ci && npm test             # TypeScript ports vs fixtures: 5 checks
cd tools/pyodide && npm ci && npm run suite      # the same physics suite under Pyodide
cd web/solver && npm ci && npm test              # 20 cache tests + 18 round-trip checks through a real worker
cd web/app && npm test -- --watch=false          # 22 unit tests (vitest)
cd web/app && npm run build:pages                # never plain `build`
cd web/app && CHROME_PATH=... npm run e2e        # dyno pull in Chrome vs native (computes its own reference)
cd web/app && CHROME_PATH=... npm run e2e:grid   # full 8 x 6 grid in Chrome vs native, cell for cell (~9 min)
```

On macOS, `CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"`.
Golden points are locked at **1e-5** (was 0.5% until session 5; REVIEW-003 m-1),
stored to 9 significant figures, with every re-baseline explained inline.
Known defects report as KNOWN, not FAIL. When one is fixed the suite reports
UNEXPECTED PASS, which is the signal to promote it to a real assertion.
Mutation runs: always `PYTHONDONTWRITEBYTECODE=1`, and a reused pool worker
keeps module-level changes (session 5's EGR slip), so set constants per job.

---

## Branches

The open stack is in the table at the top of this file. Merged branches are
**not** auto-deleted: after merging a parent, retarget its child PR to `main`
(`gh pr edit <n> --base main`). Session 4's branch table is in git history.

---

## Next actions

1. **Owner:** confirm FINDING-018's option C′ (or choose A/B/C), then merge
   #40 → #49 in order. If a different option is chosen:
   - regenerate the fixtures (`gen_fixtures.py`);
   - re-baseline the goldens and `NATIVE_TORQUE` in that PR;
   - re-run the accuracy pull;
   - check #43 (it builds on C′'s ramp speed).
2. **Phase 3 — the real-time loop in TypeScript.** It opens with these
   carried items:
   - FINDING-013 item 3: the fast path doesn't converge at part load
     (13.5% RMS, worst −39%) and has the `crdi15` limit cycle;
   - bug #11 (coast downshift);
   - a test for bug #6's key once `play.py`'s loop is ported;
   - ADR-011 step 2: port `FrictionModel.evaluate` against
     `web/physics/fixtures/friction.json`;
   - the manual gearbox's clutch;
   - integrator ports with ADR-004's per-step and terminal bounds.
3. **Enjoy mode's roster** (OPEN-F) and its prebuilt grids
   (`--converged-grid`). A browser build takes about 8 minutes (REVIEW-004 m-1).
4. **Phase 4:** the owner's by-ear sign-off, which is now its exit criterion.
   Also `hd_i6`'s tick dominance (13×) and a ramp-height parameter separate
   from `ramp_fraction`.
5. Follow-ups:
   - Row-share the p_max / T_exh check in fast grids. This recovers its cost
     but moves grid numbers.
   - A timing-based p_max limiter, if a preset ever binds.
   - Label durability's `health` as "life used".

---

## Housekeeping

- **The PAT has been pasted into chat in every session. Revoke it** and issue
  a fresh fine-grained token; keep it out of any handoff document. Give the
  next one **Checks: read** (and Actions: read) so CI results are visible.
- **Node on the Mac used from session 4:** `node` on PATH is Homebrew
  `node@20` (20.19.0) and Homebrew `node` is 24.2.0 — both below Angular 22's
  minimum (22.22.3 / 24.15.0), and the CLI refuses to start. Session 4 used a
  checksum-verified portable Node 22.23.3 in
  `~/.cache/dieselsim/node-v22.23.3-darwin-arm64/` (prepend its `bin` to PATH).
  System Node was left untouched; upgrading it is the owner's call.
- **scipy on the Mac:** not installed in the system Python, though
  `requirements.txt` lists it and `acoustics.py` renders with it. Session 4
  used an isolated venv, `~/.cache/dieselsim/venv` (numpy 2.1.0, scipy 1.18.1).
- **Git worktrees + Angular:** building `web/app` from a worktree creates an
  empty `.angular/cache/<version>` at the *main* checkout's root. Harmless;
  delete it (session 4 did, three times).
- **Mutation testing in Python: set `PYTHONDONTWRITEBYTECODE=1`.** Bytecode
  is validated by source mtime (seconds) and size; a same-length edit within a
  second otherwise runs stale code.
- **Waiting on a background job with `pgrep -f "<script>"`** matches the
  waiting shell's own command line and never ends — session 4 lost two loops
  to it. Match on something the waiter does not contain, or wait on the PID.
- **macOS `multiprocessing` spawns fresh interpreters:** a pool in a script
  piped on stdin respawns workers forever (they cannot re-import `<stdin>`).
  Put pool code in a file.
- **Dev-container notes (sessions 1–3; not re-measured on the Mac used from
  session 4).** The next two bullets were measured in that container.
- **Background jobs in the dev container must be detached with
  `setsid nohup … < /dev/null &`.** Plain `nohup … &` is killed when the tool
  call returns — measured in session 3 (a 30 s sleep did not survive; the
  `setsid` twin did). Earlier sessions' advice to use plain `nohup` is wrong.
- Solve time in the dev container is ~6.5 s against 1.47 s on developer
  hardware, one core. **Do not benchmark Pyodide here**, and never run two
  heavy jobs at once.
- The solver needs **numpy only**; `scipy.signal` is confined to `acoustics.py`
  and `play.py`. A test enforces this.
- `batch.py` imports `multiprocessing`, which does not exist in Pyodide.
- **Tool-call budget** *(hit in chat sessions 1–3; not yet observed in Claude Code)*. Chat caps tool calls per turn (the "reached its
  tool-use limit" banner); session 3 hit it by spending ~40 calls, many on
  polling. Rules: one call per long job — start it, wait, report in the same
  call, never separate sleep-and-check calls; batch related reads and checks
  into one script; test + commit + push in one call; aim for ~15 calls a
  turn, commit before nearing the cap, and end each turn with a written
  status so a cut-off lands between steps, not mid-step.
- Working style: measure before fixing; ask rather than assume; options come
  with trade-offs and positives; warn before context budget limits.
