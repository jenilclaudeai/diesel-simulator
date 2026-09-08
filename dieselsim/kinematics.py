"""
kinematics.py -- exact slider-crank kinematics (with gudgeon-pin offset)
and cam / valve lift generation.

Everything is a function of crank angle theta in *radians* measured from
TDC firing.  Vectorised so a whole cycle can be pre-computed once.
"""
from __future__ import annotations

import math

import numpy as np

from .config import Geometry, ValveTrain


# --------------------------------------------------------------------------
# Slider-crank
# --------------------------------------------------------------------------
class SliderCrank:
    """
    Offset slider-crank.  x is measured from the TDC position, positive
    downwards (increasing cylinder volume).

        x(th) = a*(1-cos th) + l*(cos b0 - cos b)
        sin b = (a sin th - e)/l
    """

    def __init__(self, geom: Geometry):
        self.a = geom.crank_radius
        self.l = geom.conrod
        self.e = geom.pin_offset
        self.Ap = geom.piston_area
        self.Vc = geom.clearance_volume
        self.lam = self.a / self.l
        self._b0 = math.asin(-self.e / self.l) if self.e else 0.0
        # TDC reference length so that x(theta_tdc)=0
        self._x_tdc = self._x_raw(0.0)

    # ---- primitive -------------------------------------------------------
    def _sin_beta(self, th):
        return (self.a * np.sin(th) - self.e) / self.l

    def _x_raw(self, th):
        sb = self._sin_beta(th)
        cb = np.sqrt(np.maximum(1e-12, 1.0 - sb * sb))
        return -self.a * np.cos(th) - self.l * cb

    # ---- public ----------------------------------------------------------
    def displacement(self, th):
        """Piston distance from TDC [m]."""
        return self._x_raw(th) - self._x_tdc

    def dx_dtheta(self, th):
        sb = self._sin_beta(th)
        cb = np.sqrt(np.maximum(1e-12, 1.0 - sb * sb))
        dsb = self.a * np.cos(th) / self.l
        return self.a * np.sin(th) + self.l * sb * dsb / cb

    def d2x_dtheta2(self, th):
        sb = self._sin_beta(th)
        cb = np.sqrt(np.maximum(1e-12, 1.0 - sb * sb))
        dsb = self.a * np.cos(th) / self.l
        d2sb = -self.a * np.sin(th) / self.l
        # d/dth [ l * sb*dsb/cb ]
        t1 = self.l * (dsb * dsb + sb * d2sb) / cb
        t2 = self.l * sb * dsb * (sb * dsb) / cb ** 3
        return self.a * np.cos(th) + t1 + t2

    def volume(self, th):
        return self.Vc + self.Ap * self.displacement(th)

    def dV_dtheta(self, th):
        return self.Ap * self.dx_dtheta(th)

    def piston_velocity(self, th, omega):
        return omega * self.dx_dtheta(th)

    def piston_accel(self, th, omega, domega=0.0):
        return omega ** 2 * self.d2x_dtheta2(th) + domega * self.dx_dtheta(th)

    def beta(self, th):
        """Con-rod angle from the cylinder axis [rad]."""
        return np.arcsin(np.clip(self._sin_beta(th), -1.0, 1.0))

    def liner_wetted_area(self, th, bore):
        """Instantaneous exposed liner area (for heat transfer)."""
        return math.pi * bore * self.displacement(th)


# --------------------------------------------------------------------------
# Cam / valve lift
# --------------------------------------------------------------------------
def _core_profile(u, ramp):
    """
    Normalised lift for u in [0,1]:
      * linear opening ramp over [0, ramp]
      * linear closing ramp over [1-ramp, 1]
      * raised-cosine main event in between
    The ramps give a *finite seating velocity*, which is exactly what makes
    valvetrain clatter audible -- so they are modelled explicitly.
    """
    u = np.asarray(u, dtype=float)
    L = np.zeros_like(u)
    ramp = max(ramp, 1e-4)
    h_r = 0.5 * (1.0 - math.cos(math.pi * ramp))     # lift at end of ramp
    m = (u >= 0.0) & (u <= 1.0)
    core = np.sin(np.pi * np.clip(u, 0.0, 1.0)) ** 2     # raised cosine
    L[m] = core[m]
    # replace the extremities with the constant-velocity ramps
    r1 = m & (u < ramp)
    L[r1] = h_r * (u[r1] / ramp)
    r2 = m & (u > 1.0 - ramp)
    L[r2] = h_r * ((1.0 - u[r2]) / ramp)
    return L


class Cam:
    """Valve lift, velocity and acceleration versus crank angle."""

    def __init__(self, open_deg, close_deg, lift_max, lash, ramp=0.06,
                 lash_ramp_lift_frac=None):
        self.open_deg = open_deg % 720.0
        self.close_deg = close_deg % 720.0
        self.dur = (self.close_deg - self.open_deg) % 720.0
        if self.dur <= 0:
            self.dur += 720.0
        self.lift_max = lift_max
        self.lash = lash
        self.ramp = ramp
        # geometric lift lost to lash -> shorter effective duration
        self.h_ramp = 0.5 * (1.0 - math.cos(math.pi * ramp)) * lift_max

    def _phase(self, theta_deg):
        return ((np.asarray(theta_deg, float) - self.open_deg) % 720.0) / self.dur

    def lift(self, theta_deg):
        u = self._phase(theta_deg)
        inside = u <= 1.0
        L = _core_profile(np.where(inside, u, 0.0), self.ramp) * self.lift_max
        L = np.where(inside, L, 0.0)
        return np.maximum(0.0, L - self.lash)      # lash eats the ramp

    def cam_lift(self, theta_deg):
        """Lift at the cam (before lash) -- drives valvetrain forces."""
        u = self._phase(theta_deg)
        inside = u <= 1.0
        L = _core_profile(np.where(inside, u, 0.0), self.ramp) * self.lift_max
        return np.where(inside, L, 0.0)

    def dlift_dtheta(self, theta_deg, dth=0.05):
        return (self.cam_lift(theta_deg + dth)
                - self.cam_lift(theta_deg - dth)) / (2.0 * math.radians(dth))

    def d2lift_dtheta2(self, theta_deg, dth=0.10):
        h = math.radians(dth)
        return (self.cam_lift(theta_deg + dth) - 2.0 * self.cam_lift(theta_deg)
                + self.cam_lift(theta_deg - dth)) / h ** 2

    def seating_velocity(self, omega):
        """Valve closing velocity at seat contact [m/s] -- the tick source."""
        v_ramp = self.h_ramp / (math.radians(self.ramp * self.dur))
        return v_ramp * omega * (1.0 + 2.2 * self.lash / max(self.h_ramp, 1e-9))

    def opening_event_deg(self):
        return self.open_deg

    def closing_event_deg(self):
        return self.close_deg


def build_cams(vt: ValveTrain):
    intake = Cam(vt.ivo_deg, vt.ivc_deg, vt.intake_lift_max,
                 vt.lash_intake, vt.ramp_fraction)
    exhaust = Cam(vt.evo_deg, vt.evc_deg, vt.exhaust_lift_max,
                  vt.lash_exhaust, vt.ramp_fraction)
    return intake, exhaust


# --------------------------------------------------------------------------
# Reciprocating dynamics helpers
# --------------------------------------------------------------------------
def piston_side_force(F_axial, beta):
    """Thrust force pressing the skirt against the liner [N]."""
    return F_axial * np.tan(beta)


def crank_effective_radius(sc: SliderCrank, th):
    """dV/dtheta / Ap  == effective moment arm of the gas force."""
    return sc.dx_dtheta(th)
