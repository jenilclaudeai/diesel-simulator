"""p14_geom.json: candidates with approximate published bore x stroke and CR.
FROM MEMORY, NOT SOURCED: a sensitivity check only (does the pass survive real
geometry?), never figures to build from."""
import json, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
c = {d['key']: d for d in json.load(open('p14_candidates.json'))}
GEOM = {  # bore mm, stroke mm, CR
    "vw19tdi": (79.5, 95.5, 19.5), "mhawk22": (85.0, 96.0, 16.5), "gd28": (92.0, 103.6, 15.6),
    "duratorq32": (89.9, 100.8, 15.7), "b57": (84.0, 90.0, 16.5), "om642": (83.0, 92.0, 15.5),
    "cummins59": (102.0, 120.0, 17.5), "cummins67": (107.0, 124.0, 17.3), "duramax66": (103.0, 99.0, 16.0),
    "powerstroke73": (104.4, 106.2, 17.5)}
HARD = {"b57": (0.08, 16.0), "om642": (0.08, 15.5)}
out = []
for k, (b, s, cr) in GEOM.items():
    d = dict(c[k]); d['key'] = k + '@geom'; d['stroke_bore'] = round(s / b, 3); d['compression_ratio'] = cr
    if k in HARD:
        d['boost_map_rise'], d['afr_limit'] = HARD[k]
    out.append(d)
json.dump(out, open('p14_geom.json', 'w'), indent=1)
print(len(out))
