# FINDING-032 — The live loop's radiator and fan breathe sea-level air everywhere

**Opened by:** session 10 (2026-10-20), measuring P06 tier 2's goals (whether
"reach the pass without overheating" can be lost).
**Lens:** PHY1, PHY2, QA1
**Status:** **open, for the owner.** Nothing changed yet.
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
