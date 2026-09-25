# Status

**Updated:** 2026-09-25 (session 4, part 2 — an autonomous stretch; see below)
**Phase:** 2 — mostly done. Python runs in the browser, the SolverPort exists,
grids are cached, CI runs, and the first web page (a dyno pull) works end to end.
**Main:** everything through PR #35 is merged; CI on `main` is green (6 of 6,
run 36186508876). #20 was closed (its record is FINDING-013; branch kept).
Open, a stack: **#36** (accuracy table for `6912cc7545ef`; STATUS) → **#37**
(closing ramps clear the lash, FINDING-017 item 2) → **#38** (cam wear
calibrated to the owner's 2000 h / 150 µm service interval) → **#39**
(ADR-011 step 1: cells carry the pressure trace; `cell_friction`). Merge in
that order, retargeting each child to `main` after its parent merges.

Read this first in a new session, then `PLAN.md`, then `DECISIONS.md`, then
`reviews/`. Those replace pasting a context document. `CLAUDE.md` says the same
for Claude Code sessions.

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
level in a real browser.

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
| 008 | `theta` indexes two references — per-cylinder local vs global engine angle | documented; roll sign fixed |
| 009 | bug #4 overstated — light-load gap is ~29%, not 2× | measured; no fix needed |
| 010 | bug #2 overstated — the loop converges; real gap is missing p_max/T_exh limits | measured |
| 011 | the real-time grid was the least accurate part — worst −10.06% | **fixed** — per-cell fresh engines at `n_cycles=9`; now exact vs reference |
| 012 | `transient()` floor sat inside the solver's NaN region and could not catch NaN | **fixed** — stall detection; root cause as first recorded was wrong |
| 013 | bug #3 understated: limiter fitted with EGR on, judged with it off; EGR valve opens 25% for any command; `crdi15` never converges at 1650 rpm | item 1 fixed and converged offline solves — **PR #21**; fast path stays unconverged (caveat online); item 2 open |
| 014 | `render_transient`: crank phase restarts every chunk; each cross-fade deletes 20 ms (bug #10) | **measured, not fixed** — PR #24 |
| 015 | cam film ~780× too thick (pressure-viscosity counted twice) + two kinematic errors — why cam wear is negligible | **measured, not fixed** — PR #25 |
| 016 | FINDING-001/002 guards rode a 1° ignition-delay step; the real response (~0.2° over 90 K) is quantised by the 1° crank step | **fixed** — PR #27 (ignition resolved within the step) |
| 017 | slap and tick normalised away in the mechanical sub-mix; mechanical-lash presets seat valves off the closing ramp | **measured, not fixed** — PR #31 |

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
| 2 | Fuelling open-loop on rpm | **measured — loop converges, no instability.** Real gap is missing p_max/T_exh limits. FINDING-010 |
| 3 | Torque limiter ±3% | **re-measured in session 4 — understated.** At n=9: `crdi15` −4.3…+6.8%, `crdi_1p5` −0.9…+5.5%. Not only "a symptom of #1": a systematic EGR-schedule bias. FINDING-013. *(Was: "partly addressed by the FINDING-007 cache fix; re-measure".)* |
| 4 | Light-load fuel understated ~2× | **measured — does not reproduce at 2×; real gap ~29%.** FINDING-009 |
| 5 | `operating_point` path-dependent | **root cause found** — `Turbocharger` keeps `n_rpm`/`vgt_pos` across calls; `warm_start=False` does not reset it. Grid now immune (FINDING-011); the API itself still leaks |
| 6 | `l` key dead in DCT | **fixed** — now reports why instead of silently no-opping |
| 7 | No cold-temperature combustion | root-caused through FINDINGs 001–004 |
| 8 | Unknown-provenance code in `engine.py` | **closed** — FINDING-007; found a real cache bug |
| 9 | Worn-vs-new audio pair suspect | root-caused — FINDING-004 and 005 |
| 10 | `render_transient` seams | **measured (session 4)** — FINDING-014, PR #24: phase resets every chunk, and each cross-fade deletes 20 ms. *(Was: "still unmeasured — blocked by FINDING-012".)* |
| 11 | Coast downshift calibration | deferred |
| 12 | Grade small-angle form | **already correct** — `atan`/`sin`/`cos` all present; entry was stale |

---

## Also found, not yet actioned

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
python3 tests/test_physics.py                    # main: 18/0/2 known; top of the stack (#30): 29 passed, 0 failed, 2 known with scipy; 28 + 1 skipped without
python3 tools/audit_dead_signals.py              # diagnostic; main: 0 dead, 2 frozen (one clamp), 1 tiny; top of the stack: 0 tiny
cd tools/pyodide && npm ci && npm run suite      # the same suite under Pyodide
cd web/solver && npm ci && npm run test:fast     # 20 cache tests, seconds
cd web/solver && npm test                        # + the round trip through a real worker
cd web/solver && npm ci                          # BEFORE any web/app build: the app compiles ../solver/src
cd web/app && npm test -- --watch=false          # 14 unit tests (vitest), once #17 is merged
cd web/app && npm run build:pages                # never plain `build`
cd web/app && NATIVE_REF='...' CHROME_PATH=... npm run e2e   # 12 browser checks with 3 reference points
```

*(With PR #23: `NATIVE_REF` is optional — the e2e computes it with
`web/app/e2e/native_ref.py`, and fails if it cannot get one. The paragraph
below describes `main` before #23.)*

**e2e needs `NATIVE_REF`** or it silently skips the native comparison and
passes on the other 9 checks. It is `{"<rpm>": torque}` for points on the page's
default `crdi15` full-load pull, computed natively the way the page does it (a
fresh engine per point, `load=1`, `n_cycles=9`):

```bash
python3 -c 'import json; from dieselsim import bridge as b
print(json.dumps({r: json.loads(b.solve_point(json.dumps({"engine": {"preset": "crdi15"}, "rpm": r, "load": 1})))["torque"] for r in (800, 2900, 4600)}))'
```

Session 4 values: `{"800": 87.2755, "2900": 223.2136, "4600": -25.1289}`. The
rpms must be on the page's sweep (idle to max in 10 steps, rounded to 50) or a
check fails as "no row". On macOS, `CHROME_PATH="/Applications/Google
Chrome.app/Contents/MacOS/Google Chrome"`.

Golden points are locked at 0.5%. They were re-baselined after FINDING-001 P-2
with the justification recorded inline — torque and BSFC moved under 1%, p_max
rose ~3%, and `hd_i6` still reproduces the documented 2310 N·m and stays inside
the 160–200 bar band.

Known defects report as KNOWN, not FAIL. When one is fixed the suite reports
UNEXPECTED PASS, which is the signal to promote it to a real assertion.

---

## Branches

Merged in session 4: #15 (this file), #17 (dyno axes), #18 (`web/app` in CI),
#19 (FINDING-013). Merged branches are **not** auto-deleted: after merging a
parent, retarget its child PR to `main` (`gh pr edit <n> --base main`).

| PR | branch | contents | needs |
|---|---|---|---|
| #27 | `fix/ignition-substep` | FINDING-016 fix — **stacked on #21** | review |
| #28 | `fix/cam-film` | FINDING-015 items 1, 3 — **stacked on #27**; includes #25's commit | review |
| #29 | `fix/render-seams` | FINDING-014 fix — **stacked on #28**; includes #24's commit | review |
| #30 | `feat/theta-global` | FINDING-008 D — **stacked on #29**; includes #22's commit | review; carries the regenerated dyno accuracy table |
| #21 | `fix/converged-solves` | converged offline solves, item 1, honest `converged`, re-baselined goldens, FINDING-016, `--converged-grid`, dyno accuracy note | ready for review, CI 5/5 green — **three judgements listed in its description**; moves `crdi15` numbers |
| #23 | `ci/e2e` | e2e in headless Chrome in CI; e2e fails without its reference | review; independent |
| #22 | `docs/finding-008-options` | FINDING-008 options | **decision** (contract) |
| #24 | `diag/bug-10-render-seams` | FINDING-014 + tool | **decision** (fix option) |
| #25 | `diag/finding-005-cam` | FINDING-015 + tool | **decision** (fix option, wear calibration) |
| #20 | `fix/steady-state-controllers` | `steady_ctrl` experiment, off by default | nothing — a record; close or keep |

**Merge order:** #21 → #27 → #28 → #29 → #30, retargeting each child to `main`
after its parent merges (`gh pr edit <n> --base main`). #22, #24 and #25 are
docs whose commits are also inside #30/#29/#28: merge them first (the stacked
copies then add nothing) or close them as superseded. #23 and #26 are
independent.

Earlier note, for #21–#26 alone: all are independent of each other and target `main`; any order works. #21
before #23 is slightly tidier (the e2e reference then reflects item 1 from its
first run), but both run the same physics on both sides.

Merged earlier: #5 `physics/verified-fixes`, #6 `audio/physical-levels`
(**not yet listened to** — revert that merge if the mix is wrong), #7 the
bug-8 audit, #8–#14 the Phase 2 stack, #16 `CLAUDE.md`.

---

## Next actions

1. **Listen** to the pairs in `out/listen/` (sent to the owner) — pair 1 first.
2. **Merge the stack** #36 → #37 → #38 → #39 (retarget each child to `main` after its parent).
3. **After listening, decide the remaining tick question**: the on-ramp lash
   penalty in `seating_velocity()` and the `_ref_vseat` level (`hd_i6` tick
   still 13× its other sources).
4. **Look at the aged-engine torque**: `crdi15` +3.6% after 2000 h (not the
   cam) — the other wear mechanisms, bug #9's territory.
5. **ADR-011 step 2** — port `FrictionModel.evaluate` to TypeScript with
   ADR-004 fixtures from `cell_friction` (Phase 3).
6. **FINDING-013 item 2** — the EGR valve's 25% start (fast path only now) and
   the VGT–EGR limit cycle at `crdi_1p5` 1450/0.5 (controller tuning).
7. **Enjoy mode's roster** (OPEN-F), then its grids with `--converged-grid`.
8. Then **Phase 3** — the real-time loop in TypeScript; manual gearbox needs a
   clutch model; the AudioWorklet must carry crank phase across source swaps
   (FINDING-014).

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
