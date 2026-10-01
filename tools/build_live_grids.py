"""
Prebuilt converged ADR-011 grids for the real-time loop (Phase 3; owner's
decision: converge offline, ship as static files).

For each preset: the full-load fuel limit per rpm row from a CONVERGED
calibration, then every cell solved to convergence twice -- walls at the
spec's warm coolant and at 273 K -- on that shared fuel. Each cell keeps
its perf, its cylinder-1 pressure trace and its acoustic sources (the six
crank-angle waveforms and their scalars, Phase 4) -- arrays as float32
base64, the form web/physics's Adr011Grid reads. Unsettled cells are
period-averaged and flagged (FINDING-013), and counted in the file.

Output: web/app/public/grids/<preset>.json, stamped with bridge.grid_hash()
(the solver sources without the real-time loop). The app uses a file only
if that hash matches its own build; otherwise it builds a fast grid in the
browser and says so.

Each file also carries what the TypeScript loop needs to run it without
Python: the live spec and the friction model's engine view (spec with its
derived geometry, cams, oil condition, wear state).

A custom engine (ADR-014) is an engine JSON in the roster's format, plus
"vehicle" (one of live.VEHICLE_KEYS). Its grid also records the JSON and its
SHA-256, and goes to out/grids/<key>.json unless --out says otherwise; the
app's "Import grid" reads it.

Run:  python3 tools/build_live_grids.py [preset ...]      (~15 min per grid, 6 cores)
      python3 tools/build_live_grids.py --engine my.json [--out my.grid.json]
      python3 tools/build_live_grids.py --annotate        (add spec + engine view to existing files)
      --size RxL (e.g. 2x2): a smaller grid, for smoke tests only
"""
import base64
import json
import os
import sys
import time
from multiprocessing import get_context

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dieselsim.acoustics import EngineSound  # noqa: E402
from dieselsim.bridge import grid_hash  # noqa: E402
from dieselsim.builder import from_dict, load_engine_dir  # noqa: E402
from dieselsim.config import PRESETS  # noqa: E402
from dieselsim.engine import DieselEngine  # noqa: E402
from dieselsim.grid import solve_cell  # noqa: E402
from dieselsim.live import VEHICLE_KEYS  # noqa: E402
from dieselsim.livesound import SOURCE_KEYS  # noqa: E402  (the six the synth reads)

OUT = os.path.join(os.path.dirname(__file__), "..", "web", "app", "public", "grids")
# the Enjoy roster (ADR-012) is built with builder.py from engines/*.json:
# register it here, so this process and every spawned worker know its keys
ENGINES = os.path.join(os.path.dirname(__file__), "..", "engines")
load_engine_dir(ENGINES)
N_RPM, N_LOAD, T_COLD = 8, 6, 273.0


def make_engine(edef):
    """edef: a preset key, or a custom engine's JSON dict (ADR-014). Tasks
    carry it, so spawned workers can build an engine no registry knows."""
    return DieselEngine(spec=from_dict(edef)) if isinstance(edef, dict) else DieselEngine(preset=edef)


def custom_engine(path):
    """(key, engine JSON, SHA-256 of the file) for --engine, or SystemExit
    with the reason: an unknown vehicle, or numbers the builder rejects."""
    import hashlib
    with open(path, "rb") as fh:
        raw = fh.read()
    d = json.loads(raw)
    key = d.get("key") or os.path.splitext(os.path.basename(path))[0]
    if d.get("vehicle") not in VEHICLE_KEYS:
        raise SystemExit(f"{path}: \"vehicle\" must be one of {', '.join(VEHICLE_KEYS)} "
                         f"(got {d.get('vehicle')!r})")
    try:
        from_dict(d)
    except (TypeError, ValueError) as e:
        raise SystemExit(f"{path}: the builder cannot make this engine: {e}")
    return key, d, hashlib.sha256(raw).hexdigest()


def row_limit(task):
    edef, rpm = task
    eng = make_engine(edef)
    eng.converged_mode = True
    return eng.fuel_limit(float(rpm))


def b64f32(a):
    return base64.b64encode(np.asarray(a, dtype="<f4").tobytes()).decode()


def cell(task):
    edef, rpm, load, flim, T_cool = task
    spec = make_engine(edef).spec
    src, perf = solve_cell(spec, rpm, load, converged=True, fuel_limit=flim, T_coolant=T_cool)
    sound = {"f32": {k: b64f32(src[k]) for k in SOURCE_KEYS},
             "meta": {k: float(v) for k, v in src["_meta"].items()}}
    return {k: float(v) for k, v in perf.items()}, b64f32(src["p_cyl"]), sound


_GF = []


def _gen_fixtures():
    """tools/fixtures/gen_fixtures.py, loaded once: main() does it before
    the first solve, so editing the tree during a build cannot reach it."""
    if not _GF:
        import importlib.util
        here = os.path.dirname(__file__)
        spec_ = importlib.util.spec_from_file_location("gen_fixtures", os.path.join(here, "fixtures", "gen_fixtures.py"))
        gf = importlib.util.module_from_spec(spec_)
        spec_.loader.exec_module(gf)
        _GF.append(gf)
    return _GF[0]


def annotation(edef):
    """The live spec and engine view for an engine, as the TypeScript loop reads them."""
    import dataclasses
    gf = _gen_fixtures()
    eng = make_engine(edef)
    live_spec = json.loads(json.dumps(dataclasses.asdict(eng.spec), default=float))
    live_spec["geom"]["displacement"] = eng.spec.geom.displacement
    return {"spec": live_spec, "engine_view": gf.friction_engine_view(eng)}


def annotate(path):
    with open(path) as fh:
        data = json.load(fh)
    data.update(annotation(data.get("engine_json") or data["preset"]))
    with open(path, "w") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print(f"annotated {os.path.relpath(path)}")


def build(key, pool, ghash, edef=None, out_path=None, extra=None, size=(N_RPM, N_LOAD)):
    edef = edef or key
    n_rpm, n_load = size
    spec = make_engine(edef).spec
    rpms = [float(x) for x in np.linspace(spec.idle_rpm, spec.max_rpm, n_rpm)]
    loads = [float(x) for x in np.linspace(0.0, 1.0, n_load)]
    t0 = time.time()
    flims = pool.map(row_limit, [(edef, r) for r in rpms])
    grids = {}
    for tag, T in (("warm", None), ("cold", T_COLD)):
        cells = pool.map(cell, [(edef, r, l, f, T) for r, f in zip(rpms, flims) for l in loads])
        grids[tag] = [cells[i * n_load:(i + 1) * n_load] for i in range(n_rpm)]
    unsettled = sum(1 for tag in grids for row in grids[tag] for p, _, _ in row if p.get("settled", 1.0) < 0.5)
    col = lambda tag, n, k=None: [[c[n] if k is None else c[n][k] for c in row] for row in grids[tag]]  # noqa: E731
    data = {"preset": key, "name": spec.name, "grid_hash": ghash, "converged": True,
            "rpms": rpms, "loads": loads, "fuel_limits": flims,
            "T_warm": spec.thermal.coolant_T, "T_cold": T_COLD,
            "grid_deg": [float(x) for x in EngineSound(spec).grid],
            "perf": col("warm", 0), "perf_cold": col("cold", 0),
            "p_cyl_f32": col("warm", 1), "p_cyl_cold_f32": col("cold", 1),
            "src_f32": col("warm", 2, "f32"), "src_cold_f32": col("cold", 2, "f32"),
            "src_meta": col("warm", 2, "meta"), "src_meta_cold": col("cold", 2, "meta"),
            "unsettled_cells": unsettled, "build_s": round(time.time() - t0)}
    # a roster engine's grid depends on its engines/<key>.json, which the grid
    # hash (dieselsim/ only) does not cover: record the file it was built from
    ef = os.path.join(ENGINES, f"{key}.json")
    if os.path.exists(ef):
        import hashlib
        with open(ef, "rb") as fh:
            data["engine_file_sha256"] = hashlib.sha256(fh.read()).hexdigest()
    data.update(extra or {})
    data.update(annotation(edef))
    path = out_path or os.path.join(OUT, f"{key}.json")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print(f"{key}: {2 * n_rpm * n_load} converged cells in {data['build_s']} s, {unsettled} unsettled "
          f"(period-averaged), {os.path.getsize(path) / 1024:.0f} KiB -> {os.path.relpath(path)}", flush=True)


def main():
    if "--annotate" in sys.argv:
        for f in sorted(os.listdir(OUT)):
            if f.endswith(".json"):
                annotate(os.path.join(OUT, f))
        return
    args = sys.argv[1:]

    def opt(name):
        if name not in args:
            return None
        i = args.index(name)
        val = args[i + 1]
        del args[i:i + 2]
        return val
    engine_path, out_path, size = opt("--engine"), opt("--out"), opt("--size")
    size = tuple(int(x) for x in size.split("x")) if size else (N_RPM, N_LOAD)
    custom = custom_engine(engine_path) if engine_path else None
    keys = [a for a in args if not a.startswith("-")] or ([] if custom else sorted(PRESETS))
    # the hash of the tree the workers import, taken before they start
    ghash = grid_hash()
    _gen_fixtures()
    with get_context("spawn").Pool(min(6, os.cpu_count() or 1)) as pool:
        for key in keys:
            build(key, pool, ghash, size=size)
        if custom:
            key, d, sha = custom
            build(key, pool, ghash, edef=d, size=size,
                  out_path=out_path or os.path.join(os.path.dirname(__file__), "..", "out", "grids", f"{key}.json"),
                  extra={"custom": True, "vehicle": d["vehicle"], "engine_json": d, "engine_file_sha256": sha})


if __name__ == "__main__":
    main()
