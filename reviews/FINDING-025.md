# FINDING-025 — The spec's ambient pressure and temperature reached no solve

**Opened by:** session 7 (2026-10-06), reading the solver's ambient inputs
before proposing Phase 7 (environment). The spec editor offers "Ambient
temperature" and "Ambient pressure" as primary thermal fields
(`web/app/src/app/spec/spec-meta.ts:37`).
**Lens:** PHY1 (lead), QA2, USR1
**Status:** **fixed** (`fix/spec-ambient`). Nothing changes at standard
ambient: every roster engine and preset is bit-identical (below).
**Reproduce:** `test_spec_ambient_reaches_the_solve`

---

## What was measured

`DieselEngine.operating_point` took `p_amb=101325.0, T_amb=298.0` as fixed
defaults, and no caller in the package passed anything else. The spec's
`thermal.ambient_p` was read **nowhere** (`grep` over `dieselsim/`).
`thermal.ambient_T` was read only by the radiator and by the live loop's
warm-up and charge-air cooler, never by a cycle solve.

The repo's pattern again: a mechanism fully built and correctly wired (the
cycle, the turbo and the air filter all take `p_amb`/`T_amb`), fed a constant,
raising no error. `tools/audit_dead_signals.py` could not see it, because
it checks outputs that never vary, not inputs that are never read.

crdi15, 2500 rpm, full load, `n_cycles = 9`, through `bridge.solve_point` as
the app calls it (2026-10-06):

| case | torque, N·m | BSFC, g/kWh | boost PR | AFR | T_exh, K | NOx, g/kWh | soot, g/kWh | outputs that moved |
|---|---|---|---|---|---|---|---|---|
| default spec | 225.9 | 210.7 | 2.47 | 29.41 | 740.8 | 2.793 | 0.01815 | — |
| spec ambient_p = 70 kPa (≈3000 m) | 225.9 | 210.7 | 2.47 | 29.41 | 740.8 | 2.793 | 0.01815 | **0 of 8** |
| spec ambient_T = 318 K (45 °C) | 225.9 | 210.7 | 2.47 | 29.41 | 740.8 | 2.793 | 0.01815 | **0 of 8** |
| *control:* `p_amb=70000` passed directly | 198.2 | 240.0 | 2.65 | 20.68 | 845.4 | 5.841 | 0.05353 | 8 of 8 |
| *control:* `T_amb=318` passed directly | 224.9 | 211.6 | 2.41 | 28.56 | 754.3 | 3.038 | 0.02102 | 8 of 8 |

(The 8: torque, BSFC, boost PR, AFR, T_exh, p_max, NOx, soot.)

## Who was affected

Every solving page reads the spec through `operating_point`: Dyno, Grid,
Cycle, Sweep and Durability. A user who set altitude or heat on `/spec` got
sea-level, 25 °C numbers with no warning. A Sweep over `thermal.ambient_p`
drew a flat line.

An edited engine's drivable grid ("Drive it") was built at 101325 Pa / 298 K,
while the live loop ran its radiator and charge-air cooler at the spec's
`ambient_T`. So the two halves of the same drive disagreed about the air.

`bridge._compressor_point` also fixed the compressor inlet at 298 K when
correcting the flow for the cycle page's compressor map.

## Fix

- `operating_point(p_amb=None, T_amb=None)`: None, which every caller in the
  package uses, reads `spec.thermal.ambient_p` / `ambient_T` at call time.
  An explicit value still wins, so the diagnostic tools and the tests that
  pass one are unchanged.
- `_compressor_point` reads the inlet temperature from the spec and returns
  it as `T_in` (`solve_cycle`'s `compressor`, typed in `solver-port.ts`).

## What changes, and what doesn't

**At standard ambient, nothing.** Every roster engine and preset sets no
ambient, so each runs at 101325 Pa / 298 K, the old defaults. The old code
(`main` at `ee84ff5`) and the new code gave **identical replies**: 21 of 21
cases by sha256 of the whole JSON. The cases were `solve_point` at
1200/0.3 and 2400/1.0 on crdi15, crdi_1p5, hd_i6, ld_i4, single, hatch15,
crdi22, truck127, v8hd and single10, plus crdi15's whole `solve_cycle` reply
at 2700/0.6.

**Off standard ambient, the solve now moves** (same point, after the fix):

| spec | torque | BSFC | AFR | T_exh | soot |
|---|---|---|---|---|---|
| 70 kPa | 218.3 | 246.3 | 18.98 | 890 K | 0.0663 |
| 318 K | 227.4 | 213.7 | 27.58 | 766 K | 0.0234 |

These don't equal the direct controls above, and they shouldn't. The
torque limiter's calibration also calls `operating_point`, so it now runs at
the spec's ambient too. The modelled ECU therefore adds fuel to hold its
torque target where the air allows, up to the smoke limit: at 3000 m, 218
instead of 198 N·m, at AFR 19 and 3.7× the soot. A torque-based ECU does
this. Whether that is the behaviour we want is a **Phase 7 question, not
part of this fix:**

- `fuel_limit_raw` builds its smoke limit from a *scheduled* pressure ratio
  times **101325 Pa** (`cycle.fuel_smoke_limit`), not from absolute manifold
  pressure. At altitude it allows sea-level fuel on thin air. A
  mechanical pump without an altitude compensator does exactly that; a
  modern ECU derates from its barometric sensor.
- At 318 K the calibrated torque rises 0.7% (more fuel, worse BSFC), where
  SAE J1349-style correction would expect a loss. It holds the target until
  a limit binds; no thermal derate acts on intake temperature at this point.

## The grid hash

`engine.py` is hashed, so the edit made all 10 prebuilt grids stale by hash.
They were **re-stamped** `15593c2d…` → `42da745d…` by
`tools/restamp_grids.py`, which asserted:
1. the package with `main`'s `engine.py` put back hashes to exactly
   `15593c2d…`, the hash every grid carries;
2. in each of the 10 grid files and the Dyno accuracy table, the only
   change is that 64-byte hash.

The third part is the A/B above: on every engine whose grid ships, old and
new code agree bit for bit at the grid's ambient.
`test_live_grid_pieces_match_the_shipped_grid` also recomputes a shipped
cell with the new code.

## The test, tested

`test_spec_ambient_reaches_the_solve`, 5 parts: the default equals an
explicit 101325 Pa / 298 K solve exactly; 70 kPa cuts AFR by 10% or more and
raises NOx and soot; 318 K heats the exhaust; a spec at 70 kPa equals an
explicit `p_amb` of 70 kPa; and the compressor point's `T_in` is the spec's.
The mutants, each on a copy with its edit asserted to apply exactly once:

| mutant | result | parts failed |
|---|---|---|
| none (baseline) | PASS | — |
| both defaults pinned to 101325 / 298 (the old code) | FAIL | 70 kPa; 318 K; spec equals explicit |
| `p_amb` pinned only | FAIL | 70 kPa; spec equals explicit |
| `T_amb` pinned only | FAIL | 318 K |
| compressor inlet pinned to 298 K | FAIL | compressor `T_in` |

4 of 4 caught, none by an error.
