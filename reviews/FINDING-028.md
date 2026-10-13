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
