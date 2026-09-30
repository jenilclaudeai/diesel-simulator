# FINDING-023 — the synth's slap input sits on the skirt film's clamp in every cold cell

**Opened by:** Phase 4, the first run of `test_grid_sources_warm_and_cold` on the rebuilt grids. The test said a cold cell's skirt film is thicker than the warm one's, and it was false in 115 of 240 cells.
**Lens:** PHY2 (lead), QA2, USR1
**Status:** open, recorded as a known defect in the suite. Left for the owner's listening review, together with FINDING-022.
**Decision (2026-09-30):** the owner chose **option A**, built together with a separate ramp-height parameter (REVIEW-003 m-5) so that the grids rebuild once.
**Reproduce:** `test_grid_sources_warm_and_cold`, `test_live_sound_follows_the_engine`

---

## What was measured

`skirt_clr`, the slap level's input (FINDING-017: the skirt **oil film**, used as a stand-in for piston-to-bore clearance), across the five prebuilt grids:

| | on the upper clamp (0.32 × skirt clearance) |
|---|---|
| cold cells (273 K coolant) | **240 of 240** |
| warm cells | **115 of 240** |

Per preset, warm cells on the clamp:
- `crdi15`: 29
- `crdi_1p5`: 31
- `hd_i6`: 10
- `ld_i4`: 35
- `single`: 10

Mostly at light load. Where both are pinned, the cold/warm ratio is exactly 1.00. Elsewhere it reaches 2.26.

In the live loop (ADR-011), crdi15 at idle, the live friction's film against oil temperature:
- oil at 273 K against 361 K, coolant 361 K: **1.00×**, so mech noise moved **+0.0%**;
- oil and coolant both at 273 K against 361 K: 1.02×, so mech moved +0.2%.

The boundary friction power, by contrast, moves (0.83×), so the rumble does
too (−8.9%). The live path works; the input it carries for slap is pinned.

## Why

`lubrication.skirt_film_thickness` caps the film at `0.32 · c_diam`: a film
cannot be thicker than the gap it fills. That is correct for friction. But
the synth reads the film as its measure of how loose the piston is, and
cold oil and cold walls push the film to that cap. So the slap level
saturates exactly where a cold diesel's slap should be growing.

The real mechanism, a cold piston contracting and its clearance opening,
is not modelled: the clearance comes from the wear state only.

It is CLAUDE.md's pattern: an input pinned against a clamp, raising no
error. `tools/audit_dead_signals.py` looks at operating points, not at
grids warm against cold, so it did not see it.

## Options (for the owner, after listening)

| option | trade-offs | positives |
|---|---|---|
| **A. Slap from a temperature-dependent clearance**: c(T) = c₀ + α·D·(T_ref − T_piston), with the film kept for friction | a new model term (α, T_piston from the coolant and load) that needs a reference; changes `acoustics.py`, so all grids rebuild (once, with FINDING-022) | cold slap from the actual cause; warm and cold differ everywhere |
| B. Keep the film, lift the clamp for the synth only | not physical: a film thicker than the gap | small change |
| C. Leave it | cold slap is capped at the clamp's level | no retuning |

Recommendation: **A**, decided with FINDING-022 in the listening review, so
that the rebuild happens once.

---

## Fixed with option A (2026-09-30, the owner's choice)

Slap now reads the **running diametral skirt clearance**. The skirt film
stays in the friction model, so torque and fuel are untouched.

    c(T) = c_ref − bore × (α_piston ΔT_piston − α_bore ΔT_bore),  floored at c_ref / 4

- `c_ref` is the clearance at the warm reference coolant (361 K), as the
  friction model uses it, wear included.
- The piston and bore move with the coolant exactly as
  `engine._apply_thermal_state` moves the walls. Its coefficients are now
  shared constants (`config.T_COOLANT_REF`, `WALL_FOLLOW`): the piston
  0.72 K and the liner mean 0.91 K per K of coolant.
- α: Al-Si piston 21e-6/K, grey-iron bore 11e-6/K.
- The level's reference moved from 30 µm of film to 30/0.32 µm of
  clearance. A warm cell whose film sat on the cap (most of them, and the
  idle the live loop spends its time at) keeps its slap level exactly.

| preset | warm | 273 K | cold/warm | slap level |
|---|---|---|---|---|
| `crdi15` | 42.0 µm | 76.5 µm | 1.82× | +3.1 dB |
| `crdi_1p5` | 42.0 | 75.6 | 1.80× | +3.1 dB |
| `hd_i6` | 90.0 | 148.3 | 1.65× | +2.6 dB |
| `ld_i4` | 45.0 | 82.2 | 1.83× | +3.1 dB |
| `single` | 70.0 | 108.5 | 1.55× | +2.3 dB |

**Wired at each place the synth's input is made:**
- `EngineSound.build_sources`, with the coolant attached by
  `grid.solve_cell` as the wear is;
- the live loop's `sound_inputs()`;
- the TypeScript loop and synth (`web/physics/src/slap.ts`).

**Tests and mutants:**
- `test_cold_slap_follows_clearance` has 7 parts. 6 of 6 mutants were
  caught, each by its own part: the meta reading the film, the grid cell not
  told its coolant, the live loop sending the film, the bore term dropped,
  `EngineSound` ignoring the coolant, and no floor.
- This finding's `known()` in `test_grid_sources_warm_and_cold` is now a
  check: every cold cell off the old cap, and cold/warm > 1.3 in every cell.
- TypeScript mutants: the film back in the live loop fails the ADR-011 live
  drives; the old level reference fails the sound fixture.

**Limitation:** the model's wall temperatures follow the coolant but not
load, so the clearance does too. A hot piston at full load would be
tighter still. That is a separate model change.

Found on the way: in the eight grids built before this fix, *every* cold
cell sat on the cap, the three roster grids included.
