"""
Native-Python reference for the grid e2e check: the page's default grid
(crdi15, 8 speeds idle..max x 6 loads 0..1 -- grid.ts gridAxes, same float
operations), each cell solved exactly as the browser solves it:
dieselsim.bridge.solve_grid_cell, a fresh engine per cell.

Prints JSON {"rpms": [...], "loads": [...], "cells": {"i,j": perf}}.
Run from the repo root:  python3 web/app/e2e/native_grid.py
"""
import json
import os
import sys
from multiprocessing import get_context

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from dieselsim import bridge  # noqa: E402

PRESET = "crdi15"
N_RPM, N_LOAD = 8, 6


def lin(a, b, n):
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def cell(task):
    i, j, rpm, load = task
    out, _ = bridge.solve_grid_cell(json.dumps({"engine": {"preset": PRESET}, "rpm": rpm, "load": load}))
    return f"{i},{j}", json.loads(out)["perf"]


if __name__ == "__main__":
    info = json.loads(bridge.runtime_info())["preset_info"][PRESET]
    rpms, loads = lin(info["idle_rpm"], info["max_rpm"], N_RPM), lin(0.0, 1.0, N_LOAD)
    tasks = [(i, j, r, l) for i, r in enumerate(rpms) for j, l in enumerate(loads)]
    with get_context("spawn").Pool(min(6, os.cpu_count() or 1)) as pool:
        cells = dict(pool.map(cell, tasks))
    print(json.dumps({"rpms": rpms, "loads": loads, "cells": cells}))
