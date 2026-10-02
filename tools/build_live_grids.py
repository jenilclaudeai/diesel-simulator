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
import json
import os
import sys
import time
from multiprocessing import get_context


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dieselsim import bridge  # noqa: E402
from dieselsim.bridge import grid_hash  # noqa: E402
from dieselsim.builder import from_dict, load_engine_dir  # noqa: E402
from dieselsim.config import PRESETS  # noqa: E402
from dieselsim.engine import DieselEngine  # noqa: E402
from dieselsim.live import VEHICLE_KEYS  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "web", "app", "public", "grids")
# the Enjoy roster (ADR-012) is built with builder.py from engines/*.json:
# register it here, so this process and every spawned worker know its keys
ENGINES = os.path.join(os.path.dirname(__file__), "..", "engines")
load_engine_dir(ENGINES)
N_RPM, N_LOAD = bridge.LIVE_N_RPM, bridge.LIVE_N_LOAD


def make_engine(edef):
    """edef: a preset key, or a custom engine's JSON dict (ADR-014). Tasks
    carry it, so spawned workers can build an engine no registry knows."""
    return DieselEngine(spec=from_dict(edef)) if isinstance(edef, dict) else DieselEngine(preset=edef)


def engine_ref(edef):
    """The bridge's form of the same engine."""
    return {"headline": edef} if isinstance(edef, dict) else {"preset": edef}


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


# the pieces are the bridge's (ADR-014 step 3), so the browser builds the same file
def row_limit(task):
    edef, rpm = task
    return json.loads(bridge.live_row_limit(json.dumps({"engine": engine_ref(edef), "rpm": rpm})))["fuel_limit"]


def cell(task):
    edef, rpm, load, flim, cold = task
    return json.loads(bridge.live_cell(json.dumps({"engine": engine_ref(edef), "rpm": rpm, "load": load,
                                                   "fuel_limit": flim, "cold": cold})))


def annotate(path):
    with open(path) as fh:
        data = json.load(fh)
    edef = data.get("engine_json") or data["preset"]
    data.update(bridge.live_annotation(make_engine(edef).spec))
    with open(path, "w") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print(f"annotated {os.path.relpath(path)}")


def build(key, pool, ghash, edef=None, out_path=None, extra=None, size=(N_RPM, N_LOAD)):
    edef = edef or key
    n_rpm, n_load = size
    plan = json.loads(bridge.live_grid_plan(json.dumps({"engine": engine_ref(edef), "n_rpm": n_rpm, "n_load": n_load})))
    rpms, loads = plan["rpms"], plan["loads"]
    t0 = time.time()
    flims = pool.map(row_limit, [(edef, r) for r in rpms])
    grids = {}
    for tag, cold in (("warm", False), ("cold", True)):
        cells = pool.map(cell, [(edef, r, l, f, cold) for r, f in zip(rpms, flims) for l in loads])
        grids[tag] = [cells[i * n_load:(i + 1) * n_load] for i in range(n_rpm)]
    # a roster engine's grid depends on its engines/<key>.json, which the grid
    # hash (dieselsim/ only) does not cover: record the file it was built from
    ext = {}
    ef = os.path.join(ENGINES, f"{key}.json")
    if os.path.exists(ef):
        import hashlib
        with open(ef, "rb") as fh:
            ext["engine_file_sha256"] = hashlib.sha256(fh.read()).hexdigest()
    ext.update(extra or {})
    text = bridge.live_grid_assemble(json.dumps({
        "engine": engine_ref(edef), "key": key, "rpms": rpms, "loads": loads, "fuel_limits": flims,
        "warm": grids["warm"], "cold": grids["cold"], "build_s": round(time.time() - t0),
        "grid_hash": ghash, "extra": ext}))
    path = out_path or os.path.join(OUT, f"{key}.json")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text + "\n")
    data = json.loads(text)
    print(f"{key}: {2 * n_rpm * n_load} converged cells in {data['build_s']} s, {data['unsettled_cells']} unsettled "
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
