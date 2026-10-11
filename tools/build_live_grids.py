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
      python3 tools/build_live_grids.py --weather [key|path ...]   (Phase 7 step 4: add the weather
            table, 390 converged solves per grid, ~35-60 min on 6 cores; WEATHER_WORKERS to change)
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


def weather_piece(task):
    ref, rpm, load, flim, p, T = task
    return json.loads(bridge.live_weather_cell(json.dumps({"engine": ref, "rpm": rpm, "load": load,
                                                           "fuel_limit": flim, "p": p, "T": T})))


def grid_engine_ref(data):
    """The bridge's form of the engine a grid file records."""
    if data.get("engine_json"):
        return {"headline": data["engine_json"]}
    if data.get("base"):
        return {"preset": data["base"], "overrides": data.get("overrides") or {}}
    return {"preset": data["preset"]}


def add_weather(path, pool, ghash):
    """Phase 7 step 4: add the weather table (shape A3) to an existing grid
    file, leaving every other byte as it was. Refused for a stale grid: the
    table's solves must come from the code that solved its cells."""
    with open(path) as fh:
        text = fh.read()
    data = json.loads(text)
    if json.dumps(data, separators=(",", ":")) + "\n" != text:
        raise SystemExit(f"{path}: doesn't round-trip through JSON byte for byte; refusing to rewrite it")
    if data.get("grid_hash") != ghash:
        raise SystemExit(f"{path}: grid stamp {str(data.get('grid_hash'))[:12]} is not this tree's {ghash[:12]}: "
                         "rebuild the grid first")
    data.pop("weather", None)
    ref = grid_engine_ref(data)
    plan = json.loads(bridge.live_weather_plan(json.dumps({"rpms": data["rpms"], "loads": data["loads"]})))
    tasks = [(ref, data["rpms"][q["i"]], data["loads"][q["j"]], data["fuel_limits"][q["i"]], q["p"], q["T"])
             for q in plan["pieces"] + plan["check"]]
    t0 = time.time()
    got = pool.map(weather_piece, tasks)
    n = len(plan["pieces"])
    table = json.loads(bridge.live_weather_assemble(json.dumps({
        "engine": ref, "grid": {k: data[k] for k in ("rpms", "loads", "perf")},
        "pieces": got[:n], "checks": got[n:]})))
    # no build_s inside the table: the browser's build writes the same keys (test:live-real)
    build_s = round(time.time() - t0)
    data["weather"] = table
    with open(path, "w") as fh:
        fh.write(json.dumps(data, separators=(",", ":")) + "\n")
    chk = table.get("check")
    print(f"{os.path.basename(path)}: weather table, {len(tasks)} converged solves in {build_s} s, "
          f"{table['unsettled']} unsettled; "
          + (f"Leh check worst {chk['worst_pct_of_full_load']:.2f}% of full-load torque" if chk
             else "no check cells in a grid this small"), flush=True)


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
    if "--weather" in args:
        # Phase 7 step 4: add weather tables to existing grid files (keys or paths)
        args.remove("--weather")
        paths = [a if a.endswith(".json") else os.path.join(OUT, f"{a}.json") for a in args] \
            or sorted(os.path.join(OUT, f) for f in os.listdir(OUT) if f.endswith(".json"))
        ghash = grid_hash()
        with get_context("spawn").Pool(min(int(os.environ.get("WEATHER_WORKERS", 6)), os.cpu_count() or 1)) as pool:
            for p in paths:
                add_weather(p, pool, ghash)
        return
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
