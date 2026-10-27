# STATUS history: Session 5 (2026-09-26 to 2026-10-05)

Moved verbatim from `STATUS.md` at `a57a6fd`, its lines 2517-3276, by step A1 of
`reviews/PROPOSAL-modularize.md` (2026-10-28). **This is history, not the present**:
`STATUS.md` is. Struck-through text and in-place corrections are as they were written.
`python3 tools/check_verbatim_move.py history/` proves the copy.

<!-- verbatim: STATUS.md@a57a6fd 2517-3276 -->
## Session 5, parts 12–19 (2026-09-30 to 2026-10-05): the detail

*(Moved here from the top of this file when it was condensed; the text is
unchanged.)*

**Phase:** 1, 2, 3 and **4 exit-ready** (REVIEW-003 to -006). The owner signed
off the sound by ear on 2026-09-30 ("Yes it sounds right to me").
- FINDING-022 is fixed (option A, #64).
- ~~Still waiting on the owner: an option for FINDING-023 (cold slap), a model
  improvement for later that needs its own ~70 min grid rebuild;~~
- **Decided 2026-09-30 (part 12):**
  - FINDING-023 **option A**: slap from a temperature-dependent clearance;
  - **a ramp-height parameter** separate from `ramp_fraction` (REVIEW-003
    m-5), in the **same** rebuild of all 8 grids, judged by ear;
  - live friction's cost on low-end phones **waits for the real Android
    check**. *(Correction: the option I offered, "compute it less often: 20
    Hz instead of 60", was wrong: live friction already runs every 6th
    frame, 10 Hz (`LiveEngine.FRICTION_EVERY`). So the 6× cost is a whole
    frame every 6th frame, not every frame. The owner chose to wait, so
    nothing was built on it.)*;
  - OPEN-B accepted as **ADR-013** (personas are review lenses).
- **Decided 2026-10-01:** custom engines from the UI and JSON, **drivable**
  (the owner's choice over Dyno/Grid only). They come after #78; see Next
  actions.
- **Decided 2026-10-01, ADR-014:** both grid paths, in the browser and
  native; the same 8×6 grid as the roster.
  - Measured: Pyodide is 2.65× slower than native. A drivable grid takes
    ~26 min on 4 browser workers, ~13 min on 8, ~15 min natively on 6
    cores, and hours on a phone.

**Part 13: custom engines, step 1 of 3, the native path (#79, stacked on
#78):**
- **The format.** A custom engine is the roster's JSON plus `"vehicle"`, one
  of `live.VEHICLE_KEYS` (held to TypeScript by the vehicles fixture).
  - `python3 tools/build_live_grids.py --engine my.json` builds its grid to
    `out/grids/<key>.json`, recording the JSON and its SHA-256.
  - A smoke run (`--size 2x2`) took 98 s, and the Python loop drove the file
    in the vehicle it names.
- **The app.** `/drive` and `/enjoy` import a grid file.
  - The file is refused, with the reason, if it is not a converged grid or
    names no known vehicle.
  - The worker takes the vehicle from the file.
  - `LiveSession.stop()` now clears the last engine's info. The new e2e
    check caught it reporting the truck while the imported engine loaded.
- **The grid hash now excludes `bridge.py`** (with `live.py` and
  `livesound.py`). Steps 2 and 3 add bridge entry points, and each would
  have staled all 8 grids.
  - That change itself moves the hash, so the grids were **re-stamped**
    66de4859… → 4838e151….
  - Proof: the only `dieselsim/` changes since the build are `builder.py`
    (ignores `"vehicle"`, a key no engine file has), `live.py` and
    `bridge.py` (both excluded). For each file, the re-stamp asserted that
    only the hash string differs.
  - The exclusion test now also starts its import walk at `builder.py`. A
    mutant excluding `builder.py` is caught.
- **Tests.** Python 68 / 0 / 2 known (scipy), 63 + 4 skipped (plain).
  App units 48 (+6 for the grid-file check); e2e:enjoy 16/16
  (+2: a bad file refused; an imported engine drives in its file's
  vehicle); `test_custom_engine_json`.
  - Mutants: the import, 3 of 3 e2e and 2 of 2 unit; the JSON, 3 of 3;
    the TypeScript key list, 1 of 1.
  - Drive 7/7, dyno 13/13, sound 6/6; `build:pages` OK.
- ~~**Next (steps 2 and 3):** the custom-engine form, with JSON import/export
  and achieved against requested, on Dyno and Grid; then the in-browser
  converged build with a worker pool, progress, resumable and cached.~~
  Step 2 is below; step 3 is next.

**#77–#80 merged 2026-10-02**, each retargeted to `main`. `main` equals the
tested top (`be26576`), 0 lines differ.

**Part 15: custom engines, step 3a, the browser builds a drivable grid
(#81):**
- **The pieces are the bridge's**: `live_grid_plan`, `live_row_limit`,
  `live_cell` and `live_grid_assemble`. `tools/build_live_grids.py` builds
  with the same functions, so a browser grid and a native grid are the same
  file.
  - The refactored tool rebuilt the 2×2 custom grid identical to the old
    code's (0 of 24 fields differ).
  - `test_live_grid_pieces_match_the_shipped_grid`: a `crdi15` cell through
    `live_cell` equals the shipped grid's, warm and cold. 3 of 3 mutants
    caught.
  - `friction_engine_view` moved into the package; the fixtures are
    unchanged.
  - **Correction, found by CI:** I first wrote that test as exact equality.
    It held on the Mac that built the grids and failed on CI's Linux
    runners (perf and sources differ; the trace does not), from floating
    point across platforms, which the golden points already allow for. It
    is now held to `GOLDEN_TOL` (1e-5) and prints the worst difference.
    Both physics mutants still fail it by far: 7.5e-2 and 1.4. Measured on
    CI's Linux: **8.95e-13** (at `perf.osc_spread`).
- **`buildLiveGrid` in `web/solver`**: a pool of Pyodide workers.
  - Rows first; each row's cells are released the moment its fuel limit is
    known.
  - Every finished piece goes to a store, so a cancelled or closed build
    resumes.
  - The ETA comes from the session's own pace.
  - The worker's `liveCall` allows only the four live-grid functions.
- **Measured: the browser's grid is the native file**, structure identical
  (26 fields, key order, grid hash), numbers within **1.3e-13**. The 2×2
  build took 425 s on 2 Node Pyodide workers (`npm run test:live-real`,
  manual: ~7 min). Extrapolated, the full 8×6 takes ~27 min on 4 workers,
  as ADR-014 estimated.
- **Tests.** Python 70 / 0 / 2 known (scipy), 65 + 4 skipped (plain).
  Scheduler 8/8 with fake workers (cancel and resume, a failing
  cell, row-before-cell order, parallelism): 5 of 5 mutants caught. Round
  trip 22/22 (+2: the plan; a non-live function refused, its mutant
  caught). Cache 20/20.
- ~~**Next, step 3b (the UI):** "Build drivable grid" on the Dyno page, with
  progress and cancel/resume (an IndexedDB piece store); saved custom
  engines listed on `/drive` and `/enjoy`; the grid file offered as a
  download, for moving it to a phone.~~ Done, below.

**Part 16: custom engines, step 3b, drivable from the app (#82, stacked on
#81). With this, ADR-014 is complete:**
- **"Build drivable grid" on the Dyno page.**
  - The page's pool of solver workers builds the grid: cores − 1, at most
    6; 2 on a device reporting under 4 GB.
  - It shows progress, an ETA and a Stop button. Pieces are kept in
    IndexedDB, so a stopped or closed build carries on; they are dropped
    once the file is saved.
- **"Your engines"** (`engine/my-engines.ts`, IndexedDB).
  - Saved engines appear in `/drive`'s and `/enjoy`'s engine lists.
  - "Drive it" opens `/enjoy` (or `/drive`) with the engine chosen
    (`?engine=my:<key>`).
  - "Download grid file" is there for a phone or a friend.
- **`e2e:custom`** (manual, ~5 min): a 2×2 grid built in Chrome through the
  e2e-only `?gridsize` hook.
  - Stopped at 2 of 10, then resumed: "8 of 10 (8 from before)".
  - Saved, then driven on `/enjoy` in its own 1.5 t compact, idling at
    800 rpm.
  - 3 of 3 mutants caught: no resume; not saved; `/enjoy` ignoring the
    link.
  - Not in CI: with CI's 2 cores the pool is 1 worker, about 15 min. Adding
    it is the owner's call.
- **Tests.** App units 56 (+2: the library, the pool size); e2e enjoy 16,
  drive 7, dyno 15; solver fast 20 + 8.
  - **Found by CI:** the new spec imported `solver.service.ts`, which
    imports the generated, gitignored `physics-version.ts`. CI runs the
    unit tests before `prepare-assets` creates it, so the build failed
    there and passed here. `poolSize` moved to `solver/pool-size.ts`.
    Reproduced locally by running the units with the file moved aside:
    56/56.
- ~~**Not measured yet:** a full 8×6 build in a real browser on a laptop.
  ADR-014's ~26 min on 4 workers is extrapolated from Node.~~ Measured in
  part 17: **21.5 min** on 6 workers.

**Part 17 (#83, stacked on #82). The owner's three choices of 2026-10-03:**
- **A full 8×6 drivable grid measured in real headless Chrome: 21.5 min**,
  the page's 6 workers on this 8-core, 8 GB Mac.
  - The ETA ran pessimistic during the row phase (17 min left at 9.5 min,
    when 12 remained) and was accurate during the cells.
- **The Derate lamp lights on hot charge air (> 80 °C) or any overheat
  derate**, not on the fuel cut (`lamps.ts`, with its history in the
  comment).
  - The new e2e check holds the truck flat out from a standstill until the
    model cuts fuel: charge air 57 °C, derate 0.943, lamp dark.
  - The previous 5% rule lights it there; that mutant is caught (59 °C,
    "lit: Derate"). Unit mutants 2 of 2.
  - Two mistakes of mine in the new check, both fixed before it passed: my
    first "full throttle" pressed 5% of the pedal, and the stall test had
    left the gearbox in Manual (the truck revved in neutral).
- **`e2e:custom` runs in CI** as its own job, `web-custom-e2e`, so it does
  not lengthen the others. With CI's 2 cores the pool is one worker, ~15–20
  min. *(Correction: measured on its first run, the job took 8 min 16 s,
  the test 460 s. My estimate was twice that.)*
- ~~**Next: roster B**, the 15 L V8 truck and an old naturally aspirated
  single (ADR-012).~~ Done, below.

**#81–#84 merged 2026-10-04**, each retargeted to `main`. `main` equals the
tested top (`5147579`), 0 lines differ.

**Part 19: published on GitHub Pages (#85). The owner's choice, so the
Android check works from anywhere over real HTTPS.**
- **`.github/workflows/pages.yml`** publishes `main` to
  **https://jenilclaudeai.github.io/diesel-simulator/** on every merge.
  - It runs the same `npm run build:pages` CI checks: 67 MB, no file over
    50 MB.
  - ADR-003 is what makes Pages possible: no `SharedArrayBuffer`, so no
    COOP/COEP headers.
- **Deep links:** Pages has no single-page-app fallback, so a refresh on
  `/diesel-simulator/enjoy` would 404. `postbuild:pages` copies
  `index.html` to `404.html`, and the workflow checks the copy.
- **Pages was switched on** (source: GitHub Actions, HTTPS enforced) through
  the API on 2026-10-04. The `github-pages` environment deploys only from
  `main`, so the first deployment happens when #85 merges.
- ~~**Not yet seen live:** the site, until that first deployment. Then check:
  the four pages load, Python boots on the Dyno page, `/enjoy` drives with
  sound, and a refresh on a deep link works.~~
- **Live since 2026-10-04** (#85 merged; the Pages run succeeded).
  Checked in headless Chrome against the published site on 2026-10-05:
  - The Dyno page boots Python 3.14.2 with numpy in 4.8 s, and a dyno point
    solves.
  - A deep link straight to `/enjoy` drives the hatchback (778 rpm) and the
    15 L V8 (577 rpm) with sound (−33 dBFS), in a secure context.
  - A deep link to `/drive` loads.
  - Assets: `.wasm` as `application/wasm`, modules as `text/javascript`,
    the grids whole.
  - No page errors, console errors or failed requests.
  - Deep links come back from Pages with HTTP 404 and the app's page (the
    `404.html` fallback). Browsers render it and the router takes over;
    only crawlers and link previews see the 404.

**Part 18: roster B (#84, stacked on #83). With it, ADR-012's roster is
complete: 1, 4, 6 and 8 cylinders, and one engine with no turbo.**
- **`v8hd`, 15 L V8, 600 ps**, in the 40 t tractor-trailer.
  - Untuned: 80.5% of the cap at the plateau start.
  - Tuned `boost_map_rise` 0.08 and `afr_limit` 17.0: plateau 99.6 / 96.5 /
    99.5 / 100.0%, rated 99.9%.
  - `verify()`: 99.7% / 97.8%.
  - Not modelled: the cross-plane per-bank "burble". It fires evenly
    every 90°.
- **`single10`, a 1.0 L naturally aspirated single, 15 hp**, in the 3 t
  utility tractor.
  - Old-engine character from two new builder switches, `mechanical_lash`
    and `pilot` (both default to today's behaviour), plus `rail_bar` 400.
  - It makes its numbers untuned: plateau 99.6–100.9%, rated 100.1%.
- **Found on the way:** the V8's file was `engines/v8_hd.json` with key
  `v8hd`. Everything reads `<key>.json`, so the tests would have crashed
  and the grid would have recorded no engine-file fingerprint. Renamed
  while its grid was still building; the grid recorded the fingerprint.
- **Grids** built (1,230 s / 271 s; 8 / 0 unsettled). The 8 older grids
  were **re-stamped** 4838e151 → dee93a17.
  - Proof: the only `dieselsim/` changes since their stamp are the
    builder's new parameters, whose defaults build specs identical to the
    old builder's for all 5 engine files, plus `live.py` and `bridge.py`
    (both excluded).
  - For each file, the re-stamp asserted that only the hash changed.
- **Found by the new e2e check: the single stalled in "Auto".** The torque
  converter was sized from 19 bar BMEP for every engine, so the 1.0 L NA
  single got a converter for 159 N·m against its 58 N·m. At a cold start
  it was dragged to the loop's 60 rpm floor.
  - Now sized by aspiration (19 bar turbo, 8 bar NA) in `live.py` and
    `driveline.ts`. Every turbo engine is unchanged (live fixtures 0 diff).
    The single idles at 555 rpm.
  - Guarded on both sides: `test_na_engines_idle_on_a_converter` and the
    e2e. Python's mutant and TypeScript's both fall back to 60 rpm.
  - **Known, recorded in the suite:** the dev preset `single` still sags
    on the same tractor's converter (1,000 → 859 rpm in 3 s), because its
    idle is high against the 1,800 rpm stall. The exact fix sizes each
    converter from the engine's own full-load torque at stall; it touches
    every engine and the live fixtures, so it is left for its own change.
- **The records** are in `engines/ROSTER.md`. Vehicles are held Python ↔
  TypeScript (vehicles fixture: 11/11). The e2e checks that each new engine
  starts and idles in its own vehicle (enjoy 19/19). The roster, lash and
  ramp tests cover all 5 engines.
- **Tests.** Python 71 / 0 / 3 known (scipy), 66 + 4 skipped (plain);
  fixtures current; audit 0 / 2 / 0; `web/physics` vehicles 11/11; app 56;
  e2e enjoy 19, drive 7, dyno 15.

**Part 14: custom engines, step 2 of 3, the form (#80, stacked on #79):**
- **"Custom engine…" on Dyno and Grid.** A form for the brochure numbers,
  the plateau, turbocharged and the vehicle, with JSON import and export in
  the `engines/*.json` format (`engine/custom-engine.ts`, unit-tested).
- **A new solver call, `describeEngine`**, through bridge → worker → client
  → cache. The builder itself reports a custom engine's idle and max rpm
  for the axes; its rules are not copied into TypeScript.
- **The Dyno pull reports achieved against asked**, as `verify()` does: peak
  torque, peak power, and torque at the plateau's start. It shows only once
  the pull finishes; my first version showed the table after 2 of 10
  points, and its peaks read as a shortfall.
  - Measured in the browser, the example 2.0 L: 100.9% of its torque, 98.2%
    of its power, 81.5% at the plateau start. That is the builder's known
    low-end shortfall (roster A was 77–86% before tuning).
- **Found by the new test:** `n_cyl: "four"` (and any number the builder
  cannot use) crashed with a raw `TypeError`. The bridge now answers
  "invalid request: the builder cannot make this engine: …". The same
  path serves `solve_point`'s custom engines.
- **Tests.**
  - Python 69 / 0 / 2 known (scipy), 63 + 4 skipped → 64 + 4 (plain);
    `test_describe_engine` (4 parts); the solver round trip +2 (20 + 20);
    app units 54 (+6); grid e2e 9/9.
  - e2e dyno 15 (+2: the builder describes the custom engine; its pull
    reports achieved against asked), grid +1 (described, ready to build).
  - Mutants: Dyno 3 of 3 (pulling a preset instead, the heading not from
    the builder, no achieved table). My first bounds (50–130%) would have
    let a pulled preset pass at 70.6%; the peaks now need 90–110%. One
    mutant first failed to compile (counted broken, redone so it compiles).

**Part 12: FINDING-023 fixed, and cam ramps with their own height
(#78, `feat/slap-and-ramp`, stacked on #77, docs):**
- **FINDING-023 option A.** Slap reads the running skirt clearance, which a
  cold engine opens: Al piston 21e-6/K, iron bore 11e-6/K, the walls moving
  with the coolant as `_apply_thermal_state` moves them. Cold opens it
  1.55–1.83×, so slap rises +2.3 to +3.1 dB. A warm cell whose film sat on
  its cap keeps its level exactly. The film stays in friction, so perf is
  untouched. Details and tables are in `reviews/FINDING-023.md`.
- **REVIEW-003 m-5.** `ramp_height_intake/_exhaust`: each ramp runs to its
  own height (1.25× the lash) at 0.025 mm per cam degree, in front of the
  unchanged main event.
  - Lift-area is kept within 0.1%; `hd_i6` 1700/1.0 torque moves +0.0098%.
  - Tick ÷ loudest other source (`tools/tick_dominance.py`, now committed):
    `hd_i6` 13.0× → 1.00×, `single` 10.6× → 2.98×; `crdi15` unchanged at
    2.30×.
  - **My first design narrowed the flank instead and lost 10–17% of the
    lift-area.** I caught it in the rendered sources (exhaust −17%, turbo
    −31%) and replaced it before any baseline moved.
- **Found on the way, my miss in #76: `truck127`'s valves landed on the
  flank.** The builder gave it the default 6% ramp, 113 µm under 550 µm of
  lash: 0.65 m/s seating, tick 224× the loudest other source. It is now
  0.90× and 26 dB quieter at idle; its `verify()` is unchanged. The lash
  test now covers the roster engines. See the correction in
  `engines/ROSTER.md`.
- **All 8 grids rebuilt once.**
  - Unsettled cells are identical to the old grids.
  - The dyno accuracy table's rows are unchanged; only the solver stamp
    moved (`66de4859…`).
  - The run also built an untuned `v8hd` grid (`load_engine_dir` found
    roster B's engine file); I deleted it.
- **Tests.**
  - Python: 67 passed, 0 failed, 2 known (scipy); 62 + 4 skipped (plain).
    The FINDING-023 known is now a passing check.
  - Fixtures current (7 modules, 0 differences); `web/physics` 5 + 36 + 10
    + 8; app 42 unit tests; `build:pages` OK; audit 0 / 2 / 0.
  - Browser, on the rebuilt grids: enjoy 14/14, drive 7/7, sound 6/6,
    dyno 13/13, grid 8/8.
  - Mutants: FINDING-023 6 of 6, ramps 6 of 6 (the first design's flank
    included), TypeScript 5 of 5.
  - Re-pinned with inline reasons: the `hd_i6` golden point, and the
    valvetrain power (its time-base mutant is still 4.5% away).
- **For the owner's ear:** `out/listen/review003m5_*.wav`, six pairs, each
  before → gap → after, with one gain per pair (local files, gitignored).
- **Seen while running the app, not changed:** the Derate lamp lights on the
  truck at full throttle and low speed (charge air 66 °C, fan off, more than
  5% fuel pulled). It is a real modelled loss, but a real dashboard would
  not warn at 66 °C. Candidate fix: light it only above a realistic intake
  temperature.
  - *(the Phase 5 decisions are made: ADR-012, 2026-09-30: roster B as A
    first; touch pedals with top paddles; a new `/enjoy`; judged on a
    mid-range Android)*

**Phase 5 has started (#74, stacked on #73 → #72): `/enjoy` with touch pedals.**
- One tap starts the engine and the sound.
- Throttle on the right, brake on the left (a clutch on the manual),
  pressed harder by sliding up; shift paddles in the top corners.
- rpm, speed, and the gear with its shift phase; a rotate hint in portrait.
- The worker and the sound moved into a shared `LiveSession`, so `/drive`
  and `/enjoy` cannot drift apart (`/drive`'s tests are unchanged:
  drive 7/7, sound 6/6).
- `e2e:enjoy` (in CI) drives it with real multi-touch on an emulated
  landscape Pixel: 9/9, and 6 of 6 mutants caught.
- **The dashboard (#75, stacked on #74):**
  - a tachometer with a red band from rated speed (a truck reads ×100 rpm);
  - a speedometer scaled to the lower of gearing and drag-limited top
    speed (the 40 t truck showed 200 km/h by gearing alone; now 160);
  - the gear with its shift phase;
  - an 8-lamp cluster;
  - coolant, oil and charge temperatures, with the warning and derate marks;
  - a trip computer labelled steady-state (FINDING-009).
- **Found by the tests:** a paddle tap while a thumb held the clutch
  produced no click, so a manual could not be shifted on a phone. Paddles
  now act on `pointerdown`. `e2e:enjoy` is 14/14 with 11 of 11 mutants
  caught; the dial scales carry property tests.
- ~~**Next:** the roster (A first), then a real Android phone.~~ Roster A
  is done (#76, below); next is a real Android phone, then roster B.

**Roster A on `/enjoy` (#76, stacked on #75), part 11:**
- **The engines.** Three builder engines, each with its own vehicle:
  - `hatch15`: 1.5 L four, 115 ps, in a 1.3 t hatchback with a 6-speed;
  - `crdi22`: 2.2 L four, 150 ps, in a 1.9 t SUV with an 8-speed automatic;
  - `truck127`: 12.7 L six, 530 hp, in the 40 t tractor-trailer.
  - `engines/ROSTER.md` records `verify()` for each, as ADR-008 requires:
    peaks within 0.7% (torque) and 2.0% (power); every plateau point ≥ 96.6%
    of the cap.
- **Tuning.** Straight out of the builder, every engine was air-limited at
  its boost target on the low plateau (77–86% of the cap).
  - A new `build_engine(boost_map_rise=)` parameter (default unchanged),
    plus a richer `afr_limit` per engine, fixed it.
  - hatch15's brochure plateau moved from 1,750 to 2,000 rpm: no setting
    held 1,750 (best 89.3%).
  - `test_roster_engines_make_their_numbers` guards the plateau start and
    rated power; the untuned crdi22 fails it (83.2%).
- **Grids.** Three new converged grids (731 / 835 / 1,191 s).
  - Unsettled cells: hatch15 1, crdi22 2, **truck127 13** (of 96). The page
    shows the count.
  - Each grid records its engine file's SHA-256, because `engines/*.json`
    is outside the grid hash. `test_roster_grids_match_their_engine_files`
    catches a grid left stale by an edited engine file.
  - The five dev grids and the dyno's accuracy table were **re-stamped**,
    not rebuilt, 226abeff… → de5d11f0…. Proof: the only `dieselsim/`
    changes are `builder.py`, which the cell solve does not import (the
    static import walk), and `live.py`, which is excluded from the hash.
- **Vehicles are held Python ↔ TypeScript field for field**: a new
  `vehicles` fixture covers all 8 keys × tc/dct/manual, exact. 8/8 pass;
  a one-ratio mutant is caught.
- **Two dashboard bugs, found by the roster:**
  - **The Derate lamp lit in ordinary driving.** It tested `derate < 0.999`.
    But `derate` includes a continuous charge-density term (hatch15 idles at
    0.9992 once the charge air warms). The lamp now means protection: any
    overheat derate, or a charge-air loss over 5% (`lamps.ts`, unit-tested
    on both edges).
  - **The stall check only ever worked on crdi15.** It released the clutch
    in 1st at idle, and a hatchback does not stall that way. Measured in
    Python: the engine dips to 369 rpm and creeps off at 6.1 km/h; with
    the brake on, it stalls at 0.53 s. The e2e now brakes and clutches,
    shifts, then lets the clutch up with the brake held. It also checks
    that no other lamp is lit.
- **Correction to part 10's e2e.** The two-thumb shift "lifted" the paddle
  finger with a `touchMove` that left that point out. **CDP keeps an
  omitted point pressed**: the clutch read 1.00 after its finger was
  "lifted" this way. The paddle check was still valid, because the paddle
  acts on press. The stall step worked only because `touchEnd` lifts every
  finger. The e2e now lifts all fingers and re-presses the brake at once;
  the comment in `enjoy.e2e.mjs` says why.
- **Mutation runs.**
  - Unit: 4 of 4 caught on `derateLit` (the old rule, heat ignored, the
    edge, never lit).
  - e2e: 3 of 4 caught (the worker ignores the brake; a dead Stalled lamp;
    the stall scenario without the brake).
  - **Survived: the old Derate rule, in the e2e.** At the stall, derate is
    about 1, so only the unit test guards that rule.
  - One mutant was discarded as invalid and redone. It released the brake
    together with the clutch; the brake springs back over 0.45 s and was
    still on when the clutch bit, so the engine stalled.

**Main has everything** (checked 2026-09-30 by content: `main` against the
tested top of each stack, 0 lines differ):
- #50 landed #41–#49 (Phases 1 and 2); #65 landed #51–#64 (Phases 3 and 4).
- **#71 landed #66–#70.** Those five were *closed unmerged* on 2026-09-29,
  because their branches were deleted before merging (deleting a PR's head
  or base branch makes GitHub close it).

~~**No PR is open.**~~ ~~**Open, a stack, merge in order:** #72
(`docs/status-main` → `main`) → #73 → #74 → #75 → #76 (`feat/roster-a`).~~
*(All merged 2026-09-30, each retargeted to `main`; `main` equals the
tested top, 0 lines differ.)* ~~**Open now:** #77 (`docs/decisions-023-ramp` →
`main`) → #78 (`feat/slap-and-ramp`) → #79 (`feat/custom-engines`) → #80
(`feat/custom-engine-form`).~~ *(All merged 2026-10-02.)* ~~**Open now:** #81
(`feat/browser-grid-build` → `main`) → #82 (`feat/drivable-grid-ui`) → #83
(`feat/derate-lamp-ci`) → #84 (`feat/roster-b`).~~ *(All merged 2026-10-04.)*
~~**Open now:** #85 (`feat/pages-deploy` → `main`).~~ *(Merged 2026-10-04.)*
**No PR is open.**
Remote branches besides those: `main`, and `fix/steady-state-controllers`
(kept; the only copy of the FINDING-013 option A experiment).

The table below is the history of the Phase 3–4 stacks.

| PR | branch | what |
|---|---|---|
| #50 | `docs/phase2-exit` → `main` | lands #41–#49 (Phases 1 and 2) |
| #51 | `feat/live-module` | the real-time loop moves to `dieselsim/live.py`, bit-identical; bug #6 tested |
| #52 | `feat/live-port` | the live loop in TypeScript, held to Python per step and end to end |
| #53 | `feat/manual-gearbox` | manual gearbox, clutch pedal, auto-clutch assist |
| #54 | `fix/coast-downshift` | lock-up is a clutch, not an unstable spring; gentle coast downshifts (FINDING-020, bug #11) |
| #55 | `feat/live-friction` | friction computed live in the loop (ADR-011 step 2) |
| #56 | `feat/prebuilt-grids` | prebuilt converged grids for the five presets |
| #57 | `feat/drive-page` | `/drive`: the TypeScript loop at 60 Hz in a worker |
| #58 | `docs/phase3-exit` | REVIEW-005, accuracy table, PLAN, STATUS |
| #59 | `fix/live-sound` | `dieselsim/livesound.py`, a streaming synth faithful to `render()`; `play.py`'s stale copy replaced (FINDING-021); grid-hash exclusion |
| #60 | `feat/grid-sources` | the grids carry warm and cold sound sources (all five rebuilt); the loop feeds the synth its live friction; FINDING-023 |
| #61 | `feat/ts-synth` | the synth in TypeScript, sample-exact to Python; FINDING-022 |
| #62 | `feat/drive-sound` | the AudioWorklet on `/drive`: Sound on, five mics, Record WAV; sound e2e in CI |
| #63 | `docs/phase4-exit` | REVIEW-006, PLAN, this file |
| #64 | `fix/finding-022` | FINDING-022 option A: intake and boost levels survive the normalisation; grids re-stamped by rebuild; the dyno's accuracy note keyed on the solver hash and re-measured |

The repository is **public** now: Actions minutes are free, and the history
was scanned for tokens before it went public (none found).

---

## Phase 5 proposal, for decision (#70): `reviews/PROPOSAL-phase5.md`

Measured today:
- `/drive` on an emulated phone fetches no Pyodide (7 requests, 0 solver).
- Audio and the loop fit at 4× (#68).
- **But the app cannot be driven on a phone:** there are no touch
  controls, only keys. That is the largest Phase 5 item, and PLAN.md did
  not list it.

The roster (OPEN-F) costs, per engine: a vehicle (every engine but three
falls through to a "3 t utility tractor"), a converged grid (3.5–15 min,
~1 MB gzip), and a tuning pass. `verify()` on the two builder engines hits
the peaks within 3.5% but not the plateau: crdi22 has 85% of its cap at
1,873 rpm, v8hd 82% at 1,133.

Options: A (3 engines), B (5), C (8). Recommended: B, delivered as A first.
Also for decision: the touch layout, `/enjoy` against reworking `/drive`,
and the phone the exit is judged on.

---

## Session 5, part 7 (2026-09-29) — `play.py` on the prebuilt grids (#69, stacked on #68)

REVIEW-005 m-6 is closed. `python3 play.py` now loads the browser's prebuilt
converged grid for a preset. It starts instantly, with live friction from
the cells' traces, the warm/cold pair and the sound sources, so the terminal
and `/drive` run the same model. The synth gets `LiveEngine.sound_inputs()`,
and the sources are blended at the live coolant: cold oil sends 80 W of
boundary power into the synth, against 97 W warm. A custom engine, rating
caps, another grid size, `--converged-grid`, `--rebuild` or the new
`--own-grid` keep the old solve-and-cache path. Both paths were run
headless in a pseudo-terminal.

A listening note: with the grids as they are, a cold start barely changes
the *total* level (engine bay −0.1% at idle, cold oil). The rumble moves
(−8.9% of that part), but the slap, which should grow, is pinned by
FINDING-023.

---

## Session 5, part 6 (2026-09-29) — phone performance (#68, stacked on #67)

The owner chose this while the PRs wait. Phase 5's exit criterion is a
mid-range phone with audio.

- **`npm run perf`** (new, reports only) times the synth, the live loop and
  live friction under Chrome's CPU throttling: 4× is DevTools' "mid-tier
  mobile", 6× its "low-end".
  - Chrome's throttling does **not** reach workers (identical at 1×/4×/6×),
    so the throttled main thread is the phone estimate.
  - A real phone is still the final test.
- **The synth was the risk.** At 6×, up to 12 of 3,445 audio blocks ran over
  the 2.9 ms budget, one at 61 ms; that looked like garbage collection.
  - It is now allocation-free: preallocated buffers, reusable 20 Hz blends.
    The output is **bit-identical** (0 of 1,154,688 values differ over all
    paths), and the fixtures pass.
  - 4×: 19–21% → 8% of the audio thread. 6×: 29–32% → 12%; p99.9 → 1.8 ms;
    over budget 0–1 of 3,445.
- **Live friction is left as it is**: 11 ms of a 16.7 ms frame at 4×, a
  whole frame at 6×, in the loop worker and off the audio path. Its cost is
  a 60-step bisection per bearing per crank sample (~176,000 evaluations
  per call). Cheaper needs an algorithm change in Python and TypeScript
  together, so it is an owner decision, and matters for low-end phones only.
- **Found and fixed on the way:**
  - `e2e:sound` had passed its idle check on an empty capture (a vacuous
    pass: `Math.min()` over nothing is +∞). It now requires samples, and it
    fails as it should on silence.
  - The e2e now uses Chrome's fake audio sink: this Mac's output stopped
    pulling samples (the clock advanced 0.006 s in 1.5 s), which silenced
    every worklet, old code too.
  - The page now reports a `processorerror` from the audio thread, which
    used to fail in silence.

---

## Session 5, part 5 (2026-09-29) — setup on a restricted network

The owner's first `npm start` failed: `ENOTFOUND cdn.jsdelivr.net`, the
build-time numpy download behind a corporate network. The script crashed
with a raw stack trace, because its hint only covered an HTTP error.

- **`prepare-assets.mjs` now explains** what failed (host, DNS or proxy
  error, HTTP status, or a missing local file) and gives three fixes:
  - `HTTPS_PROXY` plus `NODE_USE_ENV_PROXY=1`. Verified: without the flag,
    Node ignores the proxy.
  - `PYODIDE_WHEEL_DIR`.
  - A `PYODIDE_CDN` mirror.

  The checksum check is unchanged, and a corrupted wheel is refused.
- **`npm start` (`--dev`) carries on without numpy**, outside CI, and tells
  the app (`NUMPY_BUNDLED`): Drive works (drive e2e 7/7 on such a build),
  and Dyno and Grid state the cause. Builds and CI stay strict.
- **`npm run check:assets`** (in CI) runs the four failure paths with no
  network needed; 5 of 5 mutants caught.
- **#67 (docs, stacked on #66):**
  - `web/app/README.md` replaced the Angular template, which recommended
    the blank-page `ng build`;
  - `README.md` gained Getting started, and its validation table was
    re-measured (all 12 rows in band; best BSFC 213 → 200 g/kWh, lugging
    NOx 20 → 15.6, and more);
  - all five usage snippets run as written.

  `PROJECT_CONTEXT.md` §1.5's "documented" column carries the same old
  values; `tools/validate_table.py` prints both side by side.

---

## Session 5, part 4 (2026-09-28) — FINDING-022 fixed (option A)

The owner chose FINDING-022's option A, and FINDING-023 later (its own
rebuild).

- **The fix:**
  - `render()`, `livesound.py` and the TypeScript synth give the intake
    (ṁ/ṁ_ref)^1.5 after its normalisation;
  - the turbo's boost term is applied after its normalisation, referenced
    to rated;
  - ×2 now moves them +182.8% and +190.5%, where both were 0.0000%;
  - the known defect became an assertion.
- **Balance:**
  - at idle the intake and turbo parts drop 28–39 dB, and the intake-mic
    total 11–19 dB;
  - at full boost the turbo rises ~4 dB;
  - outside at 7 m the total moves ≤ 2.8 dB.
  - The table is in FINDING-022. These are the points to listen for.
- **Grids:** all five rebuilt for the new hash. Only `grid_hash` and
  `build_s` changed (sources 0 of 2,880 differ).
- **Also found and fixed, my regression from #59:** the dyno page's accuracy
  note had said "not measured" on every Phase 4 PR. It was keyed on the
  whole-package hash, which adding the synth moved.
  - It is now keyed on the solver (grid) hash, and re-measured: 0 of 50 pull
    rows differ from REVIEW-005's run.
  - Verified in the browser: "within 5.8% … 1.8 N·m".
  - The printed "worst" lines of `--pull` (e.g. +93.6%) are a known quirk at
    the governed end, where torque is near zero; they are identical in the
    old run. The table uses absolute N·m there.
- Mutation: 6 of 6 caught (4 Python, 2 TypeScript).

---

## Session 5, part 3 (2026-09-27) — Phase 4 built; the sign-off is the owner's

The owner took three decisions, all as recommended:
- warm and cold sources in the grids;
- sample-exact plus spectral testing;
- port faithfully and decide by ear.

- **#59: FINDING-021.** `play.py`'s LiveSound was a stale copy of the
  acoustics model. Slap, exhaust flow and seating speed each moved its
  output by 0.0000%.
  - `dieselsim/livesound.py` replaces it: 128-sample blocks, numpy only,
    and a pure mode that is the TypeScript reference. Against `render()`:
    levels within 1.2%, third-octaves within 1.02 dB, each source's shape
    within 1.23 dB.
  - **A mistake of mine, corrected in place:** the new file first staled
    all five prebuilt grids, because `grid_hash()` covered it. It is now
    excluded; the app reads the exclusions from `bridge.py`; and a static
    import walk proves the cell solve never imports an excluded file. That
    check was first a subprocess, which Pyodide lacks; CI caught it. The
    grid tests SKIP under Pyodide, where the harness copies no data files.
- **#60: the grids carry sources.** All five were rebuilt (~58 min).
  - perf 0 of 9,600 values and traces 0 of 480 differ, which confirms the
    re-stamp;
  - 5,139 KiB raw each; gzip 1,003 KiB (crdi15), 1,424 KiB (single).
  - `LiveEngine.sound_inputs()` passes the live friction on: cold oil moves
    the rumble −8.9% through the live path, and 0.0% without it.
  - **FINDING-023:** the slap input sits on its clamp in every cold cell.
- **#61: the synth in TypeScript**, held to Python:
  - max |diff| 2.2e-13 of peak; its own bound is 1e-8, because libm and V8
    differ by an ulp;
  - PLAN's exit peaks on the port: +38.3/+26.2/+25.8 dB at 70/140/210 Hz;
  - 12 of 13 mutants caught, the 13th equivalent;
  - **FINDING-022:** in `render()`, the intake's flow level and the turbo's
    boost term are divided out: ×2 → 0.0000%.
- **#62: `/drive` has sound.** The AudioWorklet is fed over a MessagePort
  (no SharedArrayBuffer); first sound 304 ms after the click; Record 10 s
  gives a WAV.
  - The e2e found two bugs: no `atob` in the worklet scope; and space (full
    throttle) pressed the last-clicked button.
  - A flaky e2e estimator of mine was replaced by a median floor.
- **REVIEW-006:** 0 BLOCK. 1 MAJOR: the listening sign-off. 5 MINOR:
  - phone CPU;
  - the synth bound;
  - grid size;
  - a stopped engine still sounds fuelled;
  - the I4 idle fundamental sits under the high-pass.

---

## Session 5, part 2 (2026-09-27) — Phase 3 completed

The owner confirmed FINDING-018's C′ and took four more decisions, all as
recommended:
- prebuilt converged grids for the presets;
- ADR-011 in Phase 3;
- a clutch pedal with an auto-clutch assist;
- a minimal drive page.

- **#51:** `play.py`'s loop moved to `dieselsim/live.py`. 0 of 180,000 values
  differ against the original.
- **#52:** TypeScript port; Python snapshots load field for field. Per step
  1.0e-14, every event aligned.
- **#53:** manual box, built in Python first as the reference. The clutch
  return (1.4 s) was chosen by measurement.
- **#54 — FINDING-020.** Measuring bug #11 found the converter's lock-up
  unstable (h·C/J = 17): every locked frame sat on its ±4,500 N·m clamp, and
  coast downshifts jolted at up to 1.3 g. It is now a clutch; coast shifts
  stretch.
- **#55 — ADR-011 live.** A friction port agreeing to 3.5e-13, an oil node,
  and a cold/warm pair. A cold engine drives cold (×1.74 friction at 298 K).
- **#56:** five converged grids, 32 of 480 cells unsettled and flagged, keyed on
  `grid_hash()`, which excludes the live loop.
- **#57:** `/drive`, running 60 Hz in a worker. In Chrome it matches native
  Python on a 60 s drive to 1.7e-16.

Mistakes of mine this part, corrected where they happened:
- a suite count written early (54 vs 53);
- two false alarms (m/s read as km/h; a check without the script's brake);
- a checkout that removed committed grid files from the working tree
  (restored);
- an e2e race;
- three test gaps found by their own mutants.

**Owner, please:**
1. Merge #50, then #51 → #58 in order, retargeting each to `main`.
2. Try `/drive`.

---

Read this first in a new session, then `PLAN.md`, then `DECISIONS.md`, then
`reviews/`. Those replace pasting a context document. `CLAUDE.md` says the same
for Claude Code sessions.

---

## Session 5 (2026-09-26) — Phases 1 and 2 completed

The owner asked for Phases 1 and 2 to be finished. Eight decisions were taken
up front, and all went with the recommended option: EGR starts from a target
estimate; add p_max + T_exh limits; fix the economy *claim*; seat at ramp
speed; reset the turbo too; move the by-ear audio sign-off to Phase 4;
leave the limit cycle for Phase 3; fix clear bugs.

**Phase 1 (#40–#46, REVIEW-003):**
- **EGR start (#40).** Delivered-EGR error vs converged 7.75 → 3.07 points;
  torque RMS 17.6% → 13.5%. One point got worse: `crdi15` 4000/0.25,
  −1% → −39%. That is the unconverged VGT loop, which the old over-open
  valve was masking (Phase 3).
- **Bug #5 (#41).** A cold solve after any history is bit-identical to a
  fresh engine.
- **FINDING-018 (#42), new.** Cam lift stepped 4× where the ramps meet the
  flank, 2.0 mm on `hd_i6`, since the first commit. Option C′ keeps breathing
  (≤ 0.1%) and the ramp heights, and doubles ramp speed (tick +6 dB). **Owner
  to confirm.**
- **Seating (#43).** `hd_i6` tick went from 75.7× to 13.0× its other
  mechanical sources. It stays dominant because its ramp is steep (Phase 4).
- **Limits (#44).** 100 of 100 points bit-identical with limits on vs off;
  they bind when set low. Cost: one extra solve per speed. A fuel-only p_max
  limit is severe, so it is set not to bind.
- **FINDING-019 (#45).** The aged-engine torque gain is turbo fouling acting
  through the limiter's unconverged calibration. Converged it is −0.08%, so
  there is no wear bug. `durability_run` solved at 6 cycles; now 9.
- **Exit (#46).**
  - Every fixed bug has a test (four gaps closed, mutation-tested). Bug #6,
    in `play.py`'s terminal loop, is carried to Phase 3.
  - Validation table: 12 of 12 rows in band. The 12,000 h paragraph did
    **not** hold and is corrected in place.
  - Goldens tightened 0.5% → 1e-5: PR #37 had moved one −0.09% unrecorded
    (my miss).
  - The "two fitted scalars" claim is corrected in place.

**Phase 2 (#47–#49, REVIEW-004):**
- **Golden fixtures (#47).** `tools/fixtures/gen_fixtures.py` plus the
  `web/physics` ports (kinematics 3.6e-14, thermo 4.0e-16). `--check` fails
  on stale fixtures. Finite differences are compared at their stencil's
  rounding bound (a new ADR-004 rule), and REVIEW-001 M-1 is resolved.
- **Browser grid (#48).** A full grid built in Chrome matches native in 816
  of 816 values, worst 8.7e-7. The second build comes from the cache in
  0.05 s. The build takes 487 s.
- **Accuracy table (#49).** Regenerated on the final physics build.

**Mistakes of mine this session, corrected where they happened:**
- Contaminated pool workers in the EGR comparison. Rerun; noted in
  FINDING-013.
- An option-C prototype with `min` for `max`. Caught by its own continuity
  output.
- Uncomputed ramp speeds and wrong PR numbers in draft docs. Fixed before
  commit.
- VE referenced to the wrong density in the validation tool.
- A comparator that let NaN be overwritten. Caught by its own self-test.
- A unit test that needed a generated file. Red in CI; fixed in #48.
- The dyno e2e timed out on CI after #44 made pulls longer. Fixed in #44 and
  merged up the stack.

**Owner, please:**
1. Confirm FINDING-018's option C′, or pick A, B or C, before #42 merges.
2. Merge #40 → #49 in order.
3. Listen when Phase 4 comes. That is now its exit criterion.

---

