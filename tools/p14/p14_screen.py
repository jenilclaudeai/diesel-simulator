"""P14 screen: can builder.py make real engines' published numbers?

The roster test's check (tests/test_physics.py::test_roster_engines_make_their_numbers):
plateau start >= 95% of the rating cap, rated power within 3%. Plus the plateau's
end. Fresh engine per point, 9 cycles. Untuned and with the roster's tuning
(boost_map_rise 0.12, afr_limit 16 LD / 18 HD; ROSTER.md).

usage: python3 p14_screen.py <repo> <candidates.json> <out.json> [keys...]
"""
import json, os, sys, time, traceback
from multiprocessing import Pool

REPO, CANDS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
ONLY = set(sys.argv[4:])
sys.path.insert(0, REPO)


def variants(d):
    yield "untuned", {}
    if d.get("turbocharged", True) and "boost_map_rise" not in d:
        hd = d["displacement"] / d["n_cyl"] > 1.2
        yield "tuned", {"boost_map_rise": 0.12, "afr_limit": 18.0 if hd else 16.0}


def solve(task):
    d, vname, extra, label, rpm = task
    from dieselsim.builder import from_dict
    from dieselsim.engine import DieselEngine
    t0 = time.time()
    try:
        spec = from_dict({**{k: v for k, v in d.items() if k != "control"}, **extra})
        e = DieselEngine(spec=spec)
        op = e.operating_point(float(rpm), load=1.0, n_cycles=9)
        cap = e.torque_cap(rpm)
        r = dict(torque=op.torque, cap=cap, power_kW=op.power / 1e3,
                 p_max_bar=op.p_max / 1e5, afr=op.cycle.afr, boost=op.boost_pr,
                 bsfc=op.bsfc, bmep_bar=op.bmep / 1e5, bore_mm=spec.geom.bore * 1e3,
                 idle=spec.idle_rpm)
    except Exception as ex:
        r = dict(error=repr(ex), tb=traceback.format_exc()[-600:])
    r.update(key=d["key"], variant=vname, point=label, rpm=rpm, secs=time.time() - t0)
    return r


def main():
    cands = json.load(open(CANDS))
    tasks = []
    for d in cands:
        if ONLY and d["key"] not in ONLY:
            continue
        lo, hi = d["plateau"]
        for vname, extra in variants(d):
            for label, rpm in (("plateau_lo", lo), ("plateau_hi", hi), ("rated", d["rated_rpm"])):
                tasks.append((d, vname, extra, label, rpm))
    t0 = time.time()
    with Pool(int(os.environ.get("JOBS", "8"))) as p:
        res = p.map(solve, tasks, chunksize=1)
    json.dump(res, open(OUT, "w"), indent=1)
    print(f"{len(tasks)} solves in {time.time() - t0:.0f} s wall")


if __name__ == "__main__":
    main()
