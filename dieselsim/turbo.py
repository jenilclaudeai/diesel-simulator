"""
turbo.py -- turbocharger, charge cooling and intake restriction.

The compressor map is generated from similitude rather than tabulated:
pressure ratio scales with the square of blade speed, the choke line scales
with corrected speed, and the constant-speed line is an ellipse between
surge and choke.  The turbine is treated as a variable nozzle whose
swallowing capacity comes from the same compressible-flow relation used for
the valves, with efficiency a parabola in blade-speed ratio.

The shaft is integrated in real time, which is what produces turbo lag,
spool-up whoosh and the boost overshoot after a gear change.
"""
from __future__ import annotations

import math

from . import thermo
from .config import Turbo, AirPath, Thermal

T_REF = 298.0
P_REF = 101325.0
CP_AIR_MEAN = 1010.0
CP_EXH_MEAN = 1180.0
GAMMA_AIR = 1.40
GAMMA_EXH = 1.33


class Compressor:
    def __init__(self, spec: Turbo):
        self.s = spec

    def speed_norm(self, n_rpm: float, T_in: float) -> float:
        n_corr = n_rpm / math.sqrt(max(T_in, 100.0) / T_REF)
        return n_corr / self.s.n_corr_ref

    def choke_flow(self, u: float) -> float:
        return self.s.mdot_corr_max * max(u, 1e-3) ** 0.88

    def pr_max(self, u: float) -> float:
        return 1.0 + (self.s.pr_max_ref - 1.0) * u ** 2

    def solve(self, n_rpm: float, pr: float, p_in: float, T_in: float,
              eff_scale: float = 1.0):
        """
        Returns (mdot [kg/s], efficiency, T_out [K], surge_margin, u).
        surge_margin < 0 => operating inside the surge line.
        """
        u = self.speed_norm(n_rpm, T_in)
        prm = self.pr_max(u)
        pr = max(pr, 1.0)
        if prm <= 1.0001:
            return 0.0, 0.5, T_in, 1.0, u
        y = min(1.0, (pr - 1.0) / (prm - 1.0))
        m_ch = self.choke_flow(u)
        m_corr = m_ch * math.sqrt(max(0.0, 1.0 - y ** 2))
        mdot = m_corr * (p_in / P_REF) / math.sqrt(max(T_in, 100.0) / T_REF)

        m_rel = m_corr / max(m_ch, 1e-9)
        eta = self.s.comp_eff_peak * eff_scale * (
            1.0 - 1.55 * (m_rel - 0.68) ** 2 - 0.42 * (u - 0.78) ** 2)
        eta = min(max(eta, 0.28), 0.86)
        m_surge = 0.30 * m_ch
        surge_margin = (m_corr - m_surge) / max(m_ch, 1e-9)
        T_out = T_in * (1.0 + (pr ** ((GAMMA_AIR - 1.0) / GAMMA_AIR) - 1.0)
                        / eta)
        return mdot, eta, T_out, surge_margin, u

    def power(self, mdot: float, T_in: float, pr: float, eta: float) -> float:
        if mdot <= 0.0:
            return 0.0
        dh = CP_AIR_MEAN * T_in * (pr ** ((GAMMA_AIR - 1.0) / GAMMA_AIR) - 1.0)
        return mdot * dh / max(eta, 0.15)

    def blade_pass_freq(self, n_rpm: float) -> float:
        return self.s.comp_blades * n_rpm / 60.0


class Turbine:
    def __init__(self, spec: Turbo):
        self.s = spec

    def effective_area(self, vgt_pos: float = 1.0) -> float:
        """vgt_pos: 1.0 = fully open, vgt_min_frac = closed (more boost)."""
        if not self.s.vgt:
            return self.s.turbine_area_eff
        f = min(1.0, max(self.s.vgt_min_frac, vgt_pos))
        return self.s.turbine_area_eff * f

    def flow(self, p_in: float, T_in: float, p_out: float, A_eff: float):
        return thermo.orifice_mdot(p_in, T_in, p_out, A_eff, GAMMA_EXH,
                                   thermo.R_BURNED)

    def efficiency(self, n_rpm: float, p_in: float, T_in: float, p_out: float,
                   eff_scale: float = 1.0):
        pr = max(p_in / max(p_out, 1e3), 1.0001)
        c_is = math.sqrt(2.0 * CP_EXH_MEAN * T_in *
                         (1.0 - pr ** (-(GAMMA_EXH - 1.0) / GAMMA_EXH)))
        u_tip = math.pi * self.s.turb_wheel_dia * n_rpm / 60.0
        bsr = u_tip / max(c_is, 1.0)
        x = bsr / 0.68
        eta = self.s.turb_eff_peak * eff_scale * max(0.0, 2.0 * x - x * x)
        return min(max(eta, 0.05), 0.88), bsr, c_is

    def power(self, mdot: float, T_in: float, pr: float, eta: float) -> float:
        if mdot <= 0.0:
            return 0.0
        dh = CP_EXH_MEAN * T_in * (1.0 - pr ** (-(GAMMA_EXH - 1.0) / GAMMA_EXH))
        return mdot * dh * eta

    def blade_pass_freq(self, n_rpm: float) -> float:
        return self.s.turb_blades * n_rpm / 60.0


class Turbocharger:
    """Compressor + turbine + shaft + wastegate/VGT + intercooler."""

    def __init__(self, spec: Turbo, air: AirPath, thermal: Thermal):
        self.s = spec
        self.air = air
        self.th = thermal
        self.comp = Compressor(spec)
        self.turb = Turbine(spec)
        self.n_rpm = 12000.0 if spec.enabled else 0.0
        self.vgt_pos = 1.0
        self.wg_area = 0.0
        self.surge_margin = 1.0
        self.bsr = 0.0
        self.last = {}

    # ------------------------------------------------------------------ #
    def air_filter_dp(self, mdot: float) -> float:
        return self.air.air_filter_dp_k * mdot * abs(mdot)

    def intercooler(self, T_in: float, mdot: float, eff_scale: float = 1.0):
        eff = self.s.intercooler_eff * eff_scale
        T_out = T_in - eff * (T_in - self.s.charge_cooler_medium_T)
        dp = self.s.intercooler_dp * (mdot / max(self.s.mdot_corr_max, 1e-6)) ** 2
        return T_out, dp

    # ------------------------------------------------------------------ #
    def step(self, dt: float, p_amb: float, T_amb: float, p_intake: float,
             p_exh: float, T_exh: float, p_back: float,
             eff_c: float = 1.0, eff_t: float = 1.0,
             fric_mult: float = 1.0, boost_target: float = None):
        """
        Advance the shaft by dt seconds.
        Returns dict with compressor flow/temperature and turbine flow.
        """
        if not self.s.enabled:
            self.last = dict(mdot_comp=0.0, T_comp_out=T_amb, mdot_turb=0.0,
                             pr_c=1.0, eta_c=0.0, eta_t=0.0, n_rpm=0.0,
                             P_comp=0.0, P_turb=0.0, wg_flow=0.0)
            return self.last

        # ---- compressor inlet after the air filter -----------------------
        m_prev = self.last.get("mdot_comp", 0.02)
        p1 = p_amb - self.air_filter_dp(m_prev)
        T1 = T_amb
        pr_c = max(p_intake / max(p1, 1e4), 1.0)
        mdot_c, eta_c, T2, surge, u = self.comp.solve(self.n_rpm, pr_c, p1, T1,
                                                      eff_c)
        self.surge_margin = surge
        P_c = self.comp.power(mdot_c, T1, pr_c, eta_c)

        # ---- boost control ------------------------------------------------
        pr_boost = p_intake / max(p_amb, 1e4)
        if self.s.vgt:
            tgt = boost_target if boost_target else self.s.wastegate_pset
            err = pr_boost - tgt
            self.vgt_pos = min(1.0, max(self.s.vgt_min_frac,
                                        self.vgt_pos + 2.5 * err * dt))
            self.wg_area = 0.0
        else:
            over = pr_boost - self.s.wastegate_pset
            self.wg_area = max(0.0, over) * self.s.wastegate_gain
        A_t = self.turb.effective_area(self.vgt_pos)

        # ---- turbine --------------------------------------------------------
        mdot_t = self.turb.flow(p_exh, T_exh, p_back, A_t)
        wg_flow = self.turb.flow(p_exh, T_exh, p_back, self.wg_area) \
            if self.wg_area > 0 else 0.0
        eta_t, bsr, c_is = self.turb.efficiency(self.n_rpm, p_exh, T_exh,
                                                p_back, eff_t)
        self.bsr = bsr
        P_t = self.turb.power(mdot_t, T_exh, p_exh / max(p_back, 1e4), eta_t)

        # ---- shaft ----------------------------------------------------------
        om = 2.0 * math.pi * self.n_rpm / 60.0
        T_fric = self.s.bearing_visc_k * fric_mult * om ** 2
        net = (P_t - P_c) / max(om, 50.0) - T_fric
        om += net / self.s.shaft_inertia * dt
        om = min(max(om, 2.0 * math.pi * 1000.0 / 60.0),
                 2.0 * math.pi * 1.35 * self.s.n_corr_ref / 60.0)
        self.n_rpm = om * 60.0 / (2.0 * math.pi)

        T_ic, dp_ic = self.intercooler(T2, mdot_c)
        self.last = dict(mdot_comp=mdot_c, T_comp_out=T2, T_charge=T_ic,
                         dp_ic=dp_ic, mdot_turb=mdot_t + wg_flow,
                         pr_c=pr_c, eta_c=eta_c, eta_t=eta_t,
                         n_rpm=self.n_rpm, P_comp=P_c, P_turb=P_t,
                         wg_flow=wg_flow, surge_margin=surge, bsr=bsr,
                         vgt_pos=self.vgt_pos, u_norm=u,
                         p_comp_in=p1, T_fric=T_fric * om)
        return self.last
