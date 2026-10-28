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

## The grids (done)

~~**Running:** the six grids, cells started 2026-10-28.~~ Built: cells 3,044 s plus weather
11,315 s, **4.0 h** (the estimate was 4.4).
- Unsettled cells 0 / 0 / 1 / 1 / 4 / 10; weather pieces 0–65.
- Leh checks 0.41–3.42%: within the shipped grids' ranges, and no new misfire cliff.
- Cold / warm FMEP is at most 3.00× (vw19tdi, under the 4× bar; the shipped grids are at
  1.78–2.84×; the cause is not investigated).

Table in ROSTER.md.

## Verified locally (2026-10-28, on the final grids)

- **Python suite: 100 passed, 0 failed, 3 known, 4 skipped.** The skips are the scipy-gated
  sound tests (no scipy on this Mac); CI runs them, and nothing sound- or solver-side
  changed.
- **Audit:** 0 dead, 2 frozen (known), 0 tiny. **`gen_fixtures --check`:** every module
  ok, worst difference 0.
- **TS:** `web/physics` 5 / 68 / 13 / 18 (`main` 5 / 68 / 13 / 11). `web/solver` fast tests
  20 + 15. App units 167.
- **e2e** (`build:pages`, Chrome): enjoy **51** (`main` 45), custom 7, drive 11, spec 18, all 0
  failed.
- **Layout** at the S9+'s 846 × 411 / 340 / 300 with a P14 engine picked: the header stays
  one row (40 px), the line doesn't overlap Start, and nothing scrolls sideways.
  **Noticed, not fixed (not P14):** at 846 × 300 the Start button is squashed to 40 px,
  with its label at the bottom edge. It happens with hatch15 too, so on `main` as well.
  `flex-shrink: 0` on `.start` would likely fix it.

## Next

1. Open the PR; read every CI job.
2. The owner listens on the phone: six engines, the first three and the first five.
3. Batch 2 once this merges: the pickup vehicle, then `cummins59`, `cummins67`, `duramax66`
   and `powerstroke73`.
