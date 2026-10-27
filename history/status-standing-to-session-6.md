# STATUS history: The standing sections kept up to session 6: Phase 2's state, where things stood, findings, bugs, tests, branches, next actions (2026-09-28 to 2026-10-05)

Moved verbatim from `STATUS.md` at `a57a6fd`, its lines 3459-3772, by step A1 of
`reviews/PROPOSAL-modularize.md` (2026-10-28). **This is history, not the present**:
`STATUS.md` is. Struck-through text and in-place corrections are as they were written.
`python3 tools/check_verbatim_move.py history/` proves the copy.

<!-- verbatim: STATUS.md@a57a6fd 3459-3772 -->
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
| 018 | cam lift stepped 4× where the ramps meet the flank (2.0 mm on `hd_i6`), since the first commit | **fixed with option C′ (#42), confirmed by the owner (session 5, part 2)**. *(Was: "owner to confirm", left stale in this table after the confirmation.)* |
| 019 | the aged `crdi15`'s torque gain | a fast-path artifact, not a wear bug; `durability_run` moved to 9 cycles (#45) |
| 020 | the converter's lock-up clutch was numerically unstable, pinned at its clamp (bug #11's jolts) | **fixed (#54)** |
| 021 | `play.py`'s real-time sound was a stale copy; slap, exhaust flow and seating moved it 0.0000% | **fixed (#59)** |
| 022 | intake loudness and turbo boost term normalised away in `render()`, so also in the synth | **fixed with option A (#64)**. *(Was: "open: known defect, the owner's call with the listening review".)* |
| 023 | the synth's slap input (skirt film) sits on its clamp in 240/240 cold cells, 115/240 warm | **fixed with option A (#78)**, with the ramp-height parameter in the same rebuild. *(Was, stale after #78 merged until 2026-10-05:)* open, option A chosen (2026-09-30). *(Before that:)* known defect; the owner chose to do it after 022, in its own rebuild |
| 024 | MFB50 counted combustion before TDC last: late by up to 7° (`single`, 41% of heat before TDC) | **fixed** (`fix/mfb50`); a reported figure only; the 10 grids re-stamped with proof (dee93a17 → a442cfb3) |

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
python3 tests/test_physics.py                    # #84: 71 passed, 0 failed, 3 known with scipy; 66 + 4 skipped without
python3 tools/audit_dead_signals.py              # 0 dead, 2 frozen (the h_ring clamp, known), 0 tiny
python3 tools/validate_table.py [--aged]         # PROJECT_CONTEXT §1.5 re-check: 12 of 12 in band
python3 tools/fixtures/gen_fixtures.py --check   # golden fixtures current (regenerate without --check)
cd web/physics && npm ci && npm test             # TypeScript ports vs fixtures: 5 checks
cd tools/pyodide && npm ci && npm run suite      # the same physics suite under Pyodide
cd web/solver && npm ci && npm test              # 20 cache + 8 live-grid scheduler + 22 round-trip checks through a real worker
cd web/solver && npm run test:live-real          # manual, ~7 min: a 2x2 drivable grid built by 2 Pyodide workers vs the native tool's (see the file's header)
cd web/app && npm test -- --watch=false          # 54 unit tests (vitest)
cd web/app && npm run build:pages                # never plain `build`
cd web/app && CHROME_PATH=... npm run e2e        # dyno pull in Chrome vs native (computes its own reference)
cd web/app && CHROME_PATH=... npm run e2e:grid   # full 8 x 6 grid in Chrome vs native, cell for cell (~9 min)
cd web/app && CHROME_PATH=... npm run e2e:drive  # /drive: prebuilt grid, 60 Hz, 60 s script vs native Python
cd web/physics && npm test                       # 62 checks: fixture ports, 7 live drives, the synth, 10 vehicles + their keys
cd web/app && CHROME_PATH=... npm run e2e:enjoy  # /enjoy: multi-touch on an emulated landscape Pixel, 19 checks
cd web/app && CHROME_PATH=... npm run e2e:custom # a custom engine built, stopped, resumed, saved and driven (CI: own job)
cd web/app && CHROME_PATH=... npm run e2e:sound  # /drive with sound: worklet output, firing harmonics, pitch, mics
python3 tools/fixtures/gen_fixtures.py --only live   # regenerate live drives after a live.py change (~4 min)
python3 tools/build_live_grids.py                # rebuild the prebuilt converged grids after a SOLVER change (~57 min)
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

Merged branches are **not** auto-deleted: after merging a parent, retarget
its child PR to `main` (`gh pr edit <n> --base main`), or merge top-down.

Checked on 2026-09-28 by content, not commit ancestry. The question asked
of each branch: "does merging it into the roll-up change the tree?"
- **24 branches:** contained, so safe to delete once #65 is on `main`.
- **3 closed-PR docs branches**
  (`diag/bug-10-render-seams`, `diag/finding-005-cam`,
  `docs/finding-008-options`): superseded. Every line is in `main`'s later
  copies, except one pre-fix line in a diag script.
- **`fix/steady-state-controllers`** (closed PR #20): the abandoned
  FINDING-013 option A experiment, 558 lines (`steady_ctrl`), in nothing
  else. It is the only record of that attempt: keep it, or tag it
  (`archive/steady-state-controllers`) before deleting.

Session 4's branch table is in git history.

---

## Next actions

1. ~~**Owner:** merge #50, then #51 → #58, then #59 → #64, retargeting each
   child to `main`.~~ Done (#50, #65, #71). ~~**Now: merge #72 → #76 in
   order**~~ done 2026-09-30. ~~**Now: merge #77 → #78 → #79 → #80 in order**~~
   done 2026-10-02. ~~**Now: merge #81 → #82 → #83 → #84 in order**~~ done
   2026-10-04. ~~**Now: merge #85**~~ merged; the app is live.
   ~~**Now: the owner's Android check** at
   https://jenilclaudeai.github.io/diesel-simulator/enjoy, the last Phase 5
   exit criterion.~~ Done (reported 2026-10-05); it found a few bugs. **Now:
   the owner's bug sheet**, then the fixes.
2. **Owner: listen.** On `/drive`: Sound on, keys 1–5 for the mics, "Record
   10 s (WAV)". Or `python3 play.py`. Listen for:
   - `hd_i6`'s tick dominance (13×);
   - a cold start against a warm one;
   - FINDING-022's new balance: a quiet intake at idle, and the turbo
     rising with boost;
   - cold slap, which FINDING-023 still caps.

   ~~Then pick an option for 023 (recommended: A, a temperature-dependent
   clearance), which means one ~70 min grid rebuild. A ramp-height parameter
   separate from `ramp_fraction` is still open for the same review.~~
   Decided 2026-09-30: 023 option A **and** the ramp-height parameter, one
   rebuild of all 8 grids; then a before/after pair for the owner's ears.
   **Built (#78). Listen to `out/listen/review003m5_*.wav`** (or the app on
   the branch), and judge especially `hd_i6`'s idle tick, now 0.23× the
   loudest other source: it may have become too quiet for a mechanical-lash
   truck. `RAMP_SPEED` is the single knob.
3. **Phase 5 — Enjoy mode:** ~~the roster (OPEN-F), the dashboard, and the
   steady-state economy label~~ roster A, the dashboard and the label are
   done (#75, #76). ~~Next: roster B (`v8hd`, an old NA single)~~ done (#84).
   Remaining: truck127's 13 unsettled cells, if they show on the dials; and
   **the real Android phone check** (the Phase 5 exit, the owner's), with
   live friction's and the synth's cost (REVIEW-005 m-5, REVIEW-006 m-1).
4. ~~**Custom engines, drivable (owner's choice, 2026-10-01), after #78:**~~
   Done (#79–#82, ADR-014).
   *(Was:)*
   - a brochure-numbers form, plus JSON import/export in the
     `engines/*.json` format, on Dyno and Grid, through the solver's
     existing `{"headline": ...}` contract, showing achieved against
     requested;
   - then the converged warm+cold grid built in the browser so the engine
     can be driven, plus a vehicle choice. **Measure the in-browser build
     time first**: natively it is 15–20 min on 6 cores.
   - ADR-007 (project JSON) and the Derate-lamp threshold ride along.
5. Follow-ups:
   - a TCU engine-speed match on converter downshifts (REVIEW-005 m-3);
   - ~~`play.py` on `Adr011Grid` (m-6)~~ done in #69;
   - row-sharing the p_max / T_exh check;
   - a timing-based p_max limiter;
   - "life used" labelling.

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
