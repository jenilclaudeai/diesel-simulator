"""
friction.py -- crank-angle-resolved mechanical friction.

Nothing here is a lumped "FMEP = A + B*Pmax + C*N" curve fit.  Every term is
built from a load, a sliding speed, a film thickness and a Stribeck
transition, so the model reacts correctly to oil temperature, oil condition,
peak cylinder pressure, clearance and wear.

Components
----------
  1. compression + oil control rings   (gas-loaded, mixed lubrication)
  2. piston skirt                      (side thrust from con-rod angle)
  3. big-end bearings                  (Ocvirk short bearing)
  4. main bearings                     (load split between adjacent throws)
  5. valvetrain                        (spring + inertia + gas load, EHL)
  6. crankcase windage / oil churning
  7. accessories: oil pump, water pump, fan, alternator, air compressor,
     high-pressure fuel pump
Pumping work is NOT here -- it falls out of the gas-exchange loop in cycle.py.
"""
from __future__ import annotations

import math

import numpy as np

from . import lubrication as lub
from .config import EngineSpec
from .kinematics import SliderCrank, Cam


class FrictionResult(dict):
    """Plain dict with attribute access for readability."""
    __getattr__ = dict.get


class FrictionModel:
    def __init__(self, spec: EngineSpec, sc: SliderCrank,
                 cam_int: Cam, cam_exh: Cam):
        self.spec = spec
        self.sc = sc
        self.cam_int = cam_int
        self.cam_exh = cam_exh
        t = spec.trib
        self.sigma_ring = lub.composite_roughness(t.ring_face_roughness,
                                                  t.bore_roughness)
        self.sigma_brg = lub.composite_roughness(t.bearing_roughness,
                                                 0.20e-6)
        self.sigma_cam = lub.composite_roughness(0.15e-6, 0.20e-6)

    # ------------------------------------------------------------------ #
    def evaluate(self, theta_deg: np.ndarray, p_cyl: np.ndarray, rpm: float,
                 oil: lub.Oil, wear, p_crank: float = 1.05e5,
                 fuel_mg: float = 0.0,
                 p_rail: float = 0.0) -> FrictionResult:
        """
        theta_deg : crank angle grid for ONE cylinder, 0..720, uniform
        p_cyl     : cylinder pressure on that grid [Pa]
        Returns instantaneous total-engine friction torque and a breakdown.
        """
        spec, g, t = self.spec, self.spec.geom, self.spec.trib
        n = g.n_cyl
        om = 2.0 * math.pi * rpm / 60.0
        th = np.radians(theta_deg)
        dth = np.radians(theta_deg[1] - theta_deg[0])

        # ---- kinematics --------------------------------------------------
        dxdth = self.sc.dx_dtheta(th)
        u_pist = om * dxdth                       # piston velocity [m/s]
        acc = self.sc.piston_accel(th, om)
        beta = self.sc.beta(th)
        A_p = g.piston_area

        # ---- forces along the cylinder axis ------------------------------
        F_gas = (p_cyl - p_crank) * A_p
        F_inert = -g.recip_mass * acc
        F_axial = F_gas + F_inert
        F_rod = F_axial / np.cos(beta)
        F_side = np.abs(F_axial * np.tan(beta))

        # ---- oil properties at the relevant local temperatures -----------
        T_oil = oil.cond.T_oil
        T_liner = 0.55 * spec.thermal.liner_T_top + 0.45 * spec.thermal.liner_T_bot
        T_ring = min(T_liner + 25.0, T_oil + 95.0)
        mu_ring = oil.viscosity(T_ring, 5e6, 2.0e6)
        mu_skirt = oil.viscosity(T_liner - 20.0, 1e6, 5.0e5)
        mu_brg = oil.viscosity(T_oil + 12.0, 2.0e7, 1.0e6)
        # FINDING-015: inlet viscosity. This was evaluated at 5e8 Pa, which
        # applies the Barus factor (x~13,000); hamrock_dowson_film() adds the
        # pressure-viscosity effect again through G = alpha * E', and
        # Dowson-Higginson expects the ambient-pressure viscosity. The film
        # came out ~780x too thick and cam boundary friction ~0.
        mu_cam = oil.viscosity(T_oil + 5.0, 1e5, 1.0e6)
        mu_b = oil.mu_boundary()

        # =================================================================
        # 1. RING PACK
        # =================================================================
        b1 = t.ring_axial_width
        tension_loss = 1.0 - wear.state.ring_tension_loss
        # a tired oil-control ring leaves a thicker film: less friction,
        # more oil consumption (see wear.oil_consumption_g_per_h)
        h_sup = t.oil_supply_film * (1.0 + 2.2 * wear.state.ring_tension_loss
                                     + 6.0e3 * wear.state.bore_wear_tdc)
        F_top = np.zeros_like(th)
        Pb_rings = np.zeros_like(th)
        h_ring_min = 1.0
        for i in range(t.n_comp_rings):
            # inter-ring pressure decays sharply behind the top ring
            frac = 1.0 if i == 0 else 0.18 ** i
            p_behind = p_crank + (p_cyl - p_crank) * frac
            Wl = (2.0 * t.ring_tangential_load * tension_loss / g.bore
                  + np.maximum(p_behind - p_crank, 0.0) * b1)
            h = np.array([lub.ring_film_thickness(mu_ring, u, b1, w, h_sup)
                          for u, w in zip(u_pist, Wl)])
            lam = h / self.sigma_ring
            fb = 1.0 / (1.0 + (lam / lub.LAMBDA_0) ** lub.LAMBDA_K)
            W_tot = Wl * math.pi * g.bore
            A_face = math.pi * g.bore * b1
            F_b = mu_b * fb * W_tot
            F_h = (1.0 - fb) * mu_ring * np.abs(u_pist) * A_face / h
            F_top += F_b + F_h
            Pb_rings += F_b * np.abs(u_pist)
            h_ring_min = min(h_ring_min, float(h.min()))
        # oil control ring: tension only, thin land -> mostly boundary
        b_o = t.oil_ring_width
        Wl_o = 2.0 * t.oil_ring_load * tension_loss / g.bore
        h_o = np.array([lub.ring_film_thickness(mu_ring, u, b_o, Wl_o,
                                                0.55 * h_sup)
                        for u in u_pist])
        lam_o = h_o / self.sigma_ring
        fb_o = 1.0 / (1.0 + (lam_o / lub.LAMBDA_0) ** lub.LAMBDA_K)
        W_o = Wl_o * math.pi * g.bore
        F_oil_ring = (mu_b * fb_o * W_o
                      + (1.0 - fb_o) * mu_ring * np.abs(u_pist)
                      * math.pi * g.bore * b_o / h_o)
        F_rings = F_top + F_oil_ring
        Pb_rings += mu_b * fb_o * W_o * np.abs(u_pist)

        # =================================================================
        # 2. PISTON SKIRT
        # =================================================================
        c_sk = wear.eff_skirt_clearance()
        L_sk = 0.62 * g.bore
        h_sk = np.array([lub.skirt_film_thickness(mu_skirt, u, L_sk, w,
                                                  g.bore, c_sk)
                         for u, w in zip(u_pist, F_side)])
        lam_sk = h_sk / lub.composite_roughness(0.5e-6, t.bore_roughness)
        fb_sk = 1.0 / (1.0 + (lam_sk / lub.LAMBDA_0) ** lub.LAMBDA_K)
        F_skirt = (mu_b * fb_sk * F_side
                   + (1.0 - fb_sk) * mu_skirt * np.abs(u_pist)
                   * t.skirt_area / np.maximum(h_sk, 1e-9))
        Pb_skirt = mu_b * fb_sk * F_side * np.abs(u_pist)

        # =================================================================
        # 3. BIG-END BEARINGS
        # =================================================================
        F_cent_rod = g.rot_mass_bigend * om ** 2 * g.crank_radius
        W_rod = np.abs(F_rod) + F_cent_rod
        c_rod = wear.eff_rod_clearance()
        squeeze = 3.2      # squeeze-film credit under the firing impulse
        T_rod = np.empty_like(th)
        h_rod = np.empty_like(th)
        for i, W in enumerate(W_rod):
            hm, eps, tq, _ = lub.bearing_state(W, om, mu_brg, t.rod_dia,
                                               t.rod_width, c_rod, squeeze)
            T_rod[i] = tq
            h_rod[i] = hm
        lam_rod = h_rod / self.sigma_brg
        fb_rod = 1.0 / (1.0 + (lam_rod / lub.LAMBDA_0) ** lub.LAMBDA_K)
        T_rod_b = mu_b * fb_rod * W_rod * 0.5 * t.rod_dia
        T_rod = T_rod * (1.0 - fb_rod) + T_rod_b
        Pb_rods = T_rod_b * om

        # =================================================================
        # 3b. PISTON PIN (small end) -- oscillates, so it never builds a
        #     full hydrodynamic film: boundary/mixed all the way.
        # =================================================================
        r_pin = 0.5 * t.pin_dia
        # pin sweep rate = d(beta)/dt
        dbeta = np.gradient(beta, dth)
        u_pin = np.abs(dbeta) * om * r_pin
        mu_pin = t.pin_mu_boundary * (1.0 + 0.9 * np.exp(-u_pin / 0.05))
        F_pin = mu_pin * np.abs(F_rod)
        P_pin_inst = F_pin * u_pin
        Pb_pin = P_pin_inst
        T_pin = P_pin_inst / max(om, 1.0)

        # =================================================================
        # 4. MAIN BEARINGS
        # =================================================================
        # each throw dumps its load into the two adjacent mains
        share = float(t.n_mains) / max(n, 1)
        W_main = 0.5 * W_rod / max(share, 0.5) + \
            0.5 * g.rot_mass_bigend * om ** 2 * g.crank_radius
        c_main = wear.eff_main_clearance()
        T_main = np.empty_like(th)
        h_main = np.empty_like(th)
        for i, W in enumerate(W_main):
            hm, eps, tq, _ = lub.bearing_state(W, om, mu_brg, t.main_dia,
                                               t.main_width, c_main, 2.4)
            T_main[i] = tq
            h_main[i] = hm
        lam_main = h_main / self.sigma_brg
        fb_main = 1.0 / (1.0 + (lam_main / lub.LAMBDA_0) ** lub.LAMBDA_K)
        T_main_b = mu_b * fb_main * W_main * 0.5 * t.main_dia
        T_main = T_main * (1.0 - fb_main) + T_main_b
        Pb_mains = T_main_b * om

        # =================================================================
        # 5. VALVETRAIN  (per cylinder, all valves)
        # =================================================================
        vt = spec.valves
        # FINDING-015: Cam.cam_lift() and its derivatives are per CRANK
        # radian ("versus crank angle"), so follower velocity and acceleration
        # take the crank speed. They used om / 2 here: velocity 2x low,
        # inertia force 4x low. Cam-to-crank torque is still halved below.
        T_vt = np.zeros_like(th)
        Pb_vt = 0.0
        v_seat_max = 0.0
        for cam, nv, dv_, lift_max, is_exh in (
                (self.cam_int, vt.n_intake_valves, vt.intake_valve_dia,
                 wear.eff_valve_lift("intake"), False),
                (self.cam_exh, vt.n_exhaust_valves, vt.exhaust_valve_dia,
                 wear.eff_valve_lift("exhaust"), True)):
            scale = lift_max / max(cam.lift_max, 1e-9)
            L = cam.cam_lift(theta_deg) * scale
            dL = cam.dlift_dtheta(theta_deg) * scale
            d2L = cam.d2lift_dtheta2(theta_deg) * scale
            F_spring = vt.valve_spring_preload + vt.valve_spring_rate * L
            F_in = vt.valve_train_eq_mass * d2L * om ** 2
            A_v = math.pi * dv_ ** 2 / 4.0
            F_gasv = np.maximum(p_cyl - 1.1e5, 0.0) * A_v if is_exh else 0.0
            F_cam = np.maximum(F_spring + F_in + F_gasv, 0.0) * nv
            if vt.follower_radius > 0.0:      # roller follower
                mu_roll = 0.0035 + 0.010 * np.exp(-np.abs(dL) * om / 0.35)
                u_sl = 0.06 * np.abs(dL) * om
                T_lobe = mu_roll * F_cam * (vt.cam_base_radius + L)
                # FINDING-005: this branch previously never accumulated
                # Pb_vt, so any engine with a roller follower reported
                # exactly zero valvetrain boundary friction. Wear is driven
                # by boundary power, so cam wear and lash growth were
                # identically zero forever and valvetrain tick never aged.
                #
                # A roller slides far less than a flat tappet, but not zero:
                # ~6% sliding at the contact, per u_sl above. Resolve the
                # boundary share the same way the flat-tappet branch does,
                # with an equivalent radius that includes the roller.
                R_eq_r = 1.0 / (1.0 / max(vt.cam_base_radius, 1e-4)
                                + 1.0 / max(vt.follower_radius, 1e-4))
                w_line_r = np.maximum(F_cam, 1.0) / (nv * 0.012)
                # FINDING-015 item 2: the film is entrained at the ROLLING
                # speed, the cam surface speed om_cam * (R_b + L), not at the
                # 6 % sliding speed (which still sets the boundary power)
                u_roll = 0.5 * om * (vt.cam_base_radius + L)
                h_er = np.array([lub.hamrock_dowson_film(mu_cam,
                                                         max(u, 1e-4),
                                                         R_eq_r, w,
                                                         h_floor=0.1 * self.sigma_cam)
                                 for u, w in zip(u_roll, w_line_r)])
                lam_r = h_er / self.sigma_cam
                fb_r = 1.0 / (1.0 + (lam_r / lub.LAMBDA_0) ** lub.LAMBDA_K)
                Pb_vt += float(np.mean(mu_b * fb_r * F_cam * u_sl))
            else:                              # flat tappet, high sliding
                # FINDING-015 item 2: flat-faced follower kinematics (cam
                # angle phi; L'' per cam radian = 4 x the crank-angle d2L):
                #   sliding      u_s = om_cam * (R_b + L)
                #   entrainment  u_e = om_cam * |R_b + L + 2 L''| / 2
                # u_e passes through zero near the nose, where real flat
                # tappets lose their film. The follower's lift velocity was
                # used for both, which zeroed the sliding where the film was
                # thin and cancelled the boundary power out.
                om_c = 0.5 * om
                u_sl = om_c * (vt.cam_base_radius + L)
                u_ent = om_c * np.abs(vt.cam_base_radius + L + 8.0 * d2L) / 2.0
                R_eq = vt.cam_base_radius
                w_line = np.maximum(F_cam, 1.0) / (nv * 0.012)
                h_e = np.array([lub.hamrock_dowson_film(mu_cam, max(u, 1e-4),
                                                        R_eq, w,
                                                        h_floor=0.1 * self.sigma_cam)
                                for u, w in zip(u_ent, w_line)])
                lam_c = h_e / self.sigma_cam
                fb_c = 1.0 / (1.0 + (lam_c / lub.LAMBDA_0) ** lub.LAMBDA_K)
                mu_eff = mu_b * fb_c + (1.0 - fb_c) * 0.008
                T_lobe = mu_eff * F_cam * (vt.cam_base_radius + L)
                Pb_vt += float(np.mean(mu_b * fb_c * F_cam * u_sl))
            T_vt += T_lobe * 0.5      # cam torque -> crank torque (2:1)
            v_seat_max = max(v_seat_max, cam.seating_velocity(om))

        # =================================================================
        # 6. WINDAGE / CHURNING
        # =================================================================
        rho_oil = oil.density(T_oil)
        P_wind = t.windage_k * rpm ** 2.7 * (rho_oil / 860.0) * n / 6.0
        P_wind += t.gear_train_k * rpm ** 2          # timing gear train
        P_wind += t.seal_drag_Nm * om                # crank seals
        T_wind = P_wind / max(om, 1.0)

        # =================================================================
        # 7. ACCESSORIES
        # =================================================================
        p_gal, Q_pump = oil.gallery_pressure(rpm, wear.oil_leak_factor())
        P_oilpump = oil.pump_power(rpm, p_gal)
        P_water = t.water_pump_k * rpm ** 3
        P_fan = t.fan_k * rpm ** 3 * t.fan_duty
        P_alt = t.alternator_load_W / t.alternator_eta
        P_aircomp = t.aircomp_load_W
        # high-pressure fuel pump: a 1800 bar common-rail pump is one of the
        # biggest single parasitic loads on a modern diesel
        mdot_f = fuel_mg * 1e-6 * n * rpm / 120.0
        Q_f = mdot_f / 830.0 * t.fuel_pump_spill
        P_fuelpump = p_rail * Q_f / t.fuel_pump_eta
        P_acc = P_oilpump + P_water + P_fan + P_alt + P_aircomp + P_fuelpump
        T_acc = P_acc / max(om, 1.0)

        # =================================================================
        # assemble: per-cylinder torques, then phase-sum over the engine
        # =================================================================
        T_cyl = ((F_rings + F_skirt) * np.abs(dxdth)
                 + T_rod + T_main + T_pin + T_vt)
        ns = len(theta_deg)
        T_total = np.zeros_like(T_cyl)
        for i in range(n):
            shift = int(round(g.phase_deg(i) / (theta_deg[1] - theta_deg[0])))
            T_total += np.roll(T_cyl, shift)
        T_total += T_wind + T_acc

        # Report the film/lambda where the ring is actually sliding.  The
        # instantaneous minimum is always the floor at TDC/BDC where u = 0,
        # which tells you nothing.
        fast = np.abs(u_pist) > 0.35 * np.max(np.abs(u_pist))
        h_mid = float(np.min(h[fast])) if np.any(fast) else h_ring_min
        lam_mid = h_mid / self.sigma_ring

        # ---- cycle-average powers ---------------------------------------
        def avg(x):
            return float(np.mean(x))

        P_ring_tot = avg(F_rings * np.abs(u_pist)) * n
        P_skirt_tot = avg(F_skirt * np.abs(u_pist)) * n
        P_rod_tot = avg(T_rod) * om * n
        P_main_tot = avg(T_main) * om * n
        P_vt_tot = avg(T_vt) * om * n
        P_pin_tot = avg(P_pin_inst) * n
        P_mech = (P_ring_tot + P_skirt_tot + P_rod_tot + P_main_tot
                  + P_pin_tot + P_vt_tot)
        P_fric = P_mech + P_wind + P_acc

        W_cycle = P_fric * (120.0 / rpm)
        fmep = W_cycle / g.displacement

        return FrictionResult(
            torque=T_total, torque_per_cyl=T_cyl,
            fmep=fmep, P_friction=P_fric, P_mech=P_mech,
            P_rings=P_ring_tot, P_skirt=P_skirt_tot,
            P_rods=P_rod_tot, P_mains=P_main_tot, P_valvetrain=P_vt_tot,
            P_pin=P_pin_tot,
            P_windage=P_wind, P_accessories=P_acc,
            P_oilpump=P_oilpump, P_waterpump=P_water, P_fan=P_fan,
            P_alternator=P_alt, P_aircomp=P_aircomp, P_fuelpump=P_fuelpump,
            Pb_rings=avg(Pb_rings) * n, Pb_skirt=avg(Pb_skirt) * n,
            Pb_rods=avg(Pb_rods) * n, Pb_mains=avg(Pb_mains) * n,
            Pb_pin=avg(Pb_pin) * n,
            Pb_valvetrain=Pb_vt * n,
            h_ring=h_ring_min, h_rod=float(h_rod.min()),
            h_main=float(h_main.min()), h_skirt=float(h_sk.min()),
            lambda_ring=float(lam_mid), h_ring_mid=float(h_mid),
            gallery_pressure=p_gal, oil_flow=Q_pump,
            v_seating=v_seat_max,
            F_side=F_side, F_rod=F_rod, u_piston=u_pist,
            mu_oil_bearing=mu_brg, mu_oil_ring=mu_ring,
        )
