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
