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

- The four grids: cells (`out/p14_b2_cells.log`), then `--weather`.

## Next

1. Weather; the grid table in ROSTER.md.
2. Full suite, audit, fixtures check, `web/physics`, `web/solver` fast tests, `build:pages`,
   e2e (enjoy, custom, drive, spec).
3. Commit the grids, open the PR, read every CI job.
4. The owner listens: the pickups.
