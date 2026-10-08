"""
A/B proof that a change to a hashed `dieselsim/` file moves nothing at the
rating's air (101325 Pa / 298 K), the air every prebuilt grid was solved
in, before re-stamping the grids with tools/restamp_grids.py.

The cases are FINDING-025's and #107's: bridge.solve_point at 1200/0.3 and
2400/1.0 on every engine that ships a grid, plus crdi15's whole
solve_cycle reply at 2700/0.6. Each reply is reduced to the sha256 of its
JSON, so two trees compare exactly.

Usage, from the repo root:
    git worktree add /tmp/old HEAD~1              # or any copy of the old tree
    python3 tools/ab_rating_air.py /tmp/old > old.txt
    python3 tools/ab_rating_air.py .        > new.txt
    diff old.txt new.txt && echo identical

Written in session 8 (2026-10-08) for FINDING-026. Earlier sessions' one-off
versions of this were not kept.
"""
import hashlib
import json
import os
import sys

POINTS = ((1200.0, 0.3), (2400.0, 1.0))
CYCLE = ("crdi15", 2700.0, 0.6)


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    tree = os.path.abspath(argv[0])
    sys.path.insert(0, tree)
    from dieselsim import bridge
    from dieselsim.builder import load_engine_dir
    from dieselsim.config import PRESETS
    load_engine_dir(os.path.join(tree, "engines"))
    grids = os.path.join(tree, "web", "app", "public", "grids")
    keys = sorted(f[:-5] for f in os.listdir(grids) if f.endswith(".json"))
    missing = [k for k in keys if k not in PRESETS]
    if missing:
        raise SystemExit(f"no engine for grids {missing}")
    n = 0
    for k in keys:
        for rpm, load in POINTS:
            out = bridge.solve_point(json.dumps({"engine": {"preset": k}, "rpm": rpm, "load": load}))
            print(f"solve_point {k} {rpm:.0f}/{load} {hashlib.sha256(out.encode()).hexdigest()}")
            n += 1
    k, rpm, load = CYCLE
    out = bridge.solve_cycle(json.dumps({"engine": {"preset": k}, "rpm": rpm, "load": load}))
    assert isinstance(out, str), f"solve_cycle returned {type(out)}, not its JSON string"
    print(f"solve_cycle {k} {rpm:.0f}/{load} {hashlib.sha256(out.encode()).hexdigest()}")
    print(f"# {n + 1} replies", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
