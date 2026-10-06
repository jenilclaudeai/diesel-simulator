"""
Native-Python reference for the cycle-page e2e check (Phase 6, ADR-015): the
page's default point for crdi15 (60% of the way from idle to rated, rounded to
50 rpm; load 0.6), solved exactly as the page solves it, bridge.solve_cycle.

Prints JSON {"rpm", "p_max_bar", "mfb50", "imep_net_bar", "theta_pmax"}.
Run from the repo root:  python3 web/app/e2e/native_cycle.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from dieselsim import bridge  # noqa: E402

PRESET, LOAD = "crdi15", 0.6
info = json.loads(bridge.runtime_info())["preset_info"][PRESET]
rpm = round((info["idle_rpm"] + 0.6 * (info["rated_rpm"] - info["idle_rpm"])) / 50) * 50
s = json.loads(bridge.solve_cycle(json.dumps({"engine": {"preset": PRESET}, "rpm": rpm, "load": LOAD})))["summary"]
print(json.dumps({"rpm": rpm, "p_max_bar": s["p_max"] / 1e5, "mfb50": s["mfb50"],
                  "imep_net_bar": s["imep_net"] / 1e5, "theta_pmax": s["theta_pmax"]}))
