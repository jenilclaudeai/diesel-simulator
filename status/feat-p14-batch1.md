# feat/p14-batch1 (P14 batch 1, ADR-023)

**2026-10-28.** The owner accepted every recommendation of `reviews/PROPOSAL-P14.md`
(ADR-023, recorded on #146). This branch is batch 1: six engines on today's vehicles. It
is from `main` at `df36a05`, not stacked on #146: no file in common except `CLAUDE.md`, and
there in different paragraphs.

## Done

- **Sourced** (F2): each engine's brochure figures plus bore × stroke and CR where found,
  cited in `engines/ROSTER.md`. Not found, so the builder's default: the mHawks' bore,
  stroke and CR, and the ALH's turbo type. `vw19tdi`'s torque is published at one speed,
  so its `plateau` is [1900, 1900].
- **`engines/{vw19tdi,mhawk75,mhawk22,gd28,duratorq32,b57}.json`**, tuned by "the least
  tuning that holds the plateau start ≥ 96%". As registered from `engines/`, the roster
  test's check gives 98.5–100.6% of cap at the plateau start and 99.4–100.8% at rated.
  verify() curves are in ROSTER.md.
- **Found and stated:** at 800–900 rpm full load, mhawk22 and b57 run AFR 14.4 / 14.5,
  under their limits (hatch15 / crdi22: 16.1–17.1). The cause is the calibration's
  one-sided headroom (hashed `engine.py`), so it is stated, not fixed.
- **Vehicles:** `live.ROSTER_VEHICLES` and its TS copy, applied before the vehicle switch.
  The vehicles fixture holds the map and the six keys. TS vehicles **18 passed, 0 failed**.
- **Tests (Python):** `test_roster_engines_drive_their_vehicles` (mutants 4 of 4 caught,
  baseline passing) and `test_enjoy_lists_the_roster` (4 of 4 caught after a fix, plus the
  SKIP case). A first run let a commented-out picker line through, so the test now strips
  `//` comments. `ROSTER` has eleven engines.
- **/enjoy:** `roster.ts` with groups (`<optgroup>`: Cars and SUVs, Trucks, Tractors) and
  N2 labels. Under Start, "Modelled on the published figures of …" for the selected engine,
  kept out of the header so it can't widen on a phone. `roster.spec.ts`: app units **167
  passed** (30 files; `main` 164 in 29). Mutants 3 of 3 caught, baseline passing.
- **e2e:** `enjoy.e2e.mjs` opens each of the six, checks the "modelled on" line, the
  vehicle and the idle, and drives off at 85%. **Not run yet** (needs the grids).

## Running

- **The six grids** (`build_live_grids.py`, then `--weather`): cells started 2026-10-28,
  log `out/p14_b1_cells.log`. vw19tdi 261 s, mhawk75 233 s, mhawk22 555 s so far (faster
  than the 42-min-per-grid estimate's cell share).

## Next

1. The weather pass on the six; record the unsettled cells and the Leh checks in
   ROSTER.md ("The grids").
2. Full Python suite, audit, `gen_fixtures --check`, `web/physics` and `web/solver` tests,
   `build:pages`, and `e2e:enjoy` (plus the rest of the e2e).
3. Commit the grids and open the PR; read every CI job.
4. The owner listens on the phone.
