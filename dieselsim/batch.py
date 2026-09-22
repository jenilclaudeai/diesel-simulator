"""
batch.py -- solve many independent operating points at once.

WHY THIS AND NOT A GPU
----------------------
A single operating point is a sequential recurrence: the state at crank
angle k+1 depends on the state at k, for 720 degrees times n_cycles.  You
cannot parallelise inside it, and the work per step is a handful of scalar
operations -- far less than the ~5-10 us it costs to launch a GPU kernel.
Moving that loop to a GPU makes it slower, not faster.

What IS parallel is the set of operating points: a torque curve, a
performance map, a design sweep, the grid `play.py` pre-solves.  Those are
completely independent, so they scale nearly linearly with cores.

A useful side effect: every worker builds its own engine, so each point is
solved from a clean state.  The serial path carries manifold and turbo
state between calls (warm start), which makes results mildly
path-dependent -- solve the same point twice in a row and the answer moves
by a couple of per cent until it settles.  Batch results do not have that
problem, at the cost of needing more cycles per point to converge.
"""
from __future__ import annotations

import multiprocessing as mp
import os
from dataclasses import dataclass

import numpy as np

from .engine import DieselEngine
from .overrides import apply_overrides


@dataclass
class PointResult:
    rpm: float
    load: float
    fuel_mg: float = 0.0
    torque: float = 0.0
    power: float = 0.0
    bmep: float = 0.0
    bsfc: float = 0.0
    fmep: float = 0.0
    pmep: float = 0.0
    eta_mech: float = 0.0
    p_max: float = 0.0
    boost_pr: float = 0.0
    turbo_rpm: float = 0.0
    afr: float = 0.0
    egr_pct: float = 0.0
    T_exh: float = 0.0
    nox_g_kwh: float = 0.0
    soot_g_kwh: float = 0.0
    blowby_lpm: float = 0.0
    ve: float = 0.0
    imep_gross: float = 0.0
    ign_delay_deg: float = 0.0
    mfb50: float = 0.0


def _apply(spec, overrides):
    """overrides = {'turbo.turbine_area_eff': 4.0e-4, 'afr_limit': 18.0, ...}

    Delegates to dieselsim.overrides, which rejects unknown paths instead of
    silently creating new attributes (a typo used to make a sweep report
    'no effect')."""
    apply_overrides(spec, overrides)


def _solve_one(job):
    preset, rpm, load, fuel_mg, n_cycles, overrides, warm = job
    eng = DieselEngine(preset=preset)
    _apply(eng.spec, overrides)
    if warm:                       # cheap pre-solve to settle the manifolds
        eng.operating_point(rpm, load=load, fuel_mg=fuel_mg,
                            n_cycles=max(3, n_cycles // 3))
    op = eng.operating_point(rpm, load=load, fuel_mg=fuel_mg,
                             n_cycles=n_cycles)
    c = op.cycle
    return PointResult(
        rpm=rpm, load=load if load is not None else 0.0, fuel_mg=op.fuel_mg,
        torque=op.torque, power=op.power, bmep=op.bmep, bsfc=op.bsfc,
        fmep=op.fmep, pmep=op.pmep, eta_mech=op.eta_mech, p_max=op.p_max,
        boost_pr=op.boost_pr, turbo_rpm=op.turbo_rpm, afr=c.afr,
        egr_pct=op.egr_pct, T_exh=op.T_exh, nox_g_kwh=op.nox_g_kwh,
        soot_g_kwh=op.soot_g_kwh, blowby_lpm=op.blowby_lpm, ve=c.ve,
        imep_gross=c.imep_gross, ign_delay_deg=c.ign_delay_deg,
        mfb50=c.mfb50)


def solve_points(preset: str, points, n_cycles: int = 9, jobs: int = None,
                 overrides: dict = None, warm: bool = True, verbose=False):
    """
    points: iterable of (rpm, load) or (rpm, load, fuel_mg).
    Returns a list of PointResult in the same order.

    jobs=1 runs in-process, which keeps tracebacks readable while debugging.
    """
    jobs = jobs or max(1, (os.cpu_count() or 1))
    todo = []
    for p in points:
        rpm, load = float(p[0]), p[1]
        fuel = float(p[2]) if len(p) > 2 else None
        todo.append((preset, rpm, None if load is None else float(load),
                     fuel, n_cycles, overrides, warm))
    if jobs == 1:
        return [_solve_one(j) for j in todo]
    ctx = mp.get_context("spawn")      # safe on every platform
    with ctx.Pool(jobs) as pool:
        out = []
        for i, r in enumerate(pool.imap(_solve_one, todo), 1):
            out.append(r)
            if verbose:
                print(f"\r  {i}/{len(todo)} points", end="", flush=True)
    if verbose:
        print()
    return out


def full_load_curve(preset: str, rpms, n_cycles: int = 9, jobs: int = None,
                    overrides: dict = None, verbose=False):
    return solve_points(preset, [(r, 1.0) for r in rpms], n_cycles, jobs,
                        overrides, verbose=verbose)


def performance_map(preset: str, rpms, loads, n_cycles: int = 8,
                    jobs: int = None, overrides: dict = None, verbose=False):
    pts = [(r, l) for r in rpms for l in loads]
    res = solve_points(preset, pts, n_cycles, jobs, overrides, verbose=verbose)
    grid = np.empty((len(rpms), len(loads)), dtype=object)
    k = 0
    for i in range(len(rpms)):
        for j in range(len(loads)):
            grid[i, j] = res[k]
            k += 1
    return grid


def sweep(preset: str, rpm: float, load: float, param: str, values,
          n_cycles: int = 9, jobs: int = None, verbose=False):
    """
    Sweep one spec parameter at a fixed operating point, in parallel.

        sweep("ld_i4", 2000, 1.0, "turbo.turbine_area_eff",
              np.linspace(3e-4, 7e-4, 12))
    """
    jobs = jobs or max(1, (os.cpu_count() or 1))
    todo = [(preset, float(rpm), float(load), None, n_cycles,
             {param: float(v)}, True) for v in values]
    if jobs == 1:
        return list(values), [_solve_one(j) for j in todo]
    ctx = mp.get_context("spawn")
    with ctx.Pool(jobs) as pool:
        out = list(pool.imap(_solve_one, todo))
    return list(values), out
