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
- **Except in the fuel-limit chain's calibration** (the torque limiter and
  the pressure/temperature limit, both run while `_calibrating` is set),
  which uses `engine.RATING_P_AMB` / `RATING_T_AMB` (101325 Pa, 298 K). The
  rating is calibrated in the air every engine was built and validated at,
  and it doesn't move with the weather. So the same pedal gives the same
  fuel in any air: an ECU with no barometric compensation. *(Added in the
  second commit, after the first fix's part-load result below.)*
- `_compressor_point` reads the inlet temperature from the spec and returns
  it as `T_in` (`solve_cycle`'s `compressor`, typed in `solver-port.ts`).

## What changes, and what doesn't

**At standard ambient, nothing.** Every roster engine and preset sets no
ambient, so each runs at 101325 Pa / 298 K, the old defaults (and the
rating's air).
- The cases: `solve_point` at 1200/0.3 and 2400/1.0 on crdi15, crdi_1p5,
  hd_i6, ld_i4, single, hatch15, crdi22, truck127, v8hd and single10, plus
  crdi15's whole `solve_cycle` reply at 2700/0.6.
- Old code (`main` at `ee84ff5`) against the final code: **20 of 21
  replies identical** by sha256 of the whole JSON.
- The 21st, `solve_cycle`, differs only by the **added key**
  `compressor.T_in` (298.0). Its other 51 values are identical, the traces
  compared by sha256.
- *Correction (session 7):* this section first said "identical replies: 21
  of 21". That run predated the `T_in` key, so it was true of the code then
  but not of the code committed.

**Off standard ambient, the solve now moves.** Same point, final code: the
`/spec` edits now equal the direct-pass controls in the first table, value
for value. At 70 kPa: 198.2 N·m (−12%), BSFC 240, AFR 20.7, T_exh 845 K,
soot 2.9×. At 318 K: 224.9 N·m, T_exh 754 K. Half load (crdi15 1500/0.5) at
79.5 kPa (≈2000 m) gets standard's fuel exactly, 23.67 mg, and makes 92.5
instead of 98.6 N·m (−6.2%).

### The first fix, and why it was changed (kept as written)

The first commit read the spec's ambient everywhere, calibration included.
Its numbers, same point:

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

**Correction (session 7): "a torque-based ECU does this" held at full load
only.** Measured the next turn, at part load (crdi15 1500 rpm, half load,
79.5 kPa):
- The full-load fuel limit recalibrated upward, from 47.35 to 53.76 mg
  (+13.5%), to hold the 220.6 N·m cap in thinner air.
- Half pedal is half of that limit, so it got 13.5% more fuel: 26.88 mg,
  and 103.2 instead of 98.6 N·m (**+4.6%**).
- A torque-based ECU would hold 98.6 N·m. An uncompensated one would give
  the same fuel and less torque.
- **More torque from thinner air matches neither.** The first fix was
  internally inconsistent off standard ambient. It was unmerged, so it was
  changed (Fix, above) rather than shipped.
- The mutant "calibration at spec ambient (1st fix)" reproduces it, and the
  test now catches it.

The open question remains, now on a consistent base. Should the modelled
ECU stay uncompensated, which is the final code: the pedal gives fuel, so
torque falls and smoke rises at altitude? Or should it gain a barometric
derate or torque-based control? That is Phase 7's decision. The smoke map's
fixed 101325 Pa (`cycle.fuel_smoke_limit`) is where a barometric correction
would go.

**Answered (2026-10-07, ADR-016 item 2; Phase 7 step 3, #107).** The
common-rail engines get an ECU that knows absolute pressure
(`spec.ecu_modern`); the NA singles stay mechanical, as above. It was
built differently from the sentence before this one:
- No barometric factor on `fuel_smoke_limit`. Off the rating's air, the
  boost target is absolute: the rating's MAP, capped at the compressor's
  map limit.
- The smoke limiter is closed on the air each cycle actually traps
  (`cycle.run(smoke_afr=)`), the way an ECU acts on its MAP sensor.
- At the rating's air neither acts, by construction. Old and new code
  agreed bit for bit on all 10 engines, and the grids were re-stamped
  `f298469f` → `0f1cc94c`.
- Converged, crdi15 at Leh (3500 m): 210.3 N·m and 33% less soot, against
  the mechanical pump's 198.8.
- The small-turbo hatch15 at Leh is held at its AFR limit: −29% torque
  against sea level, and 41% less soot than the mechanical pump.
- The light-load gain from PROPOSAL-phase7's measurement 3 (+8.2%) is
  gone: −1.8%.

## The grid hash

`engine.py` is hashed, so each edit made all 10 prebuilt grids stale by
hash. They were **re-stamped twice** by `tools/restamp_grids.py`: first
`15593c2d…` → `42da745d…` (first commit), then `42da745d…` → `f298469f…`
(the calibration change). Each time, the tool asserted:
1. the package with the previous `engine.py` put back hashes to exactly the
   hash every grid carries;
2. in each of the 10 grid files and the Dyno accuracy table, the only
   change is that 64-byte hash.

The third part is the A/B above, re-run on the final code: on every engine
whose grid ships, old and new code agree bit for bit at the grid's ambient.
The one exception is the added `T_in` key, which no grid holds.
`test_live_grid_pieces_match_the_shipped_grid` also recomputes a shipped
cell with the new code.

## The test, tested

`test_spec_ambient_reaches_the_solve`, 6 parts:
- the default equals an explicit 101325 Pa / 298 K solve exactly;
- 70 kPa cuts AFR by 10% or more and raises NOx and soot;
- 318 K heats the exhaust;
- a spec at 70 kPa equals the standard engine told `p_amb` = 70 kPa
  explicitly;
- half load at 79.5 kPa gets standard's fuel, and less torque;
- the compressor point's `T_in` is the spec's.

The mutants, each on a copy with its edit asserted to apply exactly once
(final code):

| mutant | result | parts failed |
|---|---|---|
| none (baseline) | PASS, 6 of 6 | — |
| both defaults pinned to 101325 / 298 (the old code) | FAIL | 70 kPa; 318 K; spec equals explicit; half load |
| `p_amb` pinned only | FAIL | 70 kPa; spec equals explicit; half load |
| `T_amb` pinned only | FAIL | 318 K |
| compressor inlet pinned to 298 K | FAIL | compressor `T_in` |
| calibration at the spec's ambient (the first fix) | FAIL | spec equals explicit; half load (26.88 mg, 103.2 N·m) |

5 of 5 caught, none by an error. *(Was, for the first commit: 5 parts, 4 of
4 mutants caught.)*
