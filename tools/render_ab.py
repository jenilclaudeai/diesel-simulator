"""
Render the A/B listening pairs that FINDING-004's changes were never judged
by ear on, and report what differs between each pair, so a listener knows
what to listen for.

  pair 1  crdi15 1800 rpm load 0.6, fully warm vs fully cold (oil AND
          coolant at 273 K -- cold coolant alone misses a 255% friction
          effect; CLAUDE.md). The pair that matters most.
  pair 2  hd_i6 1250 rpm load 0.5, new vs 12,000 h (mechanical lash, 300 um,
          so lash-driven valve tick can age now that cam wear is real --
          FINDING-015).

Each clip is 4 s on the exterior_7m microphone, same seed within a pair.
Writes WAVs to out/listen/. Needs scipy.
Run:  python3 tools/render_ab.py
      python3 tools/render_ab.py --levels   (FINDING-017's two measurements)
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dieselsim.acoustics import EngineSound  # noqa: E402
from dieselsim.engine import DieselEngine  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "out", "listen")
MIC, DUR, SEED = "exterior_7m", 4.0, 11


def render(eng, rpm, load, name):
    op = eng.operating_point(rpm, load=load, n_cycles=9)
    snd = EngineSound(eng.spec)
    snd.wear = eng.wear
    y, parts = snd.render(op, duration=DUR, mic=MIC, seed=SEED)
    snd.write_wav(os.path.join(OUT, name + ".wav"), y)
    f, P = snd.spectrum(y)
    pw = 10 ** (P / 10)
    hi = pw[f > 1500].sum() / max(pw[(f > 50) & (f <= 1500)].sum(), 1e-30)
    lev = {k: float(np.sqrt(np.mean(v ** 2))) for k, v in parts.items()}
    return dict(rms=float(np.sqrt(np.mean(y ** 2))), bright=float(hi), torque=op.torque,
                fmep=op.fmep / 1e5, parts=lev)


def compare(a, b, la, lb):
    print(f"  {'':22} {la:>10} {lb:>10} {'change':>8}")
    print(f"  {'loudness (RMS)':22} {a['rms']:10.4f} {b['rms']:10.4f} {100 * (b['rms'] / a['rms'] - 1):+7.1f}%")
    print(f"  {'brightness (>1.5k/<1.5k)':22} {a['bright']:10.4f} {b['bright']:10.4f} {100 * (b['bright'] / a['bright'] - 1):+7.1f}%")
    print(f"  {'FMEP bar':22} {a['fmep']:10.3f} {b['fmep']:10.3f} {100 * (b['fmep'] / a['fmep'] - 1):+7.1f}%")
    print("  source levels (RMS before the mic mix):")
    for k in a["parts"]:
        x, y = a["parts"][k], b["parts"][k]
        ch = f"{100 * (y / x - 1):+7.1f}%" if x > 0 else "   n/a"
        print(f"    {k:12} {x:10.4f} {y:10.4f} {ch}")


def main():
    os.makedirs(OUT, exist_ok=True)
    warm = DieselEngine(preset="crdi15")
    cold = DieselEngine(preset="crdi15")
    cold.T_coolant = 273.0
    cold._apply_thermal_state()
    cold.oil.cond.T_oil = 273.0
    a = render(warm, 1800, 0.6, "pair1_crdi15_warm")
    b = render(cold, 1800, 0.6, "pair1_crdi15_cold")
    print("pair 1: crdi15 1800 rpm load 0.6, warm vs fully cold (oil and coolant 273 K)")
    compare(a, b, "warm", "cold")

    new = DieselEngine(preset="hd_i6")
    old = DieselEngine(preset="hd_i6")
    old.durability_run(12000.0, step_h=500.0, verbose=False)
    lash = 1e6 * old.wear.state.lash_growth_exh
    a = render(new, 1250, 0.5, "pair2_hd_i6_new")
    b = render(old, 1250, 0.5, "pair2_hd_i6_12000h")
    print(f"\npair 2: hd_i6 1250 rpm load 0.5, new vs 12,000 h (exhaust lash growth {lash:.2f} um)")
    compare(a, b, "new", "12000 h")
    print(f"\nWAVs in {os.path.abspath(OUT)}")


def levels():
    """FINDING-017: (1) the mech sub-mix normalises each component by its own
    std, so doubling the piston-slap input should change nothing if the
    physical scaling is discarded; (2) lash against closing-ramp height."""
    import math
    eng = DieselEngine(preset="crdi15")
    op = eng.operating_point(1800, load=0.6, n_cycles=9)
    snd = EngineSound(eng.spec)
    snd.wear = eng.wear
    src = snd.build_sources(op)
    mech = {}
    for tag, k in (("base", 1.0), ("x2", 2.0)):
        s2 = dict(src)
        s2["_meta"] = dict(src["_meta"])
        s2["_meta"]["skirt_clr"] *= k
        mech[tag] = snd.render(op, duration=2.0, sources=s2, seed=3)[1]["mech"]
    d = float(np.max(np.abs(mech["base"] - mech["x2"])))
    print(f"1. mech output with the slap input doubled: max |difference| {d:.3e} "
          f"(mech RMS {float(np.sqrt(np.mean(mech['base'] ** 2))):.4f}); "
          f"'skirt_clr' is op.friction['h_skirt'] = {src['_meta']['skirt_clr'] * 1e6:.2f} um")
    print("2. exhaust lash vs closing-ramp height")
    for p in ("crdi15", "crdi_1p5", "hd_i6", "ld_i4", "single"):
        cam = DieselEngine(preset=p).cycle.cam_exh
        print(f"   {p:9} lash {cam.lash * 1e6:5.0f} um  ramp {cam.h_ramp * 1e6:5.0f} um  "
              f"factor {1 + 2.2 * cam.lash / max(cam.h_ramp, 1e-9):5.2f}  "
              f"v_seat at 1500 rpm {cam.seating_velocity(2 * math.pi * 1500 / 60):.3f} m/s")


if __name__ == "__main__":
    if "--levels" in sys.argv:
        levels()
    else:
        main()
