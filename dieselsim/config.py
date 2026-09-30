"""
config.py -- Engine specification: geometry, valvetrain, injection, turbo,
tribology, lubricant and thermal data.

All values SI unless the field name says otherwise.
Crank-angle convention used everywhere in this package:

    theta = 0 deg   -> TDC firing (combustion TDC)
    0   -> 180      -> expansion
    180 -> 360      -> exhaust stroke
    360 -> 540      -> intake stroke
    540 -> 720      -> compression stroke
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------
@dataclass
class Geometry:
    bore: float                      # m
    stroke: float                    # m
    conrod: float                    # m  (centre-to-centre)
    n_cyl: int
    compression_ratio: float         # geometric
    pin_offset: float = 0.0          # m  (+ = toward thrust side)
    firing_order: Tuple[int, ...] = (1,)
    vee_angle_deg: float = 0.0       # 0 => inline
    recip_mass: float = 1.10         # kg, piston + rings + pin + small end
    rot_mass_bigend: float = 0.75    # kg, rotating part of the con-rod
    flywheel_inertia: float = 1.60   # kg m^2 (flywheel + crank + damper)

    # ---- derived ---------------------------------------------------------
    @property
    def crank_radius(self) -> float:
        return self.stroke / 2.0

    @property
    def piston_area(self) -> float:
        return math.pi * self.bore ** 2 / 4.0

    @property
    def displacement_cyl(self) -> float:
        return self.piston_area * self.stroke

    @property
    def displacement(self) -> float:
        return self.displacement_cyl * self.n_cyl

    @property
    def clearance_volume(self) -> float:
        return self.displacement_cyl / (self.compression_ratio - 1.0)

    @property
    def rod_ratio(self) -> float:
        """lambda = a/l -- controls secondary motion & piston slap."""
        return self.crank_radius / self.conrod

    def mean_piston_speed(self, rpm: float) -> float:
        return 2.0 * self.stroke * rpm / 60.0

    def phase_deg(self, cyl_index: int) -> float:
        """Crank angle offset of cylinder `cyl_index` (0-based) relative to
        cylinder #1, derived from the firing order."""
        cyl_no = cyl_index + 1
        pos = self.firing_order.index(cyl_no)
        return pos * (720.0 / self.n_cyl)


# --------------------------------------------------------------------------
# Valve train
# --------------------------------------------------------------------------
@dataclass
class ValveTrain:
    # Timing in the 0..720 convention (0 = TDC firing)
    ivo_deg: float = 345.0           # intake opens (before TDC overlap)
    ivc_deg: float = 570.0           # intake closes (after BDC)
    evo_deg: float = 130.0           # exhaust opens (before BDC)
    evc_deg: float = 375.0           # exhaust closes (after TDC overlap)

    n_intake_valves: int = 2
    n_exhaust_valves: int = 2
    intake_valve_dia: float = 0.042  # m, inner seat diameter
    exhaust_valve_dia: float = 0.038
    intake_lift_max: float = 0.0125  # m
    exhaust_lift_max: float = 0.0120

    lash_intake: float = 0.30e-3     # m, cold lash at the valve
    lash_exhaust: float = 0.55e-3

    # cam / follower tribology
    cam_base_radius: float = 0.022   # m
    follower_radius: float = 0.020   # m (roller) -- 0 => flat tappet
    valve_spring_preload: float = 380.0   # N per valve at zero lift
    valve_spring_rate: float = 42.0e3     # N/m
    valve_train_eq_mass: float = 0.34     # kg referred to the valve

    # discharge coefficients (fitted vs L/D, see thermo.valve_cd)
    cd_intake: float = 0.72
    cd_exhaust: float = 0.70

    # cam ramp: fraction of the event used for the constant-velocity ramp.
    ramp_fraction: float = 0.06


# --------------------------------------------------------------------------
# Fuel injection
# --------------------------------------------------------------------------
@dataclass
class Injection:
    n_holes: int = 8
    hole_dia: float = 0.175e-3       # m
    cd_nozzle: float = 0.78
    rail_pressure_max: float = 1800e5   # Pa
    rail_pressure_idle: float = 350e5   # Pa
    soi_deg_btdc: float = 8.0        # main injection start, deg BTDC
    pilot_enabled: bool = True
    pilot_fraction: float = 0.045    # of total fuel mass
    pilot_advance_deg: float = 14.0  # deg before main SOI
    cetane_number: float = 50.0
    fuel_temp: float = 320.0         # K at the nozzle


# --------------------------------------------------------------------------
# Turbocharging / air path
# --------------------------------------------------------------------------
@dataclass
class Turbo:
    enabled: bool = True
    comp_wheel_dia: float = 0.076    # m (inducer/exducer scale)
    turb_wheel_dia: float = 0.068    # m
    comp_blades: int = 12            # full+splitter blade count (tone source)
    turb_blades: int = 11
    shaft_inertia: float = 1.8e-4    # kg m^2
    comp_eff_peak: float = 0.775
    turb_eff_peak: float = 0.760
    n_corr_ref: float = 105000.0     # rpm, speed giving pr_max_ref at u=1
    mdot_corr_max: float = 0.62      # kg/s corrected choke flow at u=1
    pr_max_ref: float = 3.60
    turbine_area_eff: float = 1.75e-3  # m^2 effective nozzle area (A/R proxy)
    vgt: bool = False                # variable geometry
    vgt_min_frac: float = 0.55       # min effective area fraction
    wastegate_pset: float = 2.55     # boost PR at which the WG starts to open
    wastegate_gain: float = 4.0e-4   # m^2 per unit PR above set point
    bearing_visc_k: float = 3.0e-11  # N m s^2 (viscous drag coeff, x omega^2)
    intercooler_eff: float = 0.78    # effectiveness
    intercooler_dp: float = 6.0e3    # Pa at rated flow
    charge_cooler_medium_T: float = 313.0   # K


@dataclass
class AirPath:
    intake_plenum_vol: float = 9.0e-3     # m^3
    exhaust_manifold_vol: float = 5.5e-3  # m^3
    runner_length_int: float = 0.30       # m (acoustic)
    runner_length_exh: float = 0.42       # m
    intake_pipe_length: float = 0.85      # m  snorkel + filter box outlet
    airbox_volume: float = 12.0e-3        # m^3 (Helmholtz)
    airbox_neck_len: float = 0.16         # m
    airbox_neck_area: float = 3.8e-3      # m^2
    air_filter_dp_k: float = 3.1e4        # Pa / (kg/s)^2
    exhaust_pipe_length: float = 3.2      # m tailpipe run
    exhaust_pipe_dia: float = 0.100       # m
    muffler_volume: float = 26.0e-3       # m^3
    muffler_length: float = 0.90          # m (chamber length, tone)
    dpf_present: bool = True
    egr_max_fraction: float = 0.22        # of trapped mass
    intake_restriction_area: float = 0.0  # m^2 (0 => auto from valve area)
    exhaust_outlet_area: float = 0.0      # m^2 (0 => auto)


# --------------------------------------------------------------------------
# Lubricant
# --------------------------------------------------------------------------
@dataclass
class Lubricant:
    name: str = "15W-40 CJ-4"
    # Vogel: mu = a * exp(b / (T - c)),  T in K, mu in Pa.s
    vogel_a: float = 6.20e-5
    vogel_b: float = 1050.0
    vogel_c: float = 155.0
    density15: float = 875.0         # kg/m^3
    viscosity_index: float = 138.0
    tbn0: float = 10.0               # mg KOH/g
    hths: float = 3.9e-3             # Pa.s at 150 C, 1e6 1/s
    sump_volume: float = 34.0e-3     # m^3 (34 L truck sump)
    pump_disp: float = 26.0e-6       # m^3/rev
    pump_relief: float = 5.2e5       # Pa gauge
    pump_eta_vol: float = 0.88
    pump_eta_mech: float = 0.82
    cooler_UA: float = 2600.0        # W/K oil-to-coolant
    change_interval_h: float = 500.0


# --------------------------------------------------------------------------
# Tribology / mechanical detail
# --------------------------------------------------------------------------
@dataclass
class Tribology:
    # ---- ring pack -----------------------------------------------------
    n_comp_rings: int = 2
    ring_axial_width: float = 2.4e-3      # m (face width in stroke dir.)
    ring_tangential_load: float = 34.0    # N per ring (free-gap tension)
    oil_ring_load: float = 42.0           # N
    oil_ring_width: float = 0.55e-3
    ring_gap_new: float = 0.35e-3         # m, installed end gap
    ring_face_roughness: float = 0.25e-6  # m Rq
    bore_roughness: float = 0.55e-6       # m Rq (plateau honed)
    oil_supply_film: float = 2.2e-6       # m film left for the ring pack
    bore_hardness: float = 2.6e9          # Pa (Vickers ~ 265 HV cast iron)
    ring_hardness: float = 6.5e9          # Pa (nitrided / CrN)

    # ---- piston skirt ---------------------------------------------------
    skirt_area: float = 6.2e-3            # m^2 per piston (both thrust faces)
    skirt_clearance_new: float = 90e-6    # m diametral, cold
    piston_alu: bool = True

    # ---- journal bearings ----------------------------------------------
    main_dia: float = 0.100
    main_width: float = 0.038
    main_clearance_new: float = 75e-6     # m diametral
    n_mains: int = 7
    rod_dia: float = 0.084
    rod_width: float = 0.034
    rod_clearance_new: float = 68e-6
    bearing_roughness: float = 0.30e-6
    bearing_hardness: float = 1.1e9       # Pa (tri-metal overlay)
    pin_dia: float = 0.050                # m, piston-pin (small end)
    pin_width: float = 0.040
    pin_clearance: float = 30e-6
    pin_mu_boundary: float = 0.010        # oscillating, film never builds

    # ---- accessories -----------------------------------------------------
    water_pump_k: float = 1.55e-9         # W / rpm^3
    fan_k: float = 4.10e-9                # W / rpm^3  (when locked)
    fan_duty: float = 0.12                # average engagement
    alternator_load_W: float = 1500.0
    alternator_eta: float = 0.58
    windage_k: float = 2.05e-8            # W / rpm^2.7
    aircomp_load_W: float = 900.0
    fuel_pump_eta: float = 0.82           # HP pump mech+vol efficiency
    fuel_pump_spill: float = 1.25         # pumped / delivered volume
    seal_drag_Nm: float = 0.85            # front + rear crank seals
    gear_train_k: float = 3.2e-8          # W / rpm^2 (timing gears)


# --------------------------------------------------------------------------
# Thermal boundary
# --------------------------------------------------------------------------
# engine._apply_thermal_state: how many kelvin each wall moves per kelvin of
# coolant away from the warm reference, at which the spec's own wall
# temperatures are given. Shared with the slap clearance (acoustics.py,
# FINDING-023), so the two cannot disagree.
T_COOLANT_REF = 361.0
WALL_FOLLOW = {"piston_T": 0.72, "head_T": 0.85, "liner_T_top": 0.88,
               "liner_T_bot": 0.95, "port_T_exh": 0.45}


@dataclass
class Thermal:
    coolant_T: float = 361.0        # K (88 C)
    piston_T: float = 553.0         # K crown mean
    head_T: float = 483.0           # K firedeck
    liner_T_top: float = 453.0      # K
    liner_T_bot: float = 383.0      # K
    port_T_exh: float = 700.0       # K
    ambient_T: float = 298.0        # K
    ambient_p: float = 101325.0     # Pa
    oil_T_start: float = 298.0      # K
    oil_T_target: float = 373.0     # K (100 C steady)
    # ---- warm-up / cooling system ------------------------------------
    coolant_volume: float = 42.0e-3  # m^3 (block + rad + heater circuit)
    metal_mass: float = 620.0        # kg of block/head that must warm up too
    radiator_UA: float = 5200.0      # W/K at the reference fan/road speed
    thermostat_open_T: float = 355.0  # K, starts to crack
    thermostat_full_T: float = 366.0  # K, fully open


# --------------------------------------------------------------------------
# Cooling package: radiator, fan, charge-air cooler and thermal protection
# --------------------------------------------------------------------------
@dataclass
class Cooling:
    """
    The cooling stack, sized the way a real one is: by core area and by the
    air you can actually get through it.

    Heat rejection is NOT a fixed UA.  It is effectiveness-NTU on the air
    side, so it falls when the airflow falls -- which is why a vehicle
    overheats crawling up a hill at full load and runs cool at the same load
    on the flat.  The fan exists to put that airflow back, and it costs real
    crank power to do it.
    """
    # ---- radiator -------------------------------------------------------
    rad_core_area: float = 0.62       # m^2 frontal
    rad_core_depth: float = 0.048     # m
    rad_UA_ref: float = 5200.0        # W/K at rad_air_ref
    rad_air_ref: float = 3.2          # kg/s of air through the core
    grille_recovery: float = 0.42     # face velocity / vehicle speed

    # ---- fan ------------------------------------------------------------
    fan_dia: float = 0.72             # m
    fan_max_flow: float = 4.5         # kg/s of air at full engagement
    fan_power_max: float = 12000.0    # W absorbed at full engagement
    fan_type: str = "viscous"         # viscous | electric | fixed
    fan_on_T: float = 368.0           # K, clutch engages
    fan_off_T: float = 363.0          # K, drops out (hysteresis)
    fan_ramp_s: float = 2.5           # s to spin up / drop out

    # ---- charge-air cooler ---------------------------------------------
    ic_UA_ref: float = 1400.0         # W/K at ic_air_ref
    ic_air_ref: float = 2.2           # kg/s
    ic_core_area: float = 0.42        # m^2 frontal
    ic_ahead_of_rad: bool = True      # stack order: IC heats the rad's air
    ic_dp_ref: float = 6.0e3          # Pa charge-side drop at rated flow

    # ---- thermal protection --------------------------------------------
    T_warn: float = 373.0             # K (100 C) light comes on
    T_derate: float = 380.0           # K (107 C) start pulling power
    T_derate_full: float = 388.0      # K (115 C) at the floor
    derate_floor: float = 0.35        # fraction of demanded fuel left
    T_shutdown: float = 393.0         # K (120 C) protect the engine
    T_restart: float = 368.0          # K, restart allowed below this
    allow_shutdown: bool = True


# --------------------------------------------------------------------------
# Aggregate
# --------------------------------------------------------------------------
@dataclass
class EngineSpec:
    name: str
    geom: Geometry
    valves: ValveTrain = field(default_factory=ValveTrain)
    inj: Injection = field(default_factory=Injection)
    turbo: Turbo = field(default_factory=Turbo)
    air: AirPath = field(default_factory=AirPath)
    oil: Lubricant = field(default_factory=Lubricant)
    trib: Tribology = field(default_factory=Tribology)
    thermal: Thermal = field(default_factory=Thermal)
    cooling: Cooling = field(default_factory=Cooling)

    idle_rpm: float = 600.0
    rated_rpm: float = 1800.0
    max_rpm: float = 2200.0
    afr_limit: float = 19.0          # smoke-limited air/fuel ratio
    afr_stoich: float = 14.5
    # ---- rated limits -------------------------------------------------
    # Real engines are not sold at whatever the smoke limit allows: the ECU
    # holds a torque structure so the gearbox, driveshaft and warranty all
    # survive.  Anything <= 0 means "no limit, let the air decide".
    torque_limit: float = 0.0        # N.m brake, flat cap
    power_limit: float = 0.0         # W brake, cap (a hyperbola in torque)
    # Optional shaped cap, ((rpm, N.m), ...), linearly interpolated and
    # applied on top of the two scalars above.  This is how you get a flat
    # torque plateau between two speeds.
    torque_limit_map: tuple = ()
    # Mechanical and thermal limits the fuel limiter respects (FINDING-010,
    # known bug #2): peak cylinder pressure [Pa] and exhaust-manifold
    # (turbine-inlet) temperature [K] at full demand. Fuel is pulled back
    # until neither is exceeded. <= 0 means no limit. Presets set them above
    # every full-load point they reach today, so they bound what the rating
    # and smoke limit do not: altitude, heat, wear, an over-boosted turbo.
    p_max_limit: float = 0.0
    T_exh_limit: float = 0.0
    # Shape of the OPEN-LOOP boost estimate the fuel limiter uses.  1.0 is
    # the old lazy rise; a VGT reaches its boost target far earlier, so a
    # smaller number (0.4-0.6) is right for one.  This only shapes the
    # fuelling map -- what the turbo actually delivers comes from turbo.py.
    boost_map_rise: float = 1.0
    # timing gear / accessory drive tooth counts (acoustic tones)
    crank_gear_teeth: int = 32
    cam_gear_teeth: int = 64
    injpump_gear_teeth: int = 48

    def summary(self) -> str:
        g = self.geom
        return (f"{self.name}: {g.n_cyl}-cyl  {g.displacement*1e3:.2f} L  "
                f"B x S = {g.bore*1e3:.1f} x {g.stroke*1e3:.1f} mm  "
                f"CR {g.compression_ratio:.1f}  rod/stroke "
                f"{g.conrod/g.stroke:.2f}")


# --------------------------------------------------------------------------
# Presets
# --------------------------------------------------------------------------
def heavy_truck_i6() -> EngineSpec:
    """~12.7 L inline-6 heavy-duty truck diesel, single VGT, ~350 kW."""
    geom = Geometry(
        bore=0.130, stroke=0.160, conrod=0.262, n_cyl=6,
        compression_ratio=16.5, firing_order=(1, 5, 3, 6, 2, 4),
        recip_mass=2.65, rot_mass_bigend=1.85, flywheel_inertia=3.1,
    )
    spec = EngineSpec(name="HD-I6 12.7L", geom=geom,
                      idle_rpm=600, rated_rpm=1800, max_rpm=2100)
    spec.turbo.vgt = True
    # FINDING-017 item 2: the closing ramp must be taller than the lash, or
    # the valve lands on the steep flank. With the default 6 % ramp (106 um)
    # under 550 um of exhaust lash, seating ran 12x the on-ramp speed and
    # valve clatter drowned this engine's sound. 15.5 % gives ramps of
    # >= 1.25 x the lash on both cams (exhaust 0.69 mm, intake 0.68 mm).
    spec.valves.ramp_fraction = 0.155
    # full load today peaks at 179 bar and 925 K (session 5 survey)
    spec.p_max_limit = 220e5
    spec.T_exh_limit = 1023.0
    return spec


def light_duty_i4() -> EngineSpec:
    """2.0 L common-rail passenger-car diesel, ~125 kW."""
    geom = Geometry(
        bore=0.083, stroke=0.0921, conrod=0.147, n_cyl=4,
        compression_ratio=16.2, firing_order=(1, 3, 4, 2),
        recip_mass=0.62, rot_mass_bigend=0.42, flywheel_inertia=0.28,
    )
    spec = EngineSpec(name="LD-I4 2.0L CRD", geom=geom,
                      idle_rpm=800, rated_rpm=4000, max_rpm=4800,
                      crank_gear_teeth=22, cam_gear_teeth=44,
                      injpump_gear_teeth=33)
    spec.valves = ValveTrain(
        ivo_deg=352, ivc_deg=562, evo_deg=140, evc_deg=372,
        intake_valve_dia=0.0275, exhaust_valve_dia=0.0250,
        intake_lift_max=0.0088, exhaust_lift_max=0.0082,
        lash_intake=0.0, lash_exhaust=0.0,      # hydraulic
        cam_base_radius=0.016, follower_radius=0.013,
        valve_spring_preload=190.0, valve_spring_rate=26e3,
        valve_train_eq_mass=0.11)
    spec.inj = Injection(n_holes=7, hole_dia=0.118e-3, rail_pressure_max=2000e5,
                         rail_pressure_idle=280e5, soi_deg_btdc=5.0,
                         pilot_fraction=0.05, pilot_advance_deg=16.0)
    spec.turbo = Turbo(comp_wheel_dia=0.049, turb_wheel_dia=0.043,
                       comp_blades=11, turb_blades=9, shaft_inertia=9.0e-6,
                       n_corr_ref=180000.0, mdot_corr_max=0.21,
                       pr_max_ref=3.4, turbine_area_eff=5.4e-4,
                       vgt=True, wastegate_pset=2.9, comp_eff_peak=0.755,
                       turb_eff_peak=0.735)
    spec.air = AirPath(intake_plenum_vol=2.2e-3, exhaust_manifold_vol=0.9e-3,
                       runner_length_int=0.22, runner_length_exh=0.26,
                       intake_pipe_length=0.55, airbox_volume=6.5e-3,
                       airbox_neck_len=0.11, airbox_neck_area=1.9e-3,
                       exhaust_pipe_length=4.1, exhaust_pipe_dia=0.055,
                       muffler_volume=11.0e-3)
    spec.oil = Lubricant(name="5W-30 C3", vogel_a=8.6e-5, vogel_b=920.0,
                         vogel_c=163.0, sump_volume=5.5e-3, pump_disp=8.5e-6,
                         pump_relief=4.2e5, cooler_UA=800.0, tbn0=7.0,
                         hths=3.5e-3, change_interval_h=350.0)
    spec.trib = Tribology(
        ring_axial_width=1.2e-3, ring_tangential_load=13.0, oil_ring_load=18.0,
        ring_gap_new=0.22e-3, skirt_area=2.1e-3, skirt_clearance_new=45e-6,
        main_dia=0.054, main_width=0.021, main_clearance_new=38e-6, n_mains=5,
        rod_dia=0.050, rod_width=0.020, rod_clearance_new=35e-6,
        water_pump_k=1.1e-10, fan_k=2.2e-10, fan_duty=0.10,
        alternator_load_W=700.0, windage_k=1.3e-9, aircomp_load_W=0.0,
        pin_dia=0.030, pin_width=0.024, oil_supply_film=1.4e-6,
        seal_drag_Nm=0.28, gear_train_k=4.0e-9)
    # A 1.5 L does not carry a 42 L / 620 kg truck cooling system.  Leaving
    # the Thermal defaults in place gave this engine a warm-up rate of 6 K
    # per minute -- it never reached operating temperature at all.
    spec.thermal = Thermal(piston_T=573.0, head_T=470.0, liner_T_top=440.0,
                           coolant_volume=6.0e-3, metal_mass=110.0,
                           radiator_UA=900.0)
    spec.cooling = Cooling(
        rad_core_area=0.185, rad_core_depth=0.026, rad_UA_ref=950.0,
        rad_air_ref=0.85, grille_recovery=0.40,
        fan_dia=0.34, fan_max_flow=0.75, fan_power_max=320.0,
        fan_type="electric", fan_on_T=367.0, fan_off_T=362.0, fan_ramp_s=1.2,
        ic_UA_ref=210.0, ic_air_ref=0.65, ic_core_area=0.085,
        T_warn=372.0, T_derate=379.0, T_derate_full=386.0,
        T_shutdown=391.0, T_restart=367.0)
    spec.afr_limit = 17.5
    # full load today peaks at 167 bar and 1050 K (session 5 survey)
    spec.p_max_limit = 190e5
    spec.T_exh_limit = 1093.0
    return spec


def compact_crdi_i4() -> EngineSpec:
    """
    1.5 L common-rail four, rated to a flat-plateau road-car curve:
    220.6 N.m (22.5 kg.m) held from 1500 to 2750 rpm, 84.6 kW (115 PS) at
    4000 rpm.

    The plateau is NOT what the hardware would give if you let it: the air
    system can make more than that in the mid-range.  It is held flat by the
    rating limits below, which is exactly how the real thing is done -- the
    ECU carries a torque structure so the gearbox and driveshafts see a
    known worst case.
    """
    geom = Geometry(
        bore=0.075, stroke=0.0840, conrod=0.136, n_cyl=4,
        compression_ratio=16.0, firing_order=(1, 3, 4, 2),
        recip_mass=0.50, rot_mass_bigend=0.34, flywheel_inertia=0.16,
    )
    spec = EngineSpec(name="CRDi-I4 1.5L", geom=geom,
                      idle_rpm=800, rated_rpm=4000, max_rpm=4600,
                      crank_gear_teeth=22, cam_gear_teeth=44,
                      injpump_gear_teeth=33)
    spec.valves = ValveTrain(
        ivo_deg=352, ivc_deg=556, evo_deg=142, evc_deg=372,
        intake_valve_dia=0.0250, exhaust_valve_dia=0.0228,
        intake_lift_max=0.0082, exhaust_lift_max=0.0076,
        lash_intake=0.0, lash_exhaust=0.0,          # hydraulic
        cam_base_radius=0.015, follower_radius=0.012,
        valve_spring_preload=175.0, valve_spring_rate=24e3,
        valve_train_eq_mass=0.095)
    spec.inj = Injection(n_holes=7, hole_dia=0.105e-3, rail_pressure_max=1800e5,
                         rail_pressure_idle=280e5, soi_deg_btdc=5.0,
                         pilot_fraction=0.05, pilot_advance_deg=16.0)
    # small, quick VGT: the plateau starts at 1500 rpm, so the turbine has to
    # be choked down hard at low flow to get ~2 bar absolute that early
    spec.turbo = Turbo(comp_wheel_dia=0.042, turb_wheel_dia=0.037,
                       comp_blades=11, turb_blades=9, shaft_inertia=5.5e-6,
                       n_corr_ref=232000.0, mdot_corr_max=0.128,
                       pr_max_ref=3.3, turbine_area_eff=2.75e-4,
                       vgt=True, vgt_min_frac=0.26, wastegate_pset=2.7,
                       comp_eff_peak=0.750, turb_eff_peak=0.730)
    spec.air = AirPath(intake_plenum_vol=1.7e-3, exhaust_manifold_vol=0.7e-3,
                       runner_length_int=0.20, runner_length_exh=0.24,
                       intake_pipe_length=0.50, airbox_volume=5.5e-3,
                       airbox_neck_len=0.10, airbox_neck_area=1.6e-3,
                       exhaust_pipe_length=3.9, exhaust_pipe_dia=0.050,
                       muffler_volume=9.0e-3)
    spec.oil = Lubricant(name="5W-30 C3", vogel_a=8.6e-5, vogel_b=920.0,
                         vogel_c=163.0, sump_volume=4.2e-3, pump_disp=7.0e-6,
                         pump_relief=4.0e5, cooler_UA=650.0, tbn0=7.0,
                         hths=3.5e-3, change_interval_h=350.0)
    spec.trib = Tribology(
        ring_axial_width=1.0e-3, ring_tangential_load=10.5, oil_ring_load=15.0,
        ring_gap_new=0.20e-3, skirt_area=1.75e-3, skirt_clearance_new=42e-6,
        main_dia=0.048, main_width=0.019, main_clearance_new=34e-6, n_mains=5,
        rod_dia=0.045, rod_width=0.018, rod_clearance_new=32e-6,
        water_pump_k=0.9e-10, fan_k=1.8e-10, fan_duty=0.10,
        alternator_load_W=600.0, windage_k=1.0e-9, aircomp_load_W=0.0,
        pin_dia=0.028, pin_width=0.022, oil_supply_film=1.3e-6,
        seal_drag_Nm=0.24, gear_train_k=3.5e-9)
    # A 1.5 L does not carry a 42 L / 620 kg truck cooling system.  Leaving
    # the Thermal defaults in place gave this engine a warm-up rate of 6 K
    # per minute -- it never reached operating temperature at all.
    spec.thermal = Thermal(piston_T=573.0, head_T=470.0, liner_T_top=440.0,
                           coolant_volume=6.0e-3, metal_mass=110.0,
                           radiator_UA=900.0)
    spec.cooling = Cooling(
        rad_core_area=0.185, rad_core_depth=0.026, rad_UA_ref=950.0,
        rad_air_ref=0.85, grille_recovery=0.40,
        fan_dia=0.34, fan_max_flow=0.75, fan_power_max=320.0,
        fan_type="electric", fan_on_T=367.0, fan_off_T=362.0, fan_ramp_s=1.2,
        ic_UA_ref=210.0, ic_air_ref=0.65, ic_core_area=0.085,
        T_warn=372.0, T_derate=379.0, T_derate_full=386.0,
        T_shutdown=391.0, T_restart=367.0)
    spec.afr_limit = 17.5
    # ---- the rating: this is what makes the graph ---------------------
    # Trimmed ~3 % low against the nameplate: the limiter's affine fit
    # lands slightly high (see fuel_for_torque), so this is the commanded
    # value that DELIVERS 220.6 N.m / 84.6 kW rather than the nameplate
    # itself.  Re-trim if you change n_cycles or the turbo.
    spec.torque_limit = 214.0
    spec.power_limit = 82.0e3
    spec.torque_limit_map = ((1200, 190.0), (1500, 214.0), (2750, 214.0),
                             (4000, 198.5), (4600, 172.0))
    # full load today peaks at 154 bar and 929 K (session 5 survey)
    spec.p_max_limit = 180e5
    spec.T_exh_limit = 1073.0
    return spec


def crdi_1_5() -> EngineSpec:
    """
    1.5 L four-cylinder common-rail turbodiesel: 115 ps @ 4000 rpm,
    22.5 kg.m (220.6 N.m) held flat from 1500 to 2750 rpm.

    22.5 kg.m out of 1.5 L is 18.5 bar BMEP, and 84.6 kW is 56 kW/L --
    both ordinary for a modern small CRDi.  The flat plateau is NOT a
    property of the hardware: the engine can make more than that in the
    midrange, and the rating map is what holds it level.  That is exactly
    how the real thing works, and it is why the torque line in a brochure
    has a corner in it that no combustion process would ever produce.
    """
    geom = Geometry(
        bore=0.077, stroke=0.0805, conrod=0.137, n_cyl=4,
        compression_ratio=16.0, firing_order=(1, 3, 4, 2),
        recip_mass=0.52, rot_mass_bigend=0.36, flywheel_inertia=0.22,
    )
    spec = EngineSpec(name="CRDi-I4 1.5L 115ps", geom=geom,
                      idle_rpm=800, rated_rpm=4000, max_rpm=4600,
                      crank_gear_teeth=22, cam_gear_teeth=44,
                      injpump_gear_teeth=33)
    spec.valves = ValveTrain(
        ivo_deg=354, ivc_deg=558, evo_deg=142, evc_deg=372,
        intake_valve_dia=0.0258, exhaust_valve_dia=0.0234,
        intake_lift_max=0.0084, exhaust_lift_max=0.0078,
        lash_intake=0.0, lash_exhaust=0.0,          # hydraulic
        cam_base_radius=0.015, follower_radius=0.012,
        valve_spring_preload=175.0, valve_spring_rate=24e3,
        valve_train_eq_mass=0.098)
    spec.inj = Injection(n_holes=7, hole_dia=0.104e-3, rail_pressure_max=1800e5,
                         rail_pressure_idle=280e5, soi_deg_btdc=5.0,
                         pilot_fraction=0.05, pilot_advance_deg=16.0)
    spec.turbo = Turbo(comp_wheel_dia=0.044, turb_wheel_dia=0.038,
                       comp_blades=11, turb_blades=9, shaft_inertia=6.5e-6,
                       n_corr_ref=205000.0, mdot_corr_max=0.165,
                       pr_max_ref=3.3, turbine_area_eff=4.1e-4,
                       vgt=True, vgt_min_frac=0.32, wastegate_pset=3.05,
                       comp_eff_peak=0.760, turb_eff_peak=0.740)
    spec.air = AirPath(intake_plenum_vol=1.7e-3, exhaust_manifold_vol=0.7e-3,
                       runner_length_int=0.20, runner_length_exh=0.24,
                       intake_pipe_length=0.50, airbox_volume=5.5e-3,
                       airbox_neck_len=0.10, airbox_neck_area=1.7e-3,
                       exhaust_pipe_length=3.9, exhaust_pipe_dia=0.050,
                       muffler_volume=9.5e-3)
    spec.oil = Lubricant(name="5W-30 C3", vogel_a=8.6e-5, vogel_b=920.0,
                         vogel_c=163.0, sump_volume=4.6e-3, pump_disp=7.2e-6,
                         pump_relief=4.0e5, cooler_UA=650.0, tbn0=7.0,
                         hths=3.5e-3, change_interval_h=350.0)
    spec.trib = Tribology(
        ring_axial_width=1.1e-3, ring_tangential_load=11.5, oil_ring_load=16.0,
        ring_gap_new=0.20e-3, skirt_area=1.8e-3, skirt_clearance_new=42e-6,
        main_dia=0.050, main_width=0.019, main_clearance_new=36e-6, n_mains=5,
        rod_dia=0.046, rod_width=0.019, rod_clearance_new=33e-6,
        water_pump_k=0.9e-10, fan_k=1.8e-10, fan_duty=0.10,
        alternator_load_W=620.0, windage_k=1.1e-9, aircomp_load_W=0.0,
        pin_dia=0.028, pin_width=0.022, oil_supply_film=1.3e-6,
        seal_drag_Nm=0.24, gear_train_k=3.6e-9)
    # A 1.5 L does not carry a 42 L / 620 kg truck cooling system.  Leaving
    # the Thermal defaults in place gave this engine a warm-up rate of 6 K
    # per minute -- it never reached operating temperature at all.
    spec.thermal = Thermal(piston_T=573.0, head_T=470.0, liner_T_top=440.0,
                           coolant_volume=6.0e-3, metal_mass=110.0,
                           radiator_UA=900.0)
    spec.cooling = Cooling(
        rad_core_area=0.185, rad_core_depth=0.026, rad_UA_ref=950.0,
        rad_air_ref=0.85, grille_recovery=0.40,
        fan_dia=0.34, fan_max_flow=0.75, fan_power_max=320.0,
        fan_type="electric", fan_on_T=367.0, fan_off_T=362.0, fan_ramp_s=1.2,
        ic_UA_ref=210.0, ic_air_ref=0.65, ic_core_area=0.085,
        T_warn=372.0, T_derate=379.0, T_derate_full=386.0,
        T_shutdown=391.0, T_restart=367.0)
    spec.afr_limit = 17.5
    # ---- the rating: 22.5 kg.m flat 1500-2750, 115 ps at 4000 ----------
    spec.boost_map_rise = 0.45
    spec.torque_limit_map = ((1250, 196.0), (1500, 220.6), (2750, 220.6),
                             (3400, 214.0), (4000, 202.0), (4600, 150.0))
    spec.power_limit = 84.6e3
    # full load today peaks at 158 bar and 786 K (session 5 survey)
    spec.p_max_limit = 180e5
    spec.T_exh_limit = 1073.0
    return spec


def industrial_single() -> EngineSpec:
    """0.6 L naturally-aspirated single -- generator / pump set."""
    geom = Geometry(bore=0.086, stroke=0.100, conrod=0.165, n_cyl=1,
                    compression_ratio=19.5, firing_order=(1,),
                    recip_mass=0.85, rot_mass_bigend=0.55,
                    flywheel_inertia=0.85)
    spec = EngineSpec(name="IND-1 0.58L NA", geom=geom, idle_rpm=1000,
                      rated_rpm=3000, max_rpm=3300,
                      crank_gear_teeth=24, cam_gear_teeth=48,
                      injpump_gear_teeth=48)
    spec.turbo = Turbo(enabled=False)
    spec.inj = Injection(n_holes=4, hole_dia=0.24e-3, rail_pressure_max=280e5,
                         rail_pressure_idle=180e5, soi_deg_btdc=16.0,
                         pilot_enabled=False, cetane_number=48.0)
    spec.valves = ValveTrain(
        ivo_deg=350, ivc_deg=565, evo_deg=135, evc_deg=372,
        intake_valve_dia=0.0300, exhaust_valve_dia=0.0270,
        intake_lift_max=0.0080, exhaust_lift_max=0.0078,
        lash_intake=0.20e-3, lash_exhaust=0.25e-3,
        cam_base_radius=0.015, follower_radius=0.0,
        valve_spring_preload=150.0, valve_spring_rate=20e3,
        valve_train_eq_mass=0.09,
        # FINDING-017 item 2: ramps >= 1.25 x the lash on both cams
        # (exhaust 0.32 mm over 0.25 mm lash; the default 6 % gave 69 um)
        ramp_fraction=0.13)
    spec.air = AirPath(intake_plenum_vol=0.8e-3, exhaust_manifold_vol=0.4e-3,
                       runner_length_int=0.16, runner_length_exh=0.20,
                       intake_pipe_length=0.30, airbox_volume=2.5e-3,
                       airbox_neck_len=0.08, airbox_neck_area=1.1e-3,
                       exhaust_pipe_length=0.9, exhaust_pipe_dia=0.040,
                       muffler_volume=4.0e-3, dpf_present=False)
    spec.oil = Lubricant(name="15W-40", sump_volume=2.4e-3, pump_disp=3.2e-6,
                         pump_relief=3.5e5, cooler_UA=180.0)
    spec.thermal = Thermal(coolant_volume=4.0e-3, metal_mass=95.0,
                           radiator_UA=420.0)
    spec.cooling = Cooling(
        rad_core_area=0.21, rad_core_depth=0.028, rad_UA_ref=1250.0,
        rad_air_ref=1.0, grille_recovery=0.40,
        fan_dia=0.38, fan_max_flow=0.95, fan_power_max=420.0,
        fan_type="electric", fan_on_T=367.0, fan_off_T=362.0, fan_ramp_s=1.2,
        ic_UA_ref=280.0, ic_air_ref=0.8, ic_core_area=0.10,
        T_warn=372.0, T_derate=379.0, T_derate_full=386.0,
        T_shutdown=391.0, T_restart=367.0)
    spec.trib = Tribology(
        ring_axial_width=2.0e-3, ring_tangential_load=16.0, oil_ring_load=22.0,
        ring_gap_new=0.30e-3, skirt_area=2.4e-3, skirt_clearance_new=70e-6,
        main_dia=0.052, main_width=0.024, main_clearance_new=45e-6, n_mains=2,
        rod_dia=0.046, rod_width=0.024, rod_clearance_new=42e-6,
        water_pump_k=1.0e-10, fan_k=6.0e-10, fan_duty=1.0,
        alternator_load_W=250.0, windage_k=8.0e-10, aircomp_load_W=0.0,
        pin_dia=0.032, pin_width=0.028, oil_supply_film=1.8e-6,
        seal_drag_Nm=0.22, gear_train_k=2.0e-9)
    spec.afr_limit = 21.0
    # full load today peaks at 132 bar and 682 K (session 5 survey)
    spec.p_max_limit = 150e5
    spec.T_exh_limit = 973.0
    return spec


PRESETS = {
    "hd_i6": heavy_truck_i6,
    "ld_i4": light_duty_i4,
    "crdi15": crdi_1_5,
    "crdi_1p5": compact_crdi_i4,
    "single": industrial_single,
}


def get_preset(name: str) -> EngineSpec:
    if name not in PRESETS:
        raise KeyError(f"unknown preset '{name}'. choose from {list(PRESETS)}")
    return PRESETS[name]()
