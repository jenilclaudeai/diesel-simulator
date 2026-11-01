# tools/p14 — the screen behind `reviews/PROPOSAL-P14.md`

Can `builder.py` make real diesel engines' published numbers? Each script is
standalone, numpy only, run from the repo root. Generated files land here and are
gitignored.

**Never move `p14_candidates.json`, or one engine of it, into `engines/`.**
`load_engine_dir` registers every file there, and `build_live_grids.py` with no
arguments builds them all.

```bash
python3 tools/p14/p14_mk_all.py .                                  # p14_all.json: 5 roster controls + 14 candidates
python3 tools/p14/p14_screen.py . tools/p14/p14_all.json tools/p14/screen1.json   # 108 solves, ~2 min on 8 cores
python3 tools/p14/p14_table.py tools/p14/screen1.json tools/p14/p14_all.json
python3 tools/p14/p14_mk_retune.py && python3 tools/p14/p14_screen.py . tools/p14/p14_retune.json tools/p14/screen2.json
python3 tools/p14/p14_mk_ddis.py   && python3 tools/p14/p14_screen.py . tools/p14/p14_ddis.json   tools/p14/screen3.json
python3 tools/p14/p14_mk_geom.py   && python3 tools/p14/p14_screen.py . tools/p14/p14_geom.json   tools/p14/screen4.json
python3 tools/p14/p14_geom_delta.py tools/p14                     # geometry's effect on the plateau start
python3 tools/p14/p14_build_estimate.py                            # the ten's build time, from P09's log x R5
python3 tools/p14/p14_ddis_sweep.py .                              # the 1.3 DDiS's fuel swept at 2,000 rpm
python3 tools/p14/p14_sound.py .                                   # needs p14_all.json; I3/I5/V6 through LiveSynth
```

The check is `test_roster_engines_make_their_numbers`'s: at the plateau's start
>= 95% of the rating cap, at rated speed within 3% of the brochure power, fresh
engine per point, 9 cycles. `p14_screen.py` adds the roster's usual tuning
(`boost_map_rise` 0.12, `afr_limit` 16 LD / 18 HD) as a second variant unless the
entry already sets `boost_map_rise`.

**The candidates' figures are from memory and not yet sourced**, and so is the
geometry in `p14_mk_geom.py`, which is a sensitivity check only. The build sources
every engine from the maker's sheet before anything goes into `engines/`.
