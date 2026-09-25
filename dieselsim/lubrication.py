"""
lubrication.py -- oil rheology, the oil circuit, film-thickness solutions
and the mixed-lubrication (Stribeck) friction law.

Physics included
----------------
* Vogel viscosity-temperature law + Barus piezo-viscosity for concentrated
  contacts + Cross-type shear thinning of the VII polymer (HTHS).
* Ocvirk short-journal-bearing solution -> eccentricity, minimum film,
  viscous drag; squeeze-film credit under the firing impulse.
* Hydrodynamic ring / skirt film from the 1-D Reynolds equation.
* Greenwood-Tripp style asperity load sharing -> boundary friction share.
* Oil circuit: positive-displacement pump, relief valve, bearing leakage
  (clearance^3 law, so wear feeds straight back into gallery pressure).
* Ageing: thermal-oxidative (Arrhenius), soot loading, TBN depletion,
  fuel dilution, and their effect on viscosity, friction and wear rate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import Lubricant, Tribology

# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------
CP_OIL = 1950.0          # J/kg/K
BARUS_ALPHA = 1.9e-8     # 1/Pa piezo-viscosity coefficient (mineral base)
MU_BOUNDARY_BASE = 0.095  # asperity friction coefficient, fresh oil + AW
LAMBDA_0 = 1.05          # Stribeck transition
LAMBDA_K = 4.0


# --------------------------------------------------------------------------
# Oil condition state
# --------------------------------------------------------------------------
@dataclass
class OilCondition:
    hours: float = 0.0
    T_oil: float = 298.0            # K bulk sump temperature
    oxidation: float = 0.0          # 0..1 arbitrary oxidation index
    soot_pct: float = 0.0           # % w/w
    tbn: float = 10.0               # mg KOH/g
    fuel_dilution: float = 0.0      # fraction w/w
    coolant_dilution: float = 0.0
    visc_multiplier: float = 1.0    # applied to base viscosity
    additive_left: float = 1.0      # anti-wear (ZDDP) film former, 0..1

    def reset(self, oil: Lubricant):
        self.hours = 0.0
        self.oxidation = 0.0
        self.soot_pct = 0.0
        self.tbn = oil.tbn0
        self.fuel_dilution = 0.0
        self.visc_multiplier = 1.0
        self.additive_left = 1.0


class Oil:
    """Lubricant with a mutable condition state."""

    def __init__(self, spec: Lubricant):
        self.spec = spec
        self.cond = OilCondition(tbn=spec.tbn0)

    # ---- rheology --------------------------------------------------------
    def base_viscosity(self, T: float) -> float:
        """Vogel equation, atmospheric pressure, low shear [Pa.s]."""
        s = self.spec
        denom = max(T - s.vogel_c, 12.0)
        return s.vogel_a * math.exp(s.vogel_b / denom)

    def viscosity(self, T: float, p: float = 1e5,
                  shear_rate: float = 1e5) -> float:
        """
        Effective dynamic viscosity [Pa.s] including
        temperature, pressure (Barus), shear thinning and oil condition.
        """
        mu = self.base_viscosity(T) * self.cond.visc_multiplier
        if p > 2e5:
            mu *= math.exp(BARUS_ALPHA * min(p, 1.2e9))
        # Cross model: polymer VII loses ~30 % at 1e6 1/s
        if shear_rate > 1e4:
            x = (shear_rate / 3.0e6) ** 0.62
            mu *= (0.62 + 0.38 / (1.0 + x))
        # fuel dilution thins, soot/oxidation thicken
        mu *= math.exp(-4.2 * self.cond.fuel_dilution)
        return max(mu, 1.2e-3)

    def density(self, T: float) -> float:
        return self.spec.density15 * (1.0 - 6.4e-4 * (T - 288.15))

    def mass(self) -> float:
        return self.spec.sump_volume * self.density(self.cond.T_oil)

    # ---- boundary friction coefficient -----------------------------------
    def mu_boundary(self) -> float:
        c = self.cond
        mu = MU_BOUNDARY_BASE
        mu *= (1.0 + 0.55 * (1.0 - c.additive_left))     # AW film exhausted
        mu *= (1.0 + 0.09 * c.soot_pct)                  # abrasive soot
        mu *= (1.0 + 0.25 * c.oxidation)
        return min(mu, 0.22)

    # ---- wear aggressiveness ---------------------------------------------
    def wear_factor(self) -> float:
        """Multiplier on the Archard coefficient from oil condition."""
        c = self.cond
        f = 1.0
        f *= 1.0 + 1.65 * c.soot_pct ** 1.15          # abrasive 3-body wear
        f *= 1.0 + 0.9 * max(0.0, 1.0 - c.tbn / max(self.spec.tbn0, 1e-6))
        f *= 1.0 + 0.75 * c.oxidation                 # corrosive acids
        f *= 1.0 + 3.0 * c.fuel_dilution              # film collapse
        f *= 1.0 + 1.2 * (1.0 - c.additive_left)
        return f

    # ---- ageing ----------------------------------------------------------
    def age(self, dt_h: float, soot_in_rate: float, fuel_dil_rate: float,
            blowby_factor: float = 1.0):
        """
        Advance the oil condition by dt_h hours.

        soot_in_rate    : % w/w per hour entering the sump
        fuel_dil_rate   : fraction w/w per hour (negative = evaporating out)
        """
        c = self.cond
        T = c.T_oil
        # Arrhenius oxidation, ~doubles every 10 K above 100 C
        # Calibrated so a 15W-40 at ~115 C sump reaches an oxidation index
        # near 0.8 and gives up roughly two thirds of its TBN over a 500 h
        # drain -- which is what used-oil analysis on a highway truck shows.
        k_ox = 6.0e5 * math.exp(-64000.0 / (8.3145 * max(T, 300.0)))
        c.oxidation = min(3.0, c.oxidation + k_ox * dt_h * blowby_factor)
        c.soot_pct = min(12.0, c.soot_pct + soot_in_rate * dt_h)
        # TBN consumed by acids (oxidation + sulphur) and by soot dispersancy
        c.tbn = max(0.0, c.tbn - dt_h * (0.008 + 2.0 * k_ox
                                         + 0.0015 * c.soot_pct))
        c.fuel_dilution = max(0.0, min(0.12, c.fuel_dilution
                                       + fuel_dil_rate * dt_h))
        c.additive_left = max(0.0, c.additive_left
                              - dt_h * (0.0011 + 0.0015 * c.oxidation))
        # viscosity: soot + oxidation thicken, shear + dilution thin
        c.visc_multiplier = (1.0 + 0.135 * c.soot_pct ** 1.2
                             + 0.30 * c.oxidation) * (1.0 - 0.10 *
                                                      min(1.0, c.hours / 400.0))
        c.hours += dt_h

    # ---- thermal ---------------------------------------------------------
    def update_temperature(self, dt_s: float, Q_friction: float,
                           Q_piston_jets: float, T_coolant: float,
                           rpm: float):
        c = self.cond
        m = self.mass()
        UA = self.spec.cooler_UA * (0.35 + 0.65 * min(1.0, rpm / 1800.0))
        Q_out = UA * (c.T_oil - T_coolant)
        # sump shell convection to ambient-ish underhood air
        Q_amb = 0.045 * self.spec.cooler_UA * (c.T_oil - 330.0)
        dT = (Q_friction + Q_piston_jets - Q_out - Q_amb) * dt_s / (m * CP_OIL)
        c.T_oil = max(250.0, min(430.0, c.T_oil + dT))

    # ---- oil circuit -----------------------------------------------------
    def gallery_pressure(self, rpm: float, leak_factor: float = 1.0) -> float:
        """
        Pump delivery against the bearing/jet leakage network.

        Bearing leakage obeys Q ~ p * c^3, so a worn engine (leak_factor>1)
        loses gallery pressure -- which is exactly what a failing engine does.
        """
        s = self.spec
        mu = self.viscosity(self.cond.T_oil, 3e5, 1e4)
        Q_pump = s.pump_disp * (rpm / 60.0) * s.pump_eta_vol
        # network conductance (m^3/s per Pa), scales with 1/mu and c^3
        K = 1.3e-11 / mu * leak_factor
        p = Q_pump / max(K, 1e-14)
        return min(p, s.pump_relief), Q_pump

    def pump_power(self, rpm: float, p_gallery: float) -> float:
        s = self.spec
        Q = s.pump_disp * (rpm / 60.0)
        return p_gallery * Q / max(s.pump_eta_mech * s.pump_eta_vol, 0.1)


# --------------------------------------------------------------------------
# Mixed lubrication
# --------------------------------------------------------------------------
def composite_roughness(r1: float, r2: float) -> float:
    return math.sqrt(r1 * r1 + r2 * r2)


def boundary_load_share(lam: float) -> float:
    """Fraction of the normal load carried by asperity contact."""
    if lam <= 0.0:
        return 1.0
    return 1.0 / (1.0 + (lam / LAMBDA_0) ** LAMBDA_K)


def stribeck_friction(load_N: float, u_slide: float, mu_oil: float,
                      h_film: float, sigma: float, area_m2: float,
                      mu_bound: float) -> tuple:
    """
    Returns (friction_force, boundary_share, lambda_ratio).

    Hydrodynamic part is Couette shear over the film; boundary part is a
    Coulomb law on the asperity-supported load.
    """
    lam = h_film / max(sigma, 1e-9)
    fb = boundary_load_share(lam)
    F_b = mu_bound * fb * load_N
    F_h = (1.0 - fb) * mu_oil * abs(u_slide) * area_m2 / max(h_film, 1e-9)
    return F_b + F_h, fb, lam


# --------------------------------------------------------------------------
# Journal bearing -- Ocvirk short bearing
# --------------------------------------------------------------------------
def _ocvirk_load(eps: float, mu: float, omega: float, L: float, D: float,
                 c_rad: float) -> float:
    """Load capacity [N] of a short journal bearing at eccentricity eps."""
    eps = min(max(eps, 1e-4), 0.99999)
    return (mu * omega * L ** 3 * D * eps
            / (4.0 * c_rad ** 2 * (1.0 - eps ** 2) ** 2)
            * math.sqrt(math.pi ** 2 * (1.0 - eps ** 2) + 16.0 * eps ** 2))


def bearing_state(load_N: float, omega: float, mu: float, D: float, L: float,
                  c_diam: float, squeeze_credit: float = 1.0):
    """
    Solve the short-bearing equation for eccentricity.

    squeeze_credit > 1 represents the extra load capacity from squeeze-film
    action under a rapidly rotating/oscillating load (the reason a rod
    bearing survives 180 bar peak cylinder pressure).

    Returns (h_min [m], eccentricity, friction_torque [N.m], leak [m^3/s]).
    """
    c_rad = 0.5 * c_diam
    W = max(load_N, 1.0) / max(squeeze_credit, 1e-3)
    om = max(abs(omega), 1.0)
    lo, hi = 1e-4, 0.999995
    if _ocvirk_load(hi, mu, om, L, D, c_rad) < W:
        eps = hi
    else:
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if _ocvirk_load(mid, mu, om, L, D, c_rad) < W:
                lo = mid
            else:
                hi = mid
        eps = 0.5 * (lo + hi)
    h_min = c_rad * (1.0 - eps)
    R = 0.5 * D
    F_visc = 2.0 * math.pi * mu * om * R ** 2 * L / \
        (c_rad * math.sqrt(max(1.0 - eps ** 2, 1e-6)))
    torque = F_visc * R
    # side leakage (Ocvirk): Q = pi * D * c^3 * dp / (12 mu L) ~ approximated
    leak = math.pi * D * c_rad ** 3 * 3.0e5 * (1.0 + 1.5 * eps ** 2) \
        / (12.0 * mu * L)
    return h_min, eps, torque, leak


# --------------------------------------------------------------------------
# Ring / skirt hydrodynamic film
# --------------------------------------------------------------------------
def ring_film_thickness(mu: float, u: float, b: float, W_per_len: float,
                        h_supply: float = 2.2e-6,
                        h_floor: float = 12e-9) -> float:
    """
    Minimum film under a parabolic-faced ring.

    Fully-flooded 1-D Reynolds for a barrel face gives
        h_hyd = b * sqrt( K * mu * |u| / W' )        K ~ 2.4
    (note the width appears linearly outside the root -- W' is load per unit
    circumference, so the group inside the root is dimensionless-per-metre).

    A real ring is never fully flooded: it can only entrain the film the
    previous stroke left on the liner.  `h_supply` is that available film,
    and the two are blended harmonically so the ring is supply-limited at
    mid-stroke and load-limited under the firing pressure.
    """
    if W_per_len <= 0.0:
        W_per_len = 1.0
    h_hyd = b * math.sqrt(2.4 * mu * abs(u) / W_per_len)
    h = h_hyd * h_supply / (h_hyd + h_supply)
    return max(h, h_floor)


def skirt_film_thickness(mu: float, u: float, L: float, W: float,
                         B: float, c_diam: float) -> float:
    """Piston-skirt film: partial journal bearing of length L, width ~0.3*pi*B."""
    if W < 1.0:
        return 0.5 * c_diam
    b = 0.30 * math.pi * B
    # slider of length L (sliding direction), width b: h ~ sqrt(K mu u L^2 b/W)
    h = math.sqrt(2.0 * mu * abs(u) * b * L * L / max(W, 1.0))
    h *= 0.42          # skirt tilt + starvation: the land is not flooded
    return max(min(h, 0.32 * c_diam), 20e-9)


def hamrock_dowson_film(mu0: float, u_entrain: float, R_eq: float,
                        load_per_len: float, E_eq: float = 2.2e11,
                        h_floor: float = 8e-9) -> float:
    """
    Central EHL film thickness for a line contact (cam / roller follower).
    Dowson-Higginson:
        Hc = 2.65 * U^0.7 * G^0.54 * W^-0.13
    h_floor: the film at vanishing entrainment. FINDING-015: callers pass a
    floor tied to the composite roughness instead of a fixed 8 nm; below
    lambda ~ 0.1 the Stribeck boundary share is 1 to ~4 decimals anyway, so
    the floor only guards the zero-speed limit.
    """
    if u_entrain <= 1e-6 or load_per_len <= 1.0:
        return h_floor
    U = mu0 * u_entrain / (E_eq * R_eq)
    G = BARUS_ALPHA * E_eq
    W = load_per_len / (E_eq * R_eq)
    Hc = 2.65 * U ** 0.7 * G ** 0.54 * W ** -0.13
    return max(Hc * R_eq, h_floor)
