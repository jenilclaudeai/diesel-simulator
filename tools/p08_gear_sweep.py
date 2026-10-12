"""P08 baseline: what today's automatic (Enjoy's 'tc' box) does.

1. Launches at a fixed throttle from rest: every upshift's turbine and engine rpm.
2. Steady cruises held by a PI controller: the gear the schedule settles in,
   then every other gear forced at the same speed, with the fuel rate and the
   torque reserve (1 - torque / full-load torque at that rpm).

Usage: python3 tools/p08_gear_sweep.py <repo> [preset ...]
"""
import json, math, os, sys

REPO = sys.argv[1]
sys.path.insert(0, REPO)
from dieselsim.live import Adr011Grid, LiveEngine  # noqa: E402
from dieselsim.builder import load_engine_dir  # noqa: E402
load_engine_dir(os.path.join(REPO, "engines"))

DT = 1 / 60
PRESETS = sys.argv[2:] or ["hatch15", "crdi15", "crdi22", "truck127"]


def make(preset):
    gj = json.load(open(os.path.join(REPO, "web/app/public/grids", preset + ".json")))
    live = LiveEngine(Adr011Grid.from_json(gj), preset, "tc")
    live.T_coolant = 361.0          # warm, as the fixtures' warm drive
    live.T_oil = 373.0
    live.FRICTION_EVERY = 60        # measurement speed: friction once per simulated second (the app: every 6 frames)
    return live


def tmax(live, rpm):
    return live._perf(rpm, 1.0)["torque"]


def launch(preset, thr, secs):
    live = make(preset)
    gb, dl = live.dl.gb, live.dl
    shifts, last = [], gb.gear
    fuel_kg, t = 0.0, 0.0
    t50 = t100 = None
    for n in range(int(secs / DT)):
        live.throttle = thr if n * DT >= 0.5 else 0.0
        n_turb = dl.w_in * 60 / (2 * math.pi)
        rpm_before = live.rpm
        live.step(DT)
        t += DT
        fuel_kg += live.fuel_kg_h * DT / 3600
        kmh = dl.speed_kmh()
        if t50 is None and kmh >= 50: t50 = t
        if t100 is None and kmh >= 100: t100 = t
        if gb.gear != last:
            shifts.append((last + 1, gb.gear + 1, round(n_turb), round(rpm_before), round(kmh)))
            last = gb.gear
    km = dl.odo_m / 1000 if hasattr(dl, "odo_m") else live.odo_m / 1000
    return shifts, t50, t100, fuel_kg / 0.832 / max(km, 1e-9) * 100


def hold(live, v_kmh, secs, measure_from):
    """PI on the throttle to hold v_kmh; returns the means over the tail."""
    dl = live.dl
    i = 0.0
    acc = {"fuel": 0.0, "kmh": 0.0, "rpm": 0.0, "load": 0.0, "T": 0.0, "Tmax": 0.0, "thr": 0.0, "n": 0}
    for n in range(int(secs / DT)):
        e = (v_kmh - dl.speed_kmh()) / 10.0
        i = min(1.0, max(-1.0, i + e * DT * 0.8))
        live.throttle = min(1.0, max(0.0, 0.25 + 1.5 * e + i))
        live.step(DT)
        if n * DT >= measure_from:
            acc["fuel"] += live.fuel_kg_h; acc["kmh"] += dl.speed_kmh(); acc["rpm"] += live.rpm
            acc["load"] += live.load_eff; acc["T"] += live.torque; acc["Tmax"] += tmax(live, live.rpm)
            acc["thr"] += live.throttle; acc["n"] += 1
    k = acc.pop("n")
    m = {a: b / k for a, b in acc.items()}
    m["L100"] = m["fuel"] / 0.832 / max(m["kmh"], 1e-6) * 100
    m["reserve"] = 1 - m["T"] / max(m["Tmax"], 1e-6)
    return m


def cruise(preset, v_kmh):
    live = make(preset)
    gb = live.dl.gb
    m_auto = hold(live, v_kmh, 90, 60)
    auto_gear = gb.gear
    rows = {}
    gb.auto = False
    for g in range(gb.n):
        while gb.gear != g:
            if gb.shifting():
                live.step(DT); continue
            gb.request(1 if g > gb.gear else -1)
            live.step(DT)
        m = hold(live, v_kmh, 40, 25)
        ok = abs(m["kmh"] - v_kmh) < 1.5 and m["thr"] < 0.97 and m["rpm"] > 1.05 * live.spec.idle_rpm \
            and m["rpm"] < live.spec.rated_rpm * 1.02
        rows[g + 1] = (m, ok)
    return auto_gear + 1, m_auto, rows


if __name__ == "__main__":
    for p in PRESETS:
        live = make(p)
        s = live.spec
        print(f"\n=== {p}: {live.veh.name}; idle {s.idle_rpm:.0f}, rated {s.rated_rpm:.0f} rpm; "
              f"gears {live.veh.gears} x {live.veh.final}")
        rpms = [1000, 1250, 1500, 1750, 2000, 2500, 3000, 3500]
        print("  full-load torque: " + ", ".join(f"{r}: {tmax(live, r):.0f}" for r in rpms if r <= s.max_rpm))
        secs = 120 if p in ("truck127", "hd_i6", "v8hd") else 45
        for thr in (0.2, 0.35, 0.5, 0.75, 1.0):
            sh, t50, t100, l100 = launch(p, thr, secs)
            print(f"  launch at throttle {thr:.2f}: 0-50 {t50 and round(t50, 1)} s, 0-100 {t100 and round(t100, 1)} s; "
                  f"upshifts (gear, turbine rpm, engine rpm, km/h): "
                  + "; ".join(f"{a}>{b} {nt}/{ne} @{k}" for a, b, nt, ne, k in sh if b > a))
        speeds = (30, 50, 70, 90) if p in ("truck127", "hd_i6", "v8hd") else (30, 50, 80, 110)
        for v in speeds:
            ag, ma, rows = cruise(p, v)
            print(f"  cruise {v} km/h: schedule holds gear {ag} at {ma['rpm']:.0f} rpm, "
                  f"{ma['L100']:.2f} L/100 km, reserve {ma['reserve']:.0%}")
            best = min((r for r in rows.items() if r[1][1]), key=lambda r: r[1][0]["L100"], default=None)
            for g, (m, ok) in rows.items():
                mark = "  <- least fuel" if best and g == best[0] else ""
                print(f"      gear {g}: {m['rpm']:5.0f} rpm, {m['kmh']:5.1f} km/h, throttle {m['thr']:.2f}, "
                      f"load {m['load']:.2f}, reserve {m['reserve']:4.0%}, {m['L100']:6.2f} L/100 km"
                      f"{'' if ok else '  (cannot hold)'}{mark}")
