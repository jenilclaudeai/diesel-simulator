# FINDING-015 — cam boundary friction is negligible because the cam film is ~780× too thick

**Opened by:** FINDING-005's open question — "cam boundary friction is ~0 for
every preset … suspects: `sigma_cam`, or entrainment velocity at nose
reversal. Untested."
**Lens:** PHY2 (lead), PHY1
**Status:** measured, not fixed — the fix is a physics and calibration
decision, see Options
**Reproduce:** `python3 tools/diag_cam_boundary.py`

---

## Summary

Neither suspect was the main cause. Three problems in `friction.py`'s
valvetrain block, in order of size:

| # | problem | effect on flat-tappet boundary power |
|---|---|---|
| 1 | **pressure-viscosity counted twice**: `mu_cam` is evaluated at 500 MPa (Barus ×≈13,000) *and* Hamrock–Dowson adds the same effect through G = αE′ | the dominant one: 5.0e-7 W → 11.7 W on its own |
| 2 | **flat-tappet kinematics**: follower lift velocity used as both sliding and entrainment speed | 7.3e-6 W on its own; with #1 fixed, 11.7 → 217 W |
| 3 | **time base**: crank-angle derivatives multiplied by cam speed — follower velocity 2× low, valvetrain inertia force 4× low | small: −2…−4% valvetrain friction power, ≤0.3% FMEP |

All three fixed: flat tappet **215 W** boundary power (was 5.0e-7 W), roller
(`hd_i6`) **27.9 W** (was 4.3e-3 W). The ordering finally comes out right —
flat tappets wear far more than rollers — but a new clamp binds (below).

## 1. Pressure-viscosity counted twice

```python
mu_cam = oil.viscosity(T_oil + 5.0, 5e8, 1.0e6)      # friction.py:88
```

`Oil.viscosity(T, p, shear)` applies Barus `exp(1.9e-8 · p)` for p > 2e5 Pa —
at 500 MPa, `exp(9.5)` ≈ 13,000. `hamrock_dowson_film()` then uses the
Dowson–Higginson line-contact formula, whose G = αE′ term *is* the
pressure-viscosity effect, and which expects the **inlet** (ambient-pressure)
viscosity. Measured at `single` 2000 rpm / 0.8:

| | viscosity |
|---|---|
| shipped (`p = 5e8`) | **80.1 Pa·s** |
| inlet (`p = 1e5`) | 0.006 Pa·s |

Film thickness goes as viscosity^0.7, so the film is inflated ≈ 13,000^0.7 ≈
780×. With a film that thick the Stribeck boundary share collapses everywhere.
The ring (5 MPa) and bearing (20 MPa) calls also apply Barus, but they feed
hydrodynamic models without a G term, so they are not double-counted.

## 2. Flat-tappet kinematics

The flat-tappet branch uses `u = |dL/dθ| · ω_cam` — the follower's lift
velocity — as both the sliding speed (boundary power) and the entrainment
speed (film). For a flat-faced follower, with cam angle φ and derivatives per
cam radian (Dowson & Higginson's cam–tappet analysis):

- sliding speed `u_s = ω_cam (R_b + L)` — large everywhere, including the base
  circle;
- entrainment speed `u_e = ω_cam |R_b + L + 2L″| / 2` — passes through zero
  near the nose, which is where real flat tappets lose their film.

With the shipped speed, the two cancel: where the film is thin (base circle,
nose: `dL/dθ → 0`), the sliding speed is zero too. The roller branch likewise
entrains the film at its 6% *sliding* speed rather than the rolling speed
`ω_cam (R_b + L)`.

## 3. Time base

`kinematics.Cam` works in **crank** angle ("valve lift, velocity and
acceleration versus crank angle"; `seating_velocity()` is fed crank speed), but
the friction block multiplies its derivatives by `om_cam = om / 2`. Measured by
giving the friction model's cams per-cam-radian derivatives (friction is the
only caller):

| point | P_valvetrain W | FMEP bar | torque N·m |
|---|---|---|---|
| `crdi15` 2000 / 0.6 | 138.1 → 133.0 | 1.059 → 1.056 | 125.58 → 125.55 |
| `crdi_1p5` 2000 / 0.6 | 129.5 → 124.6 | 1.021 → 1.019 | 134.57 → 134.58 |
| `hd_i6` 1400 / 0.6 | 584.7 → 563.1 | 0.811 → 0.810 | 1318.83 → 1318.98 |
| `ld_i4` 2500 / 0.6 | 228.4 → 222.0 | 1.077 → 1.075 | 230.86 → 230.88 |
| `single` 2000 / 0.8 | 171.4 → 171.4 | 0.980 → 0.980 | 23.86 → 23.86 |

A real error, small in effect: within the golden points' 0.5% tolerance.

## Measurement — boundary power, all variants

Flat tappet, `single` 2000 rpm / 0.8. The replica of the branch reproduces the
engine's own `Pb_valvetrain` exactly (5.0023e-07 W) before any variant runs.

| variant | Pb_valvetrain W | min λ | share of cycle λ < 1 |
|---|---|---|---|
| shipped | 5.0e-07 | 0.327 | 70.0% |
| time base fixed | 2.1e-07 | 0.327 | 70.0% |
| kinematics fixed | 7.3e-06 | 14.857 | 0.0% |
| inlet viscosity only | 1.17e+01 | 0.032 | 100.0% |
| kinematics + inlet viscosity | 2.17e+02 | 0.032 | 95.3% |
| all three fixed | 2.15e+02 | 0.032 | 95.6% |

Roller, `hd_i6` 1400 rpm / 0.6 (mechanical lash, 300 µm — the engine for which
"tick grows with lash" applies; replica matches, 4.2637e-03 W):

| variant | Pb_valvetrain W | min λ |
|---|---|---|
| shipped | 4.3e-03 | 0.249 |
| rolling entrainment + inlet viscosity + time base | **27.9** | 0.284 |

## The new clamp

With the fixes, `hamrock_dowson_film()`'s 8 nm floor binds near the nose: the
flat tappet's min λ is exactly 8 nm / 0.25 µm = 0.032. That is the dead-signal
pattern from the other side — a quantity pinned against a clamp — and a fix
that only corrects the three items above would move the problem, not remove
it. The floor needs a physical basis (a mixed-lubrication / asperity-contact
model, or a film floor tied to the composite roughness), not a constant.

## Consequences

- **FINDING-005 is explained.** Cam wear and lash growth are negligible
  because boundary power is ~0, and boundary power is ~0 because the cam film
  is ~780× too thick. `sigma_cam` (0.25 µm composite) is plausible for ground
  cam and tappet surfaces.
- **Fixing it moves wear, not performance.** Boundary power feeds the wear
  model; valvetrain friction power itself moves ≤4% (item 3) plus whatever
  item 1 does to the mixed-regime torque (not measured separately here).
- **The wear model was never exercised by realistic cam boundary power.** Once
  it is, cam wear and lash growth rates need calibrating against real
  durability expectations — otherwise a fixed film could make a flat-tappet
  engine wear out implausibly fast.

## Options (not applied)

| option | positives | trade-offs |
|---|---|---|
| A. Fix all three, add a physical film floor, then calibrate wear rates against a stated durability target (e.g. lash growth for a flat-tappet single over its life) | valvetrain tick finally ages; flat vs roller comes out right; removes a ~780× error | moves wear results everywhere; needs a calibration target and a reviewed floor model; PHY2 work |
| B. Fix items 1–3 only, keep the 8 nm floor | small, clearly-correct code change | swaps a film pinned high for one pinned at its floor near the nose; wear magnitudes uncalibrated |
| C. Fix item 3 only (time base) | tiny, unambiguous, within golden tolerance | leaves cam wear negligible |
| D. Document and state in the UI that valvetrain wear is not modelled | nothing moves | the durability story keeps a known dead path |

Recommended: **A**, starting with item 3 and item 1 (both unambiguous), with
the floor and the wear calibration as a reviewed decision.

## Caveats

One operating point per branch. The flat-tappet sliding/entrainment formulas
assume a translating flat-faced follower with no offset; the roller variant
keeps the branch's 6% sliding assumption. The 12 mm contact width
(`w_line`) and the cam radius used as R (rather than the local radius of
curvature at the contact) are further approximations, not measured here.

---

## Partly fixed (session 4, owner's decision: "unambiguous parts first")

Items 1 and 3 are fixed in `friction.py`: `mu_cam` is the inlet
(ambient-pressure) viscosity, and follower velocity and inertia use crank
speed on the crank-angle derivatives. Item 2 (flat-tappet kinematics), a film
floor and a wear calibration are left for the proposal below.

**Effect** — before → after, 9-cycle solves, and an 8000 h
`durability_run(step_h=400)`:

| | boundary power | valvetrain friction | torque | lash growth 8000 h (int / exh) |
|---|---|---|---|---|
| `single` 2000/0.8 (flat tappet) | 5.0e-7 → **22.6 W** | 171.3 → 228.2 W | 23.964 → 23.692 (−1.13%) | ~0 → **0.83 / 1.02 µm** |
| `hd_i6` 1400/0.6 (roller) | 4.3e-3 → **29.5 W** | 585.2 → 563.5 W | +0.011% | ~0 → **0.55 / 0.67 µm** |
| `crdi15` 2000/0.6 (roller) | 1.4e-3 → **7.4 W** | 134.0 → 129.0 W | +0.012% | — |

- The dead-signal audit's TINY list is now empty: `Pb_valvetrain` was the
  last entry on it.
- Wear is now non-zero but modest with the existing Archard coefficients —
  about a micron of lash in 8000 h — so the fix does not make engines wear out
  implausibly fast while the calibration is pending.
- The flat tappet's valvetrain friction rises 33%: its film is now in the
  mixed regime, as a flat tappet's should be. The goldens (crdi15, hd_i6)
  move ~0.01%, inside tolerance, and are unchanged.

Test: `test_cam_film_and_time_base` — boundary share material (> 1%) for
`hd_i6` and `single`, and `hd_i6` valvetrain friction 563.5 W ± 1% (the time
base's fingerprint; 585.2 W on the cam time base). Mutation: reverting either
fix is caught by its own check.

## Proposal — the remaining part, for decision

1. **Flat-tappet kinematics (item 2).** With the shipped `|dL/dθ|·ω` speeds
   the flat tappet's film sits on the 8 nm floor across the base circle (λ =
   0.032 for 100% of the cycle with inlet viscosity alone) because that
   "entrainment" speed is zero there. Use `u_s = ω_cam (R_b + L)` and
   `u_e = ω_cam |R_b + L + 2L″| / 2`. Measured: flat-tappet boundary power
   then ~215 W.
2. **A physical film floor.** Near the nose the entrainment speed passes
   through zero and the floor binds again (λ = 0.032). Replace the constant
   8 nm with a mixed-lubrication treatment — e.g. a floor tied to composite
   roughness, or a load-sharing (Greenwood–Tripp-style) asperity term — so the
   boundary share saturates physically instead of at a clamp.
3. **A wear-rate calibration target.** The Archard coefficient for the cam was
   never exercised. Pick a target — for example "a flat-tappet single loses
   ~X µm of lash in its first 5000 h" — and fit `K_ARCHARD["cam"]` to it, with
   the target and its source recorded.

These are physics judgements; nothing here is applied.

---

## Item 2 fixed, floor replaced (session 4, owner's decision: "kinematics + floor, measure")

- **Flat tappet:** sliding `u_s = ω_cam (R_b + L)`, entrainment
  `u_e = ω_cam |R_b + L + 2L″| / 2` (L″ per cam radian = 4 × the crank-angle
  second derivative).
- **Roller:** film entrained at the rolling speed `ω_cam (R_b + L)`; the 6%
  sliding speed still sets the boundary power.
- **Film floor:** 0.1 × composite roughness (25 nm) instead of a fixed 8 nm.

**The floor turned out to be inert.** Flat-tappet boundary power with the old
8 nm floor, the new 25 nm floor and effectively no floor (1e-12 m): 215.056761,
215.056672, 215.056761 W — 4e-7 relative. Where the film is that thin the
Stribeck boundary share is already 1, so the "clamp binding" earlier in this
finding was an audit-shaped flag with no physical consequence. The
roughness-based floor is kept as the principled value.

**Effect** — after items 1 and 3 → after item 2 too:

| | boundary power | valvetrain friction | torque | lash growth 8000 h (exh / int) |
|---|---|---|---|---|
| `single` (flat tappet) | 22.6 → **215.1 W** | 228.2 → 216.3 W | +0.24% | 1.02 → **9.23** / 0.83 → **7.55 µm** |
| `hd_i6` (roller) | 29.5 → 27.9 W | 563.5 W (same) | 0.000% | 0.67 → 0.62 / 0.55 → 0.51 µm |
| `crdi15` (roller) | 7.4 → 7.2 W | 129.0 W (same) | 0.000% | — |

Per cylinder, the flat tappet's cam boundary power is now ~46× the roller's
(215 vs 4.65 W) — the ordering real engines show.

Test `test_flat_tappet_wears_more_than_roller` (ratio > 10×, and `single`
boundary power 215.1 W ± 2% as the entrainment fix's fingerprint). Mutation:
the old kinematics (both speeds) and the old entrainment alone are each caught.

## Calibration target — for the owner to choose

`K_ARCHARD["cam"]` has never been fitted. The model now gives a flat-tappet
single ~9 µm of exhaust lash growth in 8000 h of its default duty cycle, and a
roller engine ~0.6 µm. Candidate targets (none chosen, no figure quoted from
memory):

1. **An oil-qualification valvetrain wear test** (the flat-tappet cam wear
   tests used to qualify engine oils): reproduce its duty cycle with
   `durability_run` and fit `K_ARCHARD["cam"]` to its wear limit. The limit and
   duty cycle must be taken from the standard itself.
2. **A published field measurement** of flat-tappet lobe wear or lash growth
   over a stated number of hours or kilometres, with its source recorded.
3. **A service-interval target:** choose the interval at which a
   mechanical-lash engine needs its valves adjusted, and fit the coefficient so
   lash growth reaches the adjustment tolerance at that interval.

Option 1 is the most defensible if the standard is available; option 3 is the
quickest and says plainly that it is a design choice.

---

## Wear calibrated (session 4, owner's target: service interval)

**Target, chosen by the owner:** a mechanical-lash engine needs its valves
adjusted every **2000 h**, at **150 µm** of lash growth. Fitted on the
flat-tappet `single` (default duty cycle, exhaust lash — the faster-growing
side), after FINDING-017's ramp fix. A design choice, not a measurement.

`K_ARCHARD["cam"]`: 3.2e-9 → **2.17e-7** (×67.8; the relation is linear —
the first proportional step landed at 149.89 µm).

| engine | lash growth 2000 h | 8000 h | 12,000 h (cam lift lost) |
|---|---|---|---|
| `single` (flat tappet) | **149.8 µm** | 625 µm | 934 µm (12% of lift) |
| `hd_i6` (roller) | 8.5 µm | 37 µm | 55 µm (0.5%) |
| `crdi15` (roller, hydraulic) | 1.7 µm | 7.5 µm | 11 µm (0.1%) |

Rollers wear ~17× slower than the flat tappet. An unadjusted flat tappet keeps
losing lobe linearly (Archard, no run-in modelled): −1.4% torque at 12,000 h.

**Observed, not investigated:** after 2000 h `crdi15` makes **+3.6%** torque
(and `hd_i6` −1.9%) relative to new. That is not the cam (1.7 µm of lift) — it
comes from the other wear mechanisms, whose coefficients were not touched, and
recalls known bug #9 (a worn engine with *less* blow-by than new). Worth its
own look.

Test `test_cam_wear_calibration` (150 µm ± 5% at 2000 h); the old coefficient
fails it (2.21 µm).
