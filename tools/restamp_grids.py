"""
Re-stamp the prebuilt grids after a change to a hashed `dieselsim/` file that
cannot reach a grid cell -- with the proof CLAUDE.md asks for, asserted:

1. the package, with the pre-change copies of the changed files put back,
   hashes to exactly the hash every grid carries (so the change is the only
   hashed change since they were stamped);
2. each grid file's only change is that 64-character hash (same size, one
   64-byte span) -- and the same for the Dyno page's accuracy table
   (web/app/src/app/dyno/accuracy.ts, ACCURACY_SOLVER), keyed on the same hash.

The third part of the proof is the caller's: show that nothing on a grid's
path reads what changed (a grep, and test_live_grid_pieces_match_the_shipped_grid,
which recomputes a shipped cell with the new code).

Usage, from the repo root:
    mkdir /tmp/pre && git show HEAD~1:dieselsim/engine.py > /tmp/pre/engine.py
    python3 tools/restamp_grids.py /tmp/pre            # --dry-run to check only

Written in session 6 (2026-10-05), after FINDING-024 and the durability
refactor each needed one; earlier sessions' one-off scripts were not kept.
"""
import glob
import hashlib
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)
from dieselsim import bridge  # noqa: E402


def main(argv):
    if not argv or argv[0].startswith("-"):
        raise SystemExit(__doc__)
    pre, dry = argv[0], "--dry-run" in argv
    pkg = os.path.join(REPO, "dieselsim")
    h = hashlib.sha256()
    for n in sorted(f for f in os.listdir(pkg) if f.endswith(".py") and f not in bridge.GRID_HASH_EXCLUDES):
        path = os.path.join(pre, n) if os.path.exists(os.path.join(pre, n)) else os.path.join(pkg, n)
        with open(path, "rb") as fh:
            h.update(n.encode() + b"\0" + fh.read() + b"\0")
    old_hash, new_hash = h.hexdigest(), bridge.grid_hash()
    files = sorted(glob.glob(os.path.join(REPO, "web", "app", "public", "grids", "*.json")))
    stamps = set()
    for f in files:
        with open(f) as fh:
            stamps.add(json.load(fh)["grid_hash"])
    print(f"pre-change tree: {old_hash[:12]}; grids carry {sorted(s[:12] for s in stamps)}; new: {new_hash[:12]}")
    if stamps != {old_hash}:
        raise SystemExit("the grids were not stamped by the pre-change tree: no re-stamp")
    if old_hash == new_hash:
        raise SystemExit("the hash did not change: nothing to do")
    # the Dyno page's accuracy table is keyed on the same hash (ACCURACY_SOLVER); the
    # FINDING-024 re-stamp missed it once, so it is stamped with the grids, under the
    # same rule (test_accuracy_table_is_for_this_build guards it)
    accuracy = os.path.join(REPO, "web", "app", "src", "app", "dyno", "accuracy.ts")
    for f in files + [accuracy]:
        with open(f, "rb") as fh:
            b = fh.read()
        if b.count(old_hash.encode()) != 1:
            raise SystemExit(f"{f}: the old hash is not there exactly once")
        nb = b.replace(old_hash.encode(), new_hash.encode())
        diff = [i for i in range(len(b)) if b[i] != nb[i]]
        assert len(nb) == len(b) and diff[-1] - diff[0] < 64, f
        if not dry:
            with open(f, "wb") as fh:
                fh.write(nb)
        print(f"{os.path.basename(f)}: changed span {diff[-1] - diff[0] + 1} bytes")
    print(("would re-stamp " if dry else "re-stamped ") + f"{len(files)} grids and the accuracy table {old_hash[:12]} -> {new_hash[:12]}")


if __name__ == "__main__":
    main(sys.argv[1:])
