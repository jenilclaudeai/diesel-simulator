"""
wear.py -- cumulative mechanical degradation and its feedback into the
running engine.

Wear is driven by *boundary-lubrication friction energy*, which is what the
tribology model already produces.  Archard's law

        V = k * W * s / H          [m^3]

is rewritten using  E_boundary = mu_b * W * s  so that

        V = (k / (mu_b * H)) * E_boundary

which means every joule the model burns in asperity contact removes a
deterministic amount of metal.  Wear then feeds back:

  bore/ring wear     -> larger ring gap -> more blow-by -> lower compression,
                        higher oil consumption, more piston slap noise
  bearing wear       -> larger clearance -> more leakage -> lower gallery
                        pressure -> thinner film -> *more* wear (runaway)
  cam / lash wear    -> less valve lift -> lower volumetric efficiency,
                        louder valvetrain tick
  injector coking    -> lower nozzle Cd -> longer injection & burn duration,
                        more soot, harsher combustion noise
  turbine/compressor -> lower efficiency, higher shaft drag -> less boost
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import EngineSpec, Tribology

# Archard coefficients [dimensionless] for boundary-lubricated steel/iron
K_ARCHARD = {
    "ring": 1.95e-10,   # nitrided/CrN face: far more wear resistant
                    # than the cast-iron bore it runs against
    "bore": 1.14e-09,
    "skirt": 5.5e-10,
    "main_bearing": 1.1e-9,
    "rod_bearing": 1.4e-9,
    "cam": 3.2e-9,
}


@dataclass
class WearState:
    hours: float = 0.0
    cycles: float = 0.0
    cold_starts: int = 0
    fuel_burned_kg: float = 0.0

    # --- cylinder kit (metres) ---
    bore_wear_tdc: float = 0.0        # radial wear at the top ring reversal
    bore_taper: float = 0.0           # top-to-bottom diameter difference
    ring_face_wear: float = 0.0       # radial loss on the top ring face
    ring_gap_growth: float = 0.0
    ring_tension_loss: float = 0.0    # fraction 0..1
    skirt_wear: float = 0.0           # radial

    # --- bearings ---
    main_clearance_growth: float = 0.0
    rod_clearance_growth: float = 0.0
    min_film_seen_main: float = 1e-3
    min_film_seen_rod: float = 1e-3

    # --- valvetrain ---
    cam_wear_int: float = 0.0
    cam_wear_exh: float = 0.0
    lash_growth_int: float = 0.0
    lash_growth_exh: float = 0.0
    seat_recession: float = 0.0

    # --- fuel system ---
    injector_coking: float = 0.0      # 0..1, area blockage
    injector_spray_deg: float = 0.0   # 0..1 atomisation degradation

    # --- turbo ---
    turbo_shaft_wear: float = 0.0     # m clearance growth
    turbo_foul_comp: float = 0.0      # 0..1 efficiency loss fraction
    turbo_foul_turb: float = 0.0

    # --- aftertreatment / misc ---
    dpf_soot_load: float = 0.0        # g/L
    accumulated_wear_energy: float = field(default_factory=float)

    # ---------------------------------------------------------------- #
    def health(self, spec: EngineSpec) -> dict:
        t = spec.trib
        # Percentage of usable life CONSUMED: 0 = new, 100 = at the
        # overhaul limit.  Each item is measured from the new condition,
        # not from zero, so a brand-new engine reads 0 everywhere.
        lim_bore = 0.12e-3                      # max bore wear at TDC
        lim_gap = 2.0 * t.ring_gap_new          # allowed end-gap growth
        lim_main = 0.8 * t.main_clearance_new   # allowed clearance growth
        return {
            "bore_wear_pct": 100.0 * self.bore_wear_tdc / lim_bore,
            "ring_gap_pct": 100.0 * self.ring_gap_growth / lim_gap,
            "main_clearance_pct": 100.0 * self.main_clearance_growth
            / lim_main,
            "seat_recession_pct": 100.0 * self.seat_recession / 0.60e-3,
            "injector_pct": 100.0 * self.injector_coking / 0.14,
            "turbo_pct": 100.0 * self.turbo_foul_turb / 0.085,
        }

    def overall_health(self, spec: EngineSpec) -> float:
        """
        Life consumed [%]: 0 = new, 100 = due for overhaul.

        Injector coking and turbo fouling are excluded: they are service
        items you clean or replace, not reasons to lift the head.
        """
        h = self.health(spec)
        return min(100.0, max(h["bore_wear_pct"], h["ring_gap_pct"],
                              h["main_clearance_pct"],
                              h["seat_recession_pct"]))


class WearModel:
    """Integrates wear given per-cycle tribology results."""

    def __init__(self, spec: EngineSpec):
        self.spec = spec
        self.state = WearState()

    # ------------------------------------------------------------------ #
    @staticmethod
    def cold_start_multiplier(T_oil: float) -> float:
        """
        Wear rate multiplier versus oil temperature.  Below ~40 C the film
        has not formed, fuel dilution is high and acids condense: real
        engines do the majority of their wear here.
        """
        if T_oil >= 358.0:
            return 1.0
        x = (358.0 - T_oil) / 60.0
        return 1.0 + 22.0 * x ** 2.1

    # ------------------------------------------------------------------ #
    def accumulate(self, dt_h: float, tribo: dict, oil, rpm: float,
                   soot_rate_g_h: float, boost_pr: float,
                   turbo_rpm: float, egr_frac: float):
        """
        Advance the wear state.

        tribo : dict of boundary friction ENERGY per second [W] per component
                plus the minimum films seen this cycle.
        """
        s = self.state
        t = self.spec.trib
        dt_s = dt_h * 3600.0
        kmul = self.cold_start_multiplier(oil.cond.T_oil) * oil.wear_factor()

        def dv(name, hardness, power_W):
            return K_ARCHARD[name] * power_W * dt_s / (oil.mu_boundary()
                                                       * hardness) * kmul

        n = self.spec.geom.n_cyl
        B = self.spec.geom.bore

        # ---- rings & bore -------------------------------------------------
        V_ring = dv("ring", t.ring_hardness, tribo.get("P_rings", 0.0))
        V_bore = dv("bore", t.bore_hardness, tribo.get("P_rings", 0.0))
        # ring face: spread over ring circumference x axial width
        A_ring = n * t.n_comp_rings * math.pi * B * t.ring_axial_width
        s.ring_face_wear += V_ring / max(A_ring, 1e-9)
        # bore: concentrated in the top ~15 % of the stroke (ring reversal)
        A_bore_top = n * math.pi * B * (0.15 * self.spec.geom.stroke)
        s.bore_wear_tdc += V_bore / max(A_bore_top, 1e-9)
        s.bore_taper = 0.85 * s.bore_wear_tdc
        # end gap grows with bore diameter and with ring face loss
        # The end gap is measured where the ring sits, not at the TDC
        # reversal step, so only the general bore enlargement counts -- about
        # a quarter of the peak wear depth.  Ring face loss opens the gap
        # directly by the full circumference.
        s.ring_gap_growth = (2.0 * math.pi * 0.25 * s.bore_wear_tdc
                             + 2.0 * math.pi * s.ring_face_wear)
        # tension is lost to face wear plus slow thermal relaxation of the
        # ring itself (creep at ring-groove temperature)
        s.ring_tension_loss = min(0.35, 320.0 * s.ring_face_wear
                                  + 1.2e-5 * s.hours)

        # ---- skirt ---------------------------------------------------------
        V_sk = dv("skirt", 0.35 * t.bore_hardness, tribo.get("P_skirt", 0.0))
        s.skirt_wear += V_sk / max(n * t.skirt_area, 1e-9)

        # ---- bearings ------------------------------------------------------
        V_mb = dv("main_bearing", t.bearing_hardness, tribo.get("P_mains", 0.0))
        A_mb = t.n_mains * math.pi * t.main_dia * t.main_width
        s.main_clearance_growth += 2.0 * V_mb / max(A_mb, 1e-9)
        V_rb = dv("rod_bearing", t.bearing_hardness, tribo.get("P_rods", 0.0))
        A_rb = n * math.pi * t.rod_dia * t.rod_width
        s.rod_clearance_growth += 2.0 * V_rb / max(A_rb, 1e-9)
        s.min_film_seen_main = min(s.min_film_seen_main,
                                   tribo.get("h_main", 1e-3))
        s.min_film_seen_rod = min(s.min_film_seen_rod, tribo.get("h_rod", 1e-3))

        # ---- valvetrain -----------------------------------------------------
        vt = self.spec.valves
        V_cam = dv("cam", 4.5e9, tribo.get("P_valvetrain", 0.0))
        A_cam = 2 * n * (vt.n_intake_valves + vt.n_exhaust_valves) * \
            math.pi * vt.cam_base_radius * 0.014
        lobe_loss = V_cam / max(A_cam, 1e-9)
        s.cam_wear_int += 0.45 * lobe_loss
        s.cam_wear_exh += 0.55 * lobe_loss          # exhaust lobes run hotter
        s.lash_growth_int += 0.45 * lobe_loss
        s.lash_growth_exh += 0.55 * lobe_loss
        # valve seat recession: impact energy x hot corrosion
        v_seat = tribo.get("v_seating", 0.4)
        s.seat_recession += 2.0e-13 * v_seat ** 2 * rpm * dt_h * 60.0 * \
            (1.0 + 2.0 * egr_frac)

        # ---- injectors -------------------------------------------------------
        # coking is driven by tip temperature (load) and soot; EGR accelerates it
        # Deposits build toward an equilibrium: they grow until the tip
        # temperature and the spray shear knock them off as fast as they
        # form, so the rate is proportional to the remaining headroom.
        COK_MAX = 0.14
        cok_rate = 2.6e-4 * (1.0 + 2.5 * egr_frac) * \
            (0.3 + 0.7 * min(1.0, soot_rate_g_h / 4.0))
        s.injector_coking += cok_rate * (COK_MAX - s.injector_coking) * dt_h
        s.injector_coking = min(COK_MAX, max(0.0, s.injector_coking))
        s.injector_spray_deg = min(1.0, 1.55 * s.injector_coking)

        # ---- turbocharger -----------------------------------------------------
        if self.spec.turbo.enabled:
            n_norm = turbo_rpm / max(self.spec.turbo.n_corr_ref, 1.0)
            s.turbo_shaft_wear += 1.4e-10 * n_norm ** 2.2 * dt_h * \
                self.cold_start_multiplier(oil.cond.T_oil) ** 0.5
            # fouling also self-limits -- the deposit layer spalls
            FC_MAX, FT_MAX = 0.055, 0.085
            s.turbo_foul_comp += 2.2e-4 * dt_h * (1.0 + 3.0 * egr_frac) * \
                (FC_MAX - s.turbo_foul_comp)
            s.turbo_foul_turb += 2.8e-4 * dt_h * (1.0 + 1.4 * soot_rate_g_h) \
                * (FT_MAX - s.turbo_foul_turb)
            s.turbo_foul_comp = min(FC_MAX, max(0.0, s.turbo_foul_comp))
            s.turbo_foul_turb = min(FT_MAX, max(0.0, s.turbo_foul_turb))

        s.hours += dt_h
        s.cycles += rpm * 30.0 * dt_h * 60.0

    # ------------------------------------------------------------------ #
    # Feedback -- "effective" parameters seen by the physics models
    # ------------------------------------------------------------------ #
    def eff_ring_gap(self) -> float:
        return self.spec.trib.ring_gap_new + self.state.ring_gap_growth

    def blowby_area(self) -> float:
        """
        Effective leakage area from cylinder to crankcase.
        A fresh ring pack leaks through the end gaps, the ring-groove back
        clearance and bore distortion; only a fraction of the geometric gap
        acts as a restriction because the second ring throttles the flow.
        """
        t = self.spec.trib
        gap = self.eff_ring_gap()
        h_leak = 0.11e-3 + 1.8 * self.state.bore_wear_tdc     # radial channel
        A_geo = gap * h_leak
        # labyrinth of two rings in series -> ~0.42 of a single restriction
        A = 0.42 * A_geo * (1.0 + 2.6 * self.state.ring_tension_loss)
        return max(A, 1e-9)

    def eff_skirt_clearance(self) -> float:
        return (self.spec.trib.skirt_clearance_new
                + 2.0 * self.state.skirt_wear + 2.0 * self.state.bore_wear_tdc)

    def eff_main_clearance(self) -> float:
        return self.spec.trib.main_clearance_new + self.state.main_clearance_growth

    def eff_rod_clearance(self) -> float:
        return self.spec.trib.rod_clearance_new + self.state.rod_clearance_growth

    def oil_leak_factor(self) -> float:
        """Bearing leakage scales with clearance^3 -> gallery pressure drop."""
        t = self.spec.trib
        fm = (self.eff_main_clearance() / t.main_clearance_new) ** 3
        fr = (self.eff_rod_clearance() / t.rod_clearance_new) ** 3
        return 0.55 * fm + 0.45 * fr

    def eff_valve_lift(self, which: str) -> float:
        vt = self.spec.valves
        if which == "intake":
            return max(0.2 * vt.intake_lift_max,
                       vt.intake_lift_max - self.state.cam_wear_int)
        return max(0.2 * vt.exhaust_lift_max,
                   vt.exhaust_lift_max - self.state.cam_wear_exh)

    def eff_lash(self, which: str) -> float:
        vt = self.spec.valves
        if which == "intake":
            return vt.lash_intake + self.state.lash_growth_int
        return vt.lash_exhaust + self.state.lash_growth_exh

    def eff_injector_area_factor(self) -> float:
        return 1.0 - self.state.injector_coking

    def combustion_duration_factor(self) -> float:
        """Poor atomisation stretches the diffusion burn."""
        return 1.0 + 0.55 * self.state.injector_spray_deg

    def turbo_eff_factors(self):
        s = self.state
        return (1.0 - s.turbo_foul_comp), (1.0 - s.turbo_foul_turb)

    def turbo_friction_mult(self) -> float:
        return 1.0 + 4.5e3 * self.state.turbo_shaft_wear

    def valve_leak_area(self) -> float:
        """Seat recession + carbon -> compression leak past the valves."""
        return 4.5e-7 * (self.state.seat_recession / 1e-4) ** 1.6

    def oil_consumption_g_per_h(self, rpm: float, imep: float) -> float:
        """Throw-off + blow-through + valve-guide leakage."""
        s = self.state
        base = 0.9 + 1.5e6 * (s.bore_wear_tdc + 0.6 * s.ring_face_wear)
        base *= (1.0 + 1.8 * s.ring_tension_loss)
        return base * (0.35 + 0.65 * rpm / 1800.0) * (0.5 + 0.5 * imep / 15e5)
