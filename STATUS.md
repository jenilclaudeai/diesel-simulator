# Status

**Updated:** 2026-09-24 (session 4)
**Phase:** 2 — mostly done. Python runs in the browser, the SolverPort exists,
grids are cached, CI runs, and the first web page (a dyno pull) works end to end.
**Main:** everything through PR #16 is merged; CI on `main` is green. Open work
is listed under Branches below.

Read this first in a new session, then `PLAN.md`, then `DECISIONS.md`, then
`reviews/`. Those replace pasting a context document. `CLAUDE.md` says the same
for Claude Code sessions.

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

Latest audit: 102 scalars over 8 operating points — **0 dead, 1 frozen (the
now-honestly-named `h_ring_tdc`), 1 tiny (`Pb_valvetrain`)**.

---

## Findings

| # | Issue | Status |
|---|---|---|
| 001 | `premix_fraction` pinned; Watson correlation out of domain at modern common-rail delays | P-1 and P-2 fixed |
| 002 | `dp/dθ` peaks 10° *before* ignition, so it measures compression; clatter was driven by it | fixed |
| 003 | clatter high-mode weight pinned at its ceiling; divisor 3 orders of magnitude out | fixed |
| 004 | every physical amplitude discarded by two normalisation stages | fixed |
| 005 | roller-follower branch never accumulated `Pb_vt`; cam wear structurally impossible | fixed, **but insufficient** |
| 006 | `h_min_ring` always its clamp, and exposed as a headline field | fixed |
| 007 | bug #8 audit; `fuel_for_torque` returned 8.7% different fuel depending on cache warmth | fixed |
| 008 | `theta` indexes two references — per-cylinder local vs global engine angle | documented; roll sign fixed |
| 009 | bug #4 overstated — light-load gap is ~29%, not 2× | measured; no fix needed |
| 010 | bug #2 overstated — the loop converges; real gap is missing p_max/T_exh limits | measured |
| 011 | the real-time grid was the least accurate part — worst −10.06% | **fixed** — per-cell fresh engines at `n_cycles=9`; now exact vs reference |
| 012 | `transient()` floor sat inside the solver's NaN region and could not catch NaN | **fixed** — stall detection; root cause as first recorded was wrong |
| 013 | bug #3 understated: limiter fitted with EGR on, judged with it off; EGR valve opens 25% for any command; `crdi15` never converges at 1650 rpm | **measured, not fixed** — PR #19; three physics decisions |

### Still open inside those

- **FINDING-005 is not closed.** `Pb_valvetrain` is now nonzero but runs 1e-5
  to 1e-8 of total. The flat-tappet case is *lowest* at 3.9e-7 W — the case
  that should wear most. Cam wear is still negligible and lash still does not
  grow at 8000 h. Suspects: `sigma_cam`, or entrainment velocity at nose
  reversal. Untested.
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
| 10 | `render_transient` seams | **still unmeasured** — blocked by FINDING-012; code reading suggests crank-phase reset at every chunk |
| 11 | Coast downshift calibration | deferred |
| 12 | Grade small-angle form | **already correct** — `atan`/`sin`/`cos` all present; entry was stale |

---

## Also found, not yet actioned

- **Trace arrays index two crank-angle references** — diagnosed as FINDING-008
  (per-cylinder local vs global engine angle). The fix is an API-contract
  decision. **Resolve before the Angular cycle page consumes traces.**
- **ADR-006 is on hold** and should be reassessed now that FINDINGs 001–004
  have changed the numbers it was decided on.
- **`SPL_CAL` and the 5.0e9 clatter divisor are chosen constants.** The package
  advertises exactly two fitted scalars (`NOX_CAL`, `SOOT_CAL`). That claim is
  no longer accurate; either derive the constants or update the claim.

---

## Tests

```
python3 tests/test_physics.py                    # 18 passed, 0 failed, 2 known defects
python3 tools/audit_dead_signals.py              # diagnostic; 0 dead, 1 frozen, 1 tiny
cd tools/pyodide && npm ci && npm run suite      # the same suite under Pyodide
cd web/solver && npm ci && npm run test:fast     # 20 cache tests, seconds
cd web/solver && npm test                        # + the round trip through a real worker
cd web/solver && npm ci                          # BEFORE any web/app build: the app compiles ../solver/src
cd web/app && npm test -- --watch=false          # 14 unit tests (vitest), once #17 is merged
cd web/app && npm run build:pages                # never plain `build`
cd web/app && NATIVE_REF='...' CHROME_PATH=... npm run e2e   # 12 browser checks with 3 reference points
```

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

The session-3 stack (#8–#14) merged on 2026-09-22/23, and `CLAUDE.md` (#16) on
2026-09-23. Merged branches are **not** auto-deleted: after merging a parent,
retarget its child PR to `main` (`gh pr edit <n> --base main`) or it merges into
a dead branch.

| PR | branch | contents | state |
|---|---|---|---|
| #15 | `docs/status-session-3` | this file; FINDING status lines | CI green; **merge first** |
| #17 | `fix/dyno-axis-ticks` | nice-number dyno axes; `ng test` runs; tie-break test | CI 4/4 green |
| #19 | `diag/bug-3-torque-limiter` | FINDING-013 + `tools/diag_torque_limiter.py`; diagnostic only | independent of the others |
| #18 | `ci/web-app` | `web-app` CI job — **stacked on #17** | CI 5/5 green; new job ran 14 tests + Pages build in 32 s |

Merge order: #15, then #17, then retarget #18 to `main` and merge it.

Merged earlier: #5 `physics/verified-fixes`, #6 `audio/physical-levels`
(**not yet listened to** — revert that merge if the mix is wrong), #7 the
bug-8 audit, #8–#14 the Phase 2 stack, #16 `CLAUDE.md`.

---

## Next actions

Session 3's list, with what has happened since. Items 1–3 are session 4's work.

1. ~~**Merge the stack** once #14 is green.~~ Done — #8–#14 merged, CI green.
2. ~~**Chart axis scaling**~~ — verified in session 4 and opened as **#17**;
   awaiting merge.
3. ~~**Put `web/app` in CI**~~ — **#18**, stacked on #17; awaiting merge.
   Follow-up: add the browser e2e check to CI (needs Chrome on the runner and
   a `NATIVE_REF` step).
4. **Listen to the audio** — the warm-vs-cold pair at load 0.6 matters most.
5. **FINDING-005**: chase cam boundary friction, or state that roller cams
   genuinely barely wear. Test on `hd_i6` / `single` (mechanical lash).
6. ~~**Bug #3** re-measure after FINDING-007~~ — done, FINDING-013 (PR #19).
   Fix order agreed: 3 → 1 → 2. **Item 3 measured (session 4) and it is
   bigger than one engine:** neither the VGT loop (limit cycle caused by
   `spool_accel` = 14) nor the EGR loop reaches steady state in 9 cycles.
   21 of 120 mapped points oscillate; against a converged 1× reference the
   shipped n=9 solve is off by up to −43.6% (RMS 16.2%), and the golden
   points are 9-cycle solves. Four VGT-only fixes tried, none works.
   **Blocked on a design decision** — FINDING-013 options A–D; A (solve the
   controllers' steady state per cycle) recommended. Item 1 must be
   re-measured after. **#10** still unmeasured;
   **#11** untouched.
7. **FINDING-008** contract decision before any cycle page.
8. **Reassess ADR-006** against the post-FINDING-001–004 numbers.
9. Then **Phase 3** — real-time loop in TypeScript; manual gearbox needs a
   clutch model that does not exist yet.

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
