# feat/p14-batch2 (P14 batch 2, ADR-023: the pickups)

**2026-10-28.** Batch 1 merged (#147, live). The owner answered the proposal's questions
one by one: "Most popular onces / N2 / F2 / V2" (recorded on #146). This branch is from
`main` at `2aa1710`, not stacked.

## Done

- **Sourced** (F2): the four engines' ratings, bore × stroke and CR, and the pickup's
  gearbox, axle, tyres and curb weight (a 2023 Ram 2500 6.7). The sources are in ROSTER.md.
  The 6.7's CR is disputed (19 / 17.3 / 16.2 / 16.0), so 17.3 (Wikipedia) is used.
  The vehicle's drag, rolling resistance, inertias, efficiency and tank are estimates,
  marked as such.
- **`engines/{cummins59,cummins67,duramax66,powerstroke73}.json`**, by the same rule (the
  least tuning that holds ≥ 96%). As registered: 99.1–102.0% of cap at the plateau start,
  99.6–99.8% at rated. verify() curves are in ROSTER.md. duramax66 runs rich when lugged
  (AFR 13.8 at 700 rpm), as mhawk22 and b57 do.
- **The `pickup` vehicle** in `live.Vehicle`, `VEHICLE_KEYS` (custom engines can name it),
  `vehicle.ts`, `VEHICLE_NAMES`; the four keys in `ROSTER_VEHICLES`. Fixture regenerated:
  TS vehicles **22 passed, 0 failed**; a mutant (the pickup's mass in TS) is caught in all
  four.
- **Tests:** `ROSTER` has fifteen engines. `test_roster_engines_drive_their_vehicles` 10 of
  10, `test_enjoy_lists_the_roster` 15, `test_custom_engine_json` passes with the pickup.
- **/enjoy:** a "Pickups" group; the spec is extended (labels allow "Pickup", "V8", "hp").
  App units **167**. The e2e drives off in all ten P14 engines.

## Running

- ~~The four grids: cells, then `--weather`.~~ Cells done: 2,246 s. Unsettled 0 / 7 / 7 / 0.
  Cold / warm FMEP at most 3.12× (cummins59, under the 4× bar). Fingerprints 15 of 15.
  Weather: cummins59 1,240 s (Leh 3.44%, 0 unsettled), cummins67 2,740 s (2.36%, 55); the
  V8s are running.
- **Checked meanwhile:** `gen_fixtures --check` every module ok (worst 0); `web/physics`
  5 / 68 / 13 / 22; `web/solver` fast tests 20 + 15. **A one-off stall:** the first
  `test:fast` run sat in `cache.test.js` at 0% CPU for 29 min, while the weather pass had
  the CPU. Killed; it then ran in seconds, twice. Cause unknown, and not this branch
  (`web/solver` is untouched).

## The grids (done)

Cells 2,246 s plus weather 8,873 s, **3.1 h**. The V8s' weather: duramax66 3,249 s (Leh
1.33%, 39 unsettled), powerstroke73 1,644 s (1.26%, 0). All within the shipped ranges;
table in ROSTER.md.

## Verified locally on the final grids (2026-10-29)

- **Python suite: 100 passed, 0 failed, 3 known, 4 skipped** (scipy-gated; CI has scipy).
- Audit 0 dead, 2 frozen (known), 0 tiny. Fixtures all current. `web/physics` 5 / 68 / 13 /
  22. `web/solver` fast tests 20 + 15. App units 167.
- e2e (`build:pages`, 20 grids in the bundle): **enjoy 55** (`main` 51), custom 7, drive 11,
  all 0 failed. The enjoy run shared the CPU with the suite, and passed anyway.
- The pickups idle at 563–574 rpm in drive (the builder's 600 rpm idle at these rated
  speeds); real ones idle ~650–750. Noted, not changed.

## Next

1. The PR; read every CI job.
2. The owner listens: the pickups.
