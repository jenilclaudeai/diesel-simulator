"""Write p14_retune.json: harder tuning for the three candidates that failed."""
import json, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
c ={d['key']: d for d in json.load(open('p14_candidates.json'))}
out = []
for k in ['ddis13', 'b57', 'om642']:
    for bmr, afr in [(0.08, 16.0), (0.08, 15.5), (0.05, 15.0)]:
        d = dict(c[k]); d['key'] = f"{k}@{bmr}/{afr}"; d['boost_map_rise'] = bmr; d['afr_limit'] = afr
        out.append(d)
d = dict(c['ddis13']); d['key'] = 'ddis13@vgt'; d['vgt'] = True; out.append(d)
d = dict(d); d['key'] = 'ddis13@vgt0.08/15.5'; d['boost_map_rise'] = 0.08; d['afr_limit'] = 15.5; out.append(d)
json.dump(out, open('p14_retune.json', 'w'), indent=1)
print(len(out))
