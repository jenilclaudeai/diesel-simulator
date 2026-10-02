#!/usr/bin/env python3
"""Valve tick against the loudest other mechanical source, as the mix weighs
them (FINDING-017's measure, committed so that numbers stay comparable):
tick (v_seating / ref)^2, injector 0.75, slap 0.9 (skirt_clr / ref)^0.6,
each source at unit std in acoustics.render. Warm and cold (273 K coolant).

    python3 tools/tick_dominance.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dieselsim import acoustics  # noqa: E402
from dieselsim.acoustics import EngineSound  # noqa: E402
from dieselsim.engine import DieselEngine  # noqa: E402

POINTS = [("hd_i6", 1250.0, 0.5), ("single", 2000.0, 0.8), ("crdi15", 1800.0, 0.6),
          ("hd_i6", 600.0, 0.05), ("truck127", 1200.0, 0.5)]
# FINDING-023 moved the slap reference from 30 um of film to 30/0.32 um of clearance
SLAP_REF = getattr(acoustics, "SLAP_CLR_REF", 30e-6)


def levels(key, rpm, load, T_coolant=None):
    eng = DieselEngine(preset=key)
    if T_coolant is not None:
        eng.T_coolant = T_coolant
        eng._apply_thermal_state()
    op = eng.operating_point(rpm, load=load, n_cycles=9)
    snd = EngineSound(eng.spec)
    snd.wear = eng.wear
    if T_coolant is not None:
        snd.T_coolant = T_coolant           # ignored before FINDING-023
    m = snd.build_sources(op)["_meta"]
    tick = (max(m["v_seating"], 1e-6) / snd._ref_vseat) ** 2
    slap = 0.9 * (max(m["skirt_clr"], 1e-9) / SLAP_REF) ** 0.6
    return tick, 0.75, slap, m


def main():
    try:
        from dieselsim.builder import load_engine_dir
        load_engine_dir(os.path.join(os.path.dirname(__file__), "..", "engines"))
    except Exception:
        pass
    print(f"{'point':22s} {'':5s} {'tick':>8s} {'inj':>6s} {'slap':>6s} {'tick/other':>11s}  v_seat, skirt_clr")
    for key, rpm, load in POINTS:
        for tag, T in (("warm", None), ("cold", 273.0)):
            try:
                tick, inj, slap, m = levels(key, rpm, load, T)
            except KeyError:
                print(f"{key:22s} (not available)")
                break
            print(f"{key} {rpm:.0f}/{load:<4} {tag:5s} {tick:8.3f} {inj:6.2f} {slap:6.3f} {tick / max(inj, slap):10.2f}x"
                  f"  {m['v_seating']:.4f} m/s, {m['skirt_clr'] * 1e6:.1f} um")


if __name__ == "__main__":
    main()
