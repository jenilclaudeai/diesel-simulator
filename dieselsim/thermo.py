"""
thermo.py -- working-fluid properties, fuel data and compressible flow.

The cylinder charge is treated as a two-component ideal-gas mixture:
    * fresh charge  (air + EGR-free residual)   -> "unburned"
    * combustion products (stoichiometric)      -> "burned"
mixed by the burned mass fraction yb.  Specific heats are smooth
exponential fits to JANAF data, accurate to ~2 % from 250 K to 3000 K,
with an added high-temperature term that mimics the energy absorbed by
dissociation above ~2200 K (this is what keeps single-zone peak
temperatures physical instead of running away to 3000 K+).
"""
from __future__ import annotations

import math

import math

import numpy as np

# --------------------------------------------------------------------------
# Gas constants
# --------------------------------------------------------------------------
R_AIR = 287.05          # J/kg/K
R_BURNED = 286.0        # J/kg/K, lean diesel products
R_UNIV = 8.31446        # J/mol/K

_CP_A_INF, _CP_A_AMP, _CP_A_TAU = 1310.0, 393.0, 1185.0     # air
_CP_B_INF, _CP_B_AMP, _CP_B_TAU = 1500.0, 480.0, 1100.0     # products
_T_DISS = 2200.0
_K_DISS = 0.35          # J/kg/K per K above _T_DISS


# ----------------------------------------------------------------------
# Scalar fast paths.
#
# These four functions are the hot spot of the whole simulator: a single
# operating point calls _int_cp_burned over 600 000 times.  numpy is superb
# on arrays and terrible on scalars -- np.exp() on one float costs ~0.9 us
# against ~0.06 us for math.exp, and that overhead alone was a quarter of
# the total solve time.  The try/except costs nothing when it does not
# fire, so arrays still work and still go down the numpy path.
# ----------------------------------------------------------------------
def cp_air(T):
    try:
        return _CP_A_INF - _CP_A_AMP * math.exp(-T / _CP_A_TAU)
    except TypeError:
        return _CP_A_INF - _CP_A_AMP * np.exp(-T / _CP_A_TAU)


def cp_burned(T):
    try:
        base = _CP_B_INF - _CP_B_AMP * math.exp(-T / _CP_B_TAU)
        return base + (_K_DISS * (T - _T_DISS) if T > _T_DISS else 0.0)
    except TypeError:
        base = _CP_B_INF - _CP_B_AMP * np.exp(-T / _CP_B_TAU)
        return base + _K_DISS * np.maximum(0.0, T - _T_DISS)


def gas_R(yb):
    return R_AIR + (R_BURNED - R_AIR) * yb


def cp_mix(T, yb):
    return (1.0 - yb) * cp_air(T) + yb * cp_burned(T)


def cv_mix(T, yb):
    return cp_mix(T, yb) - gas_R(yb)


def gamma_mix(T, yb):
    cp = cp_mix(T, yb)
    return cp / (cp - gas_R(yb))


def _int_cp_air(T):
    """Antiderivative of cp_air."""
    try:
        return _CP_A_INF * T + _CP_A_AMP * _CP_A_TAU * math.exp(-T / _CP_A_TAU)
    except TypeError:
        return _CP_A_INF * T + _CP_A_AMP * _CP_A_TAU * np.exp(-T / _CP_A_TAU)


def _int_cp_burned(T):
    try:
        base = _CP_B_INF * T + _CP_B_AMP * _CP_B_TAU * math.exp(-T / _CP_B_TAU)
        if T > _T_DISS:
            d = T - _T_DISS
            return base + 0.5 * _K_DISS * d * d
        return base
    except TypeError:
        base = _CP_B_INF * T + _CP_B_AMP * _CP_B_TAU * np.exp(-T / _CP_B_TAU)
        return base + 0.5 * _K_DISS * np.maximum(0.0, T - _T_DISS) ** 2


T_REF = 298.15


def u_mix(T, yb):
    """Sensible internal energy referenced to 298.15 K (J/kg)."""
    h = ((1.0 - yb) * (_int_cp_air(T) - _int_cp_air(T_REF))
         + yb * (_int_cp_burned(T) - _int_cp_burned(T_REF)))
    return h - gas_R(yb) * (T - T_REF)


def h_mix(T, yb):
    return ((1.0 - yb) * (_int_cp_air(T) - _int_cp_air(T_REF))
            + yb * (_int_cp_burned(T) - _int_cp_burned(T_REF)))


def T_from_u(u_target, yb, T_guess=800.0, tol=1e-6, itmax=30):
    """Invert u(T) by Newton iteration (used only at re-initialisation)."""
    T = float(T_guess)
    for _ in range(itmax):
        f = u_mix(T, yb) - u_target
        df = cv_mix(T, yb)
        dT = -f / df
        T += max(-400.0, min(400.0, dT))
        if abs(dT) < tol:
            break
    return max(150.0, T)


# --------------------------------------------------------------------------
# Fuel
# --------------------------------------------------------------------------
class Fuel:
    LHV = 42.7e6            # J/kg
    density15 = 832.0       # kg/m^3
    AFR_stoich = 14.5
    HC_ratio = 1.85         # H/C atom ratio
    bulk_modulus = 1.55e9   # Pa (affects rail dynamics / injector tick)
    cp_liquid = 2010.0      # J/kg/K
    hv_vap = 250e3          # J/kg latent heat of vaporisation

    @staticmethod
    def density(T, p):
        rho = Fuel.density15 * (1.0 - 7.4e-4 * (T - 288.15))
        return rho * (1.0 + p / Fuel.bulk_modulus)

    @staticmethod
    def injection_velocity(dp, T=320.0, p=1e5):
        """Bernoulli exit velocity through the nozzle hole."""
        rho = Fuel.density(T, p)
        return math.sqrt(max(0.0, 2.0 * dp / rho))


# --------------------------------------------------------------------------
# Compressible flow through a restriction
# --------------------------------------------------------------------------
def orifice_mdot(p_up, T_up, p_dn, A_eff, gamma, R):
    """
    Mass flow (kg/s) through an effective area A_eff [m^2] with the
    standard isentropic nozzle relation.  Sign convention: positive means
    flow from `up` to `dn`.  The caller must pre-order the states.
    """
    if A_eff <= 0.0 or p_up <= 0.0:
        return 0.0
    pr = p_dn / p_up
    pr_crit = (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))
    c = A_eff * p_up / math.sqrt(R * max(T_up, 60.0))
    if pr <= pr_crit:                       # choked
        return c * math.sqrt(gamma) * (2.0 / (gamma + 1.0)) ** \
            ((gamma + 1.0) / (2.0 * (gamma - 1.0)))
    pr = min(pr, 1.0)
    term = pr ** (2.0 / gamma) - pr ** ((gamma + 1.0) / gamma)
    return c * math.sqrt(max(0.0, 2.0 * gamma / (gamma - 1.0) * term))


def signed_orifice(p1, T1, yb1, p2, T2, yb2, A_eff):
    """
    Bidirectional flow between reservoir 1 and 2.
    Returns (mdot, yb_of_the_stream); mdot > 0 => 1 -> 2.
    """
    if A_eff <= 0.0:
        return 0.0, yb1
    if p1 >= p2:
        g = gamma_mix(T1, yb1)
        return orifice_mdot(p1, T1, p2, A_eff, g, gas_R(yb1)), yb1
    g = gamma_mix(T2, yb2)
    return -orifice_mdot(p2, T2, p1, A_eff, g, gas_R(yb2)), yb2


def valve_effective_area(lift, valve_dia, n_valves, cd_max):
    """
    Effective flow area of a poppet valve set.

    Low lift  -> curtain area   pi*D*L      (with the L/D-dependent Cd rise)
    High lift -> throat area    pi*D^2/4
    """
    if lift <= 0.0:
        return 0.0
    ld = lift / valve_dia
    cd = cd_max * (1.0 - math.exp(-14.0 * ld))
    a_curtain = math.pi * valve_dia * lift
    a_throat = 0.85 * math.pi * valve_dia ** 2 / 4.0
    return n_valves * cd * min(a_curtain, a_throat)


def speed_of_sound(T, yb=0.0):
    return math.sqrt(gamma_mix(T, yb) * gas_R(yb) * max(T, 60.0))


def air_density(p, T):
    return p / (R_AIR * T)


def air_viscosity(T):
    """Sutherland."""
    return 1.716e-5 * (T / 273.15) ** 1.5 * (273.15 + 110.4) / (T + 110.4)
