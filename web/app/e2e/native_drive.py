"""
Native-Python reference for the drive e2e: dieselsim.live's LiveEngine on a
prebuilt grid (web/app/public/grids/<preset>.json, ADR-011) driving the
live fixture's 60 s script -- exactly what the page's worker runs in
TypeScript. Prints JSON {"events": [...], "final": {...}}.

Run from the repo root:  python3 web/app/e2e/native_drive.py [preset] [trans]
"""
import base64
import json
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
from dieselsim.engine import DieselEngine  # noqa: E402
from dieselsim.live import Adr011Grid, LiveEngine, handle_key, pedal_return  # noqa: E402

preset = sys.argv[1] if len(sys.argv) > 1 else "crdi15"
trans = sys.argv[2] if len(sys.argv) > 2 else "tc"
with open(os.path.join(ROOT, "web", "app", "public", "grids", f"{preset}.json")) as fh:
    gj = json.load(fh)
with open(os.path.join(ROOT, "web", "physics", "fixtures", "live.json")) as fh:
    script = next(d for d in json.load(fh)["inputs"]["drives"] if d["name"] == "tc")["script"]
dec = lambda rows: [[np.frombuffer(base64.b64decode(c), dtype="<f4") for c in row] for row in rows]  # noqa: E731
spec = DieselEngine(preset=preset).spec
grid = Adr011Grid(spec, gj["rpms"], gj["loads"], gj["perf"], dec(gj["p_cyl_f32"]), gj["grid_deg"],
                  gj["perf_cold"], dec(gj["p_cyl_cold_f32"]), gj["T_warm"], gj["T_cold"])
live = LiveEngine(grid, preset, trans=trans)
keys = {k: c for k, c in script["keys"]}
grade = {k: v for k, v in script["grade"]}
events, prev = [], None
for n in range(script["n"]):
    t = n * script["dt"]
    if not live.cruise_on:
        live.throttle = script["throttle"][n]
    for t0, t1, b in script["brake"]:
        if t0 <= t < t1:
            live.dl.brake = b
    if n in grade:
        live.dl.grade = grade[n]
    for t0, t1, k in script.get("holds", []):
        if t0 <= t < t1:
            handle_key(live, k)
    if n in keys:
        handle_key(live, keys[n])
    pedal_return(live, script["dt"])
    live.step(script["dt"])
    gb = live.dl.gb
    ev = [gb.gear, gb.phase, int(live.dl.lockup), int(live.dl.rigid), int(gb.neutral), int(live.dl.lock_allowed),
          int(live.fan_on), int(live.stalled), int(live.dl.assist)]
    if ev != prev:
        events.append([n] + ev)
        prev = ev
final = {"rpm": live.rpm, "v": live.dl.v, "odo_m": live.odo_m, "trip_L": live.trip_L, "T_coolant": live.T_coolant,
         "T_oil": live.T_oil, "fmep_live": live.fmep_live, "boost": live.boost}
print(json.dumps({"events": events, "final": {k: float(v) for k, v in final.items()}, "script": script}))
