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

Run:  python3 tools/build_live_grids.py [preset ...]      (~9 min per grid, 6 cores)
      python3 tools/build_live_grids.py --annotate        (add spec + engine view to existing files)
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
from dieselsim.builder import load_engine_dir  # noqa: E402
from dieselsim.config import PRESETS  # noqa: E402
from dieselsim.engine import DieselEngine  # noqa: E402
from dieselsim.grid import solve_cell  # noqa: E402
from dieselsim.livesound import SOURCE_KEYS  # noqa: E402  (the six the synth reads)

OUT = os.path.join(os.path.dirname(__file__), "..", "web", "app", "public", "grids")
# the Enjoy roster (ADR-012) is built with builder.py from engines/*.json:
# register it here, so this process and every spawned worker know its keys
ENGINES = os.path.join(os.path.dirname(__file__), "..", "engines")
load_engine_dir(ENGINES)
N_RPM, N_LOAD, T_COLD = 8, 6, 273.0


def row_limit(task):
    key, rpm = task
    eng = DieselEngine(preset=key)
    eng.converged_mode = True
    return eng.fuel_limit(float(rpm))


def b64f32(a):
    return base64.b64encode(np.asarray(a, dtype="<f4").tobytes()).decode()


def cell(task):
    key, rpm, load, flim, T_cool = task
    spec = DieselEngine(preset=key).spec
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


def annotation(key):
    """The live spec and engine view for a preset, as the TypeScript loop reads them."""
    import dataclasses
    gf = _gen_fixtures()
    eng = DieselEngine(preset=key)
    live_spec = json.loads(json.dumps(dataclasses.asdict(eng.spec), default=float))
    live_spec["geom"]["displacement"] = eng.spec.geom.displacement
    return {"spec": live_spec, "engine_view": gf.friction_engine_view(eng)}


def annotate(path):
    with open(path) as fh:
        data = json.load(fh)
    data.update(annotation(data["preset"]))
    with open(path, "w") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print(f"annotated {os.path.relpath(path)}")


def build(key, pool, ghash):
    spec = DieselEngine(preset=key).spec
    rpms = [float(x) for x in np.linspace(spec.idle_rpm, spec.max_rpm, N_RPM)]
    loads = [float(x) for x in np.linspace(0.0, 1.0, N_LOAD)]
    t0 = time.time()
    flims = pool.map(row_limit, [(key, r) for r in rpms])
    grids = {}
    for tag, T in (("warm", None), ("cold", T_COLD)):
        cells = pool.map(cell, [(key, r, l, f, T) for r, f in zip(rpms, flims) for l in loads])
        grids[tag] = [cells[i * N_LOAD:(i + 1) * N_LOAD] for i in range(N_RPM)]
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
    data.update(annotation(key))
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{key}.json")
    with open(path, "w") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print(f"{key}: {2 * N_RPM * N_LOAD} converged cells in {data['build_s']} s, {unsettled} unsettled "
          f"(period-averaged), {os.path.getsize(path) / 1024:.0f} KiB -> {os.path.relpath(path)}", flush=True)


def main():
    if "--annotate" in sys.argv:
        for f in sorted(os.listdir(OUT)):
            if f.endswith(".json"):
                annotate(os.path.join(OUT, f))
        return
    keys = [a for a in sys.argv[1:] if not a.startswith("-")] or sorted(PRESETS)
    # the hash of the tree the workers import, taken before they start
    ghash = grid_hash()
    _gen_fixtures()
    with get_context("spawn").Pool(min(6, os.cpu_count() or 1)) as pool:
        for key in keys:
            build(key, pool, ghash)


if __name__ == "__main__":
    main()
