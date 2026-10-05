# REVIEW-008 — Phase 6 exit (Expert mode)

**Date:** 2026-10-06 (session 6)
**Scope:** PLAN.md Phase 6, as ADR-015 staged it (`PROPOSAL-phase6.md`,
option B), on the stack #89 ← #90 … ← #98 and this review's PR
**Lenses run:** PM, LEAD, SR1, SR2, PHY1, PHY2, SW1, SW2, QA1, QA2, USR1/2
(advisory)
**Reproduce:**
- `python3 tests/test_physics.py`; `cd tools/pyodide && npm run suite`
- `cd web/solver && npm test`; `cd web/app && npm test -- --watch=false && npm run check:labels`
- `cd web/app && npm run build:pages`, then `e2e:cycle`, `e2e:spec`,
  `e2e:sweep`, `e2e:durability`, `e2e:custom` (with `CHROME_PATH`)

---

## Summary

| Class | Count |
|---|---|
| BLOCK | 0 |
| MAJOR | 4, all resolved in this review (M-1 to M-4) |
| MINOR | 6 |
| NOTE | 5 |

**Phase 6 is complete once CI is green on the stack and this PR.** Every
part of PLAN's Phase 6 is built and checked against native Python in a
browser. This review found three gaps, and each is fixed here:
- CI's Pyodide job had been red since #91;
- the Dyno table's BSFC was unlabelled;
- an edited engine could not be driven;
- the physics job's 20-minute timeout killed runs (found after the review's first
  push; M-4).

The owner has nothing to do for Phase 6 but merge. Trying Expert mode is
welcome, and is the real test of the USR lens (N-4).

Phase 5 still waits on its own M-1 (REVIEW-007): the owner's re-check on the
phone.

---

## Exit criterion

PLAN.md: *Lazy-loads Pyodide. Full spec editing across all nine
dataclasses, grouped by physical subsystem rather than class name. Live 2D
schematics. Grid-invalidation banner with rebuild progress. Analysis pages:
curve, map, cycle, sweep, durability. Economy and BSFC shown anywhere are
labelled steady-state. Durability's `health` is life consumed.*

| part | state | evidence |
|---|---|---|
| lazy-loads Pyodide | **met** | The worker starts Pyodide when a page that solves first asks (`solver.start()`). `/enjoy` and `/drive` never fetch it: e2e:enjoy, "no Pyodide or solver files are fetched", in CI. |
| full spec editing, by subsystem | **met** | `/spec` (#94): `describe_spec`'s 188 fields (181 editable) over the nine dataclasses and `EngineSpec`, in 7 groups by subsystem, the influential fields first and the rest under "More". `test_spec_editor_schema`: the committed schema is current, and every editable field round-trips through `overrides`. |
| live 2D schematics (ADR-009) | **met** | #98: cross-section, valve dial, compressor map with the operating point, ring pack and bearings. Drawn from the spec with the edits applied; e2e:spec checks the redraw (liner ÷ crank = bore ÷ stroke, 0.957 → 1.148). |
| invalidation banner, rebuild progress | **met** | #95: `SpecStatus` on Dyno, Grid and Cycle says "out of date" and re-solves at native Python's 157.5 bar. The Grid page's rebuild shows its progress. A drivable grid for an edited engine is built with progress, ETA and Stop (M-3, this PR). |
| analysis pages | **met** | curve = Dyno and map = Grid (Phase 2); `/cycle` (#92): 140.1 bar, MFB50 +12.0°, IMEP 11.07 bar, as native; `/sweep` (#96): 228.1, 227.5, 228.7, 230.0 N·m, as native; `/durability` (#97): 0.062%, 0.071 µm, 202.7 N·m after 100 h, as native `durability_run`. |
| steady-state labels (FINDING-009) | **met, after M-2** | `check:labels`, in CI: 6 of 10 templates show a fuel figure, and all 6 say steady state. |
| life consumed (FINDING-019) | **met** | e2e:durability: "Life consumed (0 = new)"; the mutant showing health remaining (99.938%) is caught. |

---

## Findings

**M-1 (MAJOR, resolved): CI's Pyodide job was red on #91 to #96, and I
didn't see it.** Two tests read files that the Pyodide harness doesn't
copy: `test_accuracy_table_is_for_this_build` (added on #91) and
`test_spec_editor_schema` (added on #94). Both failed with
`FileNotFoundError` ("62 passed, 2 failed"). Six PRs went up with that red
job while I reported their tests passing from local runs.
- The "physics (Python 3.10)" red on #94 was **cancelled**, not failed.
- Fixed where each came in, and merged forward through #98:
  - the accuracy test SKIPs without `web/app`, as the grid and roster tests
    do;
  - the schema test still runs its two bridge parts under Pyodide, and
    leaves out (and says so) the two that need `tools/`.
- Proved natively: PASS; with the file moved aside, SKIP or 2 of 2; a
  mutant fails each.
- *QA2:* "verified" must mean every CI job read with `gh pr checks`, not
  the local runs. Now in memory.
- CI after the fix: #91 and #92 are 9 of 9 green. Pyodide on #92: 61 passed, 0 failed, 2 known, 13
  skipped, with the accuracy test SKIPped. The PRs above were still running at writing.

**M-2 (MAJOR, resolved): the Dyno table's BSFC column wasn't labelled
steady-state,** against PLAN's "shown anywhere". Its header now says so.
- `scripts/check-labels.mjs` (`npm run check:labels`, in CI's web-app
  job): every template that shows a fuel figure says "steady state"
  somewhere.
- Mutants 2 of 2: the old Dyno header; Enjoy's note removed.

**M-3 (MAJOR, resolved): an edited engine couldn't be driven.** The plan
the owner accepted promised it (proposal item 5: "a drivable grid for an
edited engine reuses ADR-014's build"); the stack never built it.
- Dyno's "Drive it" block is now a shared component, `engine/drive-build.ts`.
  The spec editor shows it whenever there are edits.
- It builds the grid for `{preset, overrides}` and saves it in "Your
  engines": keyed by base and edits, in the base engine's vehicle.
- The grid file records `base` and `overrides`, and `live.py` rebuilds that
  spec from them (Python test part; the mutant ignoring the edits is
  caught).
- e2e:custom 7 (+2), in 557 s:
  - crdi15 edited (idle 950, CR 18) is built at 2×2 from `/spec`;
  - its grid file holds CR 18, idle 950, a first row at 950 rpm and
    vehicle crdi15;
  - on `/enjoy` it idles at **929 rpm** (crdi15's own idle is 800).
- Mutants:
  - `/spec` building the unedited engine fails both checks (CR 16,
    idle 800; 776 rpm);
  - the key ignoring the edits' order fails a unit test;
  - `live.py` ignoring the edits fails the Python part.
- `live.py` is outside the grid hash, so no grid changes.

**M-4 (MAJOR, resolved, added after this review's first push): the physics
job's 20-minute timeout.** Once M-1's fix had gone forward, CI re-ran the
whole stack. Python 3.10 was then **cancelled at 20m15s** on #95, #96 and
#98, the job's limit, not a test failure.
- The same trees took 11 to 20 min depending on runner load: across #89 to
  #99, 9 more of the 22 physics runs went past 17 min.
- Phase 6's tests made the suite longer, and eleven PRs' CI at once made the
  runners slower.
- Raised to 30 min, as the Pyodide job has, on #90 (the first PR that grows
  the suite) and merged forward. Re-running the cancelled jobs would only
  have hidden it.
- CI after the change: see STATUS.

**m-1 (MINOR): the sweep's resolution.** Each point is a fast 9-cycle solve.
crdi15 dips 0.3% at CR 16, which is noise, and its full-load error is 5.8%
(FINDING-013). The page says both. A converged sweep would cost several
times more; that's not measured, and is left for later.

**m-2 (MINOR): durability costs ~8 min per 1,000 h in the browser**
(2.8 min natively, ×2.65). The default is 1,000 h, with the cost stated
first. Not measured on a phone.

**m-3 (MINOR): edits and kept results live in memory only.** A reload loses
them, and the page doesn't say so. "Export spec (JSON)" keeps edits today;
Phase 7's project file (OPEN-C) is the real fix.

**m-4 (MINOR): `check:labels` works per template.** A page with one labelled
figure and a second unlabelled one would pass. It caught the case that
happened; a finer check would need the figures marked in the markup.

**m-5 (MINOR): an edited engine's drivable grid costs what ADR-014's does,**
21.5–27.5 min on a laptop and hours on a phone. The grid-build plan is
deferred by the owner until v1 is done (`PROPOSAL-grid-build.md`).

**m-6 (MINOR): Expert mode hasn't been looked at on a phone.** PLAN doesn't
ask for it (Enjoy is the phone mode, ADR-012), but the 188-row editor at
360 px is unmeasured.

**N-1 (NOTE), PHY2: the schematics' proportions that aren't spec fields**
(crown, skirt, lands, the oil ring's height) are drawing proportions, and
each caption says so. The oil ring's spec "width" is its contact land, and
it's labelled that way.

**N-2 (NOTE), PHY1: FINDING-024 was found on the way.** MFB50 was late by
up to 7°; it's fixed, and the grids were re-stamped with proof. The
re-stamp's own regression (the accuracy table) is now guarded, and
`tools/restamp_grids.py` stamps the table too.

**N-3 (NOTE), LEAD: two ways to make an engine, one way to drive it.**
- Custom engines keep ADR-014's brochure form and JSON.
- Edits apply to the presets and the roster.
- Both meet in `DriveBuild` and "Your engines".

**N-4 (NOTE), USR1/2 (advisory, weakest lens): 188 fields is still a wall.**
It's ordered by influence, with the rest collapsed, a filter, and a
schematic beside four groups. Whether an enthusiast finds their way is the
owner's call, not this lens's.

**N-5 (NOTE): a dismissed item, with its reason.** The proposal said each
new bridge call gets "a golden fixture". ADR-004's fixtures exist for
TypeScript ports, and these calls have none: Python runs in the browser.
Instead, the round-trip test runs each call (`solveCycle`,
`durabilityCall`, `describeSpec`, `compressorMap`) through a real Pyodide
worker against native numbers (the cycle within 2.25e-7, durability within
5.48e-13), and each has its own Python test.

---

## Lens notes

- **PM:** the phase ends here. v1's remaining phases are 7 (environment,
  projects; m-3 belongs there) and 8 (polish). Phase 5's M-1 is still the
  owner's.
- **LEAD:** no ADR contradicted.
  - ADR-001: the new bridge calls are numpy-only and run unmodified under
    Pyodide.
  - ADR-003: no `SharedArrayBuffer`; durability is stepped in blocks, so
    Stop needs no interrupt.
  - ADR-005: standalone, signals, OnPush.
  - ADR-009: the schematics' only source is the spec.
  - ADR-014: its build is reused, not copied.
- **SR1:** the worker keeps one durability run, and a new one replaces it.
  A drivable build's pool ends on Stop, and what finished is kept (B-04's
  design).
- **SR2:** the cache keys follow the spec, so a stale result is never
  served, and the banner says when one is shown. m-3 is the persistence
  gap.
- **PHY1/PHY2:**
  - the cycle page labels cylinder 1's own crank angle (FINDING-008);
  - it reads `dpdtheta_comb`, not `dpdtheta_max`;
  - `solveCycle` refuses `n_cycles` < 9;
  - economy is steady-state everywhere (M-2).
- **SW1:** hand-drawn SVG with tested axis helpers (`cycle/plots.ts`). The
  drivable build is one component now, not two copies.
- **SW2:** `scipy` is still never imported at module level; `batch.py`'s
  `multiprocessing` stays out of the browser path (sweep loops
  `solvePoint`).
- **QA1/QA2:** every new guard was mutation-tested against a passing
  baseline, and every count here was read from a finished run.

| check | count |
|---|---|
| Python suite (native) | 77 passed, 0 failed, 3 known (with scipy) |
| Python suite under Pyodide (CI) | 61 / 0 / 2 known / 13 skipped (#92, after M-1's fix) |
| app units | 101 (passing without `physics-version.ts`) |
| `check:labels` | 6 of 10 templates; 2 of 2 mutants |
| solver round trip | 29 |
| e2e: cycle / spec / sweep / durability | 8 / 11 / 6 / 5 (CI on #98) |
| e2e:custom | 7 (557 s), locally |
| fixtures / audit | 7 of 7 current / 0 dead, 2 frozen (known), 0 tiny |
