# PROPOSAL — Phase 7 step 4: the weather table's shape, measured

**Date:** 2026-10-08 (session 8)
**Status:** **decided 2026-10-09: A3** ("A3, go ahead"; ADR-016 addendum). Being built. *(Was: "for the owner's decision. Nothing is built.")*
**Lenses:** PM, PHY2 (interpolation error), SW1/SW2 (format, cost), QA2

ADR-016 item 1 decided **a per-engine table of torque factors** for Drive
and Enjoy, fitted from converged solves and blended at run time. The
proposal said "within 1.15%", measured on 9 cells on #101's code. Measured
again on today's code (after #107's ECU and FINDING-026's fix), the
table's shape decides its accuracy, and the two choices that matter are
yours: **which cells** and **which airs**.

## What was measured

`crdi15` and `hatch15`, 312 converged solves each (as `bridge.live_cell`
solves, on the shipped grid's row fuel):
- 12 "coarse" cells: rpm rows 0/2/4/6 × loads 0.2/0.6/1.0;
- 20 airs: 4 pressures (101.3/86/72/58 kPa) × 3 temperatures (−20/25/45 °C)
  as table nodes, plus 8 held out: the four presets, three off-node airs
  and 52 kPa (beyond the nodes);
- 6 cells left out (rows 1/3/5 × loads 0.4/0.8), solved at the 12 node
  airs, to measure blending from the coarse cells to the others.

**Error is shown as a driver feels it:** |predicted − solved| torque as a
share of standard air's full-load torque at that rpm. (As a share of the
solved value, light load inflates it: a few N·m of a 31 N·m cell reads
11%.)

| | crdi15 | hatch15 |
|---|---|---|
| **no correction** (Drive today), at the presets | 32.6% | 35.3% |
| 12-air table, at the presets | 2.0% | 2.35% |
| 12-air table, any held-out air (down to 52 kPa) | 5.2% | 3.8% |
| 8-air table (3 p × 3 T), at the presets | 3.6% | 2.35% |
| 8-air table, any held-out air | 5.2% | 5.5% |
| 6-air table (3 p × 2 T), at the presets | 6.6% | 4.0% |
| **coarse cells → the others** (node airs, worst at 58 kPa / −20 °C) | **10.2%** | **7.8%** |

**The finding:** blending across air is fine. Blending across cells is
not. The coarse cells straddle the full-load knee, where the smoke limiter
starts trimming fuel in thin air, and bilinear blending cuts it off. That
error goes away if every grid cell is solved, at the cost of solve count.

## The options

Costs are per engine, from this session's measured wall time per converged
solve on this Mac (7 workers: crdi15 5.4 s, hatch15 7.0 s). The truck and
the V8 take about 1.35× longer, as their grid builds do (19.5–20.5 against
14.5 min). The browser figure uses ADR-014's measured pace: 104 pieces in
21.5 min on 8 cores, so about 12.4 s per piece. That comes **on top of**
the drivable grid's own 21.5 min.

| option | solves per engine | native, per engine | browser, custom engine | felt torque error | any air? (P06's climbing roads) |
|---|---|---|---|---|---|
| A1. 12 coarse cells × 11 airs | 132 | 12–15 min | ~27 min | 2.0–2.4% at presets; **up to 7.8–10.2% between cells** | yes |
| A2. all 48 cells × 11 airs | 528 | 47–62 min (truck/V8 ~80) | ~1.8 h | 2.0–2.4% at presets; 3.8–5.2% anywhere | yes |
| **A3. all 48 cells × 8 airs (recommended)** | 384 | 34–45 min (truck/V8 ~60) | ~1.3 h | 2.4–3.6% at presets; 5.2–5.5% anywhere | yes |
| A4. all 48 cells × the 4 presets | 192 | 17–22 min | ~40 min | **exact at the presets** (the grid's own blending only) | **no**: Drive offers the presets only, so a climbing road would need a later upgrade |

Positives, each:
- **A1** is the fastest to build, and the error at the cells it solved is
  small. But a driver crossing the knee at altitude could see a 10% step
  that isn't physics.
- **A2** is the most accurate for any air, and the roster's build is a
  one-off (about 5 h natively for all five engines, overnight). It is the
  slowest in a browser.
- **A3** solves every cell, so the 10% error is gone, and it supports
  every air, including P06's climbing roads. It costs about a quarter
  fewer solves than A2 (the roster about 4 h natively), for 0–1.5 points
  more error at the presets (crdi15 2.0 → 3.6%; hatch15 unchanged at
  2.35%).
- **A4** is exact where people will actually drive, and the cheapest that
  solves every cell. But Drive would be limited to the five places, and
  P06's altitude-along-the-road (tier 1, v1) would need A2 or A3 later
  anyway.

Common to all:
- Planned: the table lives in the grid file as one new key, so the cell
  data is untouched. Its code would go in excluded files (`bridge.py`,
  `live.py`), so the grid hash doesn't move. It is warm only: one factor
  serves warm and cold (`blend_perf_T`), and sound and friction stay the
  grid's, as ADR-016 says.
- It corrects indicated torque, fuel flow, boost, turbo speed, AFR and
  exhaust temperature. Measured with the 12-air table over the held-out
  airs (52 kPa excluded), at the coarse cells, the other keys are within
  2.0–4.7% (relative), and exhaust temperature within 27 K (hatch15) to
  48 K (crdi15). The exhaust temperature is the weakest; it drives only a
  dial.
- In the browser it would be built from resumable pieces, like ADR-014's
  grid, so a server can run the same pieces later (v2's P04).
- It is measured on two engines. The build would check every engine's
  table against a few held-out solves and write the worst error into the
  file, so the page can say it.

## Decision needed

**Which shape: A1, A2, A3 (recommended) or A4?** And, if A4: is Drive
limited to the five presets acceptable, given that P06's climbing roads
will want any air?
