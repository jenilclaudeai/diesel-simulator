# FINDING-018 — valve lift steps 4× where the ramps meet the flank

**Opened by:** reading `Cam.seating_velocity()` for Phase 1 task #27 (seat at ramp speed)
**Lens:** PHY2 (lead), QA2
**Status:** fixed with option C′. **The owner should confirm C′ before merge.** Options A, B and C are below, measured.
**Reproduce:** `python3 -c "import numpy as np; from dieselsim.kinematics import _core_profile as c; r=0.06; print(c(np.array([r-1e-9, r+1e-9]), r))"`
prints `[0.00886 0.03511]` on the old code.

---

## What is wrong

`kinematics._core_profile()` builds each valve event from a raised cosine
`sin²(πu)` with linear ramps over `[0, r]` and `[1−r, 1]`, where `r` is
`ramp_fraction`. The ramps end at `h_r = ½(1 − cos πr) = sin²(πr/2)`. But the
flank they hand over to is `sin²(πr)` at `u = r`, about 4× higher, so **lift
jumps at both junctions**:

| ramp_fraction | ramp end | flank start | step (of peak lift) | step on the engine |
|---|---|---|---|---|
| 0.06 (`crdi15`, `crdi_1p5`, `ld_i4`) | 0.0089 | 0.0351 | 0.026 | ~0.2 mm |
| 0.13 (`single`) | 0.0411 | 0.1577 | 0.117 | 0.9 mm |
| 0.155 (`hd_i6`) | 0.0581 | 0.2190 | 0.161 | **2.0 mm** |

The code has done this since the first commit (`df4c5a4`). The `h_r` formula is the
raised cosine `½(1 − cos 2πu)` evaluated at `u = r/2`: the ramp height and the ramp
length disagree by a factor of two.

What the step does:
- **Valvetrain inertia.** `d2lift_dtheta2` is a 0.1° finite difference. Near a
  step it spikes: max |d²L/dθ²| was 73 (`crdi15`) to 663 (`hd_i6`) per rad²
  against 0.2–0.7 for the smooth profile. The inertia force therefore depends
  on whether a crank sample lands within 0.1° of the junction.
- **Seating.** On closing, the valve falls 4·h_r → h_r instantaneously, and
  then rides the ramp. The seating velocity reported was the ramp speed, so
  the drop never reached the sound.
- **Breathing.** The presets were tuned with this profile. Any continuous fix
  must keep the flank, or the rating changes (option A).

## Options (measured; fresh engine, n_cycles 9)

| option | what it does | breathing | ramp height (lash clearance) | ramp speed / seating |
|---|---|---|---|---|
| **A** squeeze the flank | flank `h_r + (1−h_r)·sin²` over `[r, 1−r]` | **lift area −11 to −25%**; `hd_i6` 1700/1.0 2311 → **2123 N·m (−8.1%)**, trapped air −14%; `crdi15` 1800/0.6 −1.1% | unchanged | unchanged, but velocity drops to 0 at the junction (a dwell) |
| **B** raise the ramps | ramp over `[0, r]` up to the flank, `sin²(πr)` | unchanged | ×3.8–4 (`hd_i6` 2.7 mm) | ×3.8–4: tick +12 dB |
| **C** end the ramp at the crossing | same ramp speed, ends where it meets the flank (u = r/4) | torque +0.09% / −0.04% / −0.07% | **÷4**: `hd_i6` 172 µm and `single` 79 µm, **below their lash again**, which undoes FINDING-017 item 2 | unchanged |
| **C′** (applied) | ramp keeps its height `h_r`, meets the flank at u = r/2 | torque +0.09% (`hd_i6` 1700/1.0), −0.04% (`crdi15` 1800/0.6), −0.10% (`single` 2000/0.8); lift area +0.2% to +3.3% | unchanged | **×2**: tick +6 dB at the same lash |
| D | leave it, document | — | — | — |

C′ keeps both earlier owner decisions: the 2310 N·m validation, and ramps
that clear the lash (FINDING-017, test `test_closing_ramps_clear_the_lash`).
The price is a seating speed twice the old reported one, and a
`ramp_fraction` that now means "the ramps take the first and last r/2 of the
event". Ramp speeds after the fix: `crdi15` exhaust 0.020 mm per cam degree,
and `single` 0.042. `hd_i6` exhaust, whose ramp FINDING-017 raised to 0.70 mm
to clear 550 µm of lash, is 0.074 mm per cam degree. That is fast for a
production closing ramp, which is usually a few hundredths of a mm per cam
degree (a rule of thumb, not a sourced figure), and a real cam would clear
that lash with a longer ramp, not a steeper one. This is an argument for revisiting `hd_i6`'s ramp duration
together with task #27, not for a different profile fix.

## Applied (C′)

`_core_profile` ramps over `[0, r/2]` and `[1 − r/2, 1]` at height `h_r`,
continuous with the unchanged flank. `Cam.seating_velocity()` uses the same
ramp length.

Measured on the fix (vs the tree below it, PR #41):

| quantity | before | after |
|---|---|---|
| `crdi15` 1800/0.6 torque / p_max | 122.628 / 129.99 | 122.580 / 130.05 |
| `crdi15` 3000/1.0 torque | 216.892 | 216.888 |
| `hd_i6` 1700/1.0 torque / p_max | 2311.359 / 178.17 | 2313.377 / 178.84 |
| `hd_i6` 1400/0.6 valvetrain friction | 577.8 W | 572.7 W |
| `single` 2000/0.8 cam boundary power | 217.3 W | 215.3 W |
| `single` exhaust lash at 2000 h (K 2.17e-7) | 149.8 µm | 147.8 µm, so K re-fitted to **2.20e-7** → 149.8 µm |
| max lift change per 0.01°, any preset | 0.161 of peak (`hd_i6`) | 1.5e-4 (the smooth flank's slope) |

`hd_i6`'s golden torque returns to within 0.001% of its pre-#37 value (2313.401).
It still reproduces the documented 2310 N·m and stays in the 160–200 bar band.

**Sound:** valve tick carries 4× the energy it did (level ∝ v_seat²). In the
`crdi15` mechanical sub-mix, piston slap ×2 now moves the output +4.5% (it
was +15.8%). The tick reference `_ref_vseat = 0.10 m/s` is a chosen constant,
and I have not re-tuned it to hide the change. By-ear sign-off is a Phase 4 exit
criterion.

## Tests

- `test_cam_lift_is_continuous`: every preset, both cams. No sample-to-sample
  change on a 0.01° grid may exceed 1e-3 of peak lift. Also, the seating velocity
  must equal the profile's own ramp slope (`crdi15` exhaust, no lash) within 1%.
- `test_mech_levels_carry_physics`: the bar was lowered from +5% to +1%, with
  the reason stated inline. The defect it guards against moved the output
  3.6e-11, and removing the slap level (mutation) gives +0.0%.
- Mutations: see the PR.
