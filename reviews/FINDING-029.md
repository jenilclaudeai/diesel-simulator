# FINDING-029 — Altitude lengthens the ignition delay, but the knock mostly falls, and the live loop can't hear it

**Opened by:** session 9 (2026-10-14), measuring the owner's Feat Prop
**P09**, "Knocking: Increased knocking on high altitude"
(`reviews/PROPOSAL-P09.md`).
**Lens:** PHY1 (lead), PHY2, the sound lens
**Status:** **open, for the owner.** Nothing in `dieselsim/` is changed.
**Reproduce:** `python3 tools/p09_altitude_knock.py .` (about 2 min). The
prototype variants below were run on a scratch copy of `dieselsim/`, with
the patch given in the proposal.

---

## What was measured

"Knock" here is what the synth reads: `EngineSound.build_sources(op)
["_meta"]["dpdt_max"]`, the peak rate of the **combustion** part of the
pressure rise (the trace less the motored trace, FINDING-002), in Pa/s. It
sets both the combustion part's level and how hard it rings the block's
high modes (`sharp`, FINDING-003).

Three airs: sea level (101325 Pa, 298 K), Leh as the app has it (3500 m,
65.8 kPa, 20 °C) and 5000 m (54.0 kPa, 10 °C). `n_cycles=9`, each a fresh
engine.

| engine, point | delay sea → Leh → 5000 m (°CA) | premixed fraction | knock, sea (×1e9) | Leh | 5000 m |
|---|---|---|---|---|---|
| crdi15, 800 rpm, 5% | 1.88 → 2.66 → 3.60 | 0.72 / 0.72 / 0.72 | 1.24 | **−13%** | −19% |
| crdi15, 2000, 30% | 2.57 → 2.72 → 2.78 | 0.31 → 0.33 → 0.34 | 5.82 | −7% | −10% |
| crdi15, 2400, 100% | 2.32 → 2.34 → 2.41 | 0.10 → 0.10 → 0.11 | 7.66 | −12% | −19% |
| single10 (no turbo), 600, 5% | 3.92 → 5.82 → 7.85 | 0.72 / 0.72 / 0.72 | 0.70 | +3% | 0% |
| single10, 1100, 30% | 6.26 → 9.13 → 12.41 | 0.47 → 0.69 → **0.72** | 2.22 | **+7%** | −5% |
| single10, 1320, 100% | 7.18 → 10.56 → 15.05 | 0.20 → 0.29 → 0.41 | 1.88 | −14% | −21% |
| truck127, 600, 5% | 2.17 → 2.97 → 4.37 | 0.72 / 0.72 / 0.72 | 1.15 | −4% | −35% |
| truck127, 900, 30% | 1.98 → 2.08 → 2.12 | 0.29 → 0.30 → 0.31 | 4.60 | −8% | −12% |
| truck127, 1080, 100% | 1.84 → 1.95 → 2.09 | 0.09 → 0.13 → 0.16 | 5.48 | **+6%** | 0% |

- **The delay responds as it should.** Hardenberg-Hase sees the lower
  compression pressure: +41% to +91% at idle. On the turbo engines under
  load the modern ECU's absolute boost target (ADR-016) restores most of
  the charge (crdi15 at 2000 / 30%: pressure ratio 1.50 → 1.91), so the
  delay grows only 1–6% there. That part is realistic.
- **The knock does not follow it.** It falls at 6 of 9 points at Leh, by
  4–14%. The three rises are small: single10 at idle (+3%), single10 at a
  cruise (+7%; its premixed fraction 0.47 → 0.69), and truck127 at full
  load (+6%), where the smoke limiter cuts the fuel 348 → 269 mg, so the
  shorter injection is more premixed.

## Why: two things in `cycle.py`

1. **The premixed fraction is capped at 0.72**
   (`premix[c] = min(0.72, max(0.02, b))`, FINDING-001 P-2), and it sits
   on the cap at every idle point of all three engines, at every air. At
   idle the whole injection is over before ignition (`tau / dur_main` is
   well above 1), so a longer delay can't add premixed fuel. The pattern
   CLAUDE.md warns about: a mechanism fed a quantity pinned at a clamp.
2. **The premixed burn slows as the mixture gets richer.** Its duration
   is `d_pre = max(4, 0.30 × burn_dur)`, and
   `burn_duration = 1.3 × inj_dur + 12 + 30 × φ + 0.004 × rpm`. Thinner
   air raises φ at the same fuel, so the premixed spike burns over more
   crank angle and its peak dp/dθ falls. The literature says the
   opposite: a longer delay leaves more prepared mixture and a more abrupt
   premixed burn (the proposal's sources).

Together with the later combustion phasing (the burn starts further past
TDC, where the volume grows), these outweigh the extra premixed fuel.

## And the live loop can't hear altitude at all

Drive and Enjoy read the grid's sound sources, solved at the standard air.
The weather table (Phase 7 step 4) corrects only
`torque_ind, fuel_kg_h, boost, turbo_rpm, afr, T_exh`. Its docstring says
so: "friction and sound stay the grid's". So at Leh the knock you hear is
the sea-level knock, whatever the solver says. The table's air range is
58–101 kPa, so 5000 m (54 kPa) would be clamped to 58 kPa there anyway.

## What a fix would cost (prototype, scratch only)

Two variants on a scratch copy, run with a switches-off pass first that
matched the baseline at **27 of 27 points, exactly**:

- **V1:** the premixed burn's duration loses its φ term (it burns the
  mixture the delay prepared, not the global one).
- **V2:** V1, and the cap 0.72 → 0.95.

| point | knock at Leh, today | V1 | V2 | sea-level knock, V1 against today |
|---|---|---|---|---|
| crdi15 idle | −13% | **+21%** | +25% | −7% |
| crdi15 2000 / 30% | −7% | 0% | 0% | +18% |
| crdi15 2400 / 100% | −12% | −7% | −7% | +17% |
| single10 idle | +3% | +5% | +5% | +16% |
| single10 1100 / 30% | +7% | **+18%** | +18% | +9% |
| single10 1320 / 100% | −14% | +1% | +1% | +23% |
| truck127 idle | −4% | −8% | −8% | +5% |
| truck127 900 / 30% | −8% | −2% | −2% | **+31%** |
| truck127 1080 / 100% | +6% | **+14%** | +14% | +25% |

V1 turns the trend the right way at most points, but **it moves sea level
by −7% to +31%**, where the engines are calibrated and where the owner just
signed off the sound (ADR-018). V2's cap mostly makes idle louder at sea
level. Neither is a fix as it stands: a real one needs the premixed burn
re-derived and the engines re-checked against their brochure numbers.

## And it would barely be heard

With the P10 balance, even V1's change is inaudible. Multiplying the knock
in the synth by V1's ×1.14–1.21 moves the cabin, intake and engine-bay
mics by 0.0–0.4 dB, and by ×2 only 0.1–2.0 dB. The exhaust now carries
the sound. Details and the options are in `reviews/PROPOSAL-P09.md`.

## Added 2026-10-14, later: the sound's knock value depends on the crank step

**Measured** (crdi15 idle, the same solve at 1.0°, 0.5° and 0.25° steps):

| | the sound's `dpdt_max`, ×1e9 | the solver's `dpdtheta_comb`, bar/° |
|---|---|---|
| today, sea warm | 1.24 / 1.29 / 1.30 | 2.59 / 2.69 / 2.71 |
| today, Leh warm | 1.08 / 1.17 / 1.21 | 2.36 / 2.54 / 2.53 |
| a sharper premixed burn (V3, a = 1), Leh warm | **0.41 / 1.69 / 2.40** | 5.19 / 5.16 / 5.06 |

- **The cause:** `build_sources` takes `np.gradient` (a central difference)
  of the combustion pressure and its peak. A rise that happens within one
  solver step is spread over two steps, so it reads about half. The
  sharper the burn, the worse it gets: V3's sharper burn *lowered* the
  sound's value at the 1° step. The solver's `dpdtheta_comb` takes a
  forward difference, and moves 5–15% at most.
- **A correction to the table above:** part of today's fall at Leh is the
  same step artefact. At the 0.25° step, crdi15's idle knock at Leh is −7%
  (1.21 against 1.30), not −13%. The direction stands.
- **The fix:** read the knock with the forward difference, as
  `dpdtheta_comb` does. `acoustics.py` is hashed, and the value is stored
  in every cell's sources, so it goes in the same rebuild.

## Added 2026-10-14, later: a knock value that doesn't depend on the step

Read off the trace, the knock of a sharp premixed burn can't be resolved
at a 1° step, whichever difference is used. So the prototype computes it
from the burn law instead: the peak of the combustion term of the first
law, `(γ − 1) / V × dQ/dθ`, evaluated on 8 sub-steps inside each step
(`P09_KN` in `tools/p09_prototype.diff`). A sharper burn variant (V4,
b = 1) then reads 3.64 / 3.63 / 3.61 at 1.0 / 0.5 / 0.25°, where the
trace read 3.07 / 5.32 / 6.53.

**The owner's cases on that value, at 0.25° (crdi15, 800 rpm, 5%),
against warm sea level:**

| | today | V1 | V4, b = 0.5 | V4, b = 1 |
|---|---|---|---|---|
| a cold start (walls at 273 K) | +1% | +1% | **+6%** | +4% |
| Leh, warm | −18% | −15% | **+12%** | −1% |
| Leh, cold | −17% | −14% | **+11%** | −4% |

All four variants use the burn integrated exactly over each step
(`P09_CUM`). Two limits remain:
- **At the 1° step the "Leh, cold" point is an outlier in every variant**
  (today 1.43 at 1° against 1.09–1.11 finer). The gas exchange's step
  error (FINDING-028) is the first suspect.
- **A cold engine barely knocks more in this model.** With the walls at
  273 K the delay grows only 9%, because the compressed gas barely cools.
  A real cold start (cranking speed, cold intake air, cold walls together)
  has a much longer delay.
