"""
engine.py -- the complete engine: thermodynamics + tribology + lubrication +
wear, tied together with a governor and a flywheel.

    brake torque = indicated torque - friction torque

Indicated work comes from the p-V loop of cycle.py (so pumping loss is a
result, not an input); friction comes from the mixed-lubrication model in
friction.py; both depend on the oil, and the oil depends on the friction
heat, and the wear depends on both -- the loop is closed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import thermo
from .config import EngineSpec, get_preset
from .cycle import CycleSolver, CycleResult
from .friction import FrictionModel
from .kinematics import SliderCrank
from .lubrication import Oil
from .thermo import Fuel
from .turbo import Turbocharger
from .wear import WearModel


@dataclass
class OperatingPoint:
    rpm: float = 0.0
    fuel_mg: float = 0.0
    torque: float = 0.0             # N.m brake
    power: float = 0.0              # W brake
    bmep: float = 0.0               # Pa
    imep_net: float = 0.0
    fmep: float = 0.0
    pmep: float = 0.0
    bsfc: float = 0.0               # g/kWh
    isfc: float = 0.0
    eta_brake: float = 0.0
    eta_mech: float = 0.0
    fuel_kg_h: float = 0.0
    air_kg_s: float = 0.0
    exhaust_kg_s: float = 0.0
    p_max: float = 0.0
    T_exh: float = 0.0
    boost_pr: float = 0.0
    turbo_rpm: float = 0.0
    egr_pct: float = 0.0
    nox_ppm: float = 0.0
    nox_g_kwh: float = 0.0
    soot_g_h: float = 0.0
    soot_g_kwh: float = 0.0
    blowby_lpm: float = 0.0
    oil_T: float = 0.0
    oil_pressure: float = 0.0
    h_min_rod: float = 0.0
    h_min_main: float = 0.0
    # FINDING-006: the ring film minimum occurs at TDC/BDC where piston
    # speed is zero, so it sits on lubrication.ring_film_thickness's
    # h_floor = 12e-9 clamp in every condition tested -- 102 scalars over 8
    # operating points, identical to floating-point equality. Named for
    # where it is taken so it cannot be mistaken for a varying measurement.
    # For anything that should respond to load, speed or oil condition,
    # read h_ring_mid.
    h_ring_tdc: float = 0.0
    h_ring_mid: float = 0.0      # mid-stroke film -- the useful one
    lambda_ring: float = 0.0
    oil_cons_g_h: float = 0.0
    friction_breakdown: dict = field(default_factory=dict)
    torque_trace: np.ndarray = None      # instantaneous crank torque
    theta: np.ndarray = None
    cycle: CycleResult = None
    friction: dict = field(default_factory=dict)
    wear_health: dict = field(default_factory=dict)

    def __str__(self):
        return (f"{self.rpm:6.0f} rpm | {self.torque:7.1f} N.m | "
                f"{self.power/1000:6.1f} kW | BMEP {self.bmep/1e5:5.2f} bar | "
                f"BSFC {self.bsfc:6.1f} g/kWh | pmax {self.p_max/1e5:5.1f} bar "
                f"| eta_m {self.eta_mech*100:4.1f}%")


class DieselEngine:
    # FINDING-013: cycles for a converged solve. The fast path (14x shaft
    # acceleration, n_cycles ~9) is not converged wherever the VGT or EGR
    # loop is active -- up to -43.6% at part load against a real-time
    # reference. With converged_mode set, every operating_point() (the torque
    # limiter's calibration included) runs at real time for this many cycles
    # and reports whether its last cycles settled (CycleResult.converged).
    # For offline builds: too slow for the browser.
    CONVERGED_CYCLES = 200

    def __init__(self, spec: EngineSpec = None, dtheta: float = 1.0,
                 preset: str = "hd_i6"):
        self.spec = spec or get_preset(preset)
        self.oil = Oil(self.spec.oil)
        self.oil.cond.T_oil = self.spec.thermal.oil_T_target
        self.wear = WearModel(self.spec)
        self.turbo = Turbocharger(self.spec.turbo, self.spec.air,
                                  self.spec.thermal)
        self.cycle = CycleSolver(self.spec, self.wear, self.oil, dtheta)
        self.sc = SliderCrank(self.spec.geom)
        self.friction = FrictionModel(self.spec, self.sc, self.cycle.cam_int,
                                      self.cycle.cam_exh)
        self._state = None
        self.T_coolant = self.spec.thermal.coolant_T
        self._mode_cache = {}
        self._torque_cal = {}
        self._calibrating = False
        self.converged_mode = False
        self._fuel_seed = {}
        self._pt_limit = {}      # rpm key -> (fuel cap or None, reason)
        # Cycles used when calibrating the torque limiter.
        #
        # BUG-8: this was assigned twice, 10 then 8, with comments arguing
        # opposite cases -- one that 6 is unconverged so more cycles are
        # needed, one that the limiter should be calibrated at the same
        # convergence as the points it is judged on. The second assignment
        # won silently and the first was dead code.
        #
        # Keeping 8, which is the value that was actually in force and which
        # every number in the validation table was produced with. The second
        # argument is also the better one: a limiter fitted at a different
        # convergence than it is evaluated at carries that bias into the fit.
        # Note this interacts with known bug #1 -- n_cycles=6 drifts 10.8%,
        # and 8 is not fully converged either.
        self.cal_cycles = 8
        self._th0 = (self.spec.thermal.piston_T, self.spec.thermal.head_T,
                     self.spec.thermal.liner_T_top,
                     self.spec.thermal.liner_T_bot,
                     self.spec.thermal.port_T_exh)
        self.rpm = self.spec.idle_rpm
        self.omega = 2.0 * math.pi * self.rpm / 60.0

    # ------------------------------------------------------------------ #
    # control maps
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------
    def torque_cap(self, rpm: float):
        """
        The brake torque the rating allows at this speed, or None.

        A power limit is a hyperbola in the torque domain (T = P/omega), so
        both scalars and the optional map collapse to one number here.
        """
        s = self.spec
        caps = []
        if s.torque_limit and s.torque_limit > 0.0:
            caps.append(float(s.torque_limit))
        if s.power_limit and s.power_limit > 0.0:
            om = 2.0 * math.pi * max(rpm, 1.0) / 60.0
            caps.append(float(s.power_limit) / om)
        if s.torque_limit_map:
            r = [float(p[0]) for p in s.torque_limit_map]
            t = [float(p[1]) for p in s.torque_limit_map]
            caps.append(float(np.interp(rpm, r, t)))
        return min(caps) if caps else None

    # ------------------------------------------------------------------
    def fuel_for_torque(self, rpm: float, T_target: float,
                        f_max: float = None, tol: float = 0.01,
                        max_iter: int = 4) -> float:
        """
        Fuel that produces `T_target` brake N.m at this speed.

        Brake torque is close to affine in fuelling, so a secant iteration
        converges in two or three solves.  It is only *close* to affine --
        boost, combustion efficiency and friction all drift with fuelling,
        and the solver carries manifold state between calls, so a single
        two-point fit lands 5-10 % out.  Iterating against the real solver
        until the error is under `tol` is the only honest way to do it.

        The result is cached per speed; each iteration is a full
        crank-angle solve.  Call `reset_torque_cal()` after the engine has
        changed appreciably (wear, oil change, a different turbo).
        """
        key = int(round(rpm / 25.0))
        if f_max is None:
            f_max = self.fuel_limit_raw(rpm)
        cal = self._torque_cal.get(key)
        if cal is not None:
            # BUG-8: the cache used to store only (a, b) and clip against
            # fuel_limit_raw, while the calibration below raised its own
            # ceiling to f_max * AFR headroom. The same rpm and target then
            # returned 8.7% less fuel once the cache was warm -- measured on
            # crdi15 at 1800 rpm, 286.6 N.m: 61.31 mg cold, 55.97 mg warm,
            # the latter being exactly fuel_limit_raw. Store the ceiling so
            # both paths clip identically.
            a, b, f_cap = cal
            return float(np.clip((T_target - b) / a, 0.0, f_cap))

        self._calibrating = True
        try:
            # How much fuel the AIR actually supports, measured rather than
            # assumed.  fuel_limit_raw() builds its pressure ratio from an
            # open-loop rpm schedule, so on a well-matched turbo it leaves
            # air on the table -- AFR comes out well above the smoke limit
            # and the engine is fuel-starved for no reason.  Solving once at
            # the raw limit and scaling by the measured AFR headroom fixes
            # that.  It is safe to close this loop here, and only here,
            # because the torque cap bounds the result: without a cap the
            # same feedback runs away (more fuel -> more boost -> more fuel).
            # FINDING-013 item 1: every calibration solve runs with the
            # full-load schedules (load_est=1) that the calibrated fuel is
            # later judged under. They used to see f / fuel_limit_raw -- EGR
            # on across part of the plateau -- and the limiter overshot its
            # cap by up to +5.5% where EGR switched on.
            # The chain starts cold (gas state and turbo, bug #5) so the
            # calibrated fuel is a function of rpm alone, not of whatever
            # was solved before; on a fresh engine this changes nothing.
            op0 = self.operating_point(rpm, fuel_mg=f_max, n_cycles=self.cal_cycles,
                                       load_est=1.0, warm_start=False)
            headroom = float(np.clip(op0.cycle.afr / max(self.spec.afr_limit,
                                                         1e-6), 1.0, 2.2))
            f_ceiling = f_max * headroom
            f1 = 0.60 * f_ceiling
            T1 = self.operating_point(rpm, fuel_mg=f1,
                                      n_cycles=self.cal_cycles, load_est=1.0).torque
            f2 = f_ceiling
            T2 = self.operating_point(rpm, fuel_mg=f2,
                                      n_cycles=self.cal_cycles, load_est=1.0).torque
            f_max = f_ceiling
            a = (T2 - T1) / max(f2 - f1, 1e-9)
            if a <= 1e-6:                    # degenerate: refuse to invert
                return f_max
            b = T1 - a * f1
            if T2 <= T_target:               # the cap is out of reach
                self._torque_cal[key] = (a, b, f_max)
                return f_max
            f, T = f2, T2
            for _ in range(max_iter):
                f_new = float(np.clip((T_target - b) / a, 0.10 * f_max, f_max))
                if abs(f_new - f) < 0.05:
                    break
                T_new = self.operating_point(rpm, fuel_mg=f_new,
                                             n_cycles=self.cal_cycles,
                                             load_est=1.0).torque
                if abs(T_new - T_target) <= tol * abs(T_target):
                    f, T = f_new, T_new
                    break
                a_new = (T_new - T) / (f_new - f) if abs(f_new - f) > 1e-6 else a
                if a_new > 1e-6:
                    a, b = a_new, T_new - a_new * f_new
                f, T = f_new, T_new
        finally:
            self._calibrating = False
        self._torque_cal[key] = (a, b, f_max)
        return float(np.clip((T_target - b) / a, 0.0, f_max))

    def reset_torque_cal(self):
        self._torque_cal = {}
        self._pt_limit = {}

    # ------------------------------------------------------------------
    _TURBO_STATE = ("n_rpm", "vgt_pos", "wg_area", "surge_margin", "bsr", "last")

    def _limit_ratio(self, op):
        """How far over its p_max / T_exh limit a solve is (1.0 = at it)."""
        s = self.spec
        r = 0.0
        if s.p_max_limit and s.p_max_limit > 0.0:
            r = max(r, op.p_max / s.p_max_limit)
        if s.T_exh_limit and s.T_exh_limit > 0.0:
            r = max(r, op.T_exh / s.T_exh_limit)
        return r

    def pressure_temperature_limit(self, rpm: float, fuel_mg: float):
        """
        Fuel at full demand, pulled back until peak cylinder pressure and
        exhaust temperature are within spec.p_max_limit / spec.T_exh_limit.
        Returns (fuel_mg, reason) with reason None, "p_max" or "T_exh".

        One check solve per speed (cached), at full-load schedules, under the
        same convergence as the limiter's calibration. The solver's gas and
        turbo state are restored afterwards, so the solve that follows sees
        exactly what it would have without the check (bug #5: both carry).
        FINDING-010 / known bug #2: the limiter had no pressure or
        temperature bound, so nothing stopped an over-boosted or over-fuelled
        engine at its smoke limit.
        """
        s = self.spec
        if not ((s.p_max_limit and s.p_max_limit > 0.0)
                or (s.T_exh_limit and s.T_exh_limit > 0.0)):
            return fuel_mg, None
        key = int(round(rpm / 25.0))
        hit = self._pt_limit.get(key)
        if hit is not None and hit[2] == fuel_mg:
            return hit[0], hit[1]
        saved = (self._state, {k: getattr(self.turbo, k) for k in self._TURBO_STATE})
        was = self._calibrating
        self._calibrating = True
        try:
            def solve(f, cold=False):
                op = self.operating_point(rpm, fuel_mg=f, n_cycles=self.cal_cycles,
                                          load_est=1.0, warm_start=not cold)
                return op, self._limit_ratio(op)
            # the chain starts cold, so the answer depends on (rpm, fuel) and
            # not on whatever was solved before (bug #5); the secant steps
            # warm-start from it -- restarting each one cold leaves every
            # 8-cycle solve short of its boost and reads p_max ~7% low
            op, ratio = solve(fuel_mg, cold=True)
            f_out, reason = fuel_mg, None
            if ratio > 1.0:
                reason = ("p_max" if s.p_max_limit > 0.0
                          and op.p_max / s.p_max_limit >= ratio else "T_exh")
                # secant on fuel toward ratio = 0.995, from (f, r) and a
                # proportional first guess; both quantities rise with fuel
                f0, r0 = fuel_mg, ratio
                f1 = fuel_mg * 0.995 / ratio
                for _ in range(5):
                    op1, r1 = solve(f1)
                    if abs(r1 - 0.995) < 0.004 or abs(f1 - f0) < 1e-3:
                        break
                    slope = (r1 - r0) / (f1 - f0)
                    f0, r0 = f1, r1
                    f1 = (float(np.clip(f1 + (0.995 - r1) / slope, 0.2 * fuel_mg, fuel_mg))
                          if slope > 1e-9 else f1 * 0.995 / r1)
                f_out = min(fuel_mg, f1)
        finally:
            self._calibrating = was
            self._state = saved[0]
            for k, v in saved[1].items():
                setattr(self.turbo, k, v)
        self._pt_limit[key] = (f_out, reason, fuel_mg)
        return f_out, reason

    def seed_fuel_limit(self, rpm: float, fuel_mg: float):
        """Make fuel_limit(rpm) return fuel_mg without calibrating. For
        builders that calibrate once per speed and share the result across a
        row of cells -- in converged mode a calibration costs several
        200-cycle solves. Kept apart from the calibration cache: seeding that
        cache with a unit fit returned min(cap, fuel) -- right only while the
        cap in N.m happened to exceed the fuel in mg."""
        self._fuel_seed[int(round(rpm / 25.0))] = float(fuel_mg)

    # ------------------------------------------------------------------
    def fuel_limit_raw(self, rpm: float) -> float:
        """Smoke-limited / torque-curve-shaped max fuel per cyl-cycle [mg]."""
        s = self.spec
        pr = 1.0
        if s.turbo.enabled:
            x = min(1.0, max(0.0, (rpm - s.idle_rpm) /
                             max(s.rated_rpm - s.idle_rpm, 1.0)))
            k = getattr(s, "boost_map_rise", 1.0)
            pr = 1.15 + (s.turbo.wastegate_pset - 1.15) * \
                (1.0 - (1.0 - x) ** 2) ** k
        f = self.cycle.fuel_smoke_limit(rpm, pr)
        # de-rate above rated speed the way a real governor does
        if rpm > s.rated_rpm:
            # governor droop: fuel is pulled out between rated and high idle
            x = (rpm - s.rated_rpm) / max(s.max_rpm - s.rated_rpm, 1.0)
            f *= max(0.04, 1.0 - 0.98 * x ** 1.4)
        return f

    # ------------------------------------------------------------------
    def fuel_limit(self, rpm: float) -> float:
        """Fuel at full demand: the lesser of what the air allows and what
        the rating allows."""
        seeded = self._fuel_seed.get(int(round(rpm / 25.0)))
        if seeded is not None:
            return seeded
        f = self.fuel_limit_raw(rpm)
        if self._calibrating:
            return f
        cap = self.torque_cap(rpm)
        if cap is not None:
            # note: fuel_for_torque may return MORE than the open-loop raw
            # limit, because it measures the air instead of assuming it
            f = self.fuel_for_torque(rpm, cap, f)
        return self.pressure_temperature_limit(rpm, f)[0]

    def egr_schedule(self, rpm: float, load: float) -> float:
        """Typical calibration: heavy EGR at part load, cut at full load."""
        if not self.spec.turbo.enabled:
            return 0.0
        x = min(1.0, max(0.0, load))
        r = min(1.0, max(0.0, (rpm - self.spec.idle_rpm) /
                         max(self.spec.rated_rpm - self.spec.idle_rpm, 1.0)))
        return max(0.0, (1.0 - 1.15 * x ** 1.4) * (1.0 - 0.45 * r ** 2))

    def boost_target(self, rpm: float, load: float) -> float:
        s = self.spec
        if not s.turbo.enabled:
            return None
        r = min(1.0, max(0.0, (rpm - s.idle_rpm) /
                         max(s.rated_rpm - s.idle_rpm, 1.0)))
        # A VGT reaches its boost target early; the vanes close down at low
        # flow precisely so it can.  Shape the target the same way the
        # fuelling map is shaped, or the two disagree and the engine runs
        # lean at the bottom of the plateau.
        k = getattr(s, "boost_map_rise", 1.0)
        return 1.10 + (s.turbo.wastegate_pset - 1.10) * \
            (0.25 + 0.75 * r ** k) * (0.35 + 0.65 * min(1.0, load))

    def soi_schedule(self, rpm: float, load: float) -> float:
        """Speed/load advance relative to the base SOI [deg, + = advance]."""
        r = (rpm - self.spec.rated_rpm) / max(self.spec.rated_rpm, 1.0)
        return -(2.5 * r + 2.0 * (0.5 - min(1.0, load)))

    # ------------------------------------------------------------------ #
    # single operating point
    # ------------------------------------------------------------------ #
    def operating_point(self, rpm: float, fuel_mg: float = None,
                        load: float = None, egr: float = None,
                        n_cycles: int = 10, warm_start: bool = True,
                        update_oil: bool = False,
                        p_amb: float = 101325.0,
                        T_amb: float = 298.0,
                        converged: bool = None,
                        load_est: float = None) -> OperatingPoint:
        """
        converged: run at real time for CONVERGED_CYCLES instead of the
            accelerated n_cycles, and check that the last cycles settled
            (FINDING-013). None follows self.converged_mode.
        load_est: the load the EGR / boost-target / SOI schedules see. By
            default fuel_mg / fuel_limit(rpm). The torque limiter's
            calibration passes 1.0 so it is fitted under the same full-load
            schedules it is judged under (FINDING-013 item 1).
        """
        g = self.spec.geom
        conv = self.converged_mode if converged is None else converged
        if fuel_mg is None:
            load = 0.0 if load is None else load
            fuel_mg = max(0.0, load) * self.fuel_limit(rpm)
        if load_est is None:
            load_est = fuel_mg / max(self.fuel_limit(rpm), 1e-9)
        if egr is None:
            egr = self.egr_schedule(rpm, load_est)
        if not warm_start:
            self.turbo.reset()

        cyc = self.cycle.run(
            rpm, fuel_mg, self.turbo, egr_cmd=egr, p_amb=p_amb, T_amb=T_amb,
            boost_target=self.boost_target(rpm, load_est),
            soi_shift=self.soi_schedule(rpm, load_est),
            state0=self._state if warm_start else None,
            **(dict(n_cycles=self.CONVERGED_CYCLES, spool_accel=1.0,
                    check_convergence=True) if conv
               else dict(n_cycles=n_cycles)))
        self._state = cyc.state

        fr = self.friction.evaluate(cyc.traces.theta, cyc.traces.p[0], rpm,
                                    self.oil, self.wear,
                                    fuel_mg=fuel_mg, p_rail=cyc.rail_pressure)

        # ---- brake performance -------------------------------------------
        n_fire = rpm / 120.0                     # firing cycles per second
        P_ind = cyc.imep_net * g.displacement * n_fire
        P_fr = fr["P_friction"]
        P_brake = P_ind - P_fr
        om = 2.0 * math.pi * rpm / 60.0
        torque = P_brake / om
        bmep = P_brake / (g.displacement * n_fire)
        mdot_f = fuel_mg * 1e-6 * g.n_cyl * n_fire
        mdot_air = cyc.m_air_trapped * g.n_cyl * n_fire

        op = OperatingPoint(rpm=rpm, fuel_mg=fuel_mg, torque=torque,
                            power=P_brake, bmep=bmep, imep_net=cyc.imep_net,
                            fmep=fr["fmep"], pmep=cyc.pmep)
        op.fuel_kg_h = mdot_f * 3600.0
        op.air_kg_s = mdot_air
        op.exhaust_kg_s = mdot_air + mdot_f
        op.bsfc = (mdot_f * 3.6e9 / max(P_brake, 1.0)) if P_brake > 0 else 0.0
        op.isfc = (mdot_f * 3.6e9 / max(P_ind, 1.0)) if P_ind > 0 else 0.0
        op.eta_brake = P_brake / max(mdot_f * Fuel.LHV, 1.0)
        op.eta_mech = P_brake / max(P_ind, 1.0)
        op.p_max = cyc.p_max
        op.T_exh = cyc.T_exhaust
        op.boost_pr = cyc.boost_pr
        op.turbo_rpm = cyc.turbo_rpm
        op.egr_pct = cyc.egr_fraction * 100.0
        op.nox_ppm = cyc.nox_ppm
        nox_kg_s = cyc.nox_ppm * 1e-6 * (30.0 / 28.9) * op.exhaust_kg_s
        op.nox_g_kwh = nox_kg_s * 3.6e9 / max(P_brake, 1.0)
        soot_g_h = cyc.soot_mg_per_cycle * 1e-3 * g.n_cyl * n_fire * 3600.0
        op.soot_g_h = soot_g_h
        op.soot_g_kwh = soot_g_h / max(P_brake / 1000.0, 1e-6)
        op.blowby_lpm = cyc.blowby_lpm
        op.oil_T = self.oil.cond.T_oil
        op.oil_pressure = fr["gallery_pressure"]
        op.h_min_rod = fr["h_rod"]
        op.h_min_main = fr["h_main"]
        op.h_ring_tdc = fr["h_ring"]
        op.h_ring_mid = fr["h_ring_mid"]
        op.lambda_ring = fr["lambda_ring"]
        op.oil_cons_g_h = self.wear.oil_consumption_g_per_h(rpm, cyc.imep_gross)
        op.friction_breakdown = {
            "rings": fr["P_rings"], "skirt": fr["P_skirt"],
            "rod_bearings": fr["P_rods"], "main_bearings": fr["P_mains"],
            "valvetrain": fr["P_valvetrain"], "windage": fr["P_windage"],
            "oil_pump": fr["P_oilpump"], "water_pump": fr["P_waterpump"],
            "fan": fr["P_fan"], "alternator": fr["P_alternator"],
            "air_compressor": fr["P_aircomp"], "piston_pin": fr["P_pin"],
            "fuel_pump": fr["P_fuelpump"]}
        op.friction = fr
        op.cycle = cyc
        op.theta = cyc.traces.theta
        op.torque_trace = self.instantaneous_torque(cyc, fr, rpm)
        op.wear_health = self.wear.state.health(self.spec)

        if update_oil:
            self._update_oil(op, dt_s=1.0)
        return op

    # ------------------------------------------------------------------ #
    def instantaneous_torque(self, cyc: CycleResult, fr, rpm: float):
        """
        Total crank torque versus crank angle: gas torque + reciprocating
        inertia torque - friction torque, summed over cylinders with the
        firing order.  This ripple is what shakes the mounts and what you
        hear as 'lugging' at low speed.
        """
        g = self.spec.geom
        th = np.radians(cyc.traces.theta)
        om = 2.0 * math.pi * rpm / 60.0
        dxdth = self.sc.dx_dtheta(th)
        acc = self.sc.piston_accel(th, om)
        T = np.zeros_like(th)
        dth = cyc.traces.theta[1] - cyc.traces.theta[0]
        for c in range(g.n_cyl):
            p = cyc.traces.p[c]
            Fg = (p - 1.03e5) * g.piston_area
            Fi = -g.recip_mass * acc
            t_c = (Fg + Fi) * dxdth
            # FINDING-008: p_tr[c] is stored at kk = (k + phase_idx[c]) % n,
            # so local index kk holds the value from global step
            # kk - phase_idx[c]. Recovering the global trace therefore needs
            # a NEGATIVE roll. The shipped sign was positive.
            #
            # This was latent, not live: for an evenly-fired engine the set
            # of phase offsets is symmetric under negation mod 720 -- crdi15
            # {0,540,180,360} negates to {0,180,540,360}, hd_i6 likewise --
            # so the summed torque is identical either way and only the
            # per-cylinder identities swap. Verified for all four presets.
            # It becomes a real error for an uneven-fire engine, which
            # builder.py and vee_angle_deg make reachable.
            shift = int(round(g.phase_deg(c) / dth))
            T += np.roll(t_c, -shift)
        return T - fr["torque"]

    # ------------------------------------------------------------------ #
    def _apply_thermal_state(self):
        """
        Combustion-chamber wall temperatures follow the coolant.  A cold
        engine has cold walls, so it loses more heat per cycle, burns
        later and runs a longer ignition delay -- that is why a cold diesel
        rattles.
        """
        t = self.spec.thermal
        p0, h0, lt0, lb0, pe0 = self._th0
        f = (self.T_coolant - 361.0)
        t.piston_T = p0 + 0.72 * f
        t.head_T = h0 + 0.85 * f
        t.liner_T_top = lt0 + 0.88 * f
        t.liner_T_bot = lb0 + 0.95 * f
        t.port_T_exh = pe0 + 0.45 * f

    def _update_thermal(self, op: OperatingPoint, dt_s: float):
        """
        Two-node warm-up: coolant + metal in one lump, oil in another.

        The oil cooler couples them, the thermostat holds the coolant in
        until it cracks, and the fuel energy that went into the walls (the
        cycle solver already computed that fraction) is the heat input.
        """
        t = self.spec.thermal
        # The oil/coolant exchange time constant is ~20 s, so a naive Euler
        # step of a minute or an hour blows up.  Sub-step it.
        n_sub = max(1, int(math.ceil(dt_s / 4.0)))
        if n_sub > 1:
            for _ in range(n_sub):
                self._update_thermal(op, dt_s / n_sub)
            return
        cp_cool, rho_cool, cp_metal = 3600.0, 1035.0, 480.0
        C_cool = t.coolant_volume * rho_cool * cp_cool + t.metal_mass * cp_metal
        P_fuel = op.fuel_kg_h / 3600.0 * Fuel.LHV
        Q_wall = op.cycle.q_wall_frac * P_fuel
        Q_exh_mfld = 0.02 * P_fuel                 # manifold + head soak
        # thermostat
        x = (self.T_coolant - t.thermostat_open_T) / \
            max(t.thermostat_full_T - t.thermostat_open_T, 1.0)
        x = min(1.0, max(0.0, x))
        Q_rad = x * t.radiator_UA * max(self.T_coolant - t.ambient_T, 0.0)
        # oil <-> coolant through the cooler
        UA_o = self.spec.oil.cooler_UA * (0.35 + 0.65 *
                                          min(1.0, op.rpm / 1800.0))
        Q_oc = UA_o * (self.oil.cond.T_oil - self.T_coolant)
        self.T_coolant += (Q_wall + Q_exh_mfld + Q_oc - Q_rad) * dt_s / C_cool
        self.T_coolant = min(max(self.T_coolant, 240.0), 400.0)
        # oil node: friction heat + piston cooling jets - cooler
        q_jet = 0.055 * P_fuel
        m_oil = self.oil.mass()
        self.oil.cond.T_oil += (op.friction["P_mech"] + q_jet - Q_oc) * \
            dt_s / (m_oil * 1900.0)
        self.oil.cond.T_oil = min(max(self.oil.cond.T_oil, 240.0), 430.0)
        self._apply_thermal_state()

    # kept for backwards compatibility
    def _update_oil(self, op: OperatingPoint, dt_s: float):
        self._update_thermal(op, dt_s)

    # ------------------------------------------------------------------ #
    # torque / power curve
    # ------------------------------------------------------------------ #
    def full_load_curve(self, rpms=None, n_cycles: int = 9, verbose=True):
        s = self.spec
        if rpms is None:
            rpms = np.linspace(s.idle_rpm + 100, s.max_rpm, 9)
        out = []
        for rpm in rpms:
            op = self.operating_point(float(rpm), load=1.0, n_cycles=n_cycles)
            out.append(op)
            if verbose:
                print("  " + str(op))
        return out

    def performance_map(self, rpms=None, loads=(0.15, 0.35, 0.6, 0.85, 1.0),
                        n_cycles: int = 8, verbose=False):
        s = self.spec
        if rpms is None:
            rpms = np.linspace(s.idle_rpm + 100, s.max_rpm, 7)
        grid = []
        for rpm in rpms:
            row = []
            for ld in loads:
                op = self.operating_point(float(rpm), load=float(ld),
                                          n_cycles=n_cycles)
                row.append(op)
                if verbose:
                    print(f"  {rpm:6.0f} {ld:4.2f}  {op}")
            grid.append(row)
        return rpms, np.array(loads), grid

    # ------------------------------------------------------------------ #
    # warm-up: cold oil -> thick oil -> huge friction -> fast warm-up
    # ------------------------------------------------------------------ #
    def warmup(self, minutes: float = 12.0, rpm: float = None,
               load: float = 0.25, dt_s: float = 20.0, T_start: float = 273.0):
        rpm = rpm or self.spec.idle_rpm * 1.35
        self.oil.cond.T_oil = T_start
        self.T_coolant = T_start
        self._apply_thermal_state()
        log = []
        t = 0.0
        while t < minutes * 60.0:
            op = self.operating_point(rpm, load=load, n_cycles=5)
            self._update_oil(op, dt_s)
            self.wear.accumulate(dt_s / 3600.0,
                                 {"P_rings": op.friction["Pb_rings"],
                                  "P_skirt": op.friction["Pb_skirt"],
                                  "P_rods": op.friction["Pb_rods"],
                                  "P_mains": op.friction["Pb_mains"],
                                  "P_valvetrain": op.friction["Pb_valvetrain"],
                                  "h_main": op.h_min_main,
                                  "h_rod": op.h_min_rod,
                                  "v_seating": op.friction["v_seating"]},
                                 self.oil, rpm, op.soot_g_h, op.boost_pr,
                                 op.turbo_rpm, op.egr_pct / 100.0)
            log.append(dict(t=t, T_oil=self.oil.cond.T_oil,
                            T_coolant=self.T_coolant, fmep=op.fmep,
                            P_fric=op.friction["P_friction"], bsfc=op.bsfc,
                            oil_p=op.oil_pressure, torque=op.torque,
                            visc=self.oil.viscosity(self.oil.cond.T_oil)))
            t += dt_s
        return log

    # ------------------------------------------------------------------ #
    # durability
    # ------------------------------------------------------------------ #
    def durability_run(self, hours: float, duty_cycle=None, step_h: float = 50.0,
                       cold_starts_per_100h: float = 40.0, verbose=True,
                       resolve_every: int = 1):
        """
        Age the engine over `hours` of a duty cycle.

        duty_cycle: list of (rpm, load, time_fraction).
        Wear, oil ageing and their feedback are integrated in `step_h` blocks;
        the engine is re-solved at the start of every block so the degradation
        actually changes the running condition.
        """
        s = self.spec
        if duty_cycle is None:
            duty_cycle = [(s.idle_rpm, 0.05, 0.18),
                          (0.62 * s.rated_rpm, 0.45, 0.34),
                          (0.85 * s.rated_rpm, 0.75, 0.34),
                          (s.rated_rpm, 1.00, 0.14)]
        log = []
        t = 0.0
        oil_hours = 0.0
        n_changes = 0
        i_block = 0
        while t < hours:
            # never step past an oil change -- the drain interval is a real
            # discontinuity and stepping over it hides the whole ageing curve
            dt = min(step_h, hours - t,
                     max(self.spec.oil.change_interval_h - oil_hours, 1.0))
            block = []
            for k_mode, (rpm, load, frac) in enumerate(duty_cycle):
                dt_i = dt * frac
                # Settle the thermal state for this mode FIRST, using the
                # previous visit to it, so the point we log and the wear we
                # integrate are both at a realistic temperature rather than
                # at whatever the previous mode happened to leave behind.
                prev = self._mode_cache.get(k_mode)
                if prev is not None:
                    for _ in range(8):
                        self._update_thermal(prev, 45.0)
                # Re-solving the full crank-angle cycle every block is the
                # expensive part, and over ~100 h the operating point barely
                # moves.  `resolve_every` lets the oil/wear integration run
                # at fine time resolution while the cycle is refreshed less
                # often; the friction powers driving wear are reused.
                if prev is None or i_block % max(resolve_every, 1) == 0:
                    op = self.operating_point(rpm, load=load, n_cycles=6)
                    self._mode_cache[k_mode] = op
                else:
                    op = prev
                for _ in range(3):
                    self._update_thermal(op, 45.0)
                soot_in = 0.00042 * op.soot_g_h * (1.0 + 2.5 *
                                                   op.egr_pct / 100.0)
                fuel_dil = 2.6e-5 if op.oil_T < 340.0 else -1.0e-5
                self.oil.age(dt_i, soot_in, fuel_dil,
                             blowby_factor=1.0 + 0.02 * op.blowby_lpm)
                self.wear.accumulate(
                    dt_i,
                    {"P_rings": op.friction["Pb_rings"],
                     "P_skirt": op.friction["Pb_skirt"],
                     "P_rods": op.friction["Pb_rods"],
                     "P_mains": op.friction["Pb_mains"],
                     "P_valvetrain": op.friction["Pb_valvetrain"],
                     "h_main": op.h_min_main, "h_rod": op.h_min_rod,
                     "v_seating": op.friction["v_seating"]},
                    self.oil, rpm, op.soot_g_h, op.boost_pr, op.turbo_rpm,
                    op.egr_pct / 100.0)
                block.append(op)
            # cold-start wear bursts
            n_cs = cold_starts_per_100h * dt / 100.0
            self.wear.state.cold_starts += int(n_cs)
            self.wear.state.bore_wear_tdc += n_cs * 2.6e-10
            self.wear.state.main_clearance_growth += n_cs * 5.0e-11
            oil_hours += dt
            t += dt
            i_block += 1
            rated = block[-1]
            # oil pressure tracks the CURRENT oil condition even on blocks
            # where the cycle was not re-solved
            p_gal, _ = self.oil.gallery_pressure(rated.rpm,
                                                 self.wear.oil_leak_factor())
            log.append(dict(hours=self.wear.state.hours, power=rated.power,
                            torque=rated.torque, bsfc=rated.bsfc,
                            blowby=rated.blowby_lpm, p_max=rated.p_max,
                            boost=rated.boost_pr, fmep=rated.fmep,
                            oil_p=p_gal,
                            oil_soot=self.oil.cond.soot_pct,
                            oil_tbn=self.oil.cond.tbn,
                            oil_visc=self.oil.cond.visc_multiplier,
                            bore_wear_um=self.wear.state.bore_wear_tdc * 1e6,
                            ring_gap_mm=self.wear.eff_ring_gap() * 1e3,
                            main_clr_um=self.wear.eff_main_clearance() * 1e6,
                            inj_cok=self.wear.state.injector_coking,
                            turbo_foul=self.wear.state.turbo_foul_turb,
                            health=self.wear.state.overall_health(self.spec),
                            oil_cons=rated.oil_cons_g_h,
                            oil_run_h=oil_hours, oil_changes=n_changes,
                            oil_add=self.oil.cond.additive_left,
                            oil_dil=self.oil.cond.fuel_dilution,
                            nox=rated.nox_g_kwh, soot=rated.soot_g_kwh))
            # ---- the oil change happens AFTER the sample, so the log shows
            #      the condition the oil actually reached in service
            if oil_hours >= self.spec.oil.change_interval_h - 1e-9:
                self.oil.cond.reset(self.spec.oil)
                oil_hours = 0.0
                n_changes += 1
            if verbose:
                L = log[-1]
                print(f"  {L['hours']:7.0f} h | {L['power']/1000:6.1f} kW | "
                      f"BSFC {L['bsfc']:6.1f} | blowby {L['blowby']:5.1f} L/min"
                      f" | bore {L['bore_wear_um']:5.1f} um | "
                      f"oil p {L['oil_p']/1e5:4.2f} bar | health "
                      f"{L['health']:5.1f}%")
        return log

    # ------------------------------------------------------------------ #
    # transient with a real flywheel
    # ------------------------------------------------------------------ #
    def transient(self, duration: float, throttle_fn, load_torque_fn,
                  dt: float = 0.02, rpm0: float = None, n_cycles: int = 3):
        """
        Integrate  J dw/dt = T_engine(w, fuel) - T_load(w)
        with the governor setting fuel from the throttle demand.  Turbo lag
        is inherited from the cycle solver's live shaft state.
        """
        g = self.spec.geom
        rpm = rpm0 or self.spec.idle_rpm
        J = g.flywheel_inertia
        t = 0.0
        log = []
        # FINDING-012: stall speed. The cycle solver returns finite torque
        # down to ~250 rpm on crdi15 (negative -- friction exceeding
        # indicated work, which is right for a dying engine) and NaN from
        # ~200 rpm down. The previous floor clamped at 150 rpm, inside that
        # failure region, and `max(nan, floor)` returns nan, so it could not
        # catch what it was there to catch. A diesel has stopped well before
        # either figure; declare a stall above the solver's limit instead.
        rpm_stall = max(300.0, 0.4 * self.spec.idle_rpm)
        while t < duration:
            thr = float(throttle_fn(t))
            f_cmd = thr * self.fuel_limit(rpm)
            # simple all-speed governor around idle
            if rpm < self.spec.idle_rpm:
                f_cmd = max(f_cmd, self.fuel_limit(rpm) *
                            min(0.45, 0.02 * (self.spec.idle_rpm - rpm)))
            # always the fast path: a transient step is not a steady state
            op = self.operating_point(rpm, fuel_mg=f_cmd, n_cycles=n_cycles,
                                      converged=False)
            T_load = float(load_torque_fn(t, rpm))
            if not math.isfinite(op.torque):
                raise RuntimeError(
                    f"transient: cycle solver returned non-finite torque at "
                    f"{rpm:.1f} rpm, t={t:.3f} s. This is below the solver's "
                    f"valid range; the stall check should have caught it.")
            om = 2.0 * math.pi * rpm / 60.0
            om += (op.torque - T_load) / J * dt
            rpm = om * 60.0 / (2.0 * math.pi)
            self._update_oil(op, dt)
            stalled = rpm < rpm_stall
            log.append(dict(t=t, rpm=0.0 if stalled else rpm, throttle=thr,
                            fuel=f_cmd, torque=op.torque, power=op.power,
                            boost=op.boost_pr, turbo_rpm=op.turbo_rpm,
                            T_load=T_load, smoke=op.soot_g_h,
                            afr=op.cycle.afr, bsfc=op.bsfc, op=op,
                            stalled=stalled))
            if stalled:
                # a stalled diesel does not restart itself; stop integrating
                # rather than asking the solver about speeds it cannot model
                break
            t += dt
        return log
