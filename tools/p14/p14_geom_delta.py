"""Plateau-start % of cap: published-ish geometry (screen4) against the builder's
default geometry at the same tuning (screen1/screen2). Prints each and the worst.
usage: python3 p14_geom_delta.py <dir with screen1.json screen2.json screen4.json>"""
import json, os, sys
D = sys.argv[1]
lo = {}
for f in ("screen1.json", "screen2.json", "screen4.json"):
    for r in json.load(open(os.path.join(D, f))):
        if r["point"] == "plateau_lo" and "error" not in r:
            lo[(r["key"], r["variant"])] = 100 * r["torque"] / r["cap"]
HARD = {"b57": ("b57@0.08/16.0", "untuned"), "om642": ("om642@0.08/15.5", "untuned")}
worst = 0.0
for (k, v), x in sorted(lo.items()):
    if not k.endswith("@geom"):
        continue
    base = k[:-5]
    ref = HARD.get(base, (base, v))
    if ref not in lo:
        continue
    d = x - lo[ref]
    worst = max(worst, abs(d))
    print(f"{base:14s} {v:8s} default {lo[ref]:6.1f}  geometry {x:6.1f}  delta {d:+.1f}")
print(f"worst |delta| {worst:.1f} points")
