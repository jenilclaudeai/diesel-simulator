# STATUS history: Session 7 (2026-10-06)

Moved verbatim from `STATUS.md` at `a57a6fd`, its lines 2006-2292, by step A1 of
`reviews/PROPOSAL-modularize.md` (2026-10-28). **This is history, not the present**:
`STATUS.md` is. Struck-through text and in-place corrections are as they were written.
`python3 tools/check_verbatim_move.py history/` proves the copy.

<!-- verbatim: STATUS.md@a57a6fd 2006-2292 -->
**Session 7 (2026-10-06): FINDING-025, the spec's ambient reached no solve**
(#101, merged 2026-10-06 17:41 UTC):
- Found while reading the solver's inputs for Phase 7 (environment).
  `/spec` offers ambient pressure and temperature as primary fields, but
  `operating_point` used fixed defaults, 101325 Pa / 298 K. An edit to
  3000 m or 45 °C moved **0 of 8** Dyno outputs; passing them directly
  moved all 8. `thermal.ambient_p` was read nowhere.
- Fixed: None now means the spec's ambient, **except** in the fuel-limit
  chain's calibration, which stays at the rating's air (101325 Pa / 298 K,
  `engine.RATING_P_AMB`). The compressor point's inlet temperature is the
  spec's, returned as `T_in`.
- **Corrected in place:** the first fix also calibrated at the spec's air.
  Half load at 2000 m then got 13.5% more fuel and 4.6% more torque, which
  matches no real ECU. It was found while measuring for the Phase 7
  proposal and changed before merge.
  - Now the same pedal gives the same fuel in any air (uncompensated). At
    3000 m: 198 N·m (−12%), soot 2.9×. At 2000 m, half load: −6.2%.
- At standard ambient nothing changes: old and new code agree **bit for
  bit**, 20 of 21 replies by sha256 on all 10 engines. The 21st,
  `solve_cycle`, differs only by the added `T_in` key; its other 51 values
  are identical.
- So the grids were re-stamped `15593c2d` → `42da745d` → `f298469f`, with
  `tools/restamp_grids.py`'s proof, not rebuilt.
- `test_spec_ambient_reaches_the_solve`: 6 parts; baseline passes, 5 of 5
  mutants caught, including the first fix.
- Open, for Phase 7: keep the uncompensated ECU, or add a barometric
  derate (`cycle.fuel_smoke_limit` assumes 101325 Pa) or torque-based
  control? Details in `reviews/FINDING-025.md`.
- Also measured, for the proposal (crdi15, through the bridge):
  - Cetane 40 → 55 moves torque and BSFC under 0.3% and NOx by 4–8%. Its
    visible effects (hard starts, knock) are not modelled.
  - Final code, crdi15 2500 rpm full load (1500 rpm half load in
    brackets):
    - 2000 m: torque −6.7% (−6.2%), BSFC +7.2%, soot +88% (+54%);
    - −10 °C: torque +1.3% (+4.7%), soot −29%;
    - 40 °C: torque −0.4% (−1.5%), soot +12%.
  - *(Was, from the first fix: "−10 °C: soot −36%, NOx −27%; 2000 m at
    full load: soot ×2.9, BSFC +14%".)*

**Phase 7, step 3 of 7 (2026-10-07): the ECU knows absolute pressure**
(#107, branch `feat/ecu-absolute`; ADR-016 item 2):
- `spec.ecu_modern` (true by default; the NA singles and any NA builder
  engine are false, i.e. mechanical). A new `/spec` field: 189 fields, 181
  editable.
- **Off the rating's air only** (`engine.operating_point`):
  - the boost target becomes the rating's absolute pressure (MAP), capped
    at the compressor's map limit `turbo.pr_max_ref`;
    **Corrected 2026-10-08 (FINDING-026):** only where EGR is off. The cap
    comes before `cycle.run`'s EGR raise, so at part load the VGT chases a
    target above the limit and jams on its minimum: at Leh, light load,
    torque fell up to 76% (v8hd 1959/0.2). The test checked the limit only
    at full load, where EGR is zero.
  - the smoke limiter caps each cycle's fuel at the air the previous cycle
    trapped / `afr_limit` (`cycle.run(smoke_afr=)`), so it settles with the
    turbo inside one solve.
- A first version trimmed fuel and re-solved. On a small saturated turbo
  that chased its own tail (less fuel, less exhaust energy, less boost):
  after 2 re-solves hatch15 at Leh was still smoky (AFR 15.33 against
  16.0). It was replaced before commit.
- At the rating's air nothing moves, by construction: old and new code
  agree **bit for bit, 21 of 21 replies on all 10 engines**. Grids
  re-stamped `f298469f` → `0f1cc94c` with `tools/restamp_grids.py`'s proof.
- Converged, old ECU against modern:

  | case | old | modern |
  |---|---|---|
  | crdi15 full load, Leh | 198.8 N·m, soot 0.054 | 210.3 N·m, soot 0.036 |
  | hatch15 full load, Leh (sea level 260.1) | 238.4 N·m at AFR 14.4, turbo 287k rpm | 184.9 N·m at AFR 16.0 (its limit), 243k rpm |
  | crdi15 2800/0.3, 90 kPa (sea level 54.77) | 59.25 (+8.2%) | 53.78 (−1.8%) |
  | the mechanical single, Leh | 15.24 | 15.24 (unchanged, as designed) |

- `test_modern_ecu_knows_absolute_pressure`: 6 parts. It inlines hatch15's
  brochure numbers, so it runs under Pyodide (no `engines/` there).
  Baseline passes; 6 of 6 mutants caught. Getting there took two fixes,
  recorded here:
  - The first mutant run's baseline failed, so the run was void and
    redone. A strengthened part had moved a reference fuel.
  - The light-load part couldn't fail on fast solves (FINDING-013), so it
    is converged now, and the no-absolute-target mutant fails it.
- The count guards (spec-meta units, round trip) moved 188 → 189 for the
  new field, deliberately.
- CI on #107: 9 of 9, Pyodide 67/0/2/13 (the new test runs unmodified
  there). But **Python 3.10 took 27.0 min against its 30-minute limit**.
  - Over 24 passing runs it had taken 11.2–22.9 min; this PR's tests add
    ~4 min, and runner speed varies ~2×.
  - So the physics job's limit is now **45** (as #100 did for Pyodide,
    which has since run up to 32.9 min, over its old 30). Python 3.12 has
    reached 22.8 min.

**Phase 7, step 1 of 7 (2026-10-07): the environment presets**
(#105, merged 2026-10-07 08:20 UTC; ADR-016's order):
- `dieselsim/environment.py`: five real places, each the air and the fuel
  sold there, with sources.
  - Standard (25 °C, sea level, ISO 8178's 10.71 g/kg).
  - Jaisalmer in May (42 °C, IS 1460 summer diesel, CFPP 18 °C).
  - Rovaniemi on a January morning (−20 °C, EN 590 arctic class 2, −32 °C).
  - Leh in June (3500 m = 657.6 hPa ICAO, IS 1460 winter, 6 °C).
  - Mumbai in July (29 °C, 85% RH).
  - Two climate details are marked "approx." in the file rather than given
    false precision.
- A preset reaches the solver only as spec overrides (ambient p and T,
  cetane). So the module is in `GRID_HASH_EXCLUDES`: the grid hash is still
  `f298469f`, and the existing exclusion test proves no cell solve loads it.
- `runtime_info` carries the five (typed `EnvironmentPreset` in
  `solver-port.ts`). There's no new port method.
- crdi15 2500/1.0, against standard air's 225.9 N·m:
  - Leh 193.0 (−14.6%; AFR 29.4 → 19.2);
  - Rovaniemi 228.4;
  - Jaisalmer 222.7 (exhaust +22 K);
  - Mumbai 225.5.
- Tests:
  - `test_environment_presets_reach_the_solve`, 10 parts, each preset
    solved (FINDING-025's lesson). Baseline passes; 7 of 7 mutants caught,
    none by error. One first crashed with a KeyError, which counts as
    broken, so the test now reads the field defensively.
  - The hash guard catches the exclusion being removed (`3d33b535` vs
    `f298469f`).
  - Round trip +1 (the presets arrive from a real Pyodide worker); its
    mutant is caught.
- Humidity and CFPP are carried, not yet used: steps 5 and 6.

**Phase 7, step 2 of 7 (2026-10-07): the environment on the solving pages**
(#106: built as a draft stacked on #105, retargeted to `main` after #104 and
#105 merged at 08:20 UTC, then marked ready. Its merge into `main` differed
from the CI-tested tree only in #104's four docs files, with 0 code paths;
`main` was merged in and CI re-ran on the real base):
- A picker on Dyno, Grid, Cycle, Sweep and Durability shows the chosen
  place's numbers and fuel. It's kept across reloads, like the edits.
- On the part-load pages it carries FINDING-013's caveat. At Leh the
  Cycle page's default point (2700/0.6, a fast solve) shows net IMEP
  *rising*, 11.07 → 12.07 bar, while peak pressure falls 140.1 → 108.5
  bar: the fast-solve gap plus the pressure-ratio boost control (the
  proposal's measurements 2 and 3). Step 3 addresses the latter.
- `weather/env-choice.ts`: `withEnvironment(ref, overrides)` puts the
  environment *under* the page's own overrides, so an explicit spec edit
  wins. Standard air adds nothing, so its references, results and cache
  keys are unchanged. `/spec` and "Drive it" stay at standard air
  (ADR-016 item 1).
- The out-of-date banner now counts a change of environment.
- Found on the way: `.gitignore` ignores every `env/` directory
  (virtualenvs). A first `web/app/src/app/env/` would never have been
  committed, so the directory is `weather/`.
- Tests:
  - units 109 (+5), also without `physics-version.ts`; 6 of 6 mutants
    caught by assertions;
  - e2e:cycle 9 (+1): Leh marks the result out of date, and solved again
    it is native Python's for the plateau preset (108.5 bar, IMEP 12.07);
    with the page ignoring the environment, exactly that check fails
    (140.1 bar shown against native's 108.5).
  - **Missed, and caught by CI (corrected in place):** I ran only the
    Cycle and Spec e2e locally. CI's Dyno and Grid e2e failed: each
    "engine list comes from the solver" check read every `<option>` on the
    page, and the picker added the five places. Both are now scoped to
    `select:not(.env)`. Locally, every e2e on a page with the picker
    passes: dyno 15, grid 9, cycle 9, sweep 6, durability 5, custom 7,
    spec 12.

**Known defects and follow-ups** (none blocking):
- The dev preset `single` sags on the tractor's torque converter in
  "Auto". It is recorded as KNOWN in the suite. The exact fix is to size
  each converter from its engine's own full-load torque at stall; that
  touches every engine and the live fixtures.
- The V8 fires evenly every 90°. With no separate cylinder banks, a
  cross-plane V8's per-bank "burble" is absent.
- `truck127`'s grid has 13 unsettled cells and `v8hd`'s has 8,
  period-averaged (FINDING-013). Look only if they show on the dials.
- Live friction costs a whole frame every 6th frame on a low-end phone (6×
  throttling): decide after the Android check.
- Older follow-ups are in "Next actions" at the end of this file.

**Repository:**
- **2026-10-06, 06:30 UTC: #96 merged (`ee84ff5`), landing #96–#99 on
  `main`. All of Phase 6 stage 1 and REVIEW-008, #89–#99, is on `main`.**
  Checked by content: `main` differs from #99's tested tip `bc35ff7` only
  in `STATUS.md` (1 file, +15/−1). CI on `main` passed 9 of 9, and Pages
  deployed it. #96's run before the merge (`76f6617`) also passed 9 of 9;
  Pyodide reported 64 passed, 0 failed, 2 known, 13 skipped.
- **2026-10-06, 17:39–17:42 UTC: #100, #101 and #102 merged, in that
  order.** `main` (`1ed9f11`) has exactly the tree simulated from the
  three tested PR heads before the merge (`2d99396f`, 0 lines differing).
  Against #101's tested tip it differs only in #102's two docs files.
  - Pages deployed it. The live site serves the re-stamped grids
    (`grid_hash` `f298469f`).
  - The CI runs on the first two merges ended *cancelled*: superseded by
    the next merge (memory: utc-timestamps).
  - CI on `main` (`1ed9f11`, run 37505597658): **9 of 9 green**, every job
    read. Pyodide: 65 passed, 0 failed, 2 known, 13 skipped.
  - **Pyodide took 30.3 min: it would have been cancelled under the old
    30-minute limit**, so #100 was needed. The Python jobs are close too:
    3.10 took 22.6 min and 3.12 21.4 min, against a 30-minute limit
    (REVIEW-008 M-4 set it). If either passes ~26 min, raise it as #100 did
    (measure 20 runs first).
  - No PR is open. Remote branches safe to delete: `ci/pyodide-timeout`,
    `fix/spec-ambient`, `docs/phase7-proposal`, plus those listed below.
- Earlier (kept as written):
- **Open: #100, Pyodide's CI limit 30 → 45 min.** Measured over the last
  20 passing CI runs: Pyodide took 12.2–27.7 min, and 12 of the 20 took
  26.4–27.7 min, within 2.3–3.6 min of the old limit. Python 3.10 peaks at
  21.1 min (limit 30), so it is unchanged. The 16 cancelled runs among them
  all ended within 4.8 min: superseded, not timeouts.
- Earlier the same morning (kept as written):
- **2026-10-06, 05:32–05:36 UTC: #89–#95 merged into `main`; #96 left open
  (the owner saw failed checks).** #97, #98 and #99 still targeted
  `feat/sweep-page`, so they merged **into #96's branch, not `main`**
  (memory: stack-merge-trap). Nothing is lost: `feat/sweep-page` at
  `10e8c01` has the same tree as #99's tested tip `bc35ff7` (0 lines
  differ). **Merging #96 brings #96–#99 to `main` together**; then check
  `main` against `bc35ff7` by content.
  - The "failed checks": #96's last run on `195e54c` passed 9 of 9, but a
    duplicate run on the same commit was *cancelled*, and GitHub draws a
    cancelled check as a red ✗. The merges at 05:35 then pushed
    `10e8c01` and cancelled two more runs. The fresh run on this branch
    is the one to read.
- #86, #87 and #88 merged 2026-10-05; `main` equals the tested top
  (`8040506`), 0 lines differ. Pages deployed it.
- *(Superseded by the bullet above.)* Open, one stack, merge in order: **#89** (docs, REVIEW-007, the Phase 6
  proposal) ← #90 (solve_cycle) ← #91 (FINDING-024) ← #92 (cycle page) ←
  #93 (durability call) ← #94 (spec editor) ← #95 (edits everywhere,
  banner) ← #96 (sweep) ← #97 (durability page) ← #98 (schematics) ← #99
  (REVIEW-008 and its fixes). Each targets the branch below.
  - CI (2026-10-06): after the M-1 fix, #89–#94, #97 and #99 were 9 of 9.
    #95, #96 and #98 each had Python 3.10 cancelled at the job's 20-minute
    limit (REVIEW-008 M-4). The limit is now 30 min on #90, merged forward.
    On the re-run, 5 physics runs took 20m40s–20m53s and passed. Then
    #89–#95, #98 and #99 were 9 of 9. #96 hit a race in an e2e check
    (fixed on #94 and merged forward), and #97 a numpy load flake (N-6).
    **Final: all 11 PRs, #89–#99, are 9 of 9 green** (2026-10-06). Pyodide
    on #99: 64 passed, 0 failed, 2 known, 13 skipped. Physics jobs now take
    9–21 min.
  - *(Was: "Open: #89 (docs: …)".)*
- Remote branches: `main`, the merged `docs/pages-live`,
  `docs/grid-build-plan` and `fix/b04-stop-eta` (safe to delete), and
  `fix/steady-state-controllers`. Keep the last one: it is the only copy of
  the FINDING-013 option A experiment.
- The owner merges PRs. Stacked PRs: retarget each child to `main` after
  its parent merges, then check `main` by content (memory:
  stack-merge-trap).

**Tests, read from finished runs** (2026-10-06, on #99's tree locally unless marked; *was:* CI on #88,
2026-10-05):

| suite | result |
|---|---|
| `python3 tests/test_physics.py` | 90 passed, 0 failed, 3 known (CI on #128 `d075312`, = `main` `196f8d3`, 2026-10-14, 3.10 and 3.12). *Was (`3047f95`):* 87 / 0 / 3; *(#115's tree, with scipy):* 85 / 0 / 3; *(humidity's tree):* 82 / 0 / 3; *(#110):* 81 / 0 / 3; *(#107):* 80 / 0 / 3; *(#105):* 79 / 0 / 3; *(#101's final tree):* 78 / 0 / 3; *(#101's first commit):* 78 / 0 / 3; *(#99):* 77 / 0 / 3; *(#88):* 71 / 0 / 3 |
| Pyodide suite | 73 passed, 0 failed, 2 known, 17 skipped (CI on #128 `d075312`; 48.5 min of its 60). *Was (`3047f95`):* 71 / 0 / 2 / 16, 47.6 min (runner-dependent: 20–49 min, session 9); *(#115):* 70 / 0 / 2 / 15, 45.6 min; *(#114):* 69 / 0 / 2 / 13; *(#110):* 68 / 0 / 2 / 13; *(#107):* 67 / 0 / 2 / 13; *(#101's final tree, `b6ea065`):* 65 / 0 / 2 / 13; *(#99):* 64 / 0 / 2 / 13; *(#88):* 59 / 0 / 2 / 12 |
| `tools/fixtures/gen_fixtures.py --check` | 7 modules current |
| `tools/audit_dead_signals.py` | 0 dead, 2 frozen (known), 0 tiny |
| `web/physics npm test` | 5 + 51 + 11 + 11 = 78 (CI on #128; +1, the sound's balance check). *Was (`3047f95`):* 5 + 51 + 10 + 11 = 77. *Was (#115, +5 the weather drive):* 5 + 41 + 10 + 11 = 67; *before:* 5 + 36 + 10 + 11 = 62 |
| `web/solver npm test` | cache 20, live-grid scheduler 15, round trip 30 (#115: +3 scheduler, the weather pieces). *Was:* scheduler 12 (#105); round trip 29 |
| `web/app npm test` | 130 unit tests (CI on `main` `3047f95`, run before `physics-version.ts` exists). *Was:* 119 (#115's tree), 114 (humidity's tree), 112 (D's tree), 109 (#106), 104 (#103), 101. `check:labels` 6 of 10 templates |
| e2e (`web/app`) | (CI on #128) dyno 15, grid 9, drive 10, sound 6, enjoy 28, custom 7, cycle 11, spec 18, sweep 6, durability 5. *Was (CI on `main` `3047f95`):* dyno 15, grid 9, drive 10, sound 6, enjoy 25 (+B-05/B-06's two checks), custom 7, cycle 11, spec 18, sweep 6, durability 5. *Was (CI on #115):* dyno 15, grid 9, drive 9 (*was* 7; +Leh against native, +Leh slower), sound 6, enjoy 22 (*was* 21; +the place on the start screen), custom 7, cycle 11 (*was* 10, +the humidity note; 9, +FINDING-026's thin-air note; 8, +the environment check, #106), spec 14 (*was* 13, +the humidity field; 12, +the thin-air notes; 11, +the reload check, #103), sweep 6, durability 5 |

CI runs all of them except the manual `web/solver npm run test:live-real`.
Its jobs: physics on Python 3.10 and 3.12, Pyodide, fixtures, solver, web
app, web e2e, grid e2e, and custom-engine e2e.

**This Mac** (see Housekeeping):
- Node 22.23.3 at `~/.cache/dieselsim/node-v22.23.3-darwin-arm64/bin`
  (prepend to PATH).
- scipy in `~/.cache/dieselsim/venv/bin/python`.
- Chrome at `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
  (`CHROME_PATH` for e2e).
- The CoreAudio output is stuck, so the e2e uses Chrome's fake audio sink.
- A LAN dev server needs `npm start -- --host 0.0.0.0 --ssl` for sound
  (secure context). The live site makes it unnecessary.

**First thing next session:** read this section. Check the bug sheet for
new rows and the owner's re-check of B-01/B-02 (it closes Phase 5). Then
continue Phase 7 in ADR-016's order, from where the "Phase 7" item above
says it stands. The grid-build plan, and v2, wait until v1 is complete.
*(Was, later in session 7: "…the answers to Phase 7's six decisions (item
3b) and the "Feat Prop" questions (item 6). Then write the ADR(s) for those
decisions and start Phase 7…" — done: ADR-016.)* *(Was, in session 7:
"Check whether #100 and #101 merged, and that
`main` matches by content. Check the bug sheet for new rows, the owner's
re-check of B-01/B-02, and the answers to items 6 and 7. Then write the
Phase 7 proposal …")* *(Was, at the end of session 6: "Check which of #89–#99
merged, and that `main` matches by content. Check the bug sheet for new rows
and the owner's re-check of B-01/B-02. Then plan Phase 7 (environment and
projects; REVIEW-008 m-3 belongs there).")* *(Was, earlier in session 6: "…check the bug sheet for new
rows and the owner's re-check of B-01/B-02; ask for the grid-build
decision.")* *(Was, in session 6: "check whether #86 merged, and ask the owner
for the Android bug sheet's link. Verify each bug, fix them, then write
REVIEW-007 and close Phase 5.")*

---

