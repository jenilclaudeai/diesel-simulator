"""
Native-Python reference for the sweep-page e2e check (Phase 6, ADR-015):
crdi15's compression ratio from 15 to 18 in 4 points, at the page's default
speed (60% of idle-to-rated, rounded to 50 rpm) and full load, each value a
bridge.solve_point with it in the overrides -- exactly as the page solves.

Prints JSON {"rpm", "values": [...], "torque": [...]}.
Run from the repo root:  python3 web/app/e2e/native_sweep.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from dieselsim import bridge  # noqa: E402

PRESET, FIELD, VALUES = "crdi15", "geom.compression_ratio", [15, 16, 17, 18]
info = json.loads(bridge.runtime_info())["preset_info"][PRESET]
rpm = round((info["idle_rpm"] + 0.6 * (info["rated_rpm"] - info["idle_rpm"])) / 50) * 50
torque = [json.loads(bridge.solve_point(json.dumps({"engine": {"preset": PRESET, "overrides": {FIELD: v}},
                                                    "rpm": rpm, "load": 1.0})))["torque"] for v in VALUES]
print(json.dumps({"rpm": rpm, "values": VALUES, "torque": torque}))
