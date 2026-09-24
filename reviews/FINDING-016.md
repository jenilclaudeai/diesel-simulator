# FINDING-016 — the FINDING-001/002 guards rode a 1° ignition-delay step at `crdi15` 1800/0.6 (title as first written: "main ignition delay is pinned at 2.425° … rode a regime switch" — see the correction)

**Opened by:** FINDING-013 item 1 (limiter calibrated under the evaluation's
schedules), which made two regression guards fail
**Lens:** PHY1 (lead), QA2
**Status:** measured; first reading corrected below (delay responds ~0.2°, quantised to the 1° step); fix direction for PHY1

---

## What happened

`test_premix_responds_to_temperature` and `test_combustion_dpdtheta_responds`
compare `crdi15` at 1800 rpm, load 0.6, with coolant at 273 K and 363 K. After
item 1 both fail: premix swings 2% (the guard wants > 20%), combustion
dp/dθ +1.5% (wants > 8%).

Item 1 lowers the calibrated full-load fuel at 1800 rpm by ~11% (the old
calibration ran with EGR on, and at 9 cycles the EGR loop delivers 2–3× its
target — FINDING-013 item 2 — so it needed more fuel to reach the cap).
"Load 0.6" is 60% of that, so the operating point moves:

| calibration | coolant | fuel limit mg | fuel mg | EGR % | ign. delay ° | premix | dp/dθ comb | torque |
|---|---|---|---|---|---|---|---|---|
| old | 273 | 49.35 | 29.61 | 16.48 | **2.42** | 0.1709 | 5.240 | 121.72 |
| old | 363 | 48.00 | 28.80 | 16.68 | **1.42** | 0.1023 | 4.611 | 124.41 |
| new | 273 | 44.19 | 26.52 | 16.37 | **2.42** | 0.1839 | 5.145 | 109.56 |
| new | 363 | 42.57 | 25.54 | 16.65 | **2.42** | 0.1886 | 5.071 | 111.74 |

The guards' old margin came entirely from the warm engine's ignition delay
sitting at 1.42° instead of 2.42°. With the new fuelling the warm engine no
longer switches, and the "response" is gone.

## Ignition delay does not respond at all here

Coolant swept 273–363 K, new calibration, at two crank resolutions:

| dθ | 273 K | 303 K | 333 K | 363 K |
|---|---|---|---|---|
| 1.0° | 2.425° | 2.425° | 2.425° | 2.425° |
| 0.5° | 2.425° | 2.425° | 2.425° | 2.425° |

Exactly 2.425° everywhere, at both resolutions. Premix and dp/dθ still vary a
little (0.1834–0.1886, 5.03–5.15), through fuel quantity and injection
duration, not through ignition delay. So the temperature sensitivity these
guards were written to protect is essentially absent at this point — the
shape the project keeps meeting: a quantity pinned, raising no error.

## Correction to REVIEW-001 B-1 (item 3)

REVIEW-001 read the 2.425° → 1.425° change as "quantised to the solver crank
step … a step function on the integration grid". At dθ = 0.5° the value is
still exactly 2.425° — it does not move with the step — so step quantisation
alone does not explain it. The 1.000° jump looks like a switch between two
regimes. (REVIEW-001 now carries a pointer here; its original text is kept.)

## Mechanism — open

After the pilot ignites, the main's delay integral runs at 2.1× the
Hardenberg–Hase rate (`cycle.py`, "boost = … 2.1") and crosses 1 within a
step or two, so the main's start of combustion may be set by the pilot and
the injection timing rather than by the charge state. Why the result is
exactly 2.425° at both resolutions is not established. Suspects, untested:
the pilot–main interaction, the 180° accumulation window, or the SOI's
fractional offset on the grid (0.425°).

## What was done

- The two guards are reported as **KNOWN** defects citing this finding
  instead of FAIL; if the response returns they report UNEXPECTED PASS.
- The `crdi15` golden points are re-baselined with the justification inline
  (FINDING-013 item 1). `hd_i6` is uncapped and unchanged.

## Caveats

One preset, one operating point. Other speeds and loads may sit in the other
regime; the two-regime structure itself is what needs explaining.

---

## Correction (later the same session) — ignition delay does respond; it is quantised to the crank step

The two claims above are **wrong**, and are kept as written:

- "Ignition delay does not respond at all here" — it does, weakly.
- "At dθ = 0.5° the value is still exactly 2.425° … so step quantisation
  alone does not explain it" — that reasoning does not hold. A response of
  ~0.2° never leaves its bin on a 0.5° grid (2.425 = 0.425 + 4 × 0.5) any more
  than on a 1° grid, so an unchanged value at 0.5° says nothing against
  quantisation. REVIEW-001 B-1 was right.

Measured at dθ = 0.1°, fuel held fixed at the default engine's calibrated
42.59 mg so only temperature changes:

| coolant | ign. delay | premix | SOC main | SOC pilot |
|---|---|---|---|---|
| 273 K | 2.225° | 0.1730 | 718.800° | 708.000° |
| 318 K | 2.125° | 0.1652 | 718.700° | 707.700° |
| 363 K | 2.025° | 0.1575 | 718.600° | 707.500° |

The main ignition delay falls smoothly, ~0.2° over 90 K (~9%), and premix
swings ~10% cold against warm. At the solver's 1° step that response is
quantised: the reported delay sits in one bin, or jumps a whole degree when
the true value crosses a bin edge. The guards' old > 20% margin was one such
jump — an artifact, not the physics' sensitivity.

**What this changes:**

- The two guards stay KNOWN, but for this reason: the physical response at
  this point is ~10% in premix, below their 20% threshold, and the solver's
  1° step hides it anyway. Their notes are updated.
- **Fix direction (not applied, for PHY1):** interpolate the start of
  combustion within the step — the delay integral's crossing of 1 is known to
  a fraction of a step from its two neighbouring values. Cheap, and it gives
  the solver a smooth ignition delay at any resolution. The guards' thresholds
  would then need re-deriving from the physics (≈10% premix over 90 K here),
  not from a bin jump.
- ADR-006's premise (cold rattle through a longer delay) holds in direction
  but is weak at this point: ~0.2° over 90 K.
