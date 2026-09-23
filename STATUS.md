# Status

**Updated:** 2026-09-23 (session 3)
**Phase:** 2 — mostly done. Python runs in the browser, the SolverPort exists,
grids are cached, CI runs, and the first web page (a dyno pull) works end to end.
**Stack tip:** `phase2/web-app` (PRs #8–#14, see Branches below)

Read this first in a new session, then `PLAN.md`, then `DECISIONS.md`, then
`reviews/`. Those replace pasting a context document.

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
| 3 | Torque limiter ±3% | partly addressed by the FINDING-007 cache fix; re-measure |
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
cd web/app && npm run build:pages                # never plain `build`
cd web/app && npm run e2e                        # 11 browser checks
```

Golden points are locked at 0.5%. They were re-baselined after FINDING-001 P-2
with the justification recorded inline — torque and BSFC moved under 1%, p_max
rose ~3%, and `hd_i6` still reproduces the documented 2310 N·m and stays inside
the 160–200 bar band.

Known defects report as KNOWN, not FAIL. When one is fixed the suite reports
UNEXPECTED PASS, which is the signal to promote it to a real assertion.

---

## Branches

Everything below `main` is one open stack; each PR targets the branch beneath
it and shows only its own commits. **Merge bottom-up.** The repo does not
auto-delete merged branches, so after each merge retarget the next PR to
`main` or it merges into a dead branch.

| PR | branch | contents |
|---|---|---|
| #8 | `fix/grid-build-accuracy` | FINDING-011 — per-cell fresh engines |
| #9 | `phase2/pyodide-harness` | ADR-001 measured |
| #10 | `phase2/grid-cell-in-package` | grid cell in `dieselsim/grid.py`; lazy scipy |
| #11 | `phase2/solver-port` | SolverPort, ADR-010 |
| #12 | `phase2/grid-cache` | grid cache |
| #13 | `ci/github-actions` | CI workflow + lockfiles |
| #14 | `phase2/web-app` | the dyno page; session-3 test fix |

Merged earlier: #5 `physics/verified-fixes`, #6 `audio/physical-levels`
(**not yet listened to** — revert that merge if the mix is wrong), #7 the
bug-8 audit.

---

## Next actions

1. **Merge the stack** once #14 is green.
2. **Chart axis scaling** in `web/app/src/app/dyno/dyno.ts` — a 235 N·m peak
   gets a 500 axis and non-round ticks. Needs nice-number ticks (1/2/5 × 10ⁿ).
3. **Put `web/app` in CI**: `build:pages` at least.
4. **Listen to the audio** — the warm-vs-cold pair at load 0.6 matters most.
5. **FINDING-005**: chase cam boundary friction, or state that roller cams
   genuinely barely wear. Test on `hd_i6` / `single` (mechanical lash).
6. **Bug #3** re-measure after FINDING-007; **#10** still unmeasured;
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
- **Tool-call budget.** Chat caps tool calls per turn (the "reached its
  tool-use limit" banner); session 3 hit it by spending ~40 calls, many on
  polling. Rules: one call per long job — start it, wait, report in the same
  call, never separate sleep-and-check calls; batch related reads and checks
  into one script; test + commit + push in one call; aim for ~15 calls a
  turn, commit before nearing the cap, and end each turn with a written
  status so a cut-off lands between steps, not mid-step.
- Working style: measure before fixing; ask rather than assume; options come
  with trade-offs and positives; warn before context budget limits.
