"""
FINDING-005 follow-up: why cam boundary friction stays negligible.

Two suspected problems in friction.py's valvetrain block, measured here
without changing the solver:

  1. TIME BASE. Cam.cam_lift() and its derivatives are functions of CRANK
     angle (kinematics.Cam: "versus crank angle"; seating_velocity() is fed
     crank speed). The friction block multiplies them by the CAM speed,
     om_cam = om / 2. Follower velocity then comes out 2x low and the
     inertia force m * L'' * om_cam**2 4x low. Measured by giving the
     friction model's cams per-CAM-radian derivatives (x2, x4) on a fresh
     engine -- exactly the correction, applied to friction only (nothing
     else calls those methods).

  2. FLAT-TAPPET KINEMATICS. The branch uses |dL/dtheta| * om_cam, the
     follower's lift velocity, as both the sliding speed and the entrainment
     speed. For a flat-faced follower (cam angle phi, derivatives per cam
     radian):
         sliding       u_s = om_cam * (R_b + L)
         entrainment   u_e = om_cam * |R_b + L + 2 L''| / 2
     u_e passes through zero near the nose, which is where real flat tappets
     lose their film. A replica of the branch is checked against the
     engine's own Pb_valvetrain first, then re-run with these speeds.

  3. VISCOSITY. mu_cam = oil.viscosity(T, p=5e8, ...) applies the Barus
     pressure-viscosity factor at 500 MPa (exp(1.9e-8 * 5e8) = exp(9.5),
     ~13,000x), and hamrock_dowson_film() applies the pressure-viscosity
     effect again through G = alpha * E'. Dowson-Higginson expects the
     INLET (ambient-pressure) viscosity. Variant: mu at p = 1e5.

For the roller branch (hd_i6), the film is entrained at the rolling speed
om_cam * (R_b + L), not at the 6 % sliding speed the branch uses for it.

Diagnostic only. Run:  python3 tools/diag_cam_boundary.py
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dieselsim import lubrication as lub  # noqa: E402
from dieselsim.engine import DieselEngine  # noqa: E402

POINTS = (("crdi15", 2000, 0.6), ("crdi_1p5", 2000, 0.6), ("hd_i6", 1400, 0.6),
          ("ld_i4", 2500, 0.6), ("single", 2000, 0.8))


def per_cam_radian(cam):
    """Make cam's derivatives per cam radian (cam angle = crank angle / 2)."""
    d1, d2 = cam.dlift_dtheta, cam.d2lift_dtheta2
    cam.dlift_dtheta = lambda th, *a, **k: 2.0 * d1(th, *a, **k)
    cam.d2lift_dtheta2 = lambda th, *a, **k: 4.0 * d2(th, *a, **k)


def time_base():
    print("1. time base: valvetrain friction with crank-angle derivatives x om_cam "
          "(shipped) vs per-cam-radian (corrected)")
    print(f"{'point':18} {'P_vt W':>9} {'->':>3} {'W':>9} {'FMEP bar':>9} {'->':>3} "
          f"{'bar':>7} {'torque':>8} {'->':>3} {'N.m':>8}")
    for preset, rpm, load in POINTS:
        out = []
        for fix in (False, True):
            eng = DieselEngine(preset=preset)
            if fix:
                per_cam_radian(eng.friction.cam_int)
                per_cam_radian(eng.friction.cam_exh)
            op = eng.operating_point(rpm, load=load, n_cycles=9)
            out.append((op.friction["P_valvetrain"], op.fmep / 1e5, op.torque))
        (p0, f0, t0), (p1, f1, t1) = out
        print(f"{preset + ' ' + str(rpm) + '/' + str(load):18} {p0:9.1f} {'':>3} {p1:9.1f} "
              f"{f0:9.3f} {'':>3} {f1:7.3f} {t0:8.2f} {'':>3} {t1:8.2f}")


def flat_tappet(preset="single", rpm=2000, load=0.8):
    eng = DieselEngine(preset=preset)
    op = eng.operating_point(rpm, load=load, n_cycles=9)
    fr, oil, vt = eng.friction, eng.oil, eng.spec.valves
    assert vt.follower_radius == 0.0, "flat tappet only"
    th_deg = op.cycle.traces.theta
    p_cyl = op.cycle.traces.p[0]
    om = 2.0 * math.pi * rpm / 60.0
    om_cam = 0.5 * om
    mu_cam_shipped = oil.viscosity(oil.cond.T_oil + 5.0, 5e8, 1.0e6)
    mu_cam_inlet = oil.viscosity(oil.cond.T_oil + 5.0, 1e5, 1.0e6)
    mu_b = oil.mu_boundary()

    def branch(time_fix, kin_fix, inlet=False):
        mu_cam = mu_cam_inlet if inlet else mu_cam_shipped
        Pb, lam_min, frac_thin = 0.0, np.inf, []
        for cam, nv, dv_, lift_max, is_exh in (
                (fr.cam_int, vt.n_intake_valves, vt.intake_valve_dia,
                 eng.wear.eff_valve_lift("intake"), False),
                (fr.cam_exh, vt.n_exhaust_valves, vt.exhaust_valve_dia,
                 eng.wear.eff_valve_lift("exhaust"), True)):
            s = lift_max / max(cam.lift_max, 1e-9)
            L = cam.cam_lift(th_deg) * s
            k1, k2 = (2.0, 4.0) if time_fix else (1.0, 1.0)
            dL = cam.dlift_dtheta(th_deg) * s * k1
            d2L = cam.d2lift_dtheta2(th_deg) * s * k2
            F_spring = vt.valve_spring_preload + vt.valve_spring_rate * L
            F_in = vt.valve_train_eq_mass * d2L * om_cam ** 2
            A_v = math.pi * dv_ ** 2 / 4.0
            F_gasv = np.maximum(p_cyl - 1.1e5, 0.0) * A_v if is_exh else 0.0
            F_cam = np.maximum(F_spring + F_in + F_gasv, 0.0) * nv
            if kin_fix:
                # per-cam-radian derivatives are needed here whatever time_fix says
                d2c = cam.d2lift_dtheta2(th_deg) * s * 4.0
                u_s = om_cam * (vt.cam_base_radius + L)
                u_e = om_cam * np.abs(vt.cam_base_radius + L + 2.0 * d2c) / 2.0
            else:
                u_s = u_e = np.abs(dL) * om_cam
            w_line = np.maximum(F_cam, 1.0) / (nv * 0.012)
            h = np.array([lub.hamrock_dowson_film(mu_cam, max(u, 1e-4), vt.cam_base_radius, w)
                          for u, w in zip(u_e, w_line)])
            lam = h / fr.sigma_cam
            fb = 1.0 / (1.0 + (lam / lub.LAMBDA_0) ** lub.LAMBDA_K)
            Pb += float(np.mean(mu_b * fb * F_cam * u_s))
            lam_min = min(lam_min, float(lam.min()))
            frac_thin.append(float(np.mean(lam < 1.0)))
        return Pb, lam_min, max(frac_thin)

    engine_pb = op.friction["Pb_valvetrain"]
    rep_pb = branch(False, False)[0]
    print(f"\n2. flat tappet ({preset} {rpm}/{load}): replica check -- engine "
          f"Pb_valvetrain {engine_pb:.4e} W, replica {rep_pb:.4e} W "
          f"({'MATCH' if abs(rep_pb - engine_pb) <= 1e-9 * max(abs(engine_pb), 1e-30) else 'MISMATCH'})")
    print(f"   {'variant':44} {'Pb_vt W':>11} {'min lambda':>11} {'cycle lambda<1':>15}")
    print(f"   viscosity: shipped {mu_cam_shipped:.3g} Pa.s (at 500 MPa), inlet {mu_cam_inlet:.3g} Pa.s")
    for name, tf, kf, iv in (("shipped", False, False, False),
                             ("time base fixed", True, False, False),
                             ("flat-tappet kinematics fixed", False, True, False),
                             ("inlet viscosity only", False, False, True),
                             ("kinematics + inlet viscosity", False, True, True),
                             ("all three fixed", True, True, True)):
        pb, lm, ft = branch(tf, kf, iv)
        print(f"   {name:44} {pb:11.4e} {lm:11.3f} {100 * ft:14.1f}%")
    print(f"   (valvetrain friction power P_valvetrain, shipped: {op.friction['P_valvetrain']:.1f} W)")


def roller(preset="hd_i6", rpm=1400, load=0.6):
    eng = DieselEngine(preset=preset)
    op = eng.operating_point(rpm, load=load, n_cycles=9)
    fr, oil, vt = eng.friction, eng.oil, eng.spec.valves
    th_deg, p_cyl = op.cycle.traces.theta, op.cycle.traces.p[0]
    om_cam = 0.5 * 2.0 * math.pi * rpm / 60.0
    mu_b = oil.mu_boundary()

    def branch(fixed):
        mu_cam = oil.viscosity(oil.cond.T_oil + 5.0, 1e5 if fixed else 5e8, 1.0e6)
        Pb, lam_min = 0.0, np.inf
        for cam, nv, dv_, lift_max, is_exh in (
                (fr.cam_int, vt.n_intake_valves, vt.intake_valve_dia,
                 eng.wear.eff_valve_lift("intake"), False),
                (fr.cam_exh, vt.n_exhaust_valves, vt.exhaust_valve_dia,
                 eng.wear.eff_valve_lift("exhaust"), True)):
            s = lift_max / max(cam.lift_max, 1e-9)
            k1, k2 = (2.0, 4.0) if fixed else (1.0, 1.0)
            L = cam.cam_lift(th_deg) * s
            dL = cam.dlift_dtheta(th_deg) * s * k1
            d2L = cam.d2lift_dtheta2(th_deg) * s * k2
            F_cam = np.maximum(vt.valve_spring_preload + vt.valve_spring_rate * L
                               + vt.valve_train_eq_mass * d2L * om_cam ** 2
                               + (np.maximum(p_cyl - 1.1e5, 0.0) * math.pi * dv_ ** 2 / 4
                                  if is_exh else 0.0), 0.0) * nv
            u_sl = 0.06 * np.abs(dL) * om_cam
            u_e = om_cam * (vt.cam_base_radius + L) if fixed else u_sl
            R = 1.0 / (1.0 / max(vt.cam_base_radius, 1e-4) + 1.0 / max(vt.follower_radius, 1e-4))
            w = np.maximum(F_cam, 1.0) / (nv * 0.012)
            h = np.array([lub.hamrock_dowson_film(mu_cam, max(u, 1e-4), R, ww) for u, ww in zip(u_e, w)])
            lam = h / fr.sigma_cam
            fb = 1.0 / (1.0 + (lam / lub.LAMBDA_0) ** lub.LAMBDA_K)
            Pb += float(np.mean(mu_b * fb * F_cam * u_sl))
            lam_min = min(lam_min, float(lam.min()))
        return Pb * eng.spec.geom.n_cyl, lam_min

    pb0, l0 = branch(False)
    pb1, l1 = branch(True)
    print(f"\n3. roller ({preset} {rpm}/{load}): engine Pb_valvetrain {op.friction['Pb_valvetrain']:.4e} W, "
          f"replica {pb0:.4e} W")
    print(f"   shipped                         Pb {pb0:.4e} W, min lambda {l0:.3f}")
    print(f"   rolling entrainment, inlet visc, time base   Pb {pb1:.4e} W, min lambda {l1:.3f}")


if __name__ == "__main__":
    time_base()
    flat_tappet()
    roller()
