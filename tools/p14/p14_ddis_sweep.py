"""Can the 1.3 DDiS make 190 N.m at 2,000 rpm at all? Sweep fuel directly
(bypassing the calibration chain) and print torque, AFR, boost, p_max.
usage: python3 p14_ddis_sweep.py <repo>"""
import json, os, sys
sys.path.insert(0, sys.argv[1])
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
base = {d['key']: d for d in json.load(open(os.path.join(HERE, 'p14_candidates.json')))}['ddis13']
VARIANTS = {"as quoted (wastegate)": {}, "vgt, 0.08/15.5": {"vgt": True, "boost_map_rise": 0.08, "afr_limit": 15.5}}


def run(args):
    vname, f = args
    from dieselsim.builder import from_dict
    from dieselsim.engine import DieselEngine
    d = dict(base); d.update(VARIANTS[vname]); d['plateau'] = [2000, 2500]
    e = DieselEngine(spec=from_dict(d))
    raw = e.fuel_limit_raw(2000.0)
    op = e.operating_point(2000.0, fuel_mg=f, n_cycles=9, load_est=1.0, warm_start=False)
    return vname, f, raw, op.torque, op.cycle.afr, op.boost_pr, op.p_max / 1e5, op.T_exh


if __name__ == "__main__":
    tasks = [(v, f) for v in VARIANTS for f in (14, 16, 18, 20, 22, 24, 26)]
    with Pool(8) as p:
        for v, f, raw, T, afr, pr, pm, tx in p.map(run, tasks, chunksize=1):
            print(f"{v:24s} fuel {f:4.1f} mg (raw limit {raw:4.1f})  {T:6.1f} N.m  AFR {afr:5.1f}  "
                  f"boost {pr:4.2f}  p_max {pm:5.1f} bar  T_exh {tx:5.0f} K")
