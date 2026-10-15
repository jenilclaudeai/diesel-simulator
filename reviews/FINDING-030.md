# FINDING-030 — P09's cold cells carry ~~about 10×~~ 6–140× the friction of a real cold start

**Opened by:** session 9 (2026-10-15), reading the full suite after P09's
rebuild. P08's automatic test failed, and the cause was in the grids'
cold cells.
**Lens:** PHY1 (lead), PHY2, the driver's view
**Status:** ~~**open, for the owner.** The rebuilt grids are not committed.~~
**Fixed (option A, the owner's choice, 2026-10-15)** on `feat/p09-cold-friction`;
the grids' cold cells re-solved (`tools/rebuild_cold_cells.py`). See "Decided and fixed" below.
**Reproduce:** `out/cold_fric.py` and `out/p08_cold.py` (scratch, not kept;
the numbers are below).

---

## What was measured

P09 (ADR-019) made the grid's cold cells a true cold start
(`engine.cold_start_walls`): every chamber wall, liner included, at 273 K.
The oil is left warm (373 K). crdi15 at 1343 rpm and 0.2 load, friction by
component (kW):

| | liner top/bottom | rings | skirt | others | FMEP | brake torque |
|---|---|---|---|---|---|---|
| warm | 440 / 383 K | 0.21 | 0.04 | 1.39 | 0.98 bar | 36.7 N·m |
| cold before P09 (walls by `WALL_FOLLOW`) | 363 / 299 K | 0.39 | 0.31 | 1.40 | 1.26 bar | 34.0 N·m |
| **cold, P09** | 273 / 273 K | **2.47** | **19.13** | 1.42 | **13.73 bar** | **−109.3 N·m** |

The cause is in `friction.py`: the skirt's film viscosity is taken at
**liner − 20 K**, and the rings' at `min(liner + 25, oil + 95)`. With the
liner at 273 K, the skirt's oil is at 253 K (−20 °C). That is colder than
the metal, the air and the oil. The offset suits a hot running liner. The
hydrodynamic skirt term scales with viscosity, so it grows about 500×.

In the shipped crdi15 grid the cold cells lose 150–230 N·m of brake torque
against warm, where before P09 they lost 4–9 N·m. At 1343 rpm, full pedal
makes 39 N·m cold, against 199 warm.

## What it does to the app

- **The torque the driver feels is not affected.** The live loop's torque
  is the blend's indicated torque minus the **live** friction
  (`LiveEngine._perf`). The live friction sets its walls from the coolant
  by `WALL_FOLLOW`.
- **The automatic's choice of gear is affected for the first minutes of
  every drive.** P08's fuel map (`_econ_map`) reads the cells' **brake**
  torque, blended at `T_chamber`, which starts at the air's temperature.
  Held cruises from a cold start, 120 s (`out/p08_cold.py`):

  | | `main` | this branch |
  |---|---|---|
  | crdi15 30 km/h | 3rd | 4th |
  | crdi15 50 km/h | 5th, steady | **7th, 7 shifts in the last 20 s (hunting)** |
  | crdi22 30 km/h | 4th | 4th (2nd at 60 s) |
  | crdi22 50 km/h | 6th | 6th (4th at 60 s) |

  A warm engine is unaffected. P08's test passes 7 of 7 once its helper
  warms `T_chamber` too.
- **The files' cold columns** (`perf_cold`: torque, fmep, bsfc) carry the
  13.7 bar.
- The open note in STATUS, "the −20 °C cold-oil idle torque reads
  −1561 N·m", looks like the same family: film temperatures taken far below
  the range the model was set up for.

## Options

| option | positives | costs |
|---|---|---|
| **A. The cold cells' friction at `WALL_FOLLOW`'s walls**: the cold walls feed the combustion and heat transfer (P09's purpose), and friction sees the walls the live loop's friction sees | consistent with the live loop; P09's knock is unchanged (the walls' temperatures for combustion stay); small, contained change | `engine.py` or `grid.py` is hashed: another full rebuild (about 9.7 h) |
| B. The automatic's map ignores the cells' friction: indicated torque minus the live friction scaled to each candidate rpm | no rebuild (`live.py` is unhashed); fixes the hunting | the files' cold columns stay wrong (13.7 bar); the TS port and the live fixtures change |
| C. Fix the film temperatures in `friction.py` (a film no colder than both the liner and the oil), and check the cold FMEP against published cold-start data (about 2–3× warm at 0 °C) | fixes the cause, and probably the −1561 N·m too | a calibration with little data; touches every cold solve (Dyno, Cycle); a rebuild |

**Recommendation: A now, C as its own finding later.** A restores what the
cold cells had before P09 for friction, and keeps P09's cold combustion.

## Decided and fixed (2026-10-15, session 9, a second session)

**The owner chose A**, asked in parallel by a second session that had found
the same thing in the P09 grid's crdi15 file before reading this finding.

**Correction to the size, kept visibly above:** "about 10×" is crdi15 at
one cell. Over every cell of the ten P09 grids the cold/warm FMEP ratio is
**5.8–139×** (crdi22 the worst; crdi15 5.8–50.7×). `main`'s grids, before
P09: 1.08–2.84×.

**The fix** (`engine.py`): `cold_start_walls` records the liner that
`WALL_FOLLOW` gives at the coolant (`_friction_liner`), and
`operating_point` hands that liner to `friction.evaluate`, restoring the
cold one after. `_apply_thermal_state` drops it, so an engine warmed back
is the warm engine again. Measured on six crdi15 cells, converged,
against the P09 rebuild:

- warm cells: **0 differences** in every perf field;
- cold cells, gas side (p_max, T_exh, boost, fuel, AFR, indicated torque,
  the knock): identical to 6.7e-16;
- cold FMEP back to `main`'s: 1343 rpm / 20% 1.25 bar (P09 13.72, `main`
  1.25); 4057 / 80% 2.02 (P09 39.74, `main` 2.02).

On six more cold cells (one unsettled), only the fields friction reaches
moved: perf `torque`, `power`, `bsfc`, `fmep`, `nox` (g per brake kWh), and
meta `Pb`, `load`. The pressure traces and all six source waveforms are
byte-identical.

**Tests:** `test_cold_start_friction_sees_the_running_walls` (solver, runs
under Pyodide) and `test_shipped_grids_cold_friction` (every grid's cold
FMEP ≤ 4× warm; SKIPs without the grids). Mutants **5 of 5 caught**,
baseline passing: the fix off; friction fed the 273 K liner; the liner not
restored; `_apply_thermal_state` keeping the friction liner; the P09
rebuild's grids.

**No full rebuild.** Only the cold cells can change: the warm cells
(measured, 0 differences) and the weather table (warm solves:
`bridge.live_weather_cell` calls `solve_cell` without `T_coolant`) cannot.
`tools/rebuild_cold_cells.py` re-solves the 48 cold cells per grid and
refuses unless: the pre-change tree hashes to the grids' stamp; each cold
cell changes only in the fields above; every other key is untouched. It
re-stamps the hash and the Dyno's accuracy table (warm). About 80 min
against 9.7 h.

**Still open:** C, the film temperatures themselves (a film colder than
the liner, the oil and the air is outside the model's range), with the
−1561 N·m cold-oil note. Its own finding, later.
