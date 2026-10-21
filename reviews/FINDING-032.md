# FINDING-032 — The live loop's radiator, fan ~~and~~ and drag breathe sea-level air everywhere

**Opened by:** session 10 (2026-10-20), measuring P06 tier 2's goals (whether
"reach the pass without overheating" can be lost).
**Lens:** PHY1, PHY2, QA1
**Status:** ~~**open, for the owner.** Nothing changed yet.~~ **Decided (the owner,
2026-10-20): A**, fix it as its own PR (from `main`). **Then widened (the owner, the same day):
the drag too**: it had the same fixed 1.20 (below). **Fixed** on `fix/finding-032-air-density`.
**Reproduce:** scratch scripts in the session's job directory:
`p06_density_probe.py` and `p06_longclimb_probe.py`. Both patch
`LiveEngine._thermal` in memory only; the repo is untouched.

---

## What is wrong

`live.LiveEngine._thermal` fixes the air's density at `rho_air = 1.20`
kg/m³:
- The ram air through the grille is `rho_air · A · v`.
- The fan's flow is `fan_max_flow` (4.5 kg/s, a mass flow).

Neither reads the place's air. Everything else in the loop does: the
weather table corrects the cells (Phase 7 step 4), and `ambient_T` already
sets the radiator's inlet temperature.

Real fans move roughly a fixed **volume**, so their mass flow falls with
density, and so does the ram air. At Leh (65.8 kPa, ρ 0.78) a radiator
loses about a third of its air mass flow.

It is FINDING-025's shape: **an input that nothing reads**. The place's
pressure reaches `spec.thermal.ambient_p`, and the cooling never looks at
it.

On a P06 route it is half a model. Climbing 1,000 m cools the air by
6.5 K, which helps the radiator and is modelled. It also thins the air by
about 10 %, which hurts the radiator and is not.

## What it changes (measured)

The probe scales the ram air and the fan by ρ / 1.20 with ρ = p / (287.05 T).
Every run is flat out with the automatic, from a warm start.

| engine, place, climb | peak coolant, ρ 1.20 | peak coolant, the place's ρ |
|---|---|---|
| truck127, Leh (ρ 0.78), the pass | 94.9 °C | 95.3 °C |
| v8hd, Leh, the pass | 94.9 °C | 96.0 °C |
| hatch15, Leh, the pass | 89.4 °C | 90.3 °C |
| truck127, desert (ρ 1.09), the pass | 95.8 °C | **99.0 °C** |
| v8hd, desert, the pass | 94.9 °C | 97.2 °C |
| truck127, desert, 15 km at 7 % | 95.0 °C | 96.2 °C |
| v8hd, desert, 15 km at 7 % | 95.0 °C | 95.6 °C |
| hatch15, desert, 15 km at 7 % | 90.6 °C | 90.9 °C |

The warning is at 100 °C, the derate at 107 °C, the stop at 120 °C.
- **The largest change is +3.2 °C**, and no run crossed the warning
  either way.
- The fans have the margin: they hold full load at 42 °C in thin air,
  which is how real cooling is sized.
- Time moves by under 2 % (truck127 at Leh: 387 s to 391 s). Fuel moves by
  up to 2.4 %: truck127 at Leh 8.738 L to 8.949 L, v8hd 9.351 L to
  9.568 L.

So this is a correctness gap, **not a gameplay one**: today's roster
behaves the same within 3.2 °C.

## Options

- **A, fix it:** scale `rho_air` and the fan's mass flow by the place's
  density, in `live.py` and `web/physics/src/live/engine.ts`.
  - *Positives:* physically right; consistent with Phase 7, where every
    other part of the loop already sees the air; P06's climbs then thin
    the radiator's air as well as cooling it; a slow, heavily loaded climb
    at Leh would show it.
  - *Trade-offs:* the live fixtures move wherever the air isn't standard
    (the weather drives and P06's random route): regenerate them with
    `--only live` and re-match the TS port.
  - No grid goes stale (`live.py` is outside the hash). About an hour with
    mutants.
- **B, state it:** leave the model and note it under the dash's weather
  line.
  - *Positives:* no fixture churn.
  - *Trade-offs:* a known wrong input stays; the next feature that leans on
    cooling at altitude inherits it.

**Recommendation: A**, small and measured, as its own PR. Nothing in P06's
goals waits on it.

## The drag too (found while fixing)

`Driveline.resistance` had the same constant: `f_aero = 0.5 · 1.20 · CdA ·
v²`. The owner widened the fix to it. Measured with the place's density,
flat out from rest on the open road with the automatic:

| engine, place | ρ 1.20: at 60 s / top in 300 s | the place's ρ | top speed |
|---|---|---|---|
| hatch15, Leh (ρ 0.79) | 179.0 / 181.4 km/h | 187.0 / 187.8 km/h | +3.5 % |
| truck127, Leh | 87.3 / 107.4 km/h | 92.2 / 114.0 km/h | +6 % |
| hatch15, desert (ρ 1.10) | 182.9 / 183.1 km/h | 184.2 / 184.4 km/h | +1 % |
| truck127, desert | 88.5 / 107.8 km/h | 89.7 / 109.1 km/h | +1 % |

## Fixed

- **One rule** for the live loop: `live.air_density(thermal)` =
  `RHO_RATING` (1.20) × (p / 101325) × (298 / T), scaled from the rating's
  air. That is where the cooling and the drag were set.
  - At the rating's air every factor is exactly 1.0. The radiator's ram
    air, the fan's mass flow (a fan moves a volume) and the drag all follow
    it.
  - `LiveEngine.step` puts it in `Driveline.rho_air` each frame. A
    `Driveline` made on its own keeps 1.20.
  - Mirrored in `web/physics` (`airDensity`, `RHO_RATING` in
    `driveline.ts`).
- **Proof that nothing at standard air moved:** the live fixture, drive by
  drive.
  - The seven standard-air drives: 0 values changed (about 172,000).
  - Only `dl.rho_air` was added.
  - The weather drive changed in 10,710 values, the cold limp drive in
    11,028, and the waxed drive in 61 (a waxed car doesn't move).
- **A new fixture drive, `adr011_weather_fan`:** Leh's air with the fan
  running. No existing drive ran the fan at non-standard air, and the TS
  mutant "the fan's mass flow unscaled" survived until it was added.
- **Tests:** `test_finding_032_the_air_density`, 5 parts, on the toy grid
  (it runs under Pyodide):
  - exactly 1.20 at the rating's air;
  - Leh's density from p and T;
  - the push into the driveline each frame;
  - the drag difference equals ½·Δρ·CdA·v²;
  - the radiator's air scales by ρ / 1.20.
  - Mutants: Python 5 of 5 caught, TS 4 of 4 caught (against passing
    baselines).
- **On the way:** a same-length mutant restored within one second left a
  stale `.pyc`, and one fixture regeneration ran on the mutant. It was
  caught by the TS port disagreeing, then regenerated with clean caches.
  Mutant runs now use `PYTHONDONTWRITEBYTECODE=1` (CLAUDE.md).
- No grid goes stale (`live.py` is outside the hash).
