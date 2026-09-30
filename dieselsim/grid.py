"""
One cell of the real-time (rpm x load) grid.

This is the single implementation shared by native Python (play.py) and the
browser (Pyodide, via the SolverPort worker). Keeping it in the package, not in
play.py, is what makes "a grid built in the browser matches one built natively"
checkable at all -- there is only one piece of code to agree with.

Deliberately free of scipy, termios and multiprocessing, so it runs under a
numpy-only Pyodide.
"""
import numpy as np

from .acoustics import EngineSound
from .engine import DieselEngine

# FINDING-011: the grid was solved at n_cycles=6 on one engine iterated
# sequentially -- worst -10.06% against a fresh-engine n_cycles=9 reference,
# errors changing sign across the map.
GRID_CYCLES = 9

# crank-angle sources the runtime needs, kept as float32
# p_cyl: cylinder 1's pressure [Pa] on the same crank grid as the sound
# sources. ADR-011: friction is evaluated live from it, with the running oil
# and coolant state (see cell_friction), instead of being baked into the cell.
SOURCE_KEYS = ("exh_flow", "int_flow", "dpdth", "inj", "valve", "slap", "p_cyl")


# Averaging window for a converged cell whose tail has not settled in
# CONVERGED_CYCLES. FINDING-013, measured over 120 map points at 200 cycles:
# 115 settle (last cycle within 0.22% of the cycle-400 value); 5 do not, all
# crdi_1p5 part load. Four are damped ringing that settles later; one,
# crdi_1p5 1450 rpm / 0.5, never settles -- a 21-cycle limit cycle, the VGT
# and EGR integral controllers fighting through the exhaust-to-intake
# pressure difference. Averaging over whole periods puts all five within
# 0.20% of the long-run value (last cycle alone: up to -5.6%).
OSC_WINDOW = 120
OSC_MIN_R = 0.3          # autocorrelation below this: no clear period


def oscillation_period(x, max_lag=60, min_r=OSC_MIN_R):
    """Dominant period of a per-cycle series, by autocorrelation; 0 if none
    is clear. Used to average an unsettled cell over whole periods.

    A period counts only if the autocorrelation first goes negative (a real
    oscillation has a trough half a period out) and then peaks above min_r.
    A settling or drifting series decays without going negative, so it gets
    no period instead of a spurious short one."""
    x = np.asarray(x, dtype=float)
    if float(x.max() - x.min()) <= 1e-12 * max(float(np.abs(x).max()), 1e-300):
        return 0                                          # constant
    # remove a linear trend first, so an oscillation riding on a slow drift
    # still shows its trough
    t = np.arange(len(x), dtype=float)
    d = x - np.polyval(np.polyfit(t, x, 1), t)
    den = float(d @ d)
    lags = range(1, min(max_lag, len(x) // 2) + 1)
    r = [float(d[k:] @ d[:-k]) / den for k in lags]
    try:
        first_neg = next(i for i, v in enumerate(r) if v < 0.0)
    except StopIteration:
        return 0
    best_i = max(range(first_neg, len(r)), key=lambda i: r[i], default=None)
    if best_i is None or r[best_i] < min_r:
        return 0
    return best_i + 1


def settle_or_average(op, spec):
    """Performance for a converged-mode solve. If its tail settled, the last
    cycle is the answer. If not -- still ringing, or a limit cycle with no
    steady state at all -- average torque (through IMEP) and boost over whole
    oscillation periods and say so. Returns (overrides for perf, flags)."""
    means = op.cycle.cycle_means
    if op.cycle.converged:
        return {}, dict(settled=1.0, osc_period=0.0, osc_spread=0.0)
    tail = means[-OSC_WINDOW:]
    imep = [m["imep_net"] for m in tail]
    period = oscillation_period(imep)
    n = (len(tail) // period) * period if period else len(tail)
    win = tail[-n:]
    imep_avg = sum(m["imep_net"] for m in win) / n
    # brake torque is linear in IMEP at fixed friction: T = IMEP * Vd / (4 pi)
    torque = op.torque + (imep_avg - means[-1]["imep_net"]) * \
        spec.geom.displacement / (4.0 * np.pi)
    power = torque * 2.0 * np.pi * op.rpm / 60.0
    work = [m["work"] for m in win]
    over = dict(torque=torque, power=power,
                boost=sum(m["boost"] for m in win) / n,
                bsfc=op.bsfc * op.power / power if power > 0 and op.power > 0 else op.bsfc)
    flags = dict(settled=0.0, osc_period=float(period),
                 osc_spread=100.0 * (max(work) - min(work)) / max(abs(np.mean(work)), 1e-9))
    return over, flags


def cell_friction(eng, rpm, p_cyl, grid_deg, fuel_mg, p_rail):
    """
    ADR-011: friction for a grid cell at the engine's LIVE oil and coolant
    state, from the cell's stored cylinder-pressure trace.

    Exact with respect to oil state -- oil temperature never touches the
    pressure trace (REVIEW-002 / ADR-011 addendum: 0.000% in 9 of 9 cases).
    `eng` carries the live state: eng.oil (temperature, condition), eng.wear,
    and the coolant via eng.T_coolant / _apply_thermal_state(). Returns the
    friction model's result dict (fmep, P_friction, ...). This is the native
    reference the TypeScript port of the friction model is tested against.
    """
    return eng.friction.evaluate(np.asarray(grid_deg, dtype=float),
                                 np.asarray(p_cyl, dtype=float), float(rpm),
                                 eng.oil, eng.wear, fuel_mg=float(fuel_mg),
                                 p_rail=float(p_rail))


def solve_cell(spec, rpm, load, n_cycles=GRID_CYCLES, fs=44100,
               converged=False, fuel_limit=None, T_coolant=None):
    """
    Solve one grid cell on a FRESH engine and return (sources, perf).

    Fresh per cell: it matches exactly how the regression suite's golden
    values are made. (When this was written nothing else isolated a solve --
    warm_start=False reset only the gas state, 3.89% off after high-rpm
    history. Bug #5 is fixed since: a cold solve now resets the turbo and
    starts the limiter's calibration cold, bit-identical to a fresh engine.)

    `spec` is an EngineSpec object, not a preset name, so rating overrides
    travel with it and nothing depends on a preset registry.

    converged: solve at real time until settled (DieselEngine.converged_mode,
    FINDING-013) -- for offline builds, not the browser. The fast default is
    unconverged wherever the VGT or EGR loop is active. A converged cell adds
    settled (1/0), osc_period and osc_spread (% of work) to perf. Where the
    last cycles have not settled, torque, power, boost and bsfc are averaged
    over whole oscillation periods and the crank-angle sources are one phase
    of the oscillation.
    fuel_limit: the calibrated full-load fuel at this rpm, if the builder has
    already found it (shared across a row, see seed_fuel_limit).
    T_coolant: solve with the walls at this coolant temperature (ADR-011's
    cold grid); None keeps the spec's own (warm) walls.
    """
    eng = DieselEngine(spec=spec)
    if T_coolant is not None:
        eng.T_coolant = float(T_coolant)
        eng._apply_thermal_state()
    eng.converged_mode = bool(converged)
    if fuel_limit is not None:
        eng.seed_fuel_limit(float(rpm), fuel_limit)
    op = eng.operating_point(float(rpm), load=float(load), n_cycles=n_cycles)
    snd = EngineSound(eng.spec, fs=fs)
    snd.wear = eng.wear
    snd.T_coolant = eng.T_coolant
    sd = snd.build_sources(op)
    tr = op.cycle.traces
    sd["p_cyl"] = np.interp(snd.grid, tr.theta, tr.p[0], period=720.0)
    src = {k: np.asarray(sd[k], dtype=np.float32) for k in SOURCE_KEYS}
    src["_meta"] = sd["_meta"]
    perf = dict(
        torque=op.torque, power=op.power, fuel_mg=op.fuel_mg,
        boost=op.boost_pr, turbo_rpm=op.turbo_rpm,
        afr=op.cycle.afr, soot=op.soot_g_h, nox=op.nox_g_kwh,
        egr=op.egr_pct, T_exh=op.T_exh, p_max=op.p_max,
        bsfc=op.bsfc, fmep=op.fmep, dpdt=op.cycle.dpdtheta_max,
        fuel_kg_h=op.fuel_kg_h,
        p_rail=op.cycle.rail_pressure,       # ADR-011: cell_friction needs it
        # q_wall_frac is heat-to-wall divided by fuel energy, so at zero
        # fuelling it is 0/0 and the solver's 1e-9 floor turns it into a huge
        # number. Clamp it or the coolant node gets a nonsense heat input at
        # low load.
        q_wall=float(np.clip(op.cycle.q_wall_frac, 0.05, 0.45)))
    if converged:
        over, flags = settle_or_average(op, eng.spec)
        perf.update(over)
        perf.update(flags)
    return src, perf
