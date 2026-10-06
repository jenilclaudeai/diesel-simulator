# FINDING-024 — MFB50 counted combustion before TDC last, and came out late

**Opened by:** Phase 6, building the cycle page (ADR-015), which shows MFB50.
Reading `CycleSolver.mfb50` to place its marker.
**Lens:** PHY1 (lead), QA2
**Status:** **fixed** (`fix/mfb50`). It is a reported figure only: no physics,
sound or grid reads it.
**Reproduce:** `test_mfb50_counts_combustion_before_tdc`

---

## What was measured

`mfb50` cumulates the heat-release trace from index 0 of the cylinder's own
crank axis. Index 0 is **firing TDC** (`soi_main = 720 − soi_deg_btdc`). So
combustion just before TDC (around 700–719°) sits at the *end* of the array,
and was counted **after** everything that burns once the piston is past TDC.

Each solved point's MFB50, against the same 50% point accumulated from
gas-exchange TDC (360°) (`bridge.solve_cycle`, `n_cycles = 9`, 2026-10-05):

| point | MFB50, as reported | from 360° | heat before TDC |
|---|---|---|---|
| crdi15 2000 rpm / 0.60 | +11° | +10° | 5.5% |
| crdi15 1800 / 0.25 | +6° | +6° | 5.7% |
| hd_i6 1400 / 0.90 | +14° | +12° | 7.8% |
| **single 2000 / 0.50** | **+7°** | **0°** | **40.8%** |

The error grows with the share of heat released before TDC. On a late-injecting
common-rail engine it is a degree or two; on the old mechanical single,
which starts burning well before TDC, it is 7°.

## Who reads it

- `CycleResult.mfb50` → `batch.py`'s summary row, and `bridge.solve_cycle`
  (new in Phase 6, for the cycle page). Nothing else.
- No physics model, sound source, grid cell or golden value reads it, so the
  fix changes no simulated result.

## Fix

Accumulate from gas-exchange TDC: roll the trace and its angles by half a
cycle (`k = n // 2`) before the cumulative sum. The returned angle keeps its
convention (−360 to +360, 0 = firing TDC).

## The grid hash

`cycle.py` is hashed, so the edit marked all 10 prebuilt grids stale. They
were **re-stamped** `dee93a17…` → `a442cfb3…`, with this proof:

- **The only hashed change.** Re-hashing the package with the pre-fix
  `cycle.py` gives exactly `dee93a17…`, the hash every grid carried.
- **It can't reach a cell.** `mfb50` has no reader on any grid-building path.
  The grep above finds it only in `cycle.py`, `batch.py` and `bridge.py`.
  `test_live_grid_pieces_match_the_shipped_grid` (a shipped `crdi15` cell
  recomputed with the new code) holds: worst difference 0.00e+00, warm and
  cold.
- **Only the hash string changed.** Each file was edited by replacing the
  old hash, asserted to appear exactly once. In each of the 10 files the
  changed span is the 64 bytes of the hash, and the size is unchanged.

**Correction (2026-10-06): the re-stamp missed one artifact.** The Dyno
page's accuracy table (`web/app/src/app/dyno/accuracy.ts`, FINDING-013) is
also keyed on the grid hash, as `ACCURACY_SOLVER`. Left at `dee93a17`, it
turned every engine's measured note into "not measured for this solver
build". Found a day later while building the sweep page, which reuses that
note. It's re-stamped here to `a442cfb3`, by the same proof: the fast-path
and converged torques it compares can't be moved by MFB50's accumulation.
`test_accuracy_table_is_for_this_build` now fails whenever the table, the
grids and the build disagree; the stale table fails it. *(Was: the proof
above listed only the 10 grids.)*

## Tests

- `test_mfb50_counts_combustion_before_tdc`:
  - synthetic, equal heat in the 20° before and after TDC: −1° (the old
    code: +19°);
  - `single` at 2000 rpm and 50% load: the solver's MFB50 equals an
    independent computation from the traces (0.0°).
- **Mutant:** the old accumulation, from index 0, fails it (+19 synthetic,
  +7.0 on `single`).
- After the change:
  - the full suite: 73 passed, 0 failed, 3 known (with scipy; +2 since
    #88: this test and `test_solve_cycle`);
  - the dead-signal audit: 0 / 2 / 0 (unchanged);
  - fixtures: 7 of 7 current.
