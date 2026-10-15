"""
Re-solve only the prebuilt grids' COLD cells, after a hashed change that can
reach the cold cells' friction and nothing else -- with the proof asserted.
Written for FINDING-030 (2026-10-15): the fix moved the cold cells' friction
and left every warm cell, the weather table (warm solves) and the cold
cells' gas side as they were. A full rebuild is about 9.7 h on this Mac;
this is the cold half of the cells, about 80 min.

What it asserts, and refuses otherwise:
1. the package, with the pre-change copies of the changed files put back,
   hashes to exactly the hash every grid carries (as restamp_grids.py);
2. each re-solved cold cell differs from the file's only in the fields
   friction reaches (FRICTION_PERF, FRICTION_META): its pressure trace, its
   six source waveforms, its settled flag and every other number are
   identical, bit for bit;
3. every other key of the file -- warm cells, weather table, axes, fuel
   limits, spec -- is untouched, and only the hash string is re-stamped;
4. the Dyno's accuracy table (warm, at the rating) is re-stamped as by
   restamp_grids.py: its hash appears exactly once.

The caller's part: show that the change cannot reach a warm solve (a warm
cell re-solved with the new code equals the file's; the weather pieces call
solve_cell without T_coolant), and run test_live_grid_pieces_match_the_shipped_grid
and test_weather_pieces_match_the_grid afterwards.

Usage, from the repo root:
    mkdir /tmp/pre && git show HEAD~1:dieselsim/engine.py > /tmp/pre/engine.py
    python3 tools/rebuild_cold_cells.py /tmp/pre [key ...]    # --dry-run: solve and check, write nothing
"""
import glob
import hashlib
import json
import os
import sys
import time
from multiprocessing import get_context

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)
from dieselsim import bridge  # noqa: E402
from dieselsim.builder import load_engine_dir  # noqa: E402

load_engine_dir(os.path.join(REPO, "engines"))   # spawned workers re-run this on import
GRIDS = os.path.join(REPO, "web", "app", "public", "grids")
ACCURACY = os.path.join(REPO, "web", "app", "src", "app", "dyno", "accuracy.ts")
# the fields a cold cell's friction reaches: brake torque and what is per brake
# power (bsfc, NOx g/kWh), the FMEP, and the sound's boundary-friction power and
# load (measured on crdi15, FINDING-030: nothing else moved)
FRICTION_PERF = {"torque", "power", "bsfc", "fmep", "nox"}
FRICTION_META = {"Pb", "load"}
WORKERS = int(os.environ.get("COLD_WORKERS", "6"))


def engine_ref(data):
    """The bridge's form of the engine a grid file records (build_live_grids.grid_engine_ref)."""
    if data.get("engine_json"):
        return {"headline": data["engine_json"]}
    if data.get("base"):
        return {"preset": data["base"], "overrides": data.get("overrides") or {}}
    return {"preset": data["preset"]}


def cold_cell(task):
    ref, i, j, rpm, load, flim = task
    c = json.loads(bridge.live_cell(json.dumps({"engine": ref, "rpm": rpm, "load": load,
                                                "fuel_limit": flim, "cold": True})))
    return i, j, c


def pre_change_hash(pre):
    pkg = os.path.join(REPO, "dieselsim")
    h = hashlib.sha256()
    for n in sorted(f for f in os.listdir(pkg) if f.endswith(".py") and f not in bridge.GRID_HASH_EXCLUDES):
        path = os.path.join(pre, n) if os.path.exists(os.path.join(pre, n)) else os.path.join(pkg, n)
        with open(path, "rb") as fh:
            h.update(n.encode() + b"\0" + fh.read() + b"\0")
    return h.hexdigest()


def rebuild(path, pool, old_hash, new_hash, dry):
    with open(path) as fh:
        text = fh.read()
    data = json.loads(text)
    if json.dumps(data, separators=(",", ":")) + "\n" != text:
        raise SystemExit(f"{path}: not in the builder's compact form; refusing to rewrite it")
    if data["grid_hash"] != old_hash:
        raise SystemExit(f"{path}: stamped {data['grid_hash'][:12]}, not the pre-change tree's")
    ref = engine_ref(data)
    tasks = [(ref, i, j, rpm, load, data["fuel_limits"][i])
             for i, rpm in enumerate(data["rpms"]) for j, load in enumerate(data["loads"])]
    t0 = time.time()
    moved = {}
    perf_cold = [row[:] for row in data["perf_cold"]]
    meta_cold = [row[:] for row in data["src_meta_cold"]]
    for i, j, c in pool.imap_unordered(cold_cell, tasks):
        where = f"{os.path.basename(path)} cold [{i}][{j}]"
        if c["p_cyl_f32"] != data["p_cyl_cold_f32"][i][j]:
            raise SystemExit(f"{where}: the pressure trace changed -- not a friction-only change")
        if c["src_f32"] != data["src_cold_f32"][i][j]:
            raise SystemExit(f"{where}: a source waveform changed -- not a friction-only change")
        for part, new, old, allowed in (("perf", c["perf"], data["perf_cold"][i][j], FRICTION_PERF),
                                        ("meta", c["meta"], data["src_meta_cold"][i][j], FRICTION_META)):
            if new.keys() != old.keys():
                raise SystemExit(f"{where}: {part} keys differ")
            for k in new:
                if new[k] != old[k]:
                    if k not in allowed:
                        raise SystemExit(f"{where}: {part}.{k} changed ({old[k]!r} -> {new[k]!r}), "
                                         f"outside what friction reaches")
                    moved[f"{part}.{k}"] = moved.get(f"{part}.{k}", 0) + 1
        perf_cold[i][j], meta_cold[i][j] = c["perf"], c["meta"]
    out = dict(data)
    out["perf_cold"], out["src_meta_cold"], out["grid_hash"] = perf_cold, meta_cold, new_hash
    for k in data:
        if k not in ("perf_cold", "src_meta_cold", "grid_hash") and out[k] is not data[k]:
            raise SystemExit(f"{path}: {k} would change")
    ratio = max(c["fmep"] / w["fmep"] for rc, rw in zip(perf_cold, data["perf"]) for c, w in zip(rc, rw))
    was = max(c["fmep"] / w["fmep"] for rc, rw in zip(data["perf_cold"], data["perf"]) for c, w in zip(rc, rw))
    if not dry:
        with open(path, "w") as fh:
            fh.write(json.dumps(out, separators=(",", ":")) + "\n")
    print(f"{os.path.basename(path)}: {len(tasks)} cold cells in {time.time() - t0:.0f} s; changed "
          f"{', '.join(f'{k} x{n}' for k, n in sorted(moved.items())) or 'nothing'}; cold/warm FMEP worst "
          f"{was:.2f}x -> {ratio:.2f}x" + (" (dry run)" if dry else ""), flush=True)


def main(argv):
    if not argv or argv[0].startswith("-"):
        raise SystemExit(__doc__)
    pre, dry = argv[0], "--dry-run" in argv
    keys = [a for a in argv[1:] if not a.startswith("-")]
    old_hash, new_hash = pre_change_hash(pre), bridge.grid_hash()
    if old_hash == new_hash:
        raise SystemExit("the hash did not change: nothing to do")
    files = sorted(glob.glob(os.path.join(GRIDS, "*.json")))
    if keys:
        files = [f for f in files if os.path.splitext(os.path.basename(f))[0] in keys]
    print(f"pre-change tree {old_hash[:12]}, new {new_hash[:12]}; {len(files)} grids", flush=True)
    with get_context("spawn").Pool(WORKERS) as pool:
        for f in files:
            rebuild(f, pool, old_hash, new_hash, dry)
    with open(ACCURACY, "rb") as fh:
        b = fh.read()
    if b.count(old_hash.encode()) == 1:
        if not dry:
            with open(ACCURACY, "wb") as fh:
                fh.write(b.replace(old_hash.encode(), new_hash.encode()))
        print(f"accuracy.ts: re-stamped {old_hash[:12]} -> {new_hash[:12]}" + (" (dry run)" if dry else ""))
    elif b.count(new_hash.encode()) == 1:
        print("accuracy.ts: already stamped with the new hash")
    else:
        raise SystemExit("accuracy.ts: neither hash appears exactly once")


if __name__ == "__main__":
    main(sys.argv[1:])
