# REVIEW-004 — Phase 2 exit (solver port and fixture harness)

**Date:** 2026-09-26 (session 5)
**Scope:** PLAN.md Phase 2's checklist and exit criterion, on the stack #40 → #49
**Lenses run:** PM, LEAD, SW1, SW2, QA1, QA2, USR1/2 (advisory)
**Reproduce:**
- `cd web/app && npm run build:pages && CHROME_PATH=… npm run e2e:grid`
- `python3 tools/fixtures/gen_fixtures.py --check`
- `cd web/physics && npm test`

---

## Summary

| Class | Count |
|---|---|
| BLOCK | 0 |
| MAJOR | 0 new (REVIEW-003's M-1 and M-2 still stand) |
| MINOR | 4 |
| NOTE | 3 |

**Phase 2 can exit** once the stack is merged. The exit criterion is met at
full-grid level in a real browser, and it is checked in CI on every PR.

---

## The checklist

| item | state | where |
|---|---|---|
| `SolverPort`, one seam, Pyodide behind it | done; ADR-010 accepted | #11 |
| Pyodide in a Web Worker; scipy checked | done: unmodified solver, numpy only; scipy never imported | #9, #10 |
| Grid build with real progress, cached in IndexedDB, keyed by engine and physics hash | done: cache #12; a page with per-cell progress, #48 | #12, #48 |
| Golden-fixture generator (ADR-004) and CI | done: kinematics and thermo ported; friction fixture ready for Phase 3 | #47 |

## The exit criterion — a grid built in-browser matches native

`e2e/grid.e2e.mjs` builds `crdi15`'s full 8 × 6 operating grid in headless
Chrome, through the app's own worker and SolverPort. It compares every perf
value of every cell with `e2e/native_grid.py`, which calls
`bridge.solve_grid_cell` on the same axes with the same float operations.

| | result |
|---|---|
| values compared | 816 (17 per cell × 48) |
| worst relative difference | **8.7e-7** (soot, 2429 rpm / load 0.8) |
| tolerance | 1e-5: the SolverPort's bound, set by the limiter chain's measured amplification |
| progress | reported per cell (47 of 48 seen by 250 ms polling) |
| second build | from the cache in 0.05 s |
| console errors / failed requests | none |
| build time | 487 s locally (about 10 s per cell) |

**Test of the test:** a reference with one torque nudged by 2e-5 fails it.
CI job `web-grid-e2e` runs it on every PR. On #48's CI run (Linux Chrome
against Linux Python): worst **1.81e-8**, browser build 952 s, job 25 min in
total (the native reference takes 545 s on two cores). The job has a 60-minute
timeout.

---

## Findings of this review

**m-1 (MINOR) — a browser grid build takes about 8 minutes.** That is
acceptable for Expert mode with a progress line and a cache, where the
second build takes 0.05 s. It is not acceptable as a first experience.
Enjoy mode ships prebuilt grids (ADR-008), which this confirms. A converged
grid (544 s native on 6 cores) is out of reach in the browser.
*(USR, PM)*

**m-2 (MINOR) — the p_max / T_exh check lengthened every calibration.** On
CI's two cores, the dyno pull crossed puppeteer's 180 s protocol timeout: the
dyno e2e went red from #44 on, and was fixed in the harness (PR #44 onward).
A user sees a slower first pull too. The cost is REVIEW-003 m-3's, now
visible. Row-sharing the limit would recover it, at a re-baseline. *(SW1, QA2)*

**m-3 (MINOR) — unit tests depended on a generated file.** `grid.spec.ts`
reached the generated `physics-version.ts` through the service. CI runs unit
tests before `build:pages`, so CI failed with TS2307 while it passed locally.
Fixed: the grid axes are now a pure module. The same trap waits for any spec
that imports a service. *(SW2)*

**m-4 (MINOR) — `physics-version.ts` and the fixtures are tied to the
physics hash.** Any merge that touches `dieselsim/` has three consequences:
- the dyno accuracy note reads "not measured";
- `gen_fixtures.py --check` may fail;
- `NATIVE_TORQUE` in the SolverPort round trip moves.

All three are intended, and all three say what to do. If the owner picks a
different FINDING-018 option, all three need regenerating in that PR.
*(LEAD)*

**N-1 — the accuracy table is regenerated on the final tree.** See the
table below. It is valid for the physics build it names.

**N-2 — CI is now 9 checks.** `fixtures` (about 30 s) and `web-grid-e2e`
(10–15 min, the longest) are the additions. They are independent, so a red
one says which contract broke.

**N-3 — no lens found scope creep.** The grid page was built only because the
exit criterion needed a user-shaped way to build a grid. Its accuracy note
states part-load error, as REVIEW-003 M-1 asked.

---

## Dyno accuracy on the final tree

(`tools/diag_torque_limiter.py --pull`, fast path vs converged, full load)

Physics build `0cc90542b137`, the top of the stack. Written to
`web/app/src/app/dyno/accuracy.ts` by `--write-accuracy`.

| preset | worst gap, positive torque | before (build `dd652e959dd3`) | governed end (negative torque) |
|---|---|---|---|
| `crdi15` | −5.84% at 1650 rpm | −5.8% at 1650 | 1.8 N·m (was 2.0) |
| `crdi_1p5` | −8.48% at 1200 rpm | −8.3% at 1200 | 23.9 N·m (was 20.1) |
| `hd_i6` | −3.35% at 1950 rpm | −2.8% at 1950 | 14.2 N·m (was 10.5) |
| `ld_i4` | −3.74% at 2600 rpm | −3.8% at 2600 | 5.1 N·m |
| `single` (no turbo) | 0.00% | 0.0% | 0.0 N·m |

Full load barely moves. EGR is off at load 1, and the limits don't bind. The
`hd_i6` and governed-end changes come from FINDING-018's profile and the
limiter's cold-started chain.

A process note: the first attempt at this run was corrupted. I killed a pull
whose spawn workers kept running, and they wrote into the same output file
after the restart truncated it. It was re-run into a fresh file with no
workers left.
