"""
builder.py -- make a new engine from the numbers on the brochure.

A full EngineSpec is about 80 fields across eight dataclasses.  Most of them
are not free choices: valve sizes follow the bore, bearing sizes follow the
bore, the turbo follows the air the engine needs at rated power, the sump
follows the displacement.  Only a handful are actually design decisions.

So state the handful, and let the rest be derived:

    from dieselsim.builder import build_engine, register

    spec = build_engine(
        name        = "2.2 CRDi",
        displacement= 2.2,          # litres
        n_cyl       = 4,
        rated_rpm   = 3800,
        peak_torque = 360,          # N.m
        peak_power  = 110,          # kW
        plateau     = (1750, 2750), # rpm range the torque is held flat over
    )
    register("crdi22", spec)

or, without touching Python at all, drop a JSON file in `engines/`:

    {"key": "crdi22", "name": "2.2 CRDi", "displacement": 2.2, "n_cyl": 4,
     "rated_rpm": 3800, "peak_torque": 360, "peak_power": 110,
     "plateau": [1750, 2750]}

and call `load_engine_dir()`.

WHAT THIS DOES NOT DO
---------------------
It does not guarantee the engine makes the numbers you asked for.  The
scaling laws size plausible hardware; whether that hardware actually
delivers is a question for the solver, not for the builder.  Use `verify()`
to find out, and expect to move `afr_limit`, `turbine_area_eff` or
`boost_map_rise` by hand if it falls short.
"""
from __future__ import annotations

import json
import math
import os
import copy
from dataclasses import asdict

from .config import (AirPath, Cooling, EngineSpec, Geometry, Injection,
                     Lubricant, PRESETS, Thermal, Tribology, Turbo, ValveTrain)

LHV = 42.7e6
RHO_FUEL = 830.0


# ==========================================================================
def build_engine(name: str,
                 displacement: float,          # litres
                 n_cyl: int,
                 rated_rpm: float,
                 peak_torque: float,           # N.m
                 peak_power: float,            # kW
                 plateau: tuple = None,        # (rpm_lo, rpm_hi) flat torque
                 idle_rpm: float = None,
                 max_rpm: float = None,
                 stroke_bore: float = 1.05,
                 compression_ratio: float = None,
                 turbocharged: bool = True,
                 vgt: bool = None,
                 rail_bar: float = None,
                 afr_limit: float = None,
                 boost_map_rise: float = None,
                 firing_order: tuple = None,
                 eta_brake_rated: float = 0.42,
                 ve_rated: float = 1.05,
                 apply_rating: bool = True) -> EngineSpec:
    """
    Derive a complete EngineSpec from headline numbers.

    Every derived quantity below is a scaling law anchored on the built-in
    presets, not a guess pulled from nowhere -- valve area on bore, bearing
    size on bore, turbo flow on the air the engine must swallow at rated
    power, sump volume on displacement.
    """
    disp = displacement * 1e-3                      # m^3
    idle_rpm = idle_rpm or max(600.0, 0.20 * rated_rpm)
    max_rpm = max_rpm or 1.15 * rated_rpm
    vgt = turbocharged if vgt is None else vgt

    # ---- geometry ------------------------------------------------------
    V_cyl = disp / n_cyl
    bore = (4.0 * V_cyl / (math.pi * stroke_bore)) ** (1.0 / 3.0)
    stroke = stroke_bore * bore
    conrod = stroke / 2.0 / 0.30                    # rod ratio ~0.30
    if compression_ratio is None:
        compression_ratio = 16.8 if displacement / n_cyl > 1.2 else 16.0
    if firing_order is None:
        firing_order = {1: (1,), 2: (1, 2), 3: (1, 3, 2),
                        4: (1, 3, 4, 2), 5: (1, 2, 4, 5, 3),
                        6: (1, 5, 3, 6, 2, 4),
                        8: (1, 5, 4, 8, 6, 3, 7, 2)}.get(n_cyl,
                                                         tuple(range(1, n_cyl + 1)))
    geom = Geometry(
        bore=bore, stroke=stroke, conrod=conrod, n_cyl=n_cyl,
        compression_ratio=compression_ratio, firing_order=firing_order,
        recip_mass=0.50 * (bore / 0.083) ** 2.0,
        rot_mass_bigend=0.34 * (bore / 0.083) ** 2.0,
        flywheel_inertia=0.145 * displacement)

    spec = EngineSpec(name=name, geom=geom, idle_rpm=idle_rpm,
                      rated_rpm=rated_rpm, max_rpm=max_rpm,
                      crank_gear_teeth=max(18, int(0.18 * bore * 1000)),
                      cam_gear_teeth=max(36, int(0.36 * bore * 1000)),
                      injpump_gear_teeth=max(27, int(0.27 * bore * 1000)))

    # ---- valve train: area follows bore --------------------------------
    iv = 0.325 * bore
    ev = 0.295 * bore
    spec.valves = ValveTrain(
        intake_valve_dia=iv, exhaust_valve_dia=ev,
        intake_lift_max=0.300 * iv, exhaust_lift_max=0.315 * ev,
        lash_intake=0.0 if displacement < 4.0 else 0.30e-3,
        lash_exhaust=0.0 if displacement < 4.0 else 0.55e-3,
        cam_base_radius=0.17 * bore, follower_radius=0.15 * bore,
        valve_spring_preload=380.0 * (bore / 0.130) ** 2,
        valve_spring_rate=42e3 * (bore / 0.130),
        valve_train_eq_mass=0.34 * (bore / 0.130) ** 2.2)
    vt = spec.valves
    if vt.lash_exhaust > 0.0:
        # REVIEW-003 m-5: with mechanical lash the default 6 % ramp (0.11 mm
        # on a 12.7 L) sat far under the lash, so the valves landed on the
        # flank (truck127, roster A: 0.65 m/s at idle). The ramps get their
        # own heights, 1.25 x the lash, at RAMP_SPEED on the exhaust, in
        # front of the unchanged main event.
        from .kinematics import ramp_fraction_for
        vt.ramp_height_intake = 1.25 * vt.lash_intake
        vt.ramp_height_exhaust = 1.25 * vt.lash_exhaust
        vt.ramp_fraction = ramp_fraction_for((vt.evc_deg - vt.evo_deg) % 720.0, vt.ramp_height_exhaust)

    # ---- fuelling: size the nozzle to deliver rated fuel in ~25 deg ----
    mdot_fuel = peak_power * 1e3 / (eta_brake_rated * LHV)     # kg/s
    m_cyl_cycle = mdot_fuel / (n_cyl * rated_rpm / 120.0)      # kg
    rail = (rail_bar or (1800.0 if displacement < 6.0 else 2000.0)) * 1e5
    v_inj = 0.78 * math.sqrt(2.0 * rail / RHO_FUEL)
    t_inj = 25.0 / (6.0 * rated_rpm)
    A_tot = m_cyl_cycle / (RHO_FUEL * v_inj * t_inj)
    n_holes = 8 if displacement / n_cyl > 1.0 else 7
    hole_dia = math.sqrt(4.0 * A_tot / (math.pi * n_holes))
    spec.inj = Injection(
        n_holes=n_holes, hole_dia=hole_dia, rail_pressure_max=rail,
        rail_pressure_idle=0.18 * rail,
        soi_deg_btdc=8.0 if rated_rpm < 2600 else 5.0,
        pilot_enabled=True, pilot_fraction=0.045,
        pilot_advance_deg=14.0 if rated_rpm < 2600 else 16.0)

    # ---- turbo: sized on the air the engine must swallow ---------------
    afr_rated = 22.0
    mdot_air = mdot_fuel * afr_rated
    if turbocharged:
        # PR that gets that air in, from the ideal gas law
        n_dot = rated_rpm / 120.0
        rho_needed = mdot_air / max(disp * n_dot * ve_rated, 1e-9)
        pr = max(1.4, rho_needed * 287.0 * 318.0 / 101325.0)
        spec.turbo = Turbo(
            enabled=True, vgt=vgt,
            comp_wheel_dia=0.049 * (mdot_air / 0.13) ** 0.5,
            turb_wheel_dia=0.043 * (mdot_air / 0.13) ** 0.5,
            shaft_inertia=1.8e-4 * (mdot_air / 0.50) ** 2.5,
            n_corr_ref=105000.0 * math.sqrt(0.50 / max(mdot_air, 1e-3)),
            mdot_corr_max=1.35 * mdot_air,
            pr_max_ref=min(4.2, pr * 1.20),
            turbine_area_eff=3.2e-3 * mdot_air,
            vgt_min_frac=0.32 if vgt else 0.55,
            wastegate_pset=pr * 1.05,
            comp_eff_peak=0.775, turb_eff_peak=0.755)
        # how early the boost target (and the open-loop fuel schedule) rises
        # with rpm: lower is earlier. A VGT engine that must hold torque from
        # low in its plateau needs it lower than the default (Phase 5 roster:
        # below the plateau these engines were air-limited at their target)
        spec.boost_map_rise = boost_map_rise if boost_map_rise is not None else (0.45 if vgt else 1.0)
    else:
        spec.turbo = Turbo(enabled=False)

    # ---- air path: volumes follow displacement -------------------------
    spec.air = AirPath(
        intake_plenum_vol=0.70 * disp, exhaust_manifold_vol=0.43 * disp,
        runner_length_int=0.30 * (bore / 0.130) ** 0.5,
        runner_length_exh=0.42 * (bore / 0.130) ** 0.5,
        intake_pipe_length=0.85 * (displacement / 12.7) ** 0.25,
        airbox_volume=0.95 * disp, airbox_neck_len=0.16,
        airbox_neck_area=0.30 * disp,
        exhaust_pipe_length=3.2 * (displacement / 12.7) ** 0.25,
        exhaust_pipe_dia=0.100 * (mdot_air / 0.50) ** 0.5,
        muffler_volume=2.0 * disp,
        egr_max_fraction=0.22 if turbocharged else 0.0)

    # ---- oil ------------------------------------------------------------
    heavy = displacement > 6.0
    spec.oil = Lubricant(
        name="15W-40 CJ-4" if heavy else "5W-30 C3",
        sump_volume=2.8e-3 * displacement,
        pump_disp=2.05e-6 * displacement,
        pump_relief=5.2e5 if heavy else 4.0e5,
        cooler_UA=205.0 * displacement,
        change_interval_h=500.0 if heavy else 350.0)

    # ---- tribology: bearing sizes follow the bore ----------------------
    spec.trib = Tribology(
        ring_axial_width=0.0185 * bore, ring_tangential_load=262.0 * bore,
        oil_ring_load=323.0 * bore, ring_gap_new=0.0027 * bore,
        skirt_area=0.37 * bore ** 2 * math.pi,
        skirt_clearance_new=0.00069 * bore,
        main_dia=0.77 * bore, main_width=0.29 * bore,
        main_clearance_new=0.00058 * bore, n_mains=n_cyl + 1,
        rod_dia=0.65 * bore, rod_width=0.26 * bore,
        rod_clearance_new=0.00052 * bore,
        pin_dia=0.38 * bore, pin_width=0.31 * bore,
        oil_supply_film=2.2e-6 * (bore / 0.130) ** 0.5,
        alternator_load_W=1500.0 if heavy else 650.0,
        aircomp_load_W=900.0 if heavy else 0.0,
        windage_k=2.05e-8 * (displacement / 12.7) ** 1.6,
        seal_drag_Nm=0.85 * (bore / 0.130),
        gear_train_k=3.2e-8 * (displacement / 12.7))

    # ---- thermal + cooling: sized on the heat to be rejected -----------
    spec.thermal = Thermal(
        coolant_volume=3.5e-3 * displacement,
        metal_mass=60.0 * displacement,
        radiator_UA=12.0 * peak_power)
    spec.cooling = Cooling(
        rad_core_area=0.0022 * peak_power,
        rad_UA_ref=11.5 * peak_power,
        rad_air_ref=0.0075 * peak_power,
        fan_dia=0.30 + 0.0010 * peak_power,
        fan_max_flow=0.0095 * peak_power,
        fan_power_max=(28.0 * peak_power) if heavy else (4.0 * peak_power),
        fan_type="viscous" if heavy else "electric",
        fan_on_T=368.0 if heavy else 367.0,
        fan_off_T=363.0 if heavy else 362.0,
        fan_ramp_s=2.5 if heavy else 1.2,
        ic_UA_ref=2.6 * peak_power, ic_air_ref=0.0075 * peak_power,
        ic_core_area=0.0010 * peak_power)

    spec.afr_limit = afr_limit or (19.0 if heavy else 17.5)

    # ---- the rating ----------------------------------------------------
    if apply_rating:
        lo, hi = plateau or (0.45 * rated_rpm, 0.72 * rated_rpm)
        spec.torque_limit_map = (
            (0.60 * lo, 0.80 * peak_torque),
            (lo, peak_torque),
            (hi, peak_torque),
            (rated_rpm, peak_power * 1e3 / (2 * math.pi * rated_rpm / 60.0)),
            (max_rpm, 0.70 * peak_power * 1e3 /
             (2 * math.pi * rated_rpm / 60.0)))
        spec.power_limit = peak_power * 1e3
    return spec


# ==========================================================================
# registration and files
# ==========================================================================
def register(key: str, spec: EngineSpec):
    """Make a spec available everywhere as PRESETS[key].

    Returns a deep copy per lookup, like the built-in preset factories do.
    It used to return the same object every time, so any mutation -- a rating
    override, a spec edit -- leaked into every later lookup of that preset,
    which in a long-lived browser worker means into the next request."""
    PRESETS[key] = lambda s=spec: copy.deepcopy(s)
    return key


def from_dict(d: dict) -> EngineSpec:
    d = dict(d)
    d.pop("key", None)
    if isinstance(d.get("plateau"), list):
        d["plateau"] = tuple(d["plateau"])
    if isinstance(d.get("firing_order"), list):
        d["firing_order"] = tuple(d["firing_order"])
    return build_engine(**d)


def load_engine_file(path: str) -> str:
    with open(path) as f:
        d = json.load(f)
    key = d.get("key") or os.path.splitext(os.path.basename(path))[0]
    return register(key, from_dict(d))


def load_engine_dir(directory: str = "engines") -> list:
    """Register every .json in `directory`.  Returns the keys added."""
    if not os.path.isdir(directory):
        return []
    keys = []
    for fn in sorted(os.listdir(directory)):
        if fn.endswith(".json"):
            try:
                keys.append(load_engine_file(os.path.join(directory, fn)))
            except Exception as e:
                print(f"  skipped {fn}: {e!r}")
    return keys


def save_engine_file(path: str, key: str, **kwargs):
    """Write the headline numbers out so they can be edited by hand."""
    d = dict(key=key, **kwargs)
    for k, v in list(d.items()):
        if isinstance(v, tuple):
            d[k] = list(v)
    with open(path, "w") as f:
        json.dump(d, f, indent=2)
    return path


# ==========================================================================
def verify(spec_or_key, rpms=None, n_cycles: int = 9, jobs: int = None,
           verbose=True):
    """
    Does it actually make the numbers?

    The builder sizes plausible hardware.  Only the solver can say whether
    that hardware delivers, so this runs a real full-load curve and reports
    achieved against requested.
    """
    from .engine import DieselEngine
    if isinstance(spec_or_key, str):
        eng = DieselEngine(preset=spec_or_key)
    else:
        eng = DieselEngine(spec=spec_or_key)
    s = eng.spec
    rpms = rpms or [s.idle_rpm + 100 + i * (s.rated_rpm - s.idle_rpm) / 6.0
                    for i in range(8)]
    out = []
    for rpm in rpms:
        op = eng.operating_point(float(rpm), load=1.0, n_cycles=n_cycles)
        out.append(op)
        if verbose:
            cap = eng.torque_cap(rpm)
            print(f"  {rpm:6.0f} rpm  {op.torque:7.1f} N.m  "
                  f"{op.power/1e3:6.1f} kW  AFR {op.cycle.afr:5.1f}  "
                  f"boost {op.boost_pr:4.2f}  BSFC {op.bsfc:6.1f}"
                  + (f"  (cap {cap:6.1f})" if cap else ""))
    T = max(o.torque for o in out)
    P = max(o.power for o in out)
    if verbose:
        print(f"\n  achieved: {T:7.1f} N.m, {P/1e3:6.1f} kW "
              f"({P/735.5:5.1f} ps)")
        if s.torque_limit_map:
            want_T = max(p[1] for p in s.torque_limit_map)
            want_P = s.power_limit / 1e3
            print(f"  requested:{want_T:7.1f} N.m, {want_P:6.1f} kW  ->  "
                  f"torque {100*T/want_T:5.1f} %, power "
                  f"{100*P/1e3/want_P:5.1f} % of target")
    return out
