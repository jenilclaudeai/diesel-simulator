"""
Python side of the browser SolverPort contract.

Every entry point takes a JSON string and returns JSON (plus raw float32 bytes
for crank-angle sources), so the TypeScript side never walks Python objects
element by element and the contract is language-neutral and testable natively.

Must stay importable under a numpy-only Pyodide: no scipy, termios or
multiprocessing, directly or through its imports. tests/test_physics.py
enforces the scipy part for every module in the package.

An engine is described by

    {"preset": "crdi15"}                                    a registered preset
    {"headline": {...build_engine kwargs...}}               built from headline numbers
    {"preset": "crdi15", "overrides": {"afr_limit": 18.0}}  either, plus overrides

Overrides use the dotted-path convention batch.py already used, validated by
dieselsim.overrides: an unknown path, a type mismatch or a non-finite value is
an error, never silently ignored.
"""
import copy
import hashlib
import json
import math
import os
import sys

import numpy as np

from .config import PRESETS
from .engine import DieselEngine
from .grid import GRID_CYCLES, SOURCE_KEYS, solve_cell
from .overrides import OverrideError, apply_overrides

CONTRACT_VERSION = 1


class RequestError(ValueError):
    """The request was malformed. Maps to SolverError kind 'invalid-request'."""


def _resolve_spec(engine):
    if not isinstance(engine, dict):
        raise RequestError("'engine' must be an object")
    if "preset" in engine and "headline" in engine:
        raise RequestError("give 'preset' or 'headline', not both")
    if "preset" in engine:
        key = engine["preset"]
        if key not in PRESETS:
            raise RequestError(f"unknown preset '{key}'; known: "
                               f"{', '.join(sorted(PRESETS))}")
        spec = PRESETS[key]()
    elif "headline" in engine:
        from .builder import from_dict           # lazy: only when needed
        h = engine["headline"]
        if not isinstance(h, dict):
            raise RequestError("'headline' must be an object of build_engine's parameters")
        try:
            spec = from_dict(h)
        except (TypeError, ValueError, KeyError, ZeroDivisionError) as e:
            # a misspelt key, a string where a number belongs, a missing number:
            # the request's fault, said as such (ADR-014's form shows it)
            raise RequestError(f"the builder cannot make this engine: {e}") from None
    else:
        raise RequestError("'engine' needs 'preset' or 'headline'")
    # never mutate anything a later request could see
    spec = copy.deepcopy(spec)
    try:
        apply_overrides(spec, engine.get("overrides"))
    except OverrideError as e:
        raise RequestError(str(e)) from None
    return spec


def _num(req, key, lo=None, hi=None, default=None):
    v = req.get(key, default)
    if isinstance(v, bool) or not isinstance(v, (int, float)) \
            or not math.isfinite(v):
        raise RequestError(f"'{key}' must be a finite number, got {v!r}")
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise RequestError(f"'{key}' = {v} is outside [{lo}, {hi}]")
    return float(v)


def _finite(d, what):
    bad = [k for k, v in d.items()
           if isinstance(v, float) and not math.isfinite(v)]
    if bad:
        # the solver produced NaN/inf: say so here, at the boundary, instead of
        # handing the UI a number that will poison a chart three frames later
        raise ArithmeticError(f"{what}: non-finite result for {', '.join(bad)}")
    return d


def _finite_deep(d, what):
    """_finite for nested results (solve_cycle's summary and traces): a NaN
    deep in an array would otherwise reach json.dumps, which writes NaN, and
    the browser's JSON.parse rejects it."""
    bad = []

    def walk(v, path):
        if isinstance(v, float) and not math.isfinite(v):
            bad.append(path)
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{path}.{k}" if path else k)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                if len(bad) < 5:
                    walk(x, f"{path}[{i}]")
    walk(d, "")
    if bad:
        raise ArithmeticError(f"{what}: non-finite result at {', '.join(bad[:5])}")
    return d


def source_hash():
    """
    SHA-256 over the package's own .py files -- the identity of the physics
    that is actually loaded. Grid caches are keyed on it, so any change to the
    solver invalidates every cached grid instead of serving stale physics.

    Algorithm, which web/solver's tests reproduce from disk: for each .py file
    in sorted name order, feed  name + NUL + raw bytes + NUL.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha256()
    for name in sorted(f for f in os.listdir(here) if f.endswith(".py")):
        with open(os.path.join(here, name), "rb") as fh:
            h.update(name.encode() + b"\0" + fh.read() + b"\0")
    return h.hexdigest()


# The real-time loop and its streaming synth consume grids and do not shape
# them, so a change to either must not make every prebuilt grid stale (Phase
# 3, prebuilt converged grids; FINDING-021's synth first shipped without
# this, staling all five). This file is the browser's entry point: it calls
# the solver and never shapes a cell (no cell solve imports it, checked by
# the suite), and prebuilt grids come from tools/build_live_grids.py; it was
# added for ADR-014, whose entry points would otherwise stale every grid on
# each edit. Everything else in the package can change a cell.
GRID_HASH_EXCLUDES = ("live.py", "livesound.py", "bridge.py")


def grid_hash():
    """
    SHA-256 over the package files that can change a grid cell: the same
    algorithm as source_hash(), without GRID_HASH_EXCLUDES. Prebuilt grids
    carry it; the app uses one only if it matches its own build.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha256()
    for name in sorted(f for f in os.listdir(here) if f.endswith(".py") and f not in GRID_HASH_EXCLUDES):
        with open(os.path.join(here, name), "rb") as fh:
            h.update(name.encode() + b"\0" + fh.read() + b"\0")
    return h.hexdigest()


def _preset_info(key):
    s = PRESETS[key]()
    return {"name": s.name, "idle_rpm": float(s.idle_rpm),
            "rated_rpm": float(s.rated_rpm), "max_rpm": float(s.max_rpm),
            "displacement_l": float(s.geom.displacement * 1000.0),
            "n_cyl": int(s.geom.n_cyl)}


def runtime_info(_req_json="{}"):
    return json.dumps({
        "source_hash": source_hash(),
        "contract": CONTRACT_VERSION,
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "presets": sorted(PRESETS),
        # what a UI needs to label an engine and choose an rpm range, without
        # a solve: built-in presets construct instantly
        "preset_info": {k: _preset_info(k) for k in sorted(PRESETS)},
        "grid_cycles": GRID_CYCLES,
        "source_keys": list(SOURCE_KEYS),
    })


def describe_engine(req_json):
    """What a UI needs to label an engine and choose its rpm range, without a
    solve -- for a custom engine (ADR-014) the builder's derived idle and max
    rpm, and the brochure numbers it was asked for (achieved vs requested)."""
    req = json.loads(req_json)
    engine = req.get("engine")
    spec = _resolve_spec(engine)
    out = {"name": spec.name, "idle_rpm": float(spec.idle_rpm),
           "rated_rpm": float(spec.rated_rpm), "max_rpm": float(spec.max_rpm),
           "displacement_l": float(spec.geom.displacement * 1000.0),
           "n_cyl": int(spec.geom.n_cyl)}
    h = engine.get("headline") if isinstance(engine, dict) else None
    if h:
        plateau = h.get("plateau")
        out["requested"] = {"peak_torque": float(h["peak_torque"]), "peak_power_kw": float(h["peak_power"]),
                            "plateau": [float(x) for x in plateau] if plateau else None}
    return json.dumps(out)


def solve_point(req_json):
    req = json.loads(req_json)
    spec = _resolve_spec(req.get("engine"))
    rpm = _num(req, "rpm", lo=300.0, hi=10000.0)
    load = _num(req, "load", lo=0.0, hi=1.0)
    n_cycles = int(_num(req, "n_cycles", lo=3, hi=40, default=9))
    op = DieselEngine(spec=spec).operating_point(rpm, load=load,
                                                 n_cycles=n_cycles)
    return json.dumps(_finite({
        "rpm": op.rpm, "load": load, "fuel_mg": op.fuel_mg,
        "torque": op.torque, "power": op.power, "bmep": op.bmep,
        "bsfc": op.bsfc, "fmep": op.fmep, "eta_mech": op.eta_mech,
        "p_max": op.p_max, "boost_pr": op.boost_pr,
        "turbo_rpm": op.turbo_rpm, "afr": op.cycle.afr,
        "T_exh": op.T_exh, "nox_g_kwh": op.nox_g_kwh,
        "soot_g_kwh": op.soot_g_kwh, "fuel_kg_h": op.fuel_kg_h,
        "h_ring_mid": op.h_ring_mid,
    }, "solve_point"))


def solve_cycle(req_json):
    """One operating point's crank-angle traces, for the cycle page (Phase 6,
    ADR-015): cylinder 1's pressure, motored pressure, temperature, heat
    release and volume, the valve lifts, and the manifold pressures.

    FINDING-008: cylinder 1's arrays are in its own crank angle (0 = its
    firing TDC, 0..720); the manifolds are in engine angle. The two coincide
    for cylinder 1 only, when its phase is 0 (it leads every firing order);
    the phase is returned so the page can say so rather than assume it.
    """
    req = json.loads(req_json)
    spec = _resolve_spec(req.get("engine"))
    rpm = _num(req, "rpm", lo=300.0, hi=10000.0)
    load = _num(req, "load", lo=0.0, hi=1.0)
    n_cycles = int(_num(req, "n_cycles", lo=9, hi=40, default=9))   # >= 9: at 6 the drift is 10.8%
    op = DieselEngine(spec=spec).operating_point(rpm, load=load, n_cycles=n_cycles)
    c, tr, vt = op.cycle, op.cycle.traces, spec.valves
    arr = lambda a: [float(x) for x in np.asarray(a, dtype=float)]  # noqa: E731
    return json.dumps(_finite_deep({
        "rpm": op.rpm, "load": load, "n_cyl": spec.geom.n_cyl, "cylinder": 1,
        "cylinder_phase_deg": float(spec.geom.phase_deg(0)),
        "summary": {
            "torque": op.torque, "power": op.power, "bmep": op.bmep, "bsfc": op.bsfc,
            "imep_gross": c.imep_gross, "imep_net": c.imep_net, "pmep": c.pmep,
            "p_max": c.p_max, "theta_pmax": c.theta_pmax, "dpdtheta_comb": c.dpdtheta_comb,
            "T_max": c.T_max, "mfb50": c.mfb50, "ign_delay_deg": c.ign_delay_deg,
            "ign_delay_ms": c.ign_delay_ms, "premix_fraction": c.premix_fraction,
            "burn_duration_deg": c.burn_duration_deg, "inj_duration_deg": c.inj_duration_deg,
            "rail_pressure": c.rail_pressure, "afr": c.afr, "boost_pr": c.boost_pr,
            "egr_fraction": c.egr_fraction, "fuel_mg": op.fuel_mg,
        },
        "events": {
            "ivo": vt.ivo_deg, "ivc": vt.ivc_deg, "evo": vt.evo_deg, "evc": vt.evc_deg,
            "soi_main": tr.soi_deg, "soi_pilot": tr.pilot_soi_deg,
            "soc_main": tr.soc_main_deg, "soc_pilot": tr.soc_pilot_deg,
            "inj_dur_main": tr.inj_dur_main_deg,
        },
        "theta": arr(tr.theta), "V": arr(tr.V),
        "p": arr(tr.p[0]), "p_motored": arr(tr.p_motored[0]), "T": arr(tr.T[0]), "hrr": arr(tr.hrr[0]),
        "lift_int": arr(tr.valve_lift_int), "lift_exh": arr(tr.valve_lift_exh),
        "p_int_manifold": arr(tr.p_int_manifold), "p_exh_manifold": arr(tr.p_exh_manifold),
    }, "solve_cycle"))


def solve_grid_cell(req_json):
    """Returns (json_str, {source_key: float32 little-endian bytes})."""
    req = json.loads(req_json)
    spec = _resolve_spec(req.get("engine"))
    rpm = _num(req, "rpm", lo=300.0, hi=10000.0)
    load = _num(req, "load", lo=0.0, hi=1.0)
    n_cycles = int(_num(req, "n_cycles", lo=3, hi=40, default=GRID_CYCLES))
    src, perf = solve_cell(spec, rpm, load, n_cycles=n_cycles)
    meta = {k: float(v) for k, v in src["_meta"].items()}
    out = json.dumps({"perf": _finite(dict(perf), "perf"),
                      "meta": _finite(meta, "meta"),
                      "n": int(src[SOURCE_KEYS[0]].size)})
    arrays = {k: np.ascontiguousarray(src[k], dtype="<f4").tobytes()
              for k in SOURCE_KEYS}
    return out, arrays


# ==========================================================================
# ADR-014 step 3: a drivable grid -- converged, warm and cold -- piece by
# piece, so a pool of browser workers can build one. tools/build_live_grids.py
# builds with these same functions: a grid made in the browser and one made
# natively are the same file.
# ==========================================================================
LIVE_N_RPM, LIVE_N_LOAD, LIVE_T_COLD = 8, 6, 273.0


def friction_engine_view(eng):
    """Everything FrictionModel.evaluate reads, as plain data: the spec (with
    its derived geometry and the wall temperatures the engine's coolant has
    set), the oil condition, the wear state and both cams. The TypeScript
    port takes exactly this. (Moved here from tools/fixtures/gen_fixtures.py,
    which now imports it: the browser cannot import tools/.)"""
    import dataclasses
    spec = eng.spec
    d = json.loads(json.dumps(dataclasses.asdict(spec), default=float))
    g = spec.geom
    d["geom"].update(crank_radius=g.crank_radius, piston_area=g.piston_area, displacement=g.displacement,
                     clearance_volume=g.clearance_volume,
                     phase_deg=[g.phase_deg(i) for i in range(g.n_cyl)])
    cams = {}
    for name, cam in (("intake", eng.cycle.cam_int), ("exhaust", eng.cycle.cam_exh)):
        cams[name] = dict(open_deg=cam.open_deg, close_deg=cam.close_deg, lift_max=cam.lift_max,
                          lash=cam.lash, ramp=cam.ramp, ramp_height=cam.ramp_height)
    return {"spec": d, "cams": cams,
            "oil": {k: float(v) for k, v in dataclasses.asdict(eng.oil.cond).items()},
            "wear": {k: float(v) for k, v in dataclasses.asdict(eng.wear.state).items()}}


def live_annotation(spec):
    """The live spec and engine view, as the TypeScript loop reads them."""
    import dataclasses
    eng = DieselEngine(spec=copy.deepcopy(spec))
    live_spec = json.loads(json.dumps(dataclasses.asdict(eng.spec), default=float))
    live_spec["geom"]["displacement"] = eng.spec.geom.displacement
    return {"spec": live_spec, "engine_view": friction_engine_view(eng)}


def _b64f32(a):
    import base64
    return base64.b64encode(np.asarray(a, dtype="<f4").tobytes()).decode()


def live_grid_plan(req_json):
    """The axes of an engine's drivable grid: its rpm rows (idle to max) and
    loads, and the two coolant temperatures."""
    req = json.loads(req_json)
    spec = _resolve_spec(req.get("engine"))
    n_rpm = int(_num(req, "n_rpm", lo=2, hi=16, default=LIVE_N_RPM))
    n_load = int(_num(req, "n_load", lo=2, hi=12, default=LIVE_N_LOAD))
    return json.dumps({"name": spec.name,
                       "rpms": [float(x) for x in np.linspace(spec.idle_rpm, spec.max_rpm, n_rpm)],
                       "loads": [float(x) for x in np.linspace(0.0, 1.0, n_load)],
                       "T_warm": float(spec.thermal.coolant_T), "T_cold": LIVE_T_COLD})


def live_row_limit(req_json):
    """One rpm row's full-load fuel, from a CONVERGED calibration (every cell
    of the row, warm and cold, solves on it)."""
    req = json.loads(req_json)
    eng = DieselEngine(spec=_resolve_spec(req.get("engine")))
    eng.converged_mode = True
    return json.dumps({"fuel_limit": float(eng.fuel_limit(_num(req, "rpm", lo=300.0, hi=10000.0)))})


def live_cell(req_json):
    """One converged cell on its row's fuel, warm or cold (walls at 273 K):
    its perf, its cylinder-1 pressure trace and its six sound sources, arrays
    as float32 base64 -- what the grid file stores."""
    from .livesound import SOURCE_KEYS as SOUND_KEYS
    req = json.loads(req_json)
    spec = _resolve_spec(req.get("engine"))
    src, perf = solve_cell(spec, _num(req, "rpm", lo=300.0, hi=10000.0), _num(req, "load", lo=0.0, hi=1.0),
                           converged=True, fuel_limit=float(_num(req, "fuel_limit", lo=0.0)),
                           T_coolant=LIVE_T_COLD if req.get("cold") else None)
    return json.dumps({"perf": {k: float(v) for k, v in perf.items()}, "p_cyl_f32": _b64f32(src["p_cyl"]),
                       "src_f32": {k: _b64f32(src[k]) for k in SOUND_KEYS},
                       "meta": {k: float(v) for k, v in src["_meta"].items()}})


def live_grid_assemble(req_json):
    """The grid file, from its plan, row limits and cells (each as live_cell
    returned it, row by row): the format tools/build_live_grids.py writes and
    the app's Adr011Grid reads, key for key."""
    req = json.loads(req_json)
    spec = _resolve_spec(req.get("engine"))
    rpms, loads = req["rpms"], req["loads"]
    grids = {"warm": req["warm"], "cold": req["cold"]}
    for tag, g in grids.items():
        if len(g) != len(rpms) or any(len(row) != len(loads) for row in g):
            raise RequestError(f"the {tag} cells do not match the {len(rpms)} x {len(loads)} plan")
    unsettled = sum(1 for g in grids.values() for row in g for c in row if c["perf"].get("settled", 1.0) < 0.5)
    col = lambda tag, k: [[c[k] for c in row] for row in grids[tag]]  # noqa: E731
    from .acoustics import EngineSound
    # the native tool passes the hash it took before its workers started
    data = {"preset": req["key"], "name": spec.name, "grid_hash": req.get("grid_hash") or grid_hash(), "converged": True,
            "rpms": rpms, "loads": loads, "fuel_limits": req["fuel_limits"],
            "T_warm": spec.thermal.coolant_T, "T_cold": LIVE_T_COLD,
            "grid_deg": [float(x) for x in EngineSound(spec).grid],
            "perf": col("warm", "perf"), "perf_cold": col("cold", "perf"),
            "p_cyl_f32": col("warm", "p_cyl_f32"), "p_cyl_cold_f32": col("cold", "p_cyl_f32"),
            "src_f32": col("warm", "src_f32"), "src_cold_f32": col("cold", "src_f32"),
            "src_meta": col("warm", "meta"), "src_meta_cold": col("cold", "meta"),
            "unsettled_cells": unsettled, "build_s": int(req.get("build_s", 0))}
    data.update(req.get("extra") or {})
    data.update(live_annotation(spec))
    return json.dumps(data, separators=(",", ":"))
