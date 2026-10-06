"""
cycle.py -- the crank-angle-resolved thermodynamic core.

For every cylinder and every crank step the first law for an open system is
integrated:

  dU = dQ_comb - dQ_wall - p dV + SUM_j dm_j h_j

Physics
-------
ignition delay   Hardenberg-Hase, *integrated* along the real p-T history
                 (sum of dtheta/tau = 1), separately for the pilot and the
                 main injection; a burnt pilot shortens the main delay.
heat release     three superposed Wiebe functions:
                    pilot  (small, fast)
                    premixed main  (sharp spike, fraction grows with delay)
                    diffusion main (duration set by the ACTUAL nozzle flow)
                 -> the premixed spike is what makes diesel combustion noise
heat transfer    Woschni with the combustion velocity term referenced to a
                 tracked motored pressure
gas exchange     compressible flow, both directions, through real valve
                 curtain areas into finite-volume manifolds
blow-by          cylinder -> crankcase through the wear-dependent ring-pack
                 leakage area (and back during the intake stroke)
NOx              extended Zeldovich on a burned-zone temperature that is
                 compressed/expanded isentropically with cylinder pressure
soot             Hiroyasu formation minus oxidation
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import thermo
from .config import EngineSpec
from .kinematics import SliderCrank, build_cams
from .thermo import Fuel

R_MOL = 8.31446
GAMMA_B = 1.27
TAU_MIX_REV = 1.25   # burned-gas / excess-air entrainment time,
                     # expressed in crank revolutions
TAU_WALL = 0.11      # s, burned-zone wall heat-loss time constant
NOX_CAL = 0.030       # calibration of the lumped Zeldovich source
SOOT_CAL = 0.28


@dataclass
class CycleTraces:
    """
    Crank-angle-resolved traces for one solved cycle.

    All fields share the same crank-axis length `n` (720 at the default 1 deg
    step), at every load and preset. But `theta` indexes **two different
    references**, which is the thing that will catch you -- see FINDING-008.

      cylinder-local, shape (n_cyl, n)
          p, p_motored, T, hrr, T_burned, mdot_int, mdot_exh, mdot_blowby
          Each row is aligned to THAT cylinder's own TDC firing, so every
          cylinder reports peak pressure at the same theta. Index [0] for
          cylinder 1.

      cylinder-local, shape (n,)
          V, valve_lift_int, valve_lift_exh
          Identical geometry for every cylinder, so stored once.

      global engine angle, shape (n,)
          p_int_manifold, p_exh_manifold
          The manifolds see every cylinder, so these are in engine angle and
          their pulses are genuinely spread across the firing order.

    Consequences:
      - p[c] against V is correct for every c, for free. Both are local.
      - p[c] against theta for more than one cylinder draws every curve on
        top of the others instead of spread across the firing order.
      - Overlaying manifold pressure on cylinder events is right only for
        cylinder 0, and wrong by that cylinder's phase offset otherwise.
      - Geometry.phase_deg(i) gives the offset needed to convert.

    theta_global, shape (n_cyl, n) -- FINDING-008 option D:
      theta_global[c] is the ENGINE angle of each sample of cylinder c's
      local arrays, (theta - phase_deg[c]) % 720. Pair each array with the
      axis that is right for it:
          p[c], hrr[c], T[c] ...  vs theta            -> cylinder c's own TDC
          p[c], hrr[c], T[c] ...  vs theta_global[c]  -> engine angle
          p_int/exh_manifold      vs theta            -> engine angle
      theta_global[c] wraps at 720; sort by it (or split at the wrap) before
      drawing a line through it.

    Nothing raises an error in any of those cases.

    Separately: do not ravel a 2D field and index theta with the result.
    p.ravel() on a 4-cylinder engine gives 2880 points against theta's 720.
    Take p[0].
    """
    theta: np.ndarray
    p: np.ndarray
    p_motored: np.ndarray     # FINDING-002: reference for combustion-driven rise
    T: np.ndarray
    V: np.ndarray
    mdot_int: np.ndarray
    mdot_exh: np.ndarray
    hrr: np.ndarray
    T_burned: np.ndarray
    p_int_manifold: np.ndarray
    p_exh_manifold: np.ndarray
    mdot_blowby: np.ndarray
    valve_lift_int: np.ndarray
    valve_lift_exh: np.ndarray
    soi_deg: float = 0.0
    soc_pilot_deg: float = -1.0
    soc_main_deg: float = -1.0
    pilot_soi_deg: float = 0.0
    inj_dur_main_deg: float = 0.0
    theta_global: np.ndarray = None     # (n_cyl, n); see the docstring


@dataclass
class CycleResult:
    rpm: float
    imep_gross: float = 0.0
    imep_net: float = 0.0
    pmep: float = 0.0
    p_max: float = 0.0
    dpdtheta_max: float = 0.0
    dpdtheta_comb: float = 0.0   # combustion-driven only; see FINDING-002
    T_max: float = 0.0
    T_burned_max: float = 0.0
    theta_pmax: float = 0.0
    mfb50: float = 0.0
    ign_delay_deg: float = 0.0
    ign_delay_ms: float = 0.0
    premix_fraction: float = 0.0
    burn_duration_deg: float = 0.0
    inj_duration_deg: float = 0.0
    rail_pressure: float = 0.0
    m_air_trapped: float = 0.0
    m_fuel: float = 0.0
    afr: float = 0.0
    phi: float = 0.0
    ve: float = 0.0
    boost_pr: float = 1.0
    p_intake: float = 1e5
    T_intake: float = 300.0
    p_exhaust: float = 1e5
    T_exhaust: float = 700.0
    egr_fraction: float = 0.0
    egr_valve_area: float = 0.0
    residual_fraction: float = 0.0
    blowby_kg_s: float = 0.0
    blowby_lpm: float = 0.0
    q_wall_frac: float = 0.0
    nox_ppm: float = 0.0
    soot_mg_per_cycle: float = 0.0
    turbo_rpm: float = 0.0
    turbo: dict = field(default_factory=dict)
    traces: CycleTraces = None
    state: dict = field(default_factory=dict)
    converged: bool = False       # see _tail_converged (FINDING-013)
    n_cycles_used: int = 0
    cycle_means: list = field(default_factory=list)


# EGR valve starting opening, as a fraction of full area per unit command
# (FINDING-013 item 2; median converged opening / command over 12 points).
EGR_VALVE_START_PER_CMD = 0.14
EGR_VALVE_MIN_START = 0.005

TAIL_CYCLES = 10       # cycles judged by _tail_converged
TAIL_TOL = 1e-3        # relative spread allowed over them


def _tail_converged(means, n=TAIL_CYCLES, tol=TAIL_TOL):
    """True when gross work and boost each vary by less than tol (relative)
    over the last n cycles. Meaningful only for a real-time solve: in an
    accelerated one the last two cycles run at a different rate."""
    if len(means) < n:
        return False
    for key in ("work", "boost"):
        v = [m[key] for m in means[-n:]]
        mean = sum(v) / n
        if (max(v) - min(v)) > tol * max(abs(mean), 1e-12):
            return False
    return True


class CycleSolver:
    def __init__(self, spec: EngineSpec, wear, oil, dtheta: float = 0.5):
        self.spec = spec
        self.wear = wear
        self.oil = oil
        self.dtheta = dtheta
        self.sc = SliderCrank(spec.geom)
        self.cam_int, self.cam_exh = build_cams(spec.valves)
        self.n = int(round(720.0 / dtheta))
        self.theta = np.arange(self.n) * dtheta
        th_r = np.radians(self.theta)
        self.V = self.sc.volume(th_r)
        self.dVdth_rad = self.sc.dV_dtheta(th_r)
        self.x_pist = self.sc.displacement(th_r)
        self.phase_idx = [int(round(spec.geom.phase_deg(i) / dtheta))
                          for i in range(spec.geom.n_cyl)]
        v = spec.valves
        self.closed_mask = np.array(
            [(t >= v.ivc_deg) or (t < v.evo_deg) for t in self.theta])
        self._cache_areas = None
        # per-cylinder bookkeeping is reset in the middle of the exhaust
        # stroke, far from injection and combustion, so that no cylinder ever
        # has its accumulators cleared in the middle of a burn
        self.reset_idx = int(round(300.0 / dtheta)) % self.n
        # naturally-aspirated / bypass breathing areas
        vt = spec.valves
        a_iv = vt.n_intake_valves * math.pi * vt.intake_valve_dia ** 2 / 4.0
        a_ev = vt.n_exhaust_valves * math.pi * vt.exhaust_valve_dia ** 2 / 4.0
        self.A_in_rest = spec.air.intake_restriction_area or 1.9 * a_iv
        self.A_ex_out = spec.air.exhaust_outlet_area or 1.6 * a_ev

    # ------------------------------------------------------------------ #
    def valve_areas(self):
        """Effective valve flow areas over the cycle (wear-corrected)."""
        vt, w = self.spec.valves, self.wear
        key = (w.state.cam_wear_int, w.state.cam_wear_exh,
               w.state.lash_growth_int, w.state.lash_growth_exh)
        if self._cache_areas and self._cache_areas[0] == key:
            return self._cache_areas[1]
        si = w.eff_valve_lift("intake") / max(self.cam_int.lift_max, 1e-9)
        se = w.eff_valve_lift("exhaust") / max(self.cam_exh.lift_max, 1e-9)
        li = np.maximum(0.0, self.cam_int.cam_lift(self.theta) * si
                        - w.eff_lash("intake"))
        le = np.maximum(0.0, self.cam_exh.cam_lift(self.theta) * se
                        - w.eff_lash("exhaust"))
        Ai = np.array([thermo.valve_effective_area(L, vt.intake_valve_dia,
                                                   vt.n_intake_valves,
                                                   vt.cd_intake) for L in li])
        Ae = np.array([thermo.valve_effective_area(L, vt.exhaust_valve_dia,
                                                   vt.n_exhaust_valves,
                                                   vt.cd_exhaust) for L in le])
        out = (Ai, Ae, li, le)
        self._cache_areas = (key, out)
        return out

    # ------------------------------------------------------------------ #
    def rail_pressure(self, rpm, fuel_mg):
        inj = self.spec.inj
        load = min(1.0, fuel_mg / max(self.fuel_smoke_limit(rpm, 2.0), 1e-9))
        spd = min(1.0, rpm / max(self.spec.rated_rpm, 1.0))
        x = 0.35 * spd + 0.75 * load
        return min(inj.rail_pressure_max,
                   inj.rail_pressure_idle
                   + (inj.rail_pressure_max - inj.rail_pressure_idle)
                   * min(1.0, x))

    def fuel_smoke_limit(self, rpm, boost_pr=2.0):
        """Fuel per cylinder-cycle [mg] allowed by the smoke limit."""
        g = self.spec.geom
        rho = boost_pr * 101325.0 / (thermo.R_AIR * 320.0)
        m_air = 0.92 * rho * g.displacement_cyl
        return m_air / self.spec.afr_limit * 1e6

    def injection_profile(self, m_fuel, rail_p, rpm, p_cyl_ref=8.5e6):
        inj = self.spec.inj
        A = (inj.n_holes * math.pi * inj.hole_dia ** 2 / 4.0
             * self.wear.eff_injector_area_factor())
        dp = max(rail_p - p_cyl_ref, 5e6)
        rho = Fuel.density(inj.fuel_temp, rail_p)
        mdot = inj.cd_nozzle * A * rho * math.sqrt(2.0 * dp / rho)
        dur_deg = m_fuel / max(mdot, 1e-12) * rpm * 6.0
        return mdot, dur_deg

    @staticmethod
    def ign_delay_rate(T, p, Sp, cn):
        """Hardenberg-Hase inverse delay [1/deg CA]."""
        p_bar = max(p / 1e5, 13.0)
        Ea = 618840.0 / (cn + 25.0)
        arg = (Ea * (1.0 / (R_MOL * max(T, 300.0)) - 1.0 / 17190.0)
               + (21.2 / (p_bar - 12.4)) ** 0.63)
        tau = (0.36 + 0.22 * Sp) * math.exp(min(arg, 60.0))
        return 1.0 / max(tau, 1e-3)

    @staticmethod
    def dwiebe(x, a, m, dur_deg):
        """d(mass fraction burned)/d(theta) [1/deg]."""
        if x <= 0.0 or x >= 1.0:
            return 0.0
        return (a * (m + 1.0) / dur_deg) * x ** m * math.exp(-a * x ** (m + 1.0))

    # ------------------------------------------------------------------ #
    def run(self, rpm, fuel_mg_per_cycle, turbo, egr_cmd=0.0,
            p_amb=101325.0, T_amb=298.0, n_cycles=12, boost_target=None,
            soi_shift=0.0, state0=None, spool_accel=14.0,
            check_convergence=False) -> CycleResult:
        spec, g, thb = self.spec, self.spec.geom, self.spec.thermal
        nc = g.n_cyl
        om = 2.0 * math.pi * rpm / 60.0
        dth = self.dtheta
        dth_rad = math.radians(dth)
        dt = dth_rad / om
        Sp = g.mean_piston_speed(rpm)
        cn = spec.inj.cetane_number
        # Burned-gas entrainment timescale.  Mixing is driven by the
        # injection-generated turbulence as well as by piston motion, so it
        # does not scale with 1/rpm all the way down -- exponent < 1.
        tau_mix = TAU_MIX_REV * (60.0 / 1800.0) * (1800.0 / max(rpm, 1.0)) ** 0.55
        egr_target = max(0.0, min(1.0, egr_cmd)) * spec.air.egr_max_fraction
        A_egr_max = 4.5e-3 * (g.displacement / 12.7e-3)
        # FINDING-013 item 2: the valve used to start 25 % open for ANY
        # command and was trimmed in real time, so a 9-cycle solve delivered
        # 2-3x its target EGR at part load. Converged openings measured over
        # 12 part-load points run 0.03-0.11 of full area -- 0.07-0.24 of the
        # command, median 0.14 (one outlier 0.65) -- so start there.
        egr_cmd_c = max(0.0, min(1.0, egr_cmd))
        A_egr = (min(1.0, max(EGR_VALVE_MIN_START, EGR_VALVE_START_PER_CMD * egr_cmd_c))
                 * A_egr_max if egr_target > 0 else 0.0)
        bt_eff = None
        if boost_target:
            bt_eff = boost_target * (1.0 + 0.42 * (egr_target /
                                                   max(spec.air.egr_max_fraction,
                                                       1e-6)))

        Ai, Ae, lift_i, lift_e = self.valve_areas()
        A_bb = self.wear.blowby_area()
        A_leak = self.wear.valve_leak_area()

        m_fuel = fuel_mg_per_cycle * 1e-6
        rail = self.rail_pressure(rpm, fuel_mg_per_cycle)
        f_pilot = spec.inj.pilot_fraction if (spec.inj.pilot_enabled
                                              and m_fuel > 0) else 0.0
        mdot_inj, inj_dur = self.injection_profile(m_fuel, rail, rpm)
        dur_pilot = inj_dur * f_pilot
        dur_main = inj_dur * (1.0 - f_pilot)
        soi_main = (720.0 - spec.inj.soi_deg_btdc + soi_shift) % 720.0
        soi_pilot = (soi_main - spec.inj.pilot_advance_deg) % 720.0

        # ---- initial / warm-start state ---------------------------------
        s0 = state0 or {}
        p_int = s0.get("p_int", max(p_amb * 1.05, 1.05e5))
        T_int = s0.get("T_int", T_amb + 18.0)
        yb_int = s0.get("yb_int", 0.0)
        p_exh = s0.get("p_exh", p_amb * 1.2)
        T_exh = s0.get("T_exh", 800.0)
        yb_exh = s0.get("yb_exh", 1.0)
        V_int, V_exh = spec.air.intake_plenum_vol, spec.air.exhaust_manifold_vol
        m_int = p_int * V_int / (thermo.gas_R(yb_int) * T_int)
        m_exh = p_exh * V_exh / (thermo.gas_R(yb_exh) * T_exh)
        m_cyl = np.full(nc, p_int * self.V[0] / (thermo.R_AIR * 900.0))
        T_cyl = np.full(nc, 900.0)
        yb_cyl = np.full(nc, 0.3)
        p_crank = 1.03e5
        T_crank = min(400.0, self.oil.cond.T_oil + 15.0)

        # ---- persistent per-cylinder combustion / bookkeeping state ------
        di_p = np.zeros(nc); di_m = np.zeros(nc)
        soc_p = np.full(nc, -1.0); soc_m = np.full(nc, -1.0)
        m_inj = np.zeros(nc); xb_p = np.zeros(nc); xb_m = np.zeros(nc)
        premix = np.zeros(nc); burn_dur = np.full(nc, 50.0)
        p_prev = np.full(nc, 1e5)
        mbz = np.zeros(nc); Tbz = np.full(nc, 1200.0)
        NOx = np.zeros(nc); soot = np.zeros(nc)
        m_bb = np.zeros(nc); q_wall = np.zeros(nc)
        W_gross = np.zeros(nc); W_pump = np.zeros(nc)
        m_trap = np.zeros(nc); yb_trap = np.zeros(nc)
        p_ivc = np.zeros(nc); V_ivc = np.ones(nc) * self.V[0]
        pmx = np.zeros(nc); Tmx = np.zeros(nc); Tbmx = np.zeros(nc)
        # completed-cycle snapshots (harvested at the reset point)
        SN = dict(NOx=np.zeros(nc), soot=np.zeros(nc), mbb=np.zeros(nc),
                  qw=np.zeros(nc), Wg=np.zeros(nc), Wp=np.zeros(nc),
                  mtr=np.zeros(nc), ybtr=np.zeros(nc), pre=np.zeros(nc),
                  bd=np.full(nc, 50.0), idly=np.zeros(nc), pmax=np.zeros(nc),
                  Tmax=np.zeros(nc), Tbmax=np.zeros(nc))
        V_arr, dV_arr, x_arr = self.V, self.dVdth_rad, self.x_pist
        closed = self.closed_mask
        h_int_wall = 12.0 * V_int ** 0.66
        h_exh_wall = 165.0 * V_exh ** 0.66

        cycle_means = []
        for cyc in range(n_cycles):
            last = (cyc == n_cycles - 1)
            accel = 1.0 if cyc >= n_cycles - 2 else spool_accel
            cm_yb = cm_megr = cm_mc = cm_pint = 0.0

            p_tr = np.zeros((nc, self.n))
            pm_tr = np.zeros((nc, self.n))
            T_tr = np.zeros((nc, self.n))
            mi_tr = np.zeros((nc, self.n))
            me_tr = np.zeros((nc, self.n))
            hrr_tr = np.zeros((nc, self.n))
            tb_tr = np.zeros((nc, self.n))
            bb_tr = np.zeros((nc, self.n))
            pim_tr = np.zeros(self.n)
            pem_tr = np.zeros(self.n)

            ivc_i = int(round(spec.valves.ivc_deg / dth)) % self.n

            for k in range(self.n):
                p_back = p_amb + self.exhaust_backpressure(
                    turbo.last.get("mdot_turb", 0.05))
                ec, et = self.wear.turbo_eff_factors()
                tinfo = turbo.step(dt * accel, p_amb, T_amb, p_int, p_exh,
                                   T_exh, p_back, ec, et,
                                   self.wear.turbo_friction_mult(),
                                   bt_eff)
                mdot_c = tinfo["mdot_comp"]
                T_charge = tinfo.get("T_charge", T_amb)
                mdot_t = tinfo["mdot_turb"]
                if not spec.turbo.enabled:
                    # breathe straight through the air filter and the exhaust
                    p_in = p_amb - spec.air.air_filter_dp_k * 0.0
                    mdot_c, _ = thermo.signed_orifice(p_in, T_amb, 0.0,
                                                      p_int, T_int, yb_int,
                                                      self.A_in_rest)
                    T_charge = T_amb if mdot_c > 0 else T_int
                    mdot_t, _ = thermo.signed_orifice(p_exh, T_exh, yb_exh,
                                                      p_back, T_amb, 1.0,
                                                      self.A_ex_out)

                # EGR: closed-loop on the burnt fraction in the plenum.
                # A high-pressure EGR loop needs exhaust-to-intake dP, so the
                # VGT is biased shut whenever EGR is demanded -- exactly the
                # coupling that makes real EGR cost fuel.
                if egr_target > 0.0:
                    A_egr += 3.0e-3 * A_egr_max * (egr_target - yb_int) * dt \
                        * 1000.0
                    A_egr = min(A_egr_max, max(0.0, A_egr))
                else:
                    A_egr = 0.0
                mdot_egr = 0.0
                if A_egr > 0.0 and p_exh > p_int:
                    mdot_egr = thermo.orifice_mdot(p_exh, T_exh, p_int, A_egr,
                                                   1.33, thermo.R_BURNED)
                T_egr = T_exh - 0.68 * (T_exh - thb.coolant_T)

                dm_i = mdot_c + mdot_egr
                dU_i = (mdot_c * thermo.h_mix(T_charge, 0.0)
                        + mdot_egr * thermo.h_mix(T_egr, 1.0)
                        - h_int_wall * (T_int - thb.coolant_T))
                dyb_i = mdot_egr
                dm_e = -(mdot_t + mdot_egr)
                dU_e = (-(mdot_t + mdot_egr) * thermo.h_mix(T_exh, yb_exh)
                        - h_exh_wall * (T_exh - thb.port_T_exh))
                dyb_e = -(mdot_t + mdot_egr) * yb_exh

                for c in range(nc):
                    kk = (k + self.phase_idx[c]) % self.n
                    if kk == self.reset_idx:
                        SN["NOx"][c] = NOx[c]; SN["soot"][c] = soot[c]
                        SN["mbb"][c] = m_bb[c]; SN["qw"][c] = q_wall[c]
                        SN["Wg"][c] = W_gross[c]; SN["Wp"][c] = W_pump[c]
                        SN["mtr"][c] = m_trap[c]; SN["ybtr"][c] = yb_trap[c]
                        SN["pre"][c] = premix[c]; SN["bd"][c] = burn_dur[c]
                        SN["idly"][c] = ((soc_m[c] - soi_main) % 720.0
                                         if soc_m[c] >= 0 else 0.0)
                        NOx[c] = soot[c] * 0.0
                        soot[c] *= 0.0
                        m_bb[c] = 0.0; q_wall[c] = 0.0
                        W_gross[c] = 0.0; W_pump[c] = 0.0
                        di_p[c] = 0.0; di_m[c] = 0.0
                        soc_p[c] = -1.0; soc_m[c] = -1.0
                        m_inj[c] = 0.0; xb_p[c] = 0.0; xb_m[c] = 0.0
                        SN["pmax"][c] = pmx[c]; SN["Tmax"][c] = Tmx[c]
                        SN["Tbmax"][c] = Tbmx[c]
                        pmx[c] = 0.0; Tmx[c] = 0.0; Tbmx[c] = 0.0
                        mbz[c] = 0.0; Tbz[c] = T_cyl[c]
                    V = V_arr[kk]
                    m = m_cyl[c]
                    T = T_cyl[c]
                    yb = yb_cyl[c]
                    R = thermo.gas_R(yb)
                    p = m * R * T / V
                    tl = kk * dth

                    # ---------- flows ----------
                    mi, _ = thermo.signed_orifice(p_int, T_int, yb_int,
                                                  p, T, yb, Ai[kk])
                    me, _ = thermo.signed_orifice(p, T, yb, p_exh, T_exh,
                                                  yb_exh, Ae[kk])
                    ml = 0.0
                    if A_leak > 0.0:
                        ml, _ = thermo.signed_orifice(p, T, yb, p_exh, T_exh,
                                                      yb_exh, A_leak)
                    if p > p_crank:
                        mb = thermo.orifice_mdot(p, T, p_crank, A_bb,
                                                 thermo.gamma_mix(T, yb), R)
                    else:
                        mb = -thermo.orifice_mdot(p_crank, T_crank, p, A_bb,
                                                  1.36, thermo.R_AIR)

                    # ---------- injection ----------
                    dm_f = 0.0
                    if dur_pilot > 0.0 and ((tl - soi_pilot) % 720.0) < dur_pilot:
                        dm_f += mdot_inj * dt
                    if dur_main > 0.0 and ((tl - soi_main) % 720.0) < dur_main:
                        dm_f += mdot_inj * dt
                    dm_f = min(dm_f, max(0.0, m_fuel - m_inj[c]))
                    m_inj[c] += dm_f

                    # ---------- ignition delay ----------
                    # FINDING-016: resolved within the crank step. The delay
                    # integral used to add a whole step from the first sample
                    # after SOI, and start combustion at the sample where it
                    # passed 1 -- so the delay moved in whole-step jumps and
                    # its real temperature response (~0.2 deg over 90 K at
                    # crdi15 1800/0.6) was quantised away. Now the first
                    # increment covers only the part of the step after SOI,
                    # and SOC is placed where the integral crosses 1 inside
                    # the step (interval (tl - w, tl], so SOC <= tl and the
                    # burn arithmetic below never sees a start in the future).
                    if m_fuel > 0.0:
                        since_p = (tl - soi_pilot) % 720.0
                        if soc_p[c] < 0.0 and dur_pilot > 0.0 and since_p < 180.0:
                            w = min(dth, since_p)
                            prev = di_p[c]
                            di_p[c] += self.ign_delay_rate(T, p, Sp, cn) * w
                            if di_p[c] >= 1.0:
                                frac = (1.0 - prev) / max(di_p[c] - prev, 1e-12)
                                soc_p[c] = (tl - (1.0 - frac) * w) % 720.0
                        since_m = (tl - soi_main) % 720.0
                        if soc_m[c] < 0.0 and since_m < 180.0:
                            boost = 1.0 if soc_p[c] < 0.0 else 2.1
                            w = min(dth, since_m)
                            prev = di_m[c]
                            di_m[c] += self.ign_delay_rate(T, p, Sp, cn) * w * boost
                            if di_m[c] >= 1.0:
                                frac = (1.0 - prev) / max(di_m[c] - prev, 1e-12)
                                soc_m[c] = (tl - (1.0 - frac) * w) % 720.0
                                tau = (soc_m[c] - soi_main) % 720.0
                                m_air = max(m * (1.0 - yb), 1e-9)
                                phi = m_fuel * Fuel.AFR_stoich / m_air
                                # Premixed fraction, derived rather than
                                # correlated (FINDING-001 P-2).
                                #
                                # The premixed burn is physically the fuel
                                # that entered the chamber before ignition
                                # occurred. Injection rate is constant over
                                # the main event, so that fraction is simply
                                # the delay divided by the main injection
                                # duration -- both of which the solver has
                                # already computed from nozzle flow.
                                #
                                # This replaces a Watson-type correlation,
                                # b = 1 - 0.926*phi^0.37 / tau_ms^0.26, which
                                # was calibrated for 1-2 ms delays and returns
                                # a negative value at the 0.1-0.4 ms delays a
                                # modern common-rail engine actually runs. It
                                # was clamped to its 0.02 floor at every
                                # operating point tested, so the premixed
                                # spike could not respond to anything.
                                if dur_main > 1e-9:
                                    b = tau / dur_main
                                else:
                                    b = 0.02
                                premix[c] = min(0.72, max(0.02, b))
                                burn_dur[c] = self.burn_duration(
                                    dur_main, phi, rpm)

                    # ---------- heat release ----------
                    dQ = 0.0
                    eta_c = self.comb_efficiency(m_inj[c], m, yb)
                    if soc_p[c] >= 0.0 and f_pilot > 0.0 and xb_p[c] < 1.0:
                        d_p = max(6.0, 2.2 * dur_pilot + 4.0)
                        x = ((tl - soc_p[c]) % 720.0) / d_p
                        r = self.dwiebe(x, 6.9, 1.6, d_p)
                        xb_p[c] = min(1.0, xb_p[c] + r * dth)
                        dQ += m_fuel * f_pilot * Fuel.LHV * eta_c * r * dth
                    if soc_m[c] >= 0.0 and xb_m[c] < 1.0:
                        bd = burn_dur[c]
                        rel = (tl - soc_m[c]) % 720.0
                        xr = rel / bd
                        d_pre = max(4.0, 0.30 * bd)
                        r_pre = self.dwiebe(rel / d_pre, 6.9, 2.4, d_pre)
                        r_dif = self.dwiebe(xr, 6.9, 0.80, bd)
                        r = premix[c] * r_pre + (1.0 - premix[c]) * r_dif
                        xb_m[c] = min(1.0, xb_m[c] + r * dth)
                        dQ += m_fuel * (1.0 - f_pilot) * Fuel.LHV * eta_c \
                            * r * dth

                    # ---------- wall heat transfer (Woschni) ----------
                    if kk == ivc_i:
                        p_ivc[c] = p
                        V_ivc[c] = V
                        m_trap[c] = m
                        yb_trap[c] = yb
                    p_mot = p_ivc[c] * (V_ivc[c] / V) ** 1.34 if p_ivc[c] > 0 else p
                    C1 = 2.28 if closed[kk] else 6.18
                    C2 = 3.24e-3 if (soc_m[c] >= 0.0 or soc_p[c] >= 0.0) \
                        and closed[kk] else 0.0
                    w_g = C1 * Sp
                    if C2 > 0.0:
                        w_g += C2 * (g.displacement_cyl * 1500.0) / \
                            (max(p_ivc[c], 1e5) * max(V_ivc[c], 1e-9)) * \
                            max(p - p_mot, 0.0)
                    h_w = 3.26 * g.bore ** -0.2 * (p / 1000.0) ** 0.8 * \
                        T ** -0.55 * max(w_g, 0.5) ** 0.8
                    xp = max(x_arr[kk], 1e-5)
                    T_lin = thb.liner_T_bot + (thb.liner_T_top - thb.liner_T_bot) \
                        * (1.0 - xp / g.stroke)
                    dQ_ht = h_w * (1.18 * g.piston_area * (T - thb.head_T)
                                   + 1.42 * g.piston_area * (T - thb.piston_T)
                                   + math.pi * g.bore * xp * (T - T_lin)) * dt
                    q_wall[c] += dQ_ht

                    # ---------- first law ----------
                    u = thermo.u_mix(T, yb)
                    h_here = thermo.h_mix(T, yb)
                    h_fuel = Fuel.cp_liquid * (spec.inj.fuel_temp - thermo.T_REF) \
                        - Fuel.hv_vap
                    dm = (mi - me - ml - mb) * dt + dm_f
                    dU_flow = ((mi if mi > 0 else 0.0) *
                               thermo.h_mix(T_int, yb_int)
                               + (mi if mi < 0 else 0.0) * h_here
                               - (me if me > 0 else 0.0) * h_here
                               - (me if me < 0 else 0.0) *
                               thermo.h_mix(T_exh, yb_exh)
                               - (ml if ml > 0 else 0.0) * h_here
                               - (ml if ml < 0 else 0.0) *
                               thermo.h_mix(T_exh, yb_exh)
                               - (mb if mb > 0 else 0.0) * h_here
                               - (mb if mb < 0 else 0.0) *
                               thermo.h_mix(T_crank, 0.0)) * dt \
                        + dm_f * h_fuel
                    dW = p * dV_arr[kk] * dth_rad
                    U_new = m * u + dQ - dQ_ht - dW + dU_flow
                    m_new = max(m + dm, 1e-9)

                    dyb = (((mi if mi > 0 else 0.0) * (yb_int - yb)
                            + (me if me < 0 else 0.0) * (yb_exh - yb)) * dt
                           - dm_f * yb) / m_new
                    if dQ > 0.0:
                        dyb += dQ / (Fuel.LHV * eta_c) * \
                            (1.0 + Fuel.AFR_stoich /
                             (1.0 - min(0.55, yb_trap[c]))) / m_new
                    yb_new = min(1.0, max(0.0, yb + dyb))
                    T_new = thermo.T_from_u(U_new / m_new, yb_new, T)

                    # ---------- burned zone / NOx ----------
                    p_new = m_new * thermo.gas_R(yb_new) * T_new / V
                    if mbz[c] > 0.0:
                        # isentropic response of the burned gas to dp
                        Tbz[c] *= (p_new / max(p_prev[c], 1e3)) ** \
                            ((GAMMA_B - 1.0) / GAMMA_B)
                        # entrainment of the surrounding excess air: this is
                        # what actually quenches a diesel flame and freezes NO
                        m_free = max(0.0, m - mbz[c])
                        dm_ent = m_free * dt / tau_mix
                        if dm_ent > 0.0:
                            Tbz[c] = (Tbz[c] * mbz[c] + T_new * dm_ent) / \
                                (mbz[c] + dm_ent)
                            mbz[c] += dm_ent
                        # wall heat loss from the burned zone
                        Tbz[c] -= (Tbz[c] - thb.piston_T) * dt / TAU_WALL
                    if dQ > 0.0:
                        # EGR / residual dilution: the flame must heat inert
                        # products as well as air, so more charge mass is
                        # entrained per kg of fuel and the flame runs cooler.
                        dil = min(0.55, yb_trap[c])
                        afr_eff = Fuel.AFR_stoich / (1.0 - dil)
                        dmb = dQ / Fuel.LHV * (1.0 + afr_eff)
                        dT_ad = Fuel.LHV / (1400.0 * (1.0 + afr_eff))
                        T_ad = min(2950.0, T + dT_ad)
                        Tbz[c] = (Tbz[c] * mbz[c] + T_ad * dmb) / (mbz[c] + dmb)
                        mbz[c] += dmb
                    p_prev[c] = p_new
                    if mbz[c] > 1e-9 and Tbz[c] > 1700.0:
                        Tb = min(Tbz[c], 3100.0)
                        Vb = mbz[c] * thermo.R_BURNED * Tb / max(p_new, 1e4)
                        conc = p_new / (R_MOL * Tb) * 1e-6        # mol/cm3
                        xO2 = max(0.005, 0.21 * (1.0 - min(0.95, yb_new)))
                        rate = (6.0e16 / math.sqrt(Tb) * math.exp(-69090.0 / Tb)
                                * math.sqrt(xO2 * conc) * 0.78 * conc)
                        NOx[c] += NOX_CAL * rate * (Vb * 1e6) * 30.0e-3 * dt

                    # ---------- soot ----------
                    if (soc_m[c] >= 0.0 or soc_p[c] >= 0.0) and T_new > 1000.0:
                        m_unb = max(0.0, m_inj[c] - (xb_m[c] * (1 - f_pilot)
                                                     + xb_p[c] * f_pilot) * m_fuel)
                        kf = 4.2e2 * m_unb * (p_new / 1e5) ** 0.5 * \
                            math.exp(-1.25e4 / T_new)
                        ox = 8.0e4 * soot[c] * \
                            max(0.004, 0.21 * (1.0 - min(0.98, yb_new))) * \
                            (p_new / 1e5) ** 1.8 * math.exp(-1.95e4 / T_new)
                        soot[c] = max(0.0, soot[c] + (kf - ox) * dt)

                    # ---------- bookkeeping ----------
                    if closed[kk]:
                        W_gross[c] += dW
                    else:
                        W_pump[c] += dW
                    m_bb[c] += abs(mb) * dt

                    m_cyl[c] = m_new
                    T_cyl[c] = T_new
                    yb_cyl[c] = yb_new

                    # ---------- manifold coupling ----------
                    dm_i -= mi
                    dU_i -= ((mi if mi > 0 else 0.0) *
                             thermo.h_mix(T_int, yb_int)
                             + (mi if mi < 0 else 0.0) * h_here)
                    dyb_i -= ((mi if mi > 0 else 0.0) * yb_int
                              + (mi if mi < 0 else 0.0) * yb)
                    dm_e += me + ml
                    dU_e += ((me if me > 0 else 0.0) * h_here
                             + (me if me < 0 else 0.0) *
                             thermo.h_mix(T_exh, yb_exh)
                             + (ml if ml > 0 else 0.0) * h_here)
                    dyb_e += ((me if me > 0 else 0.0) * yb
                              + (me if me < 0 else 0.0) * yb_exh
                              + (ml if ml > 0 else 0.0) * yb)

                    if p_new > pmx[c]:
                        pmx[c] = p_new
                    if T_new > Tmx[c]:
                        Tmx[c] = T_new
                    if Tbz[c] > Tbmx[c]:
                        Tbmx[c] = Tbz[c]

                    if last:
                        p_tr[c, kk] = p_new
                        pm_tr[c, kk] = p_mot
                        T_tr[c, kk] = T_new
                        mi_tr[c, kk] = mi
                        me_tr[c, kk] = me
                        hrr_tr[c, kk] = dQ / dth
                        tb_tr[c, kk] = Tbz[c]
                        bb_tr[c, kk] = mb

                # ---------- manifolds ----------
                m_i_new = max(m_int + dm_i * dt, 1e-7)
                U_i_new = m_int * thermo.u_mix(T_int, yb_int) + dU_i * dt
                yb_int = min(1.0, max(0.0, yb_int
                                      + (dyb_i - dm_i * yb_int) * dt / m_i_new))
                T_int = thermo.T_from_u(U_i_new / m_i_new, yb_int, T_int)
                m_int = m_i_new
                p_int = m_int * thermo.gas_R(yb_int) * T_int / V_int

                m_e_new = max(m_exh + dm_e * dt, 1e-7)
                U_e_new = m_exh * thermo.u_mix(T_exh, yb_exh) + dU_e * dt
                yb_exh = min(1.0, max(0.25, yb_exh
                                      + (dyb_e - dm_e * yb_exh) * dt / m_e_new))
                T_exh = thermo.T_from_u(U_e_new / m_e_new, yb_exh, T_exh)
                m_exh = m_e_new
                p_exh = m_exh * thermo.gas_R(yb_exh) * T_exh / V_exh

                if last:
                    pim_tr[k] = p_int
                    pem_tr[k] = p_exh
                cm_yb += yb_int
                cm_megr += mdot_egr
                cm_mc += mdot_c
                cm_pint += p_int

            cycle_means.append(dict(
                yb_int=cm_yb / self.n, mdot_egr=cm_megr / self.n,
                mdot_comp=cm_mc / self.n, boost=cm_pint / self.n / p_amb,
                egr_valve=A_egr / A_egr_max if A_egr_max > 0 else 0.0,
                vgt=turbo.vgt_pos, turbo_rpm=turbo.n_rpm,
                work=float(np.mean(SN["Wg"])),
                imep_net=float(np.mean(SN["Wg"]) + np.mean(SN["Wp"]))
                / g.displacement_cyl))

        # ================= results =================
        r = CycleResult(rpm=rpm)
        # per-cycle means, every cycle: a convergence diagnostic (FINDING-013)
        r.cycle_means = cycle_means
        r.n_cycles_used = n_cycles
        # FINDING-013: this was `r.converged = True` at the end of every
        # solve, unchecked (the dead-signal audit allow-listed it). A
        # fixed-count accelerated solve establishes nothing, so it now stays
        # False; only a caller that asks (converged mode, real time) gets a
        # check of the tail -- see _tail_converged.
        r.converged = bool(check_convergence and _tail_converged(cycle_means))
        Vd = g.displacement_cyl
        r.imep_gross = float(np.mean(SN["Wg"])) / Vd
        r.pmep = float(np.mean(SN["Wp"])) / Vd
        r.imep_net = r.imep_gross + r.pmep
        r.p_max = float(np.mean(SN["pmax"]))
        r.T_max = float(np.mean(SN["Tmax"]))
        r.theta_pmax = float(self.theta[int(np.argmax(p_tr[0]))])
        dpd = np.diff(np.concatenate([p_tr[0], p_tr[0][:1]])) / dth
        r.dpdtheta_max = float(dpd.max()) / 1e5
        # Combustion-driven pressure rise only (FINDING-002).
        # dpdtheta_max above is taken over the whole trace and its maximum
        # falls on the compression stroke, ~10 deg before ignition, so it
        # cannot respond to combustion. Subtracting the motored trace leaves
        # the rise that combustion actually caused.
        _pc = p_tr[0] - pm_tr[0]
        _dpc = np.diff(np.concatenate([_pc, _pc[:1]])) / dth
        r.dpdtheta_comb = float(_dpc.max()) / 1e5
        r.m_fuel = m_fuel
        r.m_air_trapped = float(np.mean(SN["mtr"] * (1.0 - SN["ybtr"])))
        r.afr = r.m_air_trapped / max(m_fuel, 1e-15)
        r.phi = Fuel.AFR_stoich / max(r.afr, 1e-9)
        r.ve = float(np.mean(SN["mtr"])) / max(p_int / (thermo.R_AIR * T_int) * Vd,
                                            1e-15)
        r.residual_fraction = float(np.mean(SN["ybtr"]))
        r.egr_fraction = float(yb_int)
        r.egr_valve_area = float(A_egr)
        r.boost_pr = p_int / p_amb
        r.p_intake, r.T_intake = p_int, T_int
        r.p_exhaust, r.T_exhaust = p_exh, T_exh
        r.blowby_kg_s = float(np.mean(SN["mbb"])) * nc / (120.0 / rpm)
        r.blowby_lpm = r.blowby_kg_s / 1.18 * 60000.0
        q_f = m_fuel * Fuel.LHV
        r.q_wall_frac = float(np.mean(SN["qw"])) / max(q_f, 1e-9)
        r.ign_delay_deg = float(np.mean(SN["idly"]))
        r.ign_delay_ms = r.ign_delay_deg / (rpm * 6.0) * 1000.0
        r.premix_fraction = float(np.mean(SN["pre"]))
        r.burn_duration_deg = float(np.mean(SN["bd"]))
        r.inj_duration_deg = inj_dur
        r.rail_pressure = rail
        r.mfb50 = self.mfb50(hrr_tr[0], dth)
        m_out = r.m_air_trapped + m_fuel
        r.nox_ppm = float(np.mean(SN["NOx"])) / max(m_out, 1e-12) * (28.9 / 30.0) * 1e6
        r.soot_mg_per_cycle = float(np.mean(SN["soot"])) * SOOT_CAL * 1e6
        r.T_burned_max = float(np.mean(SN["Tbmax"]))
        r.turbo_rpm = turbo.n_rpm
        r.turbo = dict(turbo.last)
        r.state = dict(p_int=p_int, T_int=T_int, yb_int=yb_int,
                       p_exh=p_exh, T_exh=T_exh, yb_exh=yb_exh)
        r.traces = CycleTraces(
            theta=self.theta.copy(), p=p_tr, p_motored=pm_tr,
            T=T_tr, V=self.V.copy(),
            mdot_int=mi_tr, mdot_exh=me_tr, hrr=hrr_tr, T_burned=tb_tr,
            p_int_manifold=pim_tr, p_exh_manifold=pem_tr, mdot_blowby=bb_tr,
            valve_lift_int=lift_i, valve_lift_exh=lift_e, soi_deg=soi_main,
            soc_pilot_deg=float(soc_p[0]), soc_main_deg=float(soc_m[0]),
            pilot_soi_deg=soi_pilot, inj_dur_main_deg=dur_main,
            # local sample kk of cylinder c holds global step
            # kk - phase_idx[c] (see the storage in the step loop)
            theta_global=(self.theta[None, :]
                          - dth * np.asarray(self.phase_idx, dtype=float)[:, None]) % 720.0)
        return r

    # ------------------------------------------------------------------ #
    def exhaust_backpressure(self, mdot):
        a = self.spec.air
        k = 2.4e4 if a.dpf_present else 7.5e3
        k *= (0.06 / max(a.exhaust_pipe_dia, 0.02)) ** 2
        k *= 1.0 + 0.35 * self.wear.state.dpf_soot_load
        return k * mdot * abs(mdot)

    def burn_duration(self, inj_dur_main, phi, rpm):
        mix = 12.0 + 30.0 * min(phi, 1.3) + 0.0040 * rpm
        d = (1.30 * inj_dur_main + mix) * self.wear.combustion_duration_factor()
        return float(min(max(d, 8.0), 170.0))

    @staticmethod
    def comb_efficiency(m_inj, m_charge, yb):
        phi = m_inj * Fuel.AFR_stoich / max(m_charge * (1.0 - yb), 1e-9)
        return max(0.85, 0.995 - 0.18 * max(0.0, phi - 0.75) ** 1.5)

    def mfb50(self, hrr, dth):
        # FINDING-024: accumulate from gas-exchange TDC (360), not firing TDC
        # (0). From 0, combustion before firing TDC sat at the end of the array
        # and was counted last, which put MFB50 late: 7 deg on `single`, where
        # 41% of the heat is released before TDC.
        k = self.n // 2
        c = np.cumsum(np.roll(hrr, -k)) * dth
        if c[-1] <= 0.0:
            return 0.0
        i = int(np.searchsorted(c, 0.5 * c[-1]))
        t = np.roll(self.theta, -k)[min(i, self.n - 1)]
        return t - 720.0 if t > 360.0 else t
