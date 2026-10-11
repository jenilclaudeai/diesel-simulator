"""
How long does a standard drivable grid take on THIS machine? A benchmark for
comparing hardware (the owner's request, 2026-10-10).

A standard drivable grid (ADR-011/ADR-014, what tools/build_live_grids.py
writes) is, per engine: 8 rpm rows, each a converged full-load fuel
calibration, then 8 x 6 cells solved converged twice, warm and cold, on that
fuel: 8 + 96 = 104 converged pieces, through the same bridge functions the
native tool and the browser use.

Two modes:

  quick (default, ~3-6 min): runs one wave of row limits and one wave of
    cells (warm and cold, spread over the grid) on as many workers as the
    native tool uses, so the timings include this machine's behaviour under
    full load (heat, shared caches, SMT). Then it schedules the full build
    from those timings -- rows first, then the warm cells, then the cold,
    each phase a pool.map as build_live_grids.py does -- and reports the
    estimate.
  --full (~15-25 min on a 6-8 core laptop): builds the whole grid and
    times it. The exact number, and the check on the estimate.

Validated on an Apple M2 laptop (8 cores, 6 workers), 2026-10-10: --full
measured 22.1 min, and the schedule fed that run's own piece times gave
23.4 (+6%), so the schedule is sound. The quick mode gave 16.8 min (-24%):
over 22 minutes of full load every piece ran slower (a row 270 s against
182, a cell 57 s against 40) -- the machine slowing under sustained load,
which a 5-minute run doesn't reach. So the quick figure is for a machine
that holds its speed; to compare laptops that throttle, use --full.

It also estimates the browser's build, as a range, and says it is one: the
native estimate scaled by this project's two measured whole browser builds
on one 8-core Mac (21.5 and 27.5 min in Chrome on 6 workers, against 14.8
min natively for the same 8 x 6 grid on 6 workers: x1.45-1.86), on the
app's pool (cores - 1, at most 6). Not ADR-014's x2.65: that was measured
single-threaded, and these piece times are taken under full load, which
would count the load twice.

Run (from the repo root; numpy is the only dependency):
    python3 tools/bench_grid.py                 # quick
    python3 tools/bench_grid.py --full          # exact
    python3 tools/bench_grid.py --workers 4     # another pool size
    python3 tools/bench_grid.py --engine crdi15 # another engine (default crdi15)
Results: printed, and saved to out/bench/<host>-<date>.json for comparing.
Or use bench/run_bench.sh (macOS/Linux) or bench\\run_bench.bat (Windows),
which set up a venv first.
"""
import datetime
import json
import math
import os
import platform
import socket
import statistics
import sys
import time
from multiprocessing import get_context

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

N_RPM, N_LOAD = 8, 6                    # bridge.LIVE_N_RPM, LIVE_N_LOAD
# the browser against native, whole builds on one 8-core Mac, both on 6 workers: Chrome 21.5 and
# 27.5 min (STATUS, session 5 parts 17 and 18) against native 14.8 min (crdi15's shipped grid)
BROWSER_RATIO = (21.5 / 14.8, 27.5 / 14.8)


def native_workers():
    """build_live_grids.py's pool: min(6, cores)."""
    return min(6, os.cpu_count() or 1)


def browser_workers():
    """The app's pool (ADR-014 step 3b): cores - 1, at most 6 (2 on a device under 4 GB)."""
    return max(1, min(6, (os.cpu_count() or 2) - 1))


# ---------------------------------------------------------------- the estimate
def phase_seconds(n_tasks, workers, t_task):
    """One pool.map of n equal tasks on `workers`: ceil(n / workers) waves."""
    return math.ceil(n_tasks / max(workers, 1)) * t_task


def estimate_build_seconds(t_row, t_cell_warm, t_cell_cold, workers, n_rpm=N_RPM, n_load=N_LOAD):
    """build_live_grids.py's schedule: the rows (one pool.map), then the warm
    cells, then the cold cells (a pool.map each)."""
    n_cells = n_rpm * n_load
    return (phase_seconds(n_rpm, workers, t_row) + phase_seconds(n_cells, workers, t_cell_warm)
            + phase_seconds(n_cells, workers, t_cell_cold))


# ---------------------------------------------------------------- the pieces
def _ref(engine):
    from dieselsim.builder import load_engine_dir
    from dieselsim.config import PRESETS
    if engine not in PRESETS:
        load_engine_dir(os.path.join(REPO, "engines"))
    return {"preset": engine}


def timed_row(task):
    engine, rpm = task
    from dieselsim import bridge
    t0 = time.perf_counter()
    out = json.loads(bridge.live_row_limit(json.dumps({"engine": _ref(engine), "rpm": rpm})))
    return time.perf_counter() - t0, out["fuel_limit"]


def timed_cell(task):
    engine, rpm, load, flim, cold = task
    from dieselsim import bridge
    t0 = time.perf_counter()
    bridge.live_cell(json.dumps({"engine": _ref(engine), "rpm": rpm, "load": load, "fuel_limit": flim, "cold": cold}))
    return time.perf_counter() - t0


def plan(engine):
    from dieselsim import bridge
    return json.loads(bridge.live_grid_plan(json.dumps({"engine": _ref(engine)})))


def sample_rows(n_rows, k):
    """k row indices spread evenly over the grid, ends included (cost differs with rpm)."""
    k = max(1, min(k, n_rows))
    if k == 1:
        return [n_rows // 2]
    return [round(i * (n_rows - 1) / (k - 1)) for i in range(k)]


def sample_loads(n_loads, k):
    """k load indices that visit every load before repeating one: 2, 1, 0, 5, 4, 3, ..."""
    return [(n * (n_loads - 1) + 2) % n_loads for n in range(k)]


def machine():
    import numpy as np
    info = {"host": socket.gethostname(), "platform": platform.platform(), "machine": platform.machine(),
            "processor": platform.processor() or "", "cores_logical": os.cpu_count(),
            "python": sys.version.split()[0], "numpy": np.__version__}
    try:                                   # the CPU's name where the OS tells it cheaply
        if sys.platform == "darwin":
            import subprocess
            info["cpu"] = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                                         text=True).stdout.strip()
            info["cores_physical"] = int(subprocess.run(["sysctl", "-n", "hw.physicalcpu"], capture_output=True,
                                                        text=True).stdout.strip() or 0)
        elif sys.platform.startswith("linux"):
            with open("/proc/cpuinfo") as fh:
                names = [ln.split(":", 1)[1].strip() for ln in fh if ln.startswith("model name")]
            info["cpu"] = names[0] if names else ""
        elif sys.platform == "win32":
            info["cpu"] = platform.processor()
    except Exception:
        pass
    return info


def run(engine="crdi15", workers=None, full=False, log=print):
    workers = workers or native_workers()
    p = plan(engine)
    rpms, loads = p["rpms"], p["loads"]
    t_start = time.perf_counter()
    with get_context("spawn").Pool(workers) as pool:
        if full:
            t0 = time.perf_counter()
            rows = pool.map(timed_row, [(engine, r) for r in rpms])
            t_rows = time.perf_counter() - t0
            flims = [f for _, f in rows]
            phases = {"rows": t_rows}
            cell_times = {}
            for tag, cold in (("warm", False), ("cold", True)):
                t0 = time.perf_counter()
                cell_times[tag] = pool.map(timed_cell, [(engine, r, ld, f, cold) for r, f in zip(rpms, flims) for ld in loads])
                phases[tag] = time.perf_counter() - t0
                log(f"  {tag} cells: {phases[tag]:.0f} s")
            measured = time.perf_counter() - t_start
            row_t = [t for t, _ in rows]
            result = {"mode": "full", "measured_s": measured, "phases_s": phases,
                      "piece_s": {"row": row_t, "warm": cell_times["warm"], "cold": cell_times["cold"]}}
            means = (statistics.mean(row_t), statistics.mean(cell_times["warm"]), statistics.mean(cell_times["cold"]))
        else:
            # one wave of rows, spread over the grid
            idx = sample_rows(len(rpms), workers)
            log(f"  {len(idx)} row limits at once ({workers} workers)...")
            rows = pool.map(timed_row, [(engine, rpms[i]) for i in idx])
            flim = {i: f for i, (_, f) in zip(idx, rows)}
            # one wave of cells, warm and cold alternately, over those rows and every load
            cells = [(engine, rpms[idx[n % len(idx)]], loads[j], flim[idx[n % len(idx)]], n % 2 == 1)
                     for n, j in enumerate(sample_loads(len(loads), workers))]
            log(f"  {len(cells)} cells at once...")
            cell_t = pool.map(timed_cell, cells)
            warm = [t for t, c in zip(cell_t, cells) if not c[4]] or cell_t
            cold = [t for t, c in zip(cell_t, cells) if c[4]] or cell_t
            row_t = [t for t, _ in rows]
            means = (statistics.mean(row_t), statistics.mean(warm), statistics.mean(cold))
            result = {"mode": "quick", "benchmark_s": time.perf_counter() - t_start,
                      "piece_s": {"row": row_t, "warm": warm, "cold": cold}}
    est = estimate_build_seconds(*means, workers)
    bw = browser_workers()
    result.update({
        "engine": engine, "workers": workers, "grid": f"{len(rpms)} x {len(loads)}",
        "pieces": len(rpms) + 2 * len(rpms) * len(loads),
        "mean_piece_s": {"row": means[0], "warm_cell": means[1], "cold_cell": means[2]},
        "estimate_native_s": est,
        "estimate_browser_s": [estimate_build_seconds(*(m * r for m in means), bw) for r in BROWSER_RATIO],
        "browser_workers": bw,
        "machine": machine(), "date": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    return result


def report(r):
    m = r["machine"]
    lines = [
        "",
        "=== drivable-grid benchmark ===",
        f"machine : {m.get('cpu') or m['processor'] or m['machine']} | {m['cores_logical']} logical cores"
        + (f", {m['cores_physical']} physical" if m.get("cores_physical") else "")
        + f" | {m['platform']}",
        f"python  : {m['python']}, numpy {m['numpy']}",
        f"engine  : {r['engine']}, a {r['grid']} grid, {r['pieces']} converged pieces (rows + warm + cold cells)",
        f"workers : {r['workers']} (the native tool's pool)",
        f"pieces  : row limit {r['mean_piece_s']['row']:.1f} s, warm cell {r['mean_piece_s']['warm_cell']:.1f} s, "
        f"cold cell {r['mean_piece_s']['cold_cell']:.1f} s (mean, under full load)",
    ]
    if r["mode"] == "full":
        lines.append(f"MEASURED: the full grid took {r['measured_s'] / 60:.1f} min "
                     f"(the estimate from its own piece times: {r['estimate_native_s'] / 60:.1f} min)")
    else:
        lines.append(f"ESTIMATE: a full grid natively ~ {r['estimate_native_s'] / 60:.1f} min "
                     f"(this quick run took {r['benchmark_s'] / 60:.1f} min; --full measures it exactly)")
        lines.append("          if the machine slows under a long full load (thin, quiet laptops do), the real "
                     "build is longer: on an M2 laptop quick said 16.8 min, --full measured 22.1")
    lo, hi = r["estimate_browser_s"]
    lines.append(f"browser : ~ {lo / 60:.0f}-{hi / 60:.0f} min on {r['browser_workers']} workers (an estimate: "
                 f"x{BROWSER_RATIO[0]:.2f}-{BROWSER_RATIO[1]:.2f} of native, from two whole browser builds on a Mac)")
    return "\n".join(lines)


def main(argv):
    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default
    full = "--full" in argv
    workers = int(opt("--workers")) if "--workers" in argv else None
    engine = opt("--engine", "crdi15")
    print(f"benchmarking a drivable grid ({'full build' if full else 'quick'}) ...", flush=True)
    r = run(engine=engine, workers=workers, full=full)
    print(report(r))
    out_dir = os.path.join(REPO, "out", "bench")
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(out_dir, f"{r['machine']['host']}-{r['mode']}-{stamp}.json")
    with open(path, "w") as fh:
        json.dump(r, fh, indent=1)
    print(f"saved   : {os.path.relpath(path, REPO)}")


if __name__ == "__main__":
    main(sys.argv[1:])
