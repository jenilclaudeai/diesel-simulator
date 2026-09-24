"""
Native-Python reference for the dyno e2e check: brake torque at three points
of the page's default full-load pull (crdi15), solved exactly as the page
solves them -- dieselsim.bridge.solve_point, a fresh engine per point, load 1,
the bridge's default n_cycles. The rpms follow the page's sweep (idle to
max_rpm in 10 steps, rounded to 50): the first, sixth and last point.

Prints JSON {"<rpm>": torque}. Run from the repo root:
    python3 web/app/e2e/native_ref.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from dieselsim import bridge  # noqa: E402

PRESET = "crdi15"
info = json.loads(bridge.runtime_info())["preset_info"][PRESET]
lo, hi = info["idle_rpm"], info["max_rpm"]
rpms = [round((lo + (hi - lo) * i / 9) / 50) * 50 for i in range(10)]
ref = {}
for r in (rpms[0], rpms[5], rpms[9]):
    req = json.dumps({"engine": {"preset": PRESET}, "rpm": r, "load": 1})
    ref[str(r)] = json.loads(bridge.solve_point(req))["torque"]
print(json.dumps(ref))
