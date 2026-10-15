# FINDING-028 — At idle the port mass flows zig-zag at the solver's step

**Opened by:** session 9 (2026-10-14), during P10 (`reviews/PROPOSAL-P10.md`):
crdi15's idle exhaust, alone, had a 2.2 kHz centroid. A low-flow pulse
should be mostly bass.
**Lens:** PHY1 (lead), PHY2, the sound lens
**Status:** ~~**open, for the owner.** Nothing in `dieselsim/` is changed.
The P10 listening files hide it in the synth, in memory only (below).~~
**Option C chosen by the owner (2026-10-14, ADR-018).** Option A is built
on `feat/p10-sound`: `acoustics.smooth_port_flow` runs in `render` and
`LiveSynth.set_sources`, and `test_port_flow_zigzag_is_not_heard` guards
it. **Option B (the solver fix) is still open**, for the next rebuild.
Measured once built: the averaging cuts the zig-zag 0.78 → 0.051 of the
flow's RMS (15×, not to zero: the burst's edges sit off the exact null),
and the idle exhaust's centroid 2,159 → 208 Hz in both the synth and
render.
**Reproduce:** the session-9 scratch scripts `ripple_dt.py`,
`grid_ripple.py` and `dt_physics.py` (not kept; the numbers are below).

---

## What was measured

`cycle.traces.mdot_exh[0]` and `mdot_int[0]`, cylinder 1, at idle (load
0.05, `n_cycles=9`). "Ripple" is the power at orders of 45 per crank
revolution and above, as an RMS relative to the flow's own RMS:

| engine | dtheta 1.0 (the default) | dtheta 0.5 |
|---|---|---|
| crdi15 | exhaust 0.59, intake 0.64; peak **exactly at the step's Nyquist** (order 180/rev) | 0.001, 0.001 |
| hatch15 | 0.42, 0.56; at the step's Nyquist | 0.001, 0.001 |
| crdi22 | 0.025, 0.16; at the step's Nyquist | 0.001, 0.001 |
| single10 | 0.75, 0.74; at the step's Nyquist | **0.75, 0.74; at the new Nyquist (order 360)** |
| truck127, v8hd | 0.002–0.006 | 0.000–0.004 |

The oscillation sits at the step's Nyquist frequency (point to point,
period 2 steps), and at a finer step it either vanishes or moves to the
new Nyquist. **So it is numerical, not acoustic:** an explicit-integration
chatter of the port flow, in cylinder 1's late exhaust stroke
(θ ≈ 292–329°), where the pressure difference across the valve is near
zero.

**It is in the shipped grids.** In each grid's sound sources (`src_f32`,
`src_cold_f32`), the same ripple measure:
- **crdi15, hatch15, crdi22, ld_i4:** the idle row has 0.6–0.86 of ripple
  at most loads. Every row above idle has about 0.01.
- **single10:** 0.62 from idle up to about 1150 rpm, 0.37 at 1427 rpm,
  falling to 0.04 at the top.
- **truck127, v8hd:** 0.42 at most (the idle row at some loads).
- **hd_i6:** none.

## Why it matters

- **The sound** (`livesound.py` and `acoustics.render` differentiate the
  flow): the zig-zag's derivative is a tone at 180 × rev/s, which is 2.4 kHz
  at 800 rpm. It makes the idle exhaust's own centroid 2,159 Hz on crdi15;
  with the zig-zag averaged out it is 208 Hz. **Today it is barely audible**,
  because the exhaust is 0.1–0.2% of the idle mix (the intake is 0–2.6%).
  The moment P10 raises the exhaust, it would be the loudest thing at idle.
- **The physics, at idle** (crdi15, dtheta 1.0 against 0.5 and 0.25):
  - PMEP is 2515 Pa against 3620 and 3562 Pa (a 30% gap, in a small number).
  - VE is 1.2395 against 1.2627 (1.8%).
  - Residual gas is 0.2125 against 0.2082 (2%).
  - Air flow is 11.03 against 11.11 g/s (0.7%).
  - Torque and fuel move by 1.4% or less, about the same as the step's
    ordinary discretisation error at 2000 rpm (0.5%), where nothing
    zig-zags.

  At 800 rpm and load 0.4, PMEP is 8181 Pa against 10475 Pa, and VE is
  1.2243 against 1.2453.

## Options

| | what | positives | costs |
|---|---|---|---|
| **A** hide it in the synth | a 2° circular moving average of `exh_flow` and `int_flow` in `LiveSynth.set_sources` (and the TS port; render to match). This nulls the step's Nyquist and its harmonics | no grid rebuild (`livesound.py` is outside the hash; `acoustics.py` needs only a re-stamp); it is what the P10 files use; at 2000 rpm and up it changes the sound by nothing measurable (0 Hz of centroid at crdi15 2000/0.3, cabin) | the physics' idle PMEP/VE error stays; it trims real content at order 45 by 9% (3 kHz at 4000 rpm, after the exhaust's own low-pass) |
| **B** fix the solver | damp or implicitly integrate the port flow near Δp = 0 | removes the cause: idle PMEP and VE come right on every page | `cycle.py` is hashed: every grid rebuilt with its weather table (about 8 h on this Mac), and the golden fixtures regenerated |
| **C** both | A now, with P10; B when the next solver change forces a rebuild anyway | P10 isn't blocked by an 8-hour rebuild | two changes to review |

Recommended: **C**.

---

## Added 2026-10-14, later: option B, first attempt, measured, and it does not work

Building option B with P09 (ADR-018 put it in the next rebuild), I first
tried the simplest cure on a scratch copy: `thermo.orifice_mdot` made
linear in the pressure drop below `1 − p_dn/p_up = ε`, matched to the
isentropic law there, so the flow's slope at Δp = 0 is finite.
**It changes nothing that matters** (scratch `f28_eps.py`; "ripple" is the
power at orders ≥ 45/rev relative to the whole trace, on a different scale
from the table above):

| crdi15, 800 rpm, 5% | ripple exh / int | PMEP, Pa | VE |
|---|---|---|---|
| 1° step, today | 0.80 / 0.81 | 2515 | 1.2395 |
| 1°, ε = 0.005 | 0.83 / 0.84 | 2188 | 1.2400 |
| 1°, ε = 0.02 | 0.83 / 0.82 | 1763 | 1.2455 |
| 0.5° step, today | 0.001 / 0.001 | 3621 | 1.2627 |

So the chatter is not the √Δp singularity. It is the explicit step: a
near-equal-pressure exchange between the cylinder and a manifold settles
faster than one 1° step, and any explicit law overshoots. **The cure is
numerical:** sub-step the gas exchange while a valve is open, or integrate
the port flow implicitly. That is a solver project of its own, with its
own measurements.

**And single10 is worse than this finding said.** At 600 rpm the 1° step
costs far more than the idle PMEP:

| single10, 600 rpm | VE, 1° / 0.5° | torque, 1° / 0.5° |
|---|---|---|
| 5% load | 1.0123 / 1.1473 (−12%) | −19.66 / −18.32 N·m |
| 40% load | 1.0123 / 1.1463 (−12%) | **7.98 / 10.14 N·m (−21%)** |

At 1100 rpm and 30% load its torque is 9.17 against 9.59 N·m (−4%). The
cars at 2000 rpm agree to 0.4%. The 0.5° solve is not proven right either
(single10's ripple moves to the new Nyquist there, 0.96), so the truth
needs a 0.25° point before anything is claimed.

**The 0.25° point, measured the same day:**

| single10 | VE, 1° / 0.5° / 0.25° | torque, N·m, 1° / 0.5° / 0.25° |
|---|---|---|
| 600 rpm, 5% | 1.012 / 1.147 / **1.265** | −19.66 / −18.32 / −17.60 |
| 600 rpm, 40% | 1.012 / 1.146 / **1.262** | 7.98 / 10.14 / **10.23** |
| 1100 rpm, 30% | 1.200 / 1.266 / 1.274 | 9.17 / 9.59 / 9.44 |

~~The torque settles by 0.5°, and the VE nearly settles by 0.25°.
**single10's shipped grid, built at 1°, is about 22% low on torque at 600
rpm and 40% load, and 3% low at 1100 rpm and 30%.**~~ Its idle ripple at
0.25° is still 0.80 / 0.68, so the zig-zag isn't gone there either.
**Corrected the same day:** because of that ripple, the explicit 0.25°
solve is not a reference for single10 at 600 rpm, and "22% low" overstated
it. The semi-implicit flow (below) agrees with itself between 1° and 0.5°
(torque 9.74 / 9.83 N·m, VE 1.263 / 1.268). Against that, today's 1°
grid is about **18% low** on torque at 600 rpm and 40% (7.98 N·m). At
1100 rpm and 30% the explicit 0.25° solve is clean (ripple 0.001), and
today's grid is 3% low there.

**The semi-implicit flow, measured** (scratch switches `F28_IMP`,
`F28_AMB`): where the explicit flow would carry the pressure difference
past zero within the step, the flow is solved against the end-of-step
pressures (implicit Euler, bisection). That covers the valves and, on an
engine without a turbo, the plenum-to-air and manifold-to-air orifices.
Everywhere else it is left as it was.

| | today, 1° | semi-implicit, 1° | semi-implicit, 0.5° | explicit, 0.25° |
|---|---|---|---|---|
| crdi15 800/5% ripple | 0.80 | 0.022 | 0.073 | 0.001 |
| crdi15 800/5% VE | 1.2395 | 1.2613 | 1.2624 | 1.2626 |
| crdi15 800/5% torque | −10.583 | −10.718 | −10.708 | −10.752 |
| crdi15 2000/30% torque | 57.502 | 57.512 | 57.303 | 57.206 |
| single10 600/40% ripple | 0.99 | 0.044 | 0.041 | (0.83) |
| single10 600/40% VE | 1.012 | 1.263 | 1.268 | (1.262) |
| single10 600/40% torque | 7.98 | 9.74 | 9.83 | (10.23) |
| single10 1100/30% torque | 9.17 | 9.30 | 9.43 | 9.44 |

The values in brackets come from a solve that still zig-zags.
- **Still not right: PMEP.** It converges only first-order, because the
  pumping work takes the pressure at the start of each step. crdi15's idle
  PMEP is 1788 / 3179 / 3562 Pa at 1° / 0.5° / 0.25° with the
  semi-implicit flow; today's 1° value is 2515. Torque is unaffected (it
  matches to 0.3%). The Cycle page shows PMEP, so this stays open: a
  midpoint pressure in `p dV` would fix it, but it changes the calibrated
  gross work at every point.
- **Cost:** the first version, with 40 bisection steps, took 34.7 s
  against 20.8 s for the same six solves (shared CPU; to be re-measured).

**Two cures tried and rejected, and where single10's zig-zag lives** (same
day, scratch):
- **A flow limiter** (no step carries more than the mass that equalises
  the two pressures): crdi15's ripple 0.80 → 0.008, and VE 1.2395 →
  1.2570 (0.25°: 1.2626). But idle PMEP goes 2515 → −1654 Pa (0.25°: 3562),
  and it shifts 2000 rpm too, where nothing zig-zagged (−16773 → −18218,
  0.25°: −17060). It holds back flow that isn't overshooting. single10: no
  change (0.99).
- **single10 at 600 rpm, 40%**: the zig-zag fills the whole exhaust
  stroke (186–322°) and the whole intake stroke (393–523°), at the step's
  Nyquist at 1°, 0.5° and 0.25° alike (orders 180, 360, 720 per rev). With
  the valve wide open the cylinder and manifold sit at nearly equal
  pressure, where the √Δp law's conductance is unbounded. So some band of
  small Δp overshoots at any step size, and a finer step only narrows it.
  The cars' zig-zag is the same thing near TDC, where the cylinder is small
  (crdi15: TDC filling time 0.088 ms against 0.21 ms per 1° step at 800
  rpm; 0.083 ms per step at 2000 rpm, where it is stable).
- **Next:** a semi-implicit flow, only where a step would overshoot (the
  predicted end-of-step Δp flips sign). There the flow is solved
  consistent with the end-of-step pressures; everywhere else it is left
  bit for bit.
