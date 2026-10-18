"""
P13 option N: build a custom engine's drivable grid on this computer, in one
command, then load it in the app with "Import grid" (/drive or /enjoy).

The engine file is what the app's Dyno page exports: Dyno -> Custom -> Export
(<key>.json, the engines/*.json format with a "vehicle"). The grid is the same
file the browser builds -- the same bridge pieces, cells and then the weather
table -- natively, which is 1.45-1.86x faster than a browser tab on the same
machine (bench/README.md), and uses more workers on a machine with more cores.

Usually run through buildgrid/build.sh (macOS, Linux) or buildgrid\\build.bat
(Windows), which set up Python and numpy first. Directly:

    python3 tools/build_my_grid.py my-engine.json [--out PATH] [--workers N]
                                   [--no-weather] [--offline] [--size RxL]

  --out PATH      where to write the grid (default out/grids/<key>.grid.json)
  --workers N     solver processes (default: min(6, cores), as the roster build)
  --no-weather    cells only: about a quarter of the time; Drive then corrects
                  nothing off the standard air (it says "no table")
  --offline       skip comparing this copy's solver with the live site's
  --size RxL      a smaller grid (e.g. 2x2), for trying the script out only
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SITE = "https://jenilclaudeai.github.io/diesel-simulator/"
# the live site's stamp: the head of one of its prebuilt grids carries the solver's hash
SITE_GRID = SITE + "grids/crdi15.json"
ROW_WEIGHT = 4.0   # a row calibration costs about four cells (PROPOSAL-grid-build.md)


def stamp_in(head):
    """The grid hash in the first bytes of a grid file, or None."""
    m = re.search(rb'"grid_hash"\s*:\s*"([0-9a-f]{64})"', head)
    return m.group(1).decode() if m else None


def site_stamp(timeout=10.0):
    """(the live site's solver hash or None, why not). From the first 4 KiB of
    one of its grids. certifi's roots when installed (the wrappers install it):
    python.org's macOS Python trusts no roots until its "Install Certificates"
    step has been run, and every https request then fails."""
    import ssl
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    req = urllib.request.Request(SITE_GRID, headers={"Range": "bytes=0-4095"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            got = stamp_in(r.read(4096))
            return got, None if got else "the site's grid has no stamp in its first 4 KiB"
    except Exception as e:     # noqa: BLE001 -- offline, proxy, certificates: only a check
        return None, str(getattr(e, "reason", e))


def default_out(key):
    return os.path.join(REPO, "out", "grids", f"{key}.grid.json")


class Progress:
    """Weighted progress and an estimate of the time left, a line at most every
    `every` seconds and at the end of each phase.

    The estimate counts waves, not pieces: `workers` pieces run at once, so
    the first to finish took one piece's time, not 1/workers of the phase.
    Elapsed / done x left -- what the app's first ETA did -- read 344 min at
    the first row of a ~1 h build (PROPOSAL-grid-build.md, part 1). Here a
    unit of work takes (time in this phase) / (waves finished) / (its weight)
    on one worker, and what is left is spread over the workers."""

    def __init__(self, phases, workers=1, every=20.0, clock=time.time, out=print):
        self.phases = phases                      # {name: (pieces, weight)}, in order
        self.total = sum(n * w for n, w in phases.values())
        self.workers = max(1, workers)
        self.done_before = 0.0                    # work units of finished phases
        self.t0 = clock()
        self.phase_t0 = {}
        self.last_end = self.t0
        self.last = -1e9
        self.every, self.clock, self.out = every, clock, out

    def seconds_left(self, phase, done, now):
        n, w = self.phases.get(phase, (done, 1.0))
        el = now - self.phase_t0[phase]
        waves = -(-done // self.workers)          # ceil
        unit_s = el / max(waves, 1) / w           # one unit, on one worker
        names = list(self.phases)
        later = names[names.index(phase) + 1:] if phase in names else []
        units = (n - done) * w + sum(self.phases[k][0] * self.phases[k][1] for k in later)
        return units * unit_s / self.workers

    def __call__(self, phase, done, total):
        now = self.clock()
        self.phase_t0.setdefault(phase, self.last_end)
        w = self.phases.get(phase, (total, 1.0))[1]
        units = self.done_before + done * w
        end = done == total
        if end or now - self.last >= self.every:
            left = self.seconds_left(phase, done, now)
            self.out(f"[{100 * units / self.total:3.0f}%] {phase} {done}/{total}  "
                     f"{(now - self.t0) / 60:.1f} min so far, about {left / 60:.0f} min left", flush=True)
            self.last = now
        if end:
            self.done_before += total * w
            self.last_end = now


def main(argv=None):
    # imported here: build_live_grids registers engines/*.json as presets on
    # import, which the helpers above (and their test) must not do
    import build_live_grids as B
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("engine")
    ap.add_argument("--out")
    ap.add_argument("--workers", type=int, default=min(6, os.cpu_count() or 1))
    ap.add_argument("--no-weather", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--size")
    a = ap.parse_args(argv)
    if not os.path.exists(a.engine):
        raise SystemExit(f"{a.engine}: no such file. Export it from the app: Dyno -> Custom -> Export.")
    key, d, sha = B.custom_engine(a.engine)          # refuses an unknown vehicle or an unbuildable engine
    size = tuple(int(x) for x in a.size.split("x")) if a.size else (B.N_RPM, B.N_LOAD)
    out = os.path.abspath(a.out or default_out(key))
    ghash = B.grid_hash()

    print(f"engine {key} ({d.get('vehicle')}), from {a.engine}")
    if not a.offline:
        live, why = site_stamp()
        if live is None:
            print(f"could not compare this copy's solver with the live site's ({why}); building anyway")
        elif live != ghash:
            print(f"NOTE: this copy's solver ({ghash[:12]}) is not the live site's ({live[:12]}). The grid will "
                  "drive with this copy's physics. For the site's, update this copy first (git pull, branch main).")
        else:
            print(f"this copy's solver matches the live site's ({ghash[:12]})")

    plan = json.loads(B.bridge.live_grid_plan(json.dumps({"engine": B.engine_ref(d), "n_rpm": size[0],
                                                           "n_load": size[1]})))
    n_rpm, n_cells = len(plan["rpms"]), len(plan["rpms"]) * len(plan["loads"])
    phases = {"rows": (n_rpm, ROW_WEIGHT), "warm cells": (n_cells, 1.0), "cold cells": (n_cells, 1.0)}
    if not a.no_weather:
        wp = json.loads(B.bridge.live_weather_plan(json.dumps({"rpms": plan["rpms"], "loads": plan["loads"]})))
        phases["weather"] = (len(wp["pieces"]) + len(wp["check"]), 1.0)
    pieces = sum(n for n, _ in phases.values())
    print(f"{pieces} converged solves on {a.workers} workers -> {out}")

    t0 = time.time()
    prog = Progress(phases, workers=a.workers)
    with B.SafePool(a.workers) as pool:
        B.build(key, pool, ghash, edef=d, size=size, out_path=out, progress=prog,
                extra={"custom": True, "vehicle": d["vehicle"], "engine_json": d, "engine_file_sha256": sha})
        if not a.no_weather:
            B.add_weather(out, pool, ghash, progress=prog)
    print(f"\ndone in {(time.time() - t0) / 60:.1f} min: {out}")
    print(f"Load it in the app: {SITE}drive (or /enjoy) -> Import grid -> pick that file.")
    return out


if __name__ == "__main__":
    main()
