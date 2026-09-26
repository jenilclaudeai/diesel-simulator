"""
Re-check the validation table in PROJECT_CONTEXT.md section 1.5 on the
current tree (Phase 1 exit criterion: "the validation table still holds").

hd_i6, fresh engine per point, n_cycles 9 -- the way the dyno page and the
regression suite solve. Prints each row next to the documented value and the
real-engine band.

Run:  python3 tools/validate_table.py            (sweeps, ~2 min on 6 cores)
      python3 tools/validate_table.py --aged     (+ the 12,000 h durability
                                                  paragraph, ~15-25 min)
"""
import math
import os
import sys
from multiprocessing import get_context

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dieselsim.engine import DieselEngine  # noqa: E402

P = "hd_i6"
R_AIR = 287.0


def solve(task):
    rpm, load = task
    e = DieselEngine(preset=P)
    op = e.operating_point(float(rpm), load=load, n_cycles=9)
    g = e.spec.geom
    v_cyl = g.displacement / g.n_cyl
    # referenced to intake-manifold density, as usual for a boosted engine
    # (against ambient density hd_i6 at rated reads 2.74 -- the boost ratio)
    st = op.cycle.state
    ve = op.cycle.m_air_trapped / (st["p_int"] / (R_AIR * st["T_int"]) * v_cyl)
    return dict(rpm=rpm, load=load, torque=op.torque, power=op.power, bmep=op.bmep,
                bsfc=op.bsfc, pmax=op.p_max, fmep=op.fmep, eta_mech=op.eta_mech,
                ve=ve, nox=op.nox_g_kwh, soot=op.soot_g_kwh, blowby=op.blowby_lpm,
                q_wall=op.cycle.q_wall_frac)


def aged(_):
    e = DieselEngine(preset=P)
    log = e.durability_run(12000.0, step_h=500.0, verbose=False)
    return log


def row(name, sim, doc, band, ok):
    print(f"| {name:26} | {sim:24} | {doc:22} | {band:12} | {'yes' if ok else '**NO**':6} |")


def main():
    s = DieselEngine(preset=P).spec
    speeds = list(range(800, int(s.max_rpm) + 1, 50))
    tasks = [(r, 1.0) for r in speeds] + [(r, l) for r in range(1000, 1801, 200)
                                         for l in (0.5, 0.6, 0.7, 0.8, 0.9)]
    with get_context("spawn").Pool(min(6, os.cpu_count() or 1)) as pool:
        res = pool.map(solve, tasks)
        log = pool.apply_async(aged, (None,)) if "--aged" in sys.argv else None
        full = [x for x in res if x["load"] == 1.0]
        pk = max(full, key=lambda x: x["torque"])
        rated = next(x for x in full if x["rpm"] == int(s.rated_rpm))
        lug = next(x for x in full if x["rpm"] == 1000)
        best = min((x for x in res if x["torque"] > 0), key=lambda x: x["bsfc"])
        print(f"{P} on this tree (fresh engine per point, n_cycles 9)\n")
        print("| Quantity | Simulated now | Documented | Real HD diesel | in band |")
        print("|---|---|---|---|---|")
        row("peak torque", f"{pk['torque']:.0f} N·m @ {pk['rpm']} rpm", "2310 N·m @ 1700 rpm",
            "2000–2500", 2000 <= pk["torque"] <= 2500)
        row("rated power", f"{rated['power'] / 1e3:.0f} kW @ {rated['rpm']} rpm", "432 kW @ 1800 rpm",
            "350–450", 350e3 <= rated["power"] <= 450e3)
        row("peak BMEP", f"{pk['bmep'] / 1e5:.1f} bar", "22.8 bar", "20–24",
            20e5 <= pk["bmep"] <= 24e5)
        row("best BSFC", f"{best['bsfc']:.0f} g/kWh @ {best['rpm']}/{best['load']}", "213 g/kWh",
            "190–215", 190 <= best["bsfc"] <= 215)
        pmax = max(x["pmax"] for x in full)
        row("peak cylinder pressure", f"{pmax / 1e5:.0f} bar", "176 bar", "160–200",
            160e5 <= pmax <= 200e5)
        row("FMEP at rated", f"{rated['fmep'] / 1e5:.2f} bar", "1.08 bar", "0.9–1.5",
            0.9e5 <= rated["fmep"] <= 1.5e5)
        row("mechanical efficiency", f"{100 * rated['eta_mech']:.0f}% @ rated", "95% @ rated", "88–95",
            0.88 <= rated["eta_mech"] <= 0.955)
        row("volumetric efficiency", f"{rated['ve']:.2f}", "1.19", "1.1–1.3", 1.1 <= rated["ve"] <= 1.3)
        row("engine-out NOx", f"{rated['nox']:.1f} rated, {lug['nox']:.1f} lugging (1000)",
            "4.5 rated, 20 lugging", "4–20", 4 <= rated["nox"] <= 20)
        row("engine-out soot", f"{rated['soot']:.3f} g/kWh", "0.05 g/kWh", "0.02–0.08",
            0.02 <= rated["soot"] <= 0.08)
        row("blow-by, new", f"{rated['blowby']:.1f} L/min", "11.8 L/min", "8–20", 8 <= rated["blowby"] <= 20)
        row("wall heat loss", f"{100 * rated['q_wall']:.0f}% of fuel energy", "19%", "15–25",
            0.15 <= rated["q_wall"] <= 0.25)
        if log is not None:
            L = log.get()
            a, b = L[0], L[-1]
            life = max(x["health"] for x in L)
            print(f"\nOver 12,000 h (step 500 h; rated point): power {100 * (b['power'] / a['power'] - 1):+.1f}%, "
                  f"BSFC {100 * (b['bsfc'] / a['bsfc'] - 1):+.1f}%, blow-by {a['blowby']:.1f} -> "
                  f"{b['blowby']:.1f} L/min, oil soot peak {max(x['oil_soot'] for x in L):.1f}%, "
                  f"life consumed {life:.0f}%")
            print("documented: power -5%, BSFC +6%, blow-by 11.8 -> 18 L/min, "
                  "oil soot 0 -> 2.8% per 500 h drain, life consumed ~20%")


if __name__ == "__main__":
    main()
