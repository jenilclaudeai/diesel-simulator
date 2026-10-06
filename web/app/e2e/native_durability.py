"""
Native-Python reference for the durability-page e2e check (Phase 6, ADR-015):
crdi15 aged 100 h in 50 h blocks by DieselEngine.durability_run, which the
page steps through bridge.durability_* (the same log rows, exactly).

Prints JSON {"rows": n, "health", "bore_wear_um", "torque"} of the last row.
Run from the repo root:  python3 web/app/e2e/native_durability.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from dieselsim.engine import DieselEngine  # noqa: E402

log = DieselEngine(preset="crdi15").durability_run(100.0, step_h=50.0, verbose=False)
last = log[-1]
print(json.dumps({"rows": len(log), "health": last["health"], "bore_wear_um": last["bore_wear_um"], "torque": last["torque"]}))
