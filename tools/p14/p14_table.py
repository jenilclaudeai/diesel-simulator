"""Tabulate p14_screen.py output: one row per engine and variant.
usage: python3 p14_table.py <screen.json> <candidates.json>"""
import json, sys
res = json.load(open(sys.argv[1]))
cands = {d["key"]: d for d in json.load(open(sys.argv[2]))}
rows = {}
for r in res:
    rows.setdefault((r["key"], r["variant"]), {})[r["point"]] = r
print("| engine | variant | lo % cap | hi % cap | rated kW / want | p_max bar | AFR lo | pass |")
print("|---|---|---|---|---|---|---|---|")
npass = {}
for (k, v), pts in rows.items():
    d = cands[k]
    if any("error" in p for p in pts.values()):
        err = next(p["error"] for p in pts.values() if "error" in p)
        print(f"| {k} | {v} | ERROR {err[:80]} |")
        continue
    lo, hi, ra = pts["plateau_lo"], pts["plateau_hi"], pts["rated"]
    flo = lo["torque"] / lo["cap"]
    fhi = hi["torque"] / hi["cap"]
    pr = ra["power_kW"] / d["peak_power"]
    pmax = max(p["p_max_bar"] for p in pts.values())
    ok = flo >= 0.95 and abs(pr - 1) <= 0.03
    npass.setdefault(k, False)
    npass[k] |= ok
    print(f"| {k} | {v} | {100*flo:.1f} | {100*fhi:.1f} | {ra['power_kW']:.1f} / {d['peak_power']} ({100*pr:.1f}%) "
          f"| {pmax:.0f} | {lo['afr']:.1f} | {'yes' if ok else 'no'} |")
c = [k for k in npass if not k.startswith("CTL_")]
print(f"\ncandidates passing in some variant: {sum(npass[k] for k in c)} of {len(c)}; "
      f"controls passing: {sum(npass[k] for k in npass if k.startswith('CTL_'))} of "
      f"{sum(1 for k in npass if k.startswith('CTL_'))}")
print("max solve secs:", round(max(r["secs"] for r in res), 1))
