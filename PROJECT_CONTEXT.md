# dieselsim — Complete Project Context

**One file. Everything.** Paste this into a new chat and the assistant will
have full context without any of the prior conversation.

Contents:
1. [Technical Document](#1-technical-document) — the physics and why it's built this way
2. [Implementation Document](#2-implementation-document) — files, APIs, data flow, known bugs
3. [Angular Build Guide](#3-angular-build-guide) — how to put a real UI on it

**Attach `dieselsim_package.tar.gz` when you start the new chat.** The
container filesystem resets between sessions; this document describes the code
but does not contain it.

---

# 1. TECHNICAL DOCUMENT

## 1.1 What this is

A physics-based diesel engine simulator in Python. Not a lookup table, not a
curve fit, not a sample library. Torque, fuel consumption, emissions, wear and
**sound** are all consequences of solving the same equations that govern a real
engine.

Scope is deliberately broad, in the spirit of *Automation*: geometry, valve
timing, injection strategy, turbo matching, oil grade, surface finish and
clearances are inputs, and everything downstream reacts.

Two layers:
- **`dieselsim/`** — the batch research package. Solve an operating point, a
  curve, a map, a 12,000-hour durability run. Slow and accurate.
- **`play.py`** — a real-time interactive driving simulator with sound, a
  torque-converter or dual-clutch driveline, and a full instrument cluster.
  Fast, using a pre-solved grid.

## 1.2 The governing equation

Everything starts from a crank-angle-resolved first-law energy balance on each
cylinder, integrated over the full 720° at 0.5–1° steps:

```
du/dθ = (−p·dV/dθ + dQ_comb/dθ − dQ_wall/dθ + Σ ṁ_i·h_i/ω) / m
```

Nothing about it is quasi-steady. Mass crosses the valves both ways, blow-by
leaks past the rings in both directions, and the turbo shaft has inertia.

### The crank-angle convention (get this wrong and nothing works)

```
θ = 0          TDC firing
0   → 180      expansion
180 → 360      exhaust stroke
360 → 540      intake stroke
540 → 720      compression stroke
```

`soi_deg_btdc = 8.0` means injection at θ = 712. `evo_deg = 130` means the
exhaust valve cracks 50° before BDC on the power stroke.
`Geometry.phase_deg(i)` gives cylinder *i*'s offset from cylinder 1, derived
from `firing_order`.

## 1.3 Physics, module by module

### `thermo.py` — gas properties

Two-component mixture (unburned/burned) tracked by burned mass fraction `yb`.
`cp` is fitted to JANAF data as `cp = c∞ − A·exp(−T/τ)`, with a **dissociation
term above 2200 K**. γ is never assumed constant. Without dissociation, peak
temperatures come out hundreds of K high and NOx is badly overpredicted.

Constants: `_CP_A_INF/AMP/TAU = 1310/393/1185` (air),
`_CP_B_INF/AMP/TAU = 1500/480/1100` (burned), `_T_DISS = 2200`,
`_K_DISS = 0.35`. Fuel: `LHV = 42.7 MJ/kg`, `AFR_stoich = 14.5`.

Also: compressible orifice flow (choked and subsonic), bidirectional
`signed_orifice`, lift-dependent valve areas (curtain vs throat, `Cd` varying
with L/D), Sutherland viscosity.

### `kinematics.py` — slider-crank and cams

Exact offset slider-crank — no small-angle shortcuts. Cam profiles are a
raised-cosine main event with **explicit constant-velocity opening and closing
ramps**. The ramps are deliberate: the finite seating velocity they produce is
the physical source of valvetrain tick. ~~It grows as lash opens with wear.~~
*Corrected 2026-09-26:* while the lash stays inside the closing ramp, the
valve seats at the ramp's own speed whatever the lash (PR #43). Only lash
that outgrows the ramp raises it. The ramps end where they meet the flank, so
lift is continuous (FINDING-018).

### `lubrication.py` — oil and films

- **Viscosity**: Vogel base curve → Barus piezo-viscosity (`α = 1.9e-8 /Pa`) →
  Cross shear thinning → condition multipliers. A bearing at 2 GPa sees a very
  different oil than the sump does.
- **Journal bearings**: Ocvirk short-bearing solution, solved by bisection on
  eccentricity for `h_min`, attitude, friction torque and side leakage, with a
  squeeze-film credit under the firing impulse.
- **Ring and skirt films**: 1-D Reynolds, **supply-limited** — a ring can only
  entrain the film the previous stroke left on the liner (`oil_supply_film`).
- **Cam/follower**: Hamrock-Dowson EHL line contact.
- **Mixed lubrication**: Greenwood-Tripp-style λ ratio with
  `boundary_share = 1/(1+(λ/1.05)⁴)`.
- **Oil circuit**: positive-displacement pump against a clearance-cubed leakage
  network — a worn engine genuinely loses oil pressure.
- **Oil ageing**: Arrhenius oxidation, soot loading, TBN depletion, fuel
  dilution, additive consumption. Calibrated so a 15W-40 at ~115 °C reaches an
  oxidation index near 0.8 and gives up two-thirds of its TBN over a 500 h
  drain — what used-oil analysis on a highway truck shows.

### `friction.py` — component-level, crank-resolved

**There is no `FMEP = A + B·N + C·p_max` fit anywhere in this package.**

| Source | Model |
|---|---|
| compression rings | gas-loaded, inter-ring pressure decay 0.18^i, mixed lubrication |
| oil control ring | tension-loaded, boundary-dominated |
| piston skirt | side thrust from rod angle, partial journal bearing |
| piston pin | oscillates, never builds a full film → boundary/mixed always |
| rod & main bearings | Ocvirk + squeeze credit + asperity share |
| valvetrain | spring + inertia + gas load, roller or flat-tappet branch |
| windage | oil density and speed dependent |
| timing gears, crank seals | tooth mesh + lip drag |
| accessories | oil pump, water pump, fan, alternator, air compressor |
| **HP fuel pump** | `P = p_rail·Q/η` — at 1800 bar this is ~8.6 kW at rated on the HD engine, one of the largest single parasitic loads |

Boundary-friction power from each contact feeds the wear model.

### `wear.py` — Archard in energy form

```
V = k · E_boundary / (μ_b · H)
```

Wear is driven by the friction the tribology model actually computed, including
a cold-start multiplier reaching ~23× below 40 °C.

`K_ARCHARD`: `ring 1.95e-10`, `bore 1.14e-9`, `skirt 5.5e-10`,
`main_bearing 1.1e-9`, `rod_bearing 1.4e-9`, `cam 3.2e-9`. The ring is an order
of magnitude below the bore because it's nitrided and the bore isn't.

`health()` returns **life consumed** (0 = new, 100 = overhaul due).

### `turbo.py` — real shaft dynamics

Similitude compressor map: `pr_max = 1 + (pr_max_ref − 1)·u²` where
`u = n_corr/n_corr_ref`. The `u²` is Euler's turbomachinery equation, not a
fitted curve — double shaft speed, roughly quadruple the pressure rise. That's
why lag hurts.

Constant-speed lines are ellipses between surge and choke:
`m_corr = m_choke·√(1 − y²)` where `y = (pr−1)/(pr_max−1)`.

Turbine: variable nozzle via `effective_area(vgt_pos)`, efficiency peaking at
blade-speed ratio 0.68. Shaft integrated **live**:
`J·dω/dt = (P_turb − P_comp − P_fric)/ω`. Nothing is quasi-steady, which is
where turbo lag comes from.

### `cycle.py` — the core solver

- **Ignition delay**: Hardenberg-Hase, **integrated along the real p–T
  history** (`∫dt/τ = 1`), not evaluated once at injection.
- **Heat release**: three superposed Wiebe functions — pilot, premixed main,
  diffusion main. Premixed fraction from a Watson correlation driven by the
  computed delay. **The diffusion burn duration comes from actual nozzle
  flow**, so rail pressure, hole count, hole diameter and injector coking all
  change the burn shape.
- **Heat transfer**: Woschni, with motored pressure tracked in parallel.
- **Gas exchange**: bidirectional compressible flow through lift-dependent
  valve areas into finite-volume manifolds. Back-flow, overlap scavenging and
  residual gas all emerge. **PMEP is a result, not an input.**
- **Blow-by**: both directions through the ring-gap labyrinth (factor 0.42),
  using the gap the wear model currently reports.
- **EGR**: a real high-pressure loop. Flow needs exhaust-to-intake ΔP, so the
  VGT must close, and that costs pumping work.
- **Emissions**: extended Zeldovich NO in a two-zone burned region with
  excess-air entrainment; Hiroyasu formation/oxidation for soot.

Constants: `TAU_MIX_REV = 1.25` (entrainment timescale in crank revolutions,
scaled `(1800/rpm)^0.55` — mixing is driven by injection turbulence as well as
piston motion, so it does not scale as 1/rpm), `TAU_WALL = 0.11`,
`NOX_CAL = 0.030`, `SOOT_CAL = 0.28`, `GAMMA_B = 1.27`.

~~**The two emissions constants are the only fitted scalars in the package.**~~
*Corrected 2026-09-26 (Phase 1 exit):* that is no longer true. `NOX_CAL` and
`SOOT_CAL` are the two constants **fitted to data**. Beside them sit
**chosen** constants: set by judgement or to an owner's target, not fitted to
measurements. Each is stated where it lives:

- acoustics: `SPL_CAL = 0.10`, the combustion-sharpness divisor `5.0e9`
  (FINDING-003), the reference levels `_ref_dpdt`, `_ref_vseat`, `_ref_mdot`;
- wear: `K_ARCHARD["cam"] = 2.20e-7`, set to the owner's service-interval
  target of 150 µm at 2000 h (FINDING-015, FINDING-018);
- the limiter: the `crdi_1p5` torque trim, and the per-preset p_max / T_exh
  limits (FINDING-010);
- the EGR valve's starting opening, `EGR_VALVE_START_PER_CMD = 0.14`, the
  median of measured converged openings (FINDING-013).

### `engine.py` — governor, flywheel, orchestration

Couples everything and adds the control layer:

```
J·dω/dt = T_indicated(ω, fuel) − T_friction(ω, oil, wear) − T_load(ω)
```

- `fuel_limit_raw(rpm)` — smoke limit against an **open-loop** boost estimate,
  then governor droop above rated.
- `fuel_limit(rpm)` — the above, capped by the rating (`torque_limit`,
  `power_limit`, `torque_limit_map`).
- `fuel_for_torque()` — secant iteration against the real solver, cached per
  speed, to invert torque → fuel.
- `torque_cap(rpm)` — collapses flat torque limit, power limit and shaped map
  into one number.
- Two-node warm-up (coolant + block metal, thermostat, radiator) with wall
  temperatures following the coolant.
- `warmup()`, `durability_run()`, `transient()`, `full_load_curve()`,
  `performance_map()`.

### `acoustics.py` — sound from the physics

Every source is driven by something the solver already computed:

| You hear | It comes from |
|---|---|
| exhaust note | ṁ through the exhaust valve → 1-D waveguide (delay `2L/c`, open-end reflection, wall loss) → reactive muffler |
| intake roar | ṁ through the intake valve → runner quarter-wave → airbox Helmholtz → turbulent hiss ∝ ṁ³ |
| diesel clatter | `dp/dθ` exciting block/head structural modes; sharper rise lights up the high modes |
| injector tick | commanded injection events |
| valvetrain tick | cam seating velocity, growing with lash wear |
| piston slap | thrust reversal of rod side force, scaled by skirt clearance |
| turbo whine | shaft order of live turbo speed (blade-pass usually ultrasonic; included only if below Nyquist) |
| gear whine | tooth-mesh frequency of the timing gear train |
| rumble | boundary-friction power, firing-modulated |

**Synthesis happens in the crank-angle domain**, then resamples through
instantaneous engine speed by integrating crank phase. Pitch tracks rpm
exactly; a rev sweep needs no pitch-shifting, and engine orders fan out
correctly on a spectrogram.

Five mic positions: `exhaust_tip`, `intake`, `engine_bay`, `cabin`,
`exterior_7m`.

## 1.4 The feedback loops

The point of the package is that these are **closed, not scripted**.

**Wear → everything.** Ring gap grows → blow-by rises → trapped mass falls →
IMEP falls. Bearing clearance grows → leakage ∝ clearance³ → gallery pressure
falls → films thin → wear accelerates. Cam wears → lift lost → breathing
suffers. Injector cokes → burn lengthens → soot rises.

**Oil → friction → wear → oil.** Boundary friction generates wear; debris and
blow-by age the oil; aged oil thickens and loses TBN; that changes viscosity
and boundary friction coefficient, changing the wear rate.

**EGR trade-off.** Not scripted. Dilution means the flame must heat inert
products as well as air, so more charge mass is entrained per kg fuel and flame
temperature drops — Zeldovich NOx falls hard. The same dilution displaces
oxygen, so Hiroyasu soot oxidation slows and soot rises. And the HP loop needs
ΔP, so the VGT must close, costing pumping work. Measured: **20% EGR → NOx
−75%, soot +12%, IMEP −4%.**

**Thermal.** Wall temperatures follow coolant, so a cold engine loses more heat
per cycle, has a longer ignition delay, a bigger premixed spike and a sharper
`dp/dθ` — which is exactly why a cold diesel rattles.

## 1.5 Validation

12.74 L heavy-duty inline-6, VGT, cooled EGR:

| Quantity | Simulated | Real HD diesel |
|---|---|---|
| peak torque | 2310 N·m @ 1700 rpm | 2000–2500 |
| rated power | 432 kW @ 1800 rpm | 350–450 |
| peak BMEP | 22.8 bar | 20–24 |
| best BSFC | 213 g/kWh | 190–215 |
| peak cylinder pressure | 176 bar | 160–200 |
| FMEP at rated | 1.08 bar | 0.9–1.5 |
| mechanical efficiency | 95% @ rated | 88–95 |
| volumetric efficiency | 1.19 | 1.1–1.3 |
| engine-out NOx | 4.5 g/kWh rated, 20 lugging | 4–20 |
| engine-out soot | 0.05 g/kWh | 0.02–0.08 |
| blow-by, new | 11.8 L/min | 8–20 |
| wall heat loss | 19% of fuel energy | 15–25 |

Re-checked 2026-09-26 at the Phase 1 exit (`python3 tools/validate_table.py`,
fresh engine per point, n_cycles 9). All 12 rows are in band: peak torque
2313 N·m @ 1700, rated 432 kW, peak BMEP 22.8 bar, best BSFC 200 g/kWh
(1800 rpm, load 0.5), peak p_max 179 bar, FMEP at rated 1.10 bar, mechanical
efficiency 95%, volumetric efficiency 1.18 (on intake-manifold density), NOx
4.4 rated / 15.6 lugging at 1000 rpm, soot 0.047 g/kWh, blow-by 11.7 L/min,
wall heat 18%.

~~Over 12,000 h: power −5%, BSFC +6%, blow-by 11.8 → 18 L/min, oil soot sawtooths
0 → 2.8% per 500 h drain, life consumed ~20%.~~
*Corrected 2026-09-26:* that paragraph no longer holds, and how it was measured
was not recorded. On this tree (`tools/validate_table.py --aged`, 500 h steps,
rated point): power **−3.6%**, BSFC **+3.7%**, blow-by 11.5 → 18.3 L/min, oil
soot peaking at **1.8%** per drain, life consumed **6%**. The cylinder-kit
and bearing wear rates follow from boundary friction powers that FINDINGs
005, 006 and 015 changed.

Rendered audio at 1400 rpm peaks at 70/140/210 Hz — exactly firing frequency
and harmonics for an I6.

## 1.6 Honest limitations

- Burned zone is "two-zone-lite": one lumped burned region with air
  entrainment, not a multi-zone spray model. NOx and soot each carry one
  calibration constant.
- Manifolds are filling-and-emptying, not 1-D gas dynamics. Ram tuning is
  approximated; the acoustic waveguide is a separate downstream model.
- Compressor and turbine maps are similitude-generated, not measured.
- Structural response in the sound engine is a bank of modal resonators with
  assumed frequencies. A real one would come from an FE model.
- Wear coefficients are literature values, except the cam's, which is set to
  the owner's service-interval target (FINDING-015).
- Combustion is a Wiebe parameterisation informed by physics, not CFD spray and
  chemistry. **Removing that assumption is the single biggest fidelity upgrade
  available.**
- No tyre model in `play.py` — nothing stops tractive force exceeding grip.

---

# 2. IMPLEMENTATION DOCUMENT

## 2.1 File layout

```
dieselsim/
  __init__.py          7 lines
  config.py          684   spec dataclasses + presets
  thermo.py          211   gas properties, fuel, compressible flow
  kinematics.py      190   slider-crank, cam profiles
  lubrication.py     313   viscosity, films, bearings, oil ageing
  wear.py            317   Archard wear + feedback
  friction.py        328   crank-resolved component friction
  turbo.py           205   compressor, turbine, shaft dynamics
  cycle.py           706   the crank-angle first-law solver
  engine.py          660   governor, flywheel, maps, durability, transients
  acoustics.py       522   physics-driven sound synthesis
  batch.py           156   parallel multi-point solving
  builder.py         332   make an engine from headline numbers
demo.py              455   generates every figure and wav
play.py             2079   real-time interactive driver
engines/*.json             user engine definitions
```

Environment: Python 3.10+ (developed on 3.12, tested on 3.10.14 via pyenv on
WSL2/Ubuntu). Requires `numpy`, `scipy`, `matplotlib`. Optional: `sounddevice`
+ `libportaudio2` for live audio.

**Python 3.10 gotcha:** escapes inside f-string `{}` expressions are a
`SyntaxError` before 3.12. `ast.parse(feature_version=(3,10))` does **not**
catch this — grep for it instead.

## 2.2 Public API

```python
from dieselsim.engine import DieselEngine
from dieselsim.acoustics import EngineSound
from dieselsim import batch
from dieselsim.builder import build_engine, register, verify, load_engine_dir

eng = DieselEngine(preset="crdi15")          # or spec=EngineSpec(...)
op  = eng.operating_point(rpm, fuel_mg=None, load=None, egr=None,
                          n_cycles=10, warm_start=True, update_oil=False,
                          p_amb=101325.0, T_amb=298.0) -> OperatingPoint

eng.full_load_curve(rpms, n_cycles=9)
eng.performance_map(rpms, loads, n_cycles=8)
eng.warmup(minutes=12.0, rpm=None, load=0.25, dt_s=20.0, T_start=273.0)
eng.durability_run(hours, duty_cycle=None, step_h=50.0,
                   cold_starts_per_100h=40.0, resolve_every=1)
eng.transient(duration, throttle_fn, load_torque_fn, dt=0.02, rpm0=None,
              n_cycles=3)
eng.torque_cap(rpm)                          # rating cap, or None
eng.fuel_for_torque(rpm, T_target)           # cached secant inversion

snd = EngineSound(spec, fs=44100, dtheta=0.5)
snd.wear = eng.wear                          # so the engine ages audibly
y, sources = snd.render(op, duration=4.0, mic="exterior_7m", rpm_traj=None)
snd.write_wav(path, y, fs=44100, stereo=True)
snd.render_transient(eng, transient_log, mic=..., blend=0.35)

batch.solve_points(preset, [(rpm, load), ...], n_cycles=9, jobs=None,
                   overrides={"turbo.turbine_area_eff": 4e-4})
batch.full_load_curve(preset, rpms, jobs=8)
batch.performance_map(preset, rpms, loads, jobs=8)
batch.sweep(preset, rpm, load, "turbo.turbine_area_eff", values, jobs=8)

spec = build_engine(name, displacement, n_cyl, rated_rpm, peak_torque,
                    peak_power, plateau=(lo,hi), ...)
register("key", spec); verify(spec); load_engine_dir("engines")
```

Presets shipped: `hd_i6` (12.74 L HD I6 VGT), `ld_i4` (2.0 L CRD),
`crdi15` (1.5 L, 115 ps / 22.5 kg·m), `single` (0.58 L NA genset).

## 2.3 Data structures

**`OperatingPoint`**: `rpm, fuel_mg, torque, power, bmep, imep_net, fmep, pmep,
bsfc, isfc, eta_brake, eta_mech, fuel_kg_h, air_kg_s, exhaust_kg_s, p_max,
T_exh, boost_pr, turbo_rpm, egr_pct, nox_ppm, nox_g_kwh, soot_g_h, soot_g_kwh,
blowby_lpm, oil_T, oil_pressure, h_min_rod, h_min_main, h_min_ring,
lambda_ring, oil_cons_g_h, friction_breakdown, torque_trace, theta, cycle,
friction, wear_health`

**`CycleResult`**: `rpm, imep_gross, imep_net, pmep, p_max, dpdtheta_max, T_max,
T_burned_max, theta_pmax, mfb50, ign_delay_deg, ign_delay_ms, premix_fraction,
burn_duration_deg, inj_duration_deg, rail_pressure, m_air_trapped, m_fuel, afr,
phi, ve, boost_pr, p_intake, T_intake, p_exhaust, T_exhaust, egr_fraction,
egr_valve_area, residual_fraction, blowby_kg_s, blowby_lpm, q_wall_frac,
nox_ppm, soot_mg_per_cycle, turbo_rpm, turbo, traces, state, converged`

**`CycleTraces`** (crank-angle arrays): `theta, p, T, V, mdot_int, mdot_exh,
hrr, T_burned, p_int_manifold, p_exh_manifold, mdot_blowby, valve_lift_int,
valve_lift_exh` + scalars `soi_deg, soc_pilot_deg, soc_main_deg, pilot_soi_deg,
inj_dur_main_deg`

**`FrictionResult`** keys: powers `P_rings, P_skirt, P_pin, P_rods, P_mains,
P_valvetrain, P_windage, P_oilpump, P_waterpump, P_fan, P_alternator,
P_aircomp, P_fuelpump, P_accessories, P_mech, P_friction`; boundary powers
(drive wear) `Pb_rings, Pb_skirt, Pb_pin, Pb_rods, Pb_mains, Pb_valvetrain`;
state `h_ring, h_ring_mid, h_skirt, h_rod, h_main, lambda_ring, mu_oil_ring,
mu_oil_bearing, gallery_pressure, oil_flow, v_seating, F_side, F_rod, u_piston,
torque, torque_per_cyl, fmep`

⚠ **`h_ring` is the instantaneous minimum, which always occurs at TDC/BDC where
piston speed is zero and tells you nothing. Read `h_ring_mid`.**

**`WearState`**: `hours, cycles, cold_starts, fuel_burned_kg,
accumulated_wear_energy, bore_wear_tdc, bore_taper, ring_face_wear,
ring_gap_growth, ring_tension_loss, skirt_wear, main_clearance_growth,
rod_clearance_growth, cam_wear_int, cam_wear_exh, lash_growth_int,
lash_growth_exh, seat_recession, injector_coking, injector_spray_deg,
turbo_shaft_wear, turbo_foul_comp, turbo_foul_turb, dpf_soot_load,
min_film_seen_main, min_film_seen_rod`

## 2.4 EngineSpec fields

Nine dataclasses. Full field-by-field tables are in `REFERENCE.md`; the
headline ones:

**`Geometry`**: `bore, stroke, conrod, n_cyl, compression_ratio, pin_offset,
firing_order, vee_angle_deg, recip_mass, rot_mass_bigend, flywheel_inertia`.
Derived properties: `crank_radius, piston_area, displacement_cyl,
displacement, clearance_volume, rod_ratio, mean_piston_speed(rpm),
phase_deg(i)`.

**`ValveTrain`**: `ivo_deg, ivc_deg, evo_deg, evc_deg, n_intake_valves,
n_exhaust_valves, intake_valve_dia, exhaust_valve_dia, intake_lift_max,
exhaust_lift_max, lash_intake, lash_exhaust, cam_base_radius, follower_radius
(0 ⇒ flat tappet), valve_spring_preload, valve_spring_rate,
valve_train_eq_mass, cd_intake, cd_exhaust, ramp_fraction`

**`Injection`**: `n_holes, hole_dia, cd_nozzle, rail_pressure_max,
rail_pressure_idle, soi_deg_btdc, pilot_enabled, pilot_fraction,
pilot_advance_deg, cetane_number, fuel_temp`

**`Turbo`**: `enabled, comp_wheel_dia, turb_wheel_dia, comp_blades, turb_blades,
shaft_inertia, comp_eff_peak, turb_eff_peak, n_corr_ref, mdot_corr_max,
pr_max_ref, turbine_area_eff, vgt, vgt_min_frac, wastegate_pset,
wastegate_gain, bearing_visc_k, intercooler_eff, intercooler_dp,
charge_cooler_medium_T`

**`AirPath`**: `intake_plenum_vol, exhaust_manifold_vol, runner_length_int,
runner_length_exh, intake_pipe_length, airbox_volume, airbox_neck_len,
airbox_neck_area, air_filter_dp_k, exhaust_pipe_length, exhaust_pipe_dia,
muffler_volume, muffler_length, dpf_present, egr_max_fraction,
intake_restriction_area, exhaust_outlet_area`

**`Lubricant`**: `name, vogel_a, vogel_b, vogel_c, density15, viscosity_index,
tbn0, hths, sump_volume, pump_disp, pump_relief, pump_eta_vol, pump_eta_mech,
cooler_UA, change_interval_h`

**`Tribology`**: ring pack (`n_comp_rings, ring_axial_width,
ring_tangential_load, oil_ring_load, oil_ring_width, ring_gap_new,
ring_face_roughness, bore_roughness, oil_supply_film, bore_hardness,
ring_hardness`), piston/bearings (`skirt_area, skirt_clearance_new, piston_alu,
main_dia, main_width, main_clearance_new, n_mains, rod_dia, rod_width,
rod_clearance_new, bearing_roughness, bearing_hardness, pin_dia, pin_width,
pin_clearance, pin_mu_boundary`), accessories (`water_pump_k, fan_k, fan_duty,
alternator_load_W, alternator_eta, windage_k, aircomp_load_W, fuel_pump_eta,
fuel_pump_spill, seal_drag_Nm, gear_train_k`)

**`Thermal`**: `coolant_T, piston_T, head_T, liner_T_top, liner_T_bot,
port_T_exh, ambient_T, ambient_p, oil_T_start, oil_T_target, coolant_volume,
metal_mass, radiator_UA, thermostat_open_T, thermostat_full_T`

**`Cooling`**: radiator (`rad_core_area, rad_core_depth, rad_UA_ref,
rad_air_ref, grille_recovery`), fan (`fan_dia, fan_max_flow, fan_power_max,
fan_type, fan_on_T, fan_off_T, fan_ramp_s`), charge cooler (`ic_UA_ref,
ic_air_ref, ic_core_area, ic_ahead_of_rad, ic_dp_ref`), protection (`T_warn,
T_derate, T_derate_full, derate_floor, T_shutdown, T_restart, allow_shutdown`)

**`EngineSpec`** top level: `name, geom, valves, inj, turbo, air, oil, trib,
thermal, cooling, idle_rpm, rated_rpm, max_rpm, afr_limit, afr_stoich,
torque_limit, power_limit, torque_limit_map, boost_map_rise,
crank_gear_teeth, cam_gear_teeth, injpump_gear_teeth`

## 2.5 `play.py` — real-time architecture

### Why a pre-solved grid
One operating point takes 1.5–3 s. You cannot do that 60×/second. So:
- **Offline, once**: solve an (rpm × load) grid and keep the crank-angle
  acoustic sources for each point. Cached to
  `.dieselsim_grid_{preset}_v{CACHE_VERSION}.pkl`. **CACHE_VERSION = 5.**
- **At runtime**: integrate only the cheap things — flywheel, turbo shaft,
  driveline, thermal — and bilinearly interpolate the grid.

Honest: combustion phasing is interpolated, not re-solved per frame. Flywheel
inertia, governor, smoke limit, turbo lag and crank-phase-derived pitch remain
real.

### The transmission switch
```python
TRANSMISSION = "dct"     # "tc" = torque-converter auto, "dct" = dual clutch
```
Also `--transmission tc|dct`.

### Key classes
- **`EngineGrid`** — build/save/load, `blend_sources()`, `blend_perf()`,
  `peak_torque`, `peak_power`.
- **`Vehicle`** — `mass, r_wheel, gears, final, CdA, Crr, eta, J_trans,
  J_wheel, TR_stall, stall_rpm, v_lock_min, launch_rpm, clutch_cap_max,
  fuel_tank_L, trans`.
- **`TorqueConverter`** — `k_cap = T_ref/ω_stall²`,
  `T_pump = k_cap·λ(SR)·ω_e²`, `T_turb = TR(SR)·T_pump`. λ flat to SR≈0.5 then
  collapses (real K-factor shape), zero at SR=1, negative beyond (engine
  braking). ⚠ **A converter is specified by STALL SPEED, not rated speed.**
- **`LaunchClutch`** (DCT) — commanded capacity holds engine at `launch_rpm`
  while the car catches up; when slip closes, clamps and the driveline is
  **rigid crank-to-wheels**. Solved as reflected inertia, not a stiff spring —
  unconditionally stable.
- **`Gearbox`** — clutch-to-clutch with real two-phase shifts (below).
- **`Driveline`** — converter/clutch + gearbox + vehicle. States: `v`, `w_in`
  (input shaft is a **state**, not a function of road speed), `rigid`, `i_eff`.
- **`LiveEngine`** — governor, turbo lag, cruise control, trip computer,
  cooling stack, derates.
- **`LiveSound`** — streaming DSP with persistent filter state; ~15× realtime.

### The two-phase shift
- **Torque phase** (110–220 ms TC, ~45–90 ms DCT): oncoming clutch takes the
  load, input speed doesn't move. New gear is numerically lower ⇒ output torque
  **drops**. That's the torque hole. Measured: 22.0 → 11.1 kN on the truck.
- **Inertia phase** (260–520 ms TC, ~130–260 ms DCT): offgoing out, oncoming
  slips at commanded capacity, and *that slip drags the turbine and engine to
  the new ratio*. Input ramps 1698 → 942 rpm. Output torque is the clutch
  capacity, usually above steady — the firm push at the end. Measured
  11.1 → 24.6 kN.
- TCU commands a 25–35% engine torque cut during the inertia phase.
- ⚠ **Capacity must be latched from the slip at phase entry.** Recomputing it
  from live slip makes the excess shrink as the error shrinks → exponential
  decay → the shift never finishes and hits the abort timer.

### Cooling stack
Front to back: grille → charge cooler → radiator → out. Both cores solved with
effectiveness-NTU **on their own airflow**, so rejection scales with airflow,
not a fixed UA. The IC heats the air the radiator then gets. Fan engages on
hysteresis, costs crank power (`fan_power_max·frac³`) unless electric.

Two derates: charge temperature (multiplicative on torque, since air mass
follows density; clamped ≤1.0 — a better IC than the grid assumed cannot invent
torque) and overheat (linear from `T_derate` to `T_derate_full` down to
`derate_floor`, shutdown at `T_shutdown`, restart below `T_restart`).

### CLI
```
--preset {auto-discovered}  --mic {5 positions}  --transmission tc|dct
--no-audio  --audio-test  --rebuild  --rpm-points N  --load-points N
--torque-limit NM  --power-limit KW
--curve  --curve-points N  --curve-load F  --curve-png F  --curve-csv F
--jobs/-j N  --load FRAC  --start-kmh V  --record WAV
```

### Keys
`w/s` throttle · `space` full · `x` cut · `b` brake · `e` exhaust brake ·
`n` neutral · `m` auto/manual · `,`/`.` gear · `[`/`]` grade · `c` cruise ·
`+`/`-` set speed · `o` trip reset · `f` refuel · `l` lockup allow (TC only) ·
`1`–`5` mic · `r` reset/restart · `q` quit

## 2.6 Performance

- One solve: **1.47 s** (was 4.58 s before the scalar-numpy fix).
- Sound synthesis: **~15× realtime**.
- Grid build (8×6): ~2 min, cached.
- `batch.py` scales near-linearly with cores.

### The optimisation that mattered
Profiling showed 623,502 calls to `_int_cp_burned` per solve. `np.exp()` on a
single float costs 0.87 µs vs ~0.06 µs for `math.exp` — that overhead alone was
a quarter of runtime. Scalar fast paths with numpy fallback gave **3.1×** with
worst relative difference **3.07e-14** (machine precision).

### Why not GPU
The crank loop is a sequential recurrence — step *k+1* needs step *k*. Work per
step is a handful of scalar ops, far less than the 5–10 µs of a kernel launch.
A GPU port of a single solve is **slower**. GPUs also default to float32; this
runs float64, so naive porting is **less** accurate.

The only real GPU design is a batched rewrite with the **batch dimension over
operating points** and crank angle stepping sequentially — worth it for
hundreds of points, not one. Order of value: Numba `@njit` on the four thermo
functions (biggest win, smallest change) → `batch.py` across cores → batched
array rewrite in JAX/PyTorch.

## 2.7 KNOWN BUGS AND OPEN ISSUES

Read this section before trusting any number.

1. **`n_cycles=6` is not converged.** Five identical calls drift
   245 → 252 N·m; at 14 cycles it settles near 267. Results at 6 cycles run a
   few percent light. Use ≥9. `cal_cycles = 8` in `engine.py` for limiter
   calibration.
2. **Fuelling is open-loop on rpm, not closed on measured boost.** Improving
   the turbo does **not** raise fuelling or torque on its own. Closing the loop
   naively is unstable — it collapses to the low-boost equilibrium at 1500 rpm
   (148 N·m) and runs away to 524 N·m (33 bar BMEP) at 2500. Needs a
   rate-limited boost-follower.
3. **Torque limiter residual error ±3%** across the plateau (was 11%). Symptom
   of #1, not a separate bug.
4. **Light-load fuel consumption is understated**, probably by ~2×. Cruise
   economy reads 26 km/L at 90 km/h on the 1.5 L; real is 4.5–5.5 L/100km.
   Trends are trustworthy, absolute figures are not. **Trace `fuel_kg_h` at low
   load against the grid's `fuel_mg` before relying on economy numbers.**
5. **`operating_point` warm-starts from the previous call**, so results are
   mildly path-dependent. `batch.py` avoids this.
6. **The `l` key is dead in DCT mode** — `lock_allowed` is only read in
   `_step_tc`.
7. **Real-time combustion doesn't respond to coolant temperature.** The grid is
   solved warm, so the gauge, fan and radiator respond but the engine doesn't
   run worse cold. `demo.py` stage s3 models this properly.
8. **`engine.py` contains code of unknown provenance** — an AFR-headroom block
   in `fuel_for_torque` and a duplicate `self.cal_cycles` (10 then 8; the
   second wins). Also a `compact_crdi_i4` preset and `crdi_1p5` key I did not
   write. Read before trusting.
9. **Worn-vs-new audio pair is suspect** — the worn engine reported *lower*
   blow-by than new and zero lash growth.
10. **`render_transient` cross-fade seams** are audible where the source
    operating point switches.
11. **Coast downshifts use power-on calibration**; a real TCU is gentler
    off-throttle. Lockup is binary, not continuous slip control.
12. **Grade force uses the small-angle form** `m·g·grade` and rolling
    resistance omits `cos θ`. Under 10% grade the error is <0.5%.

### Bugs already fixed — do not reintroduce
- Ring/skirt film formulas dimensionally wrong (`b` vs `b²`, `L` vs `L²`) →
  400 µm films.
- Missing friction: piston pin, timing gears, crank seals, HP fuel pump.
- Oil thermal model had no coolant node; integrator unstable at 60 s steps.
- `overall_health()` read 56% on a new engine.
- Archard `K` had a nitrided ring wearing faster than the cast-iron bore.
- **`acoustics._impulses()` window was identically zero** —
  `raised_cosine(w)` with `w=2`. Valve tick, injector tick and piston slap
  produced silence with no error.
- TBN consumed 10× too fast (stray `×1e3`).
- Turbine speed teleported on ratio change (TC), and road speed teleported
  (DCT) — the latter produced 700 kW of kinetic energy from nowhere.
- 23 g acceleration spike on DCT clamping (residual slip was being put into the
  car instead of the engine).
- Converter sized off rated speed instead of stall speed.
- `q_wall_frac` is 0/0 at zero fuelling → coolant gauge read −33 °C.
- 1.5 L was using the truck's 42 L / 620 kg cooling system.
- f-string escapes inside `{}` — `SyntaxError` on Python 3.10.

---

# 3. ANGULAR BUILD GUIDE

Goal: a browser UI that is genuinely nicer than the terminal — a live
instrument cluster, an engine designer, and a results explorer.

## 3.1 Architecture

```
┌──────────────────────────────────────────────┐
│ Angular 17+ (standalone components, signals) │
│  dashboard │ designer │ analysis │ garage    │
└───────┬──────────────────────┬───────────────┘
        │ WebSocket (60 Hz)    │ REST
┌───────▼──────────────────────▼───────────────┐
│ FastAPI (Python 3.10+)                       │
│  sim loop thread  ·  batch workers  ·  audio │
└───────┬──────────────────────────────────────┘
        │
┌───────▼──────────────────────────────────────┐
│ dieselsim package (unchanged)                │
└──────────────────────────────────────────────┘
```

**Do not rewrite the physics in TypeScript.** It is 3,700 lines of coupled
numerics with float64 dependencies and a 1.5 s solve time. Wrap it.

## 3.2 Backend: FastAPI

```python
# server.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio, threading, time

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4200"],
                   allow_methods=["*"], allow_headers=["*"])
```

### REST endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/presets` | list keys + display names + headline specs |
| GET | `/api/spec/{key}` | full EngineSpec as nested JSON |
| PUT | `/api/spec/{key}` | update spec fields (invalidates grid cache) |
| POST | `/api/engines` | build from headline numbers → new key |
| DELETE | `/api/engines/{key}` | remove a user engine |
| POST | `/api/curve` | full-load curve; body `{preset, points, load, jobs, torque_limit, power_limit}` |
| POST | `/api/map` | performance map (rpm × load grid) |
| POST | `/api/sweep` | parameter sweep; body `{preset, rpm, load, param, values}` |
| POST | `/api/cycle` | single operating point + **full crank-angle traces** |
| POST | `/api/durability` | long run; returns a job id |
| GET | `/api/jobs/{id}` | poll progress `{state, pct, result}` |
| POST | `/api/session` | create a live sim session; returns `{session_id}` |
| GET | `/api/audio/{session_id}.wav` | rendered clip at current operating point |

Long jobs (grid build, durability, map) must be **background tasks with
progress**, never blocking requests. Grid build is ~2 min.

```python
@app.post("/api/curve")
async def curve(req: CurveRequest):
    from dieselsim import batch
    pts = np.linspace(req.rpm_min, req.rpm_max, req.points)
    res = await asyncio.get_running_loop().run_in_executor(
        None, lambda: batch.full_load_curve(req.preset, pts, jobs=req.jobs))
    return {"points": [asdict(r) for r in res]}
```

### WebSocket: `/ws/sim/{session_id}`

**Client → server** (on input change, not every frame):
```json
{"type":"control","throttle":0.6,"brake":0.0,"gear_up":false,
 "gear_down":false,"neutral":false,"auto":true,"grade":0.06,
 "cruise":true,"cruise_set_kmh":90,"mic":"cabin","transmission":"dct",
 "reset":false,"refuel":false}
```

**Server → client** at 30–60 Hz (tune down to 20 Hz if the browser struggles):
```json
{"t":12.34,"rpm":2301,"speed_kmh":80.4,"gear":5,"gear_label":"5",
 "shift_phase":"idle","throttle":0.21,"fuelling":0.21,"smoke_limited":false,
 "torque":34.2,"power_kw":8.2,"peak_torque":235,"peak_power_kw":82,
 "boost_pr":1.31,"turbo_rpm":54000,"afr":28.4,"egr_pct":12.0,
 "p_max_bar":92.1,"bsfc":214,"nox_g_kwh":3.1,"soot_g_h":0.02,
 "coolant_c":85.8,"charge_c":40.7,"ic_eff":0.90,"rad_air":3.77,
 "fan_frac":0.0,"derate":1.0,"overheat_msg":"",
 "fuel_l":43.4,"fuel_frac":0.96,"range_km":507,
 "odo_km":19.04,"trip_km":19.04,"inst_kmpl":7.7,"trip_kmpl":11.7,
 "converter":{"sr":1.00,"tr":1.00,"eff":1.0,"locked":true,"rigid":true},
 "engine_stopped":false}
```

Server loop runs at a fixed 60 Hz in its own thread, decoupled from the send
rate:

```python
def sim_thread(session):
    dt = 1.0 / 60.0
    nxt = time.perf_counter()
    while session.alive:
        session.live.dl.brake = max(0.0, session.live.dl.brake - dt / 0.45)
        with session.live.lock:
            session.live.step(dt)
        session.telemetry = snapshot(session.live)
        nxt += dt
        time.sleep(max(0.0, nxt - time.perf_counter()))
```

⚠ **Never step the sim from the WebSocket handler.** Physics must run at a
fixed rate regardless of network jitter, or the flywheel integration goes
wrong.

## 3.3 Audio

Two options — pick based on whether you need continuous engine sound.

**Option A (simpler, good enough):** render 3–4 s WAV clips server-side at
representative operating points, serve over REST, loop and crossfade in the
browser with Web Audio, and adjust `playbackRate` with rpm. Cheap but pitch
drifts from truth under hard acceleration.

**Option B (correct):** stream PCM over a second WebSocket. `LiveSound.block()`
already produces float32 blocks with persistent filter state at ~15× realtime.

```python
# /ws/audio/{session_id}: send 1024-sample float32 blocks
y = session.snd.block(1024, rpm, load_eff, boost, turbo_rpm, running=True)
await ws.send_bytes(y.astype("<f4").tobytes())
```

Browser side: `AudioWorkletProcessor` with a ring buffer, target ~150 ms
latency, ~4 blocks of jitter buffer.

```js
class EngineProcessor extends AudioWorkletProcessor {
  constructor() { super(); this.buf = new Float32Array(65536);
    this.r = 0; this.w = 0;
    this.port.onmessage = e => { /* append e.data to ring */ }; }
  process(_, outputs) {
    const out = outputs[0][0];
    for (let i = 0; i < out.length; i++)
      out[i] = this.w - this.r > 0 ? this.buf[this.r++ & 65535] : 0;
    return true;
  }
}
```

Autoplay policy: audio cannot start without a user gesture. Put a **"Start
engine"** button over the dashboard; use it to `audioContext.resume()`.

## 3.4 Angular app structure

```
src/app/
  core/
    services/
      sim-socket.service.ts      WebSocket + reconnect, exposes signals
      api.service.ts             typed REST client
      audio.service.ts           AudioWorklet + gain + mute
      keyboard.service.ts        keybinds mirroring the CLI
    models/
      telemetry.model.ts
      engine-spec.model.ts
      curve-point.model.ts
  features/
    dashboard/                   the live cluster
      dashboard.page.ts
      widgets/
        tachometer.component.ts
        speedometer.component.ts
        gauge-arc.component.ts   generic arc gauge
        bar-gauge.component.ts
        gear-indicator.component.ts
        shift-phase.component.ts
        trip-computer.component.ts
        driveline-diagram.component.ts
        warning-lamps.component.ts
    designer/                    build/edit an engine
      designer.page.ts
      headline-form.component.ts
      spec-editor.component.ts   grouped accordion over all 9 dataclasses
      verify-panel.component.ts
    analysis/                    curves, maps, cycle traces
      curve.page.ts
      map.page.ts
      cycle.page.ts              p-V, p-θ, HRR, valve lift, manifolds
      sweep.page.ts
      durability.page.ts
    garage/                      preset library, vehicle setup
  shared/
    ui/                          buttons, sliders, cards, toasts
```

Use **standalone components**, **signals** for state (not NgRx — the state is
small and mostly streaming), and `ChangeDetectionStrategy.OnPush` everywhere.

### Telemetry service pattern

```ts
@Injectable({providedIn: 'root'})
export class SimSocketService {
  private ws?: WebSocket;
  readonly telemetry = signal<Telemetry | null>(null);
  readonly connected = signal(false);

  // derived signals: components subscribe to exactly what they need
  readonly rpm = computed(() => this.telemetry()?.rpm ?? 0);
  readonly speedKmh = computed(() => this.telemetry()?.speed_kmh ?? 0);
  readonly overheating = computed(() => (this.telemetry()?.coolant_c ?? 0) > 105);

  connect(sessionId: string) { /* ws.onmessage -> this.telemetry.set(...) */ }
  send(control: Partial<Control>) { this.ws?.send(JSON.stringify(
      {type: 'control', ...control})); }
}
```

⚠ **Do not run change detection at 60 Hz on the whole tree.** Update signals
inside `NgZone.runOutsideAngular` and let OnPush components with `computed()`
pull only what changed. For the fastest-moving needles, render on canvas in a
`requestAnimationFrame` loop that reads the signal directly and never triggers
CD at all.

## 3.5 The dashboard — every detail

Layout: three columns on desktop (≥1280px), stacked on mobile.

### Centre: the cluster
- **Tachometer** — large arc, 0 → `max_rpm`. Green to `rated_rpm`, amber to
  `max_rpm`, red beyond. Redline tick at rated. Needle animated with a spring
  (stiffness ~180, damping ~26) so it settles like a real one instead of
  snapping. Digital rpm inside.
- **Speedometer** — mirrored arc, km/h, digital readout, small mph secondary.
- **Gear indicator** — big numeral. During a shift show the phase: amber during
  torque phase, brighter during inertia phase, with a small caption
  ("torque phase" / "inertia phase · cut 35%"). **This is a signature feature
  — the sim models it and nothing else on the web shows it.**
- **Warning lamps row** — coolant temp (amber at `T_warn`, red at `T_derate`),
  derate active, engine stopped, low fuel, smoke-limited, surge. Use real
  ISO-style glyphs.

### Left: engine vitals
Arc or bar gauges: torque (vs `peak_torque`), power (vs `peak_power`), boost
(PR, with 1.0 marked), turbo speed (krpm), AFR (with the smoke limit drawn as a
red zone), EGR %, peak cylinder pressure, BSFC.

### Right: thermal + trip
- Coolant temperature arc, blue < 60 °C, green 60–103, red above. Fan icon
  spins when `fan_frac > 0.05`, speed proportional.
- Charge-air temperature + IC effectiveness + core airflow — a small
  **stack diagram** (grille → IC → radiator) with animated airflow arrows whose
  density tracks `rad_air`. This makes the "slow climb overheats" behaviour
  legible at a glance.
- Fuel bar with range, amber < 25%, red < 12%.
- Trip computer: odo, trip, L used, now/trip/avg km/L.
- Cruise control chip showing set speed when active.

### Bottom: controls
Throttle and brake as **vertical sliders** that respond to pointer drag and to
keyboard. Grade slider −20…+20%. Gear mode toggle (auto/manual) with paddle
buttons in manual. Transmission toggle (TC/DCT) — note this **rebuilds nothing**,
it's a live switch. Mic selector as a segmented control. Master audio
mute/volume.

### Micro-detail that makes it feel real
- Needle sweep on connect (full scale and back), like a car's self-test.
- Shift indicator flashes on upshift.
- Coolant needle rises visibly during warm-up — do not smooth it away.
- When `engine_stopped`, dim the whole cluster and show
  "ENGINE STOPPED — OVERHEAT" with a restart button that is **disabled until
  `coolant_c < T_restart`**. Show the countdown temperature.
- Torque hole: the tractive-force readout dips during the torque phase. Plot
  the last 5 s of tractive effort as a sparkline so the dip is visible.

## 3.6 Engine designer

Two modes on one page.

**Headline mode** (default, for everyone): displacement, cylinders, rated rpm,
peak torque, peak power, plateau start/end, turbo on/off, VGT on/off. Live
preview of derived bore/stroke/CR/valve sizes as you type. A **"Verify"**
button runs `verify()` on the server and shows achieved vs requested as a
gauge pair with a percentage — this is honest and it teaches the user that the
builder sizes hardware but the solver decides.

**Expert mode**: an accordion over all nine dataclasses, one panel each, every
field with units, tooltip (pull the text from `REFERENCE.md`), min/max, and a
"reset to preset" button. Group by physical subsystem, not by class name.

Show a **warning banner** when a change invalidates the grid cache, with a
"Rebuild grid (~2 min)" button and a progress bar.

## 3.7 Analysis pages

- **Curve** — torque/power dual-axis, and small multiples for BSFC, p_max,
  boost, AFR, η_mech, NOx/soot. Overlay multiple engines for comparison. Export
  CSV/PNG. Show the rating cap as a dashed line where set.
- **Map** — rpm × load heat map of BSFC (the classic "island" plot), with a
  torque-curve overlay and a crosshair that shows the full operating point on
  hover.
- **Cycle** — the money page. p–V on log-log, p–θ zoomed to ±60° ATDC, heat
  release rate, valve lift, manifold pressures, two-zone temperature. Annotate
  SOI, start of combustion, CA50. A crank-angle scrubber that moves a marker
  across every chart at once.
- **Sweep** — pick any spec parameter, a range, and a fixed operating point;
  plot any output against it. This is the turbo-matching tool.
- **Durability** — 12 small charts over hours, with the oil-drain sawtooth
  clearly visible. A "life consumed" gauge set.

Charts: **ECharts** (`ngx-echarts`) or **Plotly**. Both handle 2,000-point
crank traces and log axes well. Avoid Chart.js for the cycle page — log-log and
dual-axis get awkward.

## 3.8 Practical notes for whoever builds this

- **Poll rate**: send telemetry at 30 Hz, not 60. The eye can't tell, and it
  halves the JSON churn. Keep physics at 60.
- **Backpressure**: if the client can't keep up, drop frames — never queue
  telemetry. Use `ws.send` with a "latest wins" slot.
- **Session lifetime**: one `LiveEngine` per session, cleaned up on disconnect
  with a 30 s grace period for reconnects.
- **Grid cache**: keyed by preset **and** spec hash. Changing a spec field must
  invalidate it, or the UI will silently show stale physics.
- **Units**: the API should send SI and let the UI convert. Offer a
  metric/imperial toggle; a lot of engine people want psi and lb-ft.
- **Error surfacing**: if a solve fails, show it. Do not silently substitute
  zeros — that is how the `_impulses` silent-zero bug survived so long here.
- **Mobile**: the cluster works on a phone in landscape. Throttle/brake as
  touch sliders is genuinely playable. The designer and analysis pages should
  be desktop-first.
- **Accessibility**: gauges need text alternatives; do not encode warnings in
  colour alone (add the glyph and the word).

## 3.9 Suggested build order

1. FastAPI wrapper + `/api/presets`, `/api/curve`, `/api/cycle`. Verify against
   the CLI's numbers before touching Angular.
2. Angular shell + curve page. Proves the REST path and charting.
3. Session + WebSocket + a minimal dashboard (rpm, speed, gear only).
4. Full cluster widgets.
5. Audio (Option A first, then B).
6. Designer.
7. Map, sweep, durability.

Get 1–3 correct before building anything pretty. The physics is the product;
the UI's job is to not lie about it.
