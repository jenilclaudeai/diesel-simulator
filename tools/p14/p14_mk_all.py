"""p14_all.json: the five shipped roster engines as controls (keys CTL_<key>,
as shipped, tuning included), then the candidates. usage: python3 p14_mk_all.py <repo>"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ctl = []
for k in ['hatch15', 'crdi22', 'truck127', 'v8hd', 'single10']:
    d = json.load(open(os.path.join(sys.argv[1], 'engines', k + '.json')))
    d['key'] = 'CTL_' + k
    d['control'] = True
    ctl.append(d)
cands = json.load(open(os.path.join(HERE, 'p14_candidates.json')))
json.dump(ctl + cands, open(os.path.join(HERE, 'p14_all.json'), 'w'), indent=1)
print(len(ctl) + len(cands))
