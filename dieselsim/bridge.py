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
        spec = from_dict(engine["headline"])
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
