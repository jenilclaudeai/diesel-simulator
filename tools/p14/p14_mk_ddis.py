"""p14_ddis.json: the 1.3 DDiS with its plateau starting at 2,000 rpm (Maruti's quoted peak)."""
import json, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
c = {d['key']: d for d in json.load(open('p14_candidates.json'))}
out = []
for tag, extra in [("2000", {}), ("2000@vgt", {"vgt": True}),
                   ("2000@vgt0.08/15.5", {"vgt": True, "boost_map_rise": 0.08, "afr_limit": 15.5}),
                   ("2000@0.05/15.0", {"boost_map_rise": 0.05, "afr_limit": 15.0})]:
    d = dict(c['ddis13']); d.update(extra); d['plateau'] = [2000, 2500]; d['key'] = 'ddis13@' + tag
    out.append(d)
json.dump(out, open('p14_ddis.json', 'w'), indent=1)
print(len(out))
