# Status

**Updated:** 2026-10-02 (session 5, part 15: custom engines, step 3a, the browser's grid build; #77–#80 merged, #81 open)
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
    Both physics mutants still fail it by far: 7.5e-2 and 1.4.
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
- **Next, step 3b (the UI):** "Build drivable grid" on the Dyno page, with
  progress and cancel/resume (an IndexedDB piece store); saved custom
  engines listed on `/drive` and `/enjoy`; the grid file offered as a
  download, for moving it to a phone.

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
(`feat/custom-engine-form`).~~ *(All merged 2026-10-02.)* **Open now:** #81
(`feat/browser-grid-build` → `main`).
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

## Session 4, part 4 (2026-09-26)

Owner's decisions, applied as the stack #36 → #39:

- **#37 — ramps above lash** on `hd_i6` (ramp_fraction 0.155) and `single`
  (0.13): seating 0.81 → 0.45 and 0.39 → 0.25 m/s at 1500 rpm. `hd_i6`'s valve
  tick falls from ~41× to **13×** its loudest other source — still dominant;
  the on-ramp lash penalty in `seating_velocity()` and the `_ref_vseat`
  calibration are open judgements (FINDING-017).
- **#38 — cam wear calibrated**: `K_ARCHARD["cam"]` 3.2e-9 → 2.17e-7 so the
  flat-tappet `single` grows 150 µm of exhaust lash in 2000 h (the owner's
  service interval). Rollers ~17× slower. *Observed, not investigated:*
  `crdi15` gains 3.6% torque after 2000 h from the other (untouched) wear
  mechanisms — recalls bug #9.
- **#39 — ADR-011 step 1**: cells carry `p_cyl` and `perf.p_rail`;
  `grid.cell_friction()` evaluates friction from the stored trace at live
  oil/coolant state (matches the cell's own to −0.008%, a full cold solve to
  +0.070%). `GRID_FORMAT` 2, `CACHE_VERSION` 7.
- **Harness trap found:** Python's bytecode cache validates a source by its
  mtime (whole seconds) and size, so a same-length mutation restored within a
  second runs stale bytecode. Mutation runs now use
  `PYTHONDONTWRITEBYTECODE=1`. Earlier results were re-checked: a stale cache
  can make a mutant falsely *survive*, never falsely *caught*, and every
  surviving mutant reported this session changed the line's length.

---

## Session 4, part 3 (2026-09-25, later)

- **The listening pairs were finally rendered and sent to the owner**
  (`tools/render_ab.py`, WAVs in `out/listen/`): `crdi15` 1800/0.6 warm vs fully
  cold is now **+28% brighter, +3.5% louder** (before FINDING-004: +1% / −11%).
  **Awaiting the owner's ears.**
- **FINDING-017 (#31):** piston slap and valve tick lose their physical scaling
  inside the mechanical sub-mix (each divided by its own std — FINDING-004's
  pattern again; doubling the slap input changes the output by 3.6e-11), and
  `hd_i6` / `single` seat valves off the closing ramp (lash 550 / 250 µm above
  ramps of 106 / 69 µm), so `hd_i6`'s valve clatter is ~45× its other sources.
- **REVIEW-002 (#32):** ADR-006 reassessed with converged solves. The cold
  engine is an **oil** effect (FMEP +224–375%, torque −21–78%); coolant drives a
  small, linear combustion change. Two-grid linear interpolation in
  temperature errs up to +108% FMEP. **ADR-011 accepted by the owner:**
  friction computed live; indicated performance from a cold/warm coolant pair.
  Then measured how friction reaches the loop: a fitted FMEP(viscosity)
  surface needs ~6 viscosity nodes × a coolant axis for ~1%, while friction
  evaluated from each cell's stored pressure trace with the live oil state is
  **exact** (0.000% in 9/9; oil never touches the trace). Chosen:
  trace-based. Cost 44 ms per call in Python (94% the bearing eccentricity
  solve); ~ms as compiled JS — to confirm in the port.
- **#34 — FINDING-017 item 1 fixed:** tick, injector and slap carry their own
  physical levels. `crdi15`'s mechanical level ×2.3; warm/cold now +11%
  brighter cold. **`hd_i6` gets far brighter** — item 2 (lash above the ramp)
  now matters more. The updated pair 1 was re-sent to the owner.
- **#35 — FINDING-015 item 2 fixed:** flat-tappet kinematics, rolling
  entrainment, roughness-based film floor (measured inert). `single` cam
  boundary power 22.6 → 215 W, 8000 h lash growth ~1 → ~9 µm; flat tappet ~46×
  a roller per cylinder. **Wear-rate calibration target: owner to choose**
  (options in FINDING-015).

---

## Session 4, part 2 — autonomous stretch (2026-09-25)

The owner merged #15, #17, #18, #19, then asked for ~6 hours of independent
work, pre-deciding: unsettled offline cells are period-averaged and flagged;
goldens may be re-baselined on the PR branch with inline justification; the
e2e-in-CI, bug #10, FINDING-005 and FINDING-008 items may be picked up
(measurement and write-ups only for the physics ones). Nothing was merged —
the permission check blocks merging without review.

**What landed as PRs:**

- **#21 — converged offline solves + FINDING-013 item 1** (the main work).
  `DieselEngine.converged_mode`: real time, 200 cycles — validated on the
  120-point map: ≤ 0.36% everywhere a steady state exists (95th pct 0.11%).
  One point, `crdi_1p5` 1450/0.5, has no steady state even at real time (VGT
  and EGR integral controllers fight; 21-cycle sawtooth, ±7.5%); unsettled
  cells are period-averaged (all 5 within 0.20%) and flagged `settled = 0`.
  Item 1 (calibrate the limiter under the evaluation's schedules): with
  converged solves the plateau overshoot goes from **+3.0% to within ±0.3%**.
  `CycleResult.converged` no longer claims convergence it never checked.
  Goldens re-baselined for `crdi15` (1800/0.6 torque −10.2%: the old
  calibration's fuel limit was inflated by EGR over-delivery). **Two guards
  became KNOWN — see FINDING-016; a judgement to review.** SolverPort
  round-trip tolerance 1e-8 → 1e-5 (native vs Pyodide now 1.2e-6 here: the
  calibration's warm-started solves amplify platform differences through the
  VGT limit cycle — measured; ADR-001 addendum). `play.py --converged-grid`
  builds a converged grid: `crdi15` 8×6 in **544 s** vs 55 s fast (6
  workers). The dyno page states its own accuracy against converged solves,
  tied to the physics build it was measured on.
- **#23 — e2e in CI** (headless Chrome on the runner; 13/13 there). The e2e
  no longer passes silently without its native reference.
- **#24 — FINDING-014, bug #10 measured**: `render_transient` restarts crank
  phase at 0 every chunk (seam firing intervals off 13% median, 29% max) and
  each cross-fade deletes 20 ms (2.00 s renders as 1.86 s). No fix applied.
- **#25 — FINDING-015, FINDING-005 explained**: the cam film is ~780× too
  thick — pressure-viscosity counted twice (`mu_cam` at 500 MPa *and*
  Hamrock–Dowson's G) — plus two kinematic errors. Fixed, boundary power
  becomes plausible (flat tappet 215 W, roller 28 W) but the 8 nm film floor
  then binds. No fix applied.
- **#22 — FINDING-008 options** for the crank-angle contract (docs).
- **#20** stays a draft: the `steady_ctrl` experiment, kept as a record.

**Then the owner decided four fixes, all the recommended options, now a
stack on #21 (each PR shows only its own commits):**

- **#27 — FINDING-016 fixed**: start of combustion resolved within the crank
  step. Ignition delay at 1° agrees with 0.1° within 0.007° (was up to 1°);
  the two guards are real assertions again, thresholds re-derived from the
  physics; a direct delay guard and a resolution test added.
- **#28 — FINDING-015 items 1 and 3 fixed**: cam film at inlet viscosity, cam
  kinematics on crank speed. Cam boundary power single 5e-7 → 22.6 W, hd_i6
  4e-3 → 29.5 W; 8000 h lash growth ~0 → ~1 µm (modest, no runaway). The
  dead-signal audit's TINY list is now empty. Flat-tappet kinematics, a film
  floor and a wear calibration await a decision (proposal in FINDING-015).
- **#29 — FINDING-014 fixed**: `render_transient` continues crank phase and
  keeps its length (2.000 s for 2.000 s; seams indistinguishable from an
  uninterrupted render). The suite now counts SKIPs separately — it had been
  counting them as passes.
- **#30 — FINDING-008 option D**: `CycleTraces.theta_global`.

**Found on the way:** FINDING-016 — the FINDING-001/002 guards had been
passing on a single 1° jump of the main ignition delay. The real response at
`crdi15` 1800/0.6 is ~0.2° / ~10% premix over 90 K (measured at dθ = 0.1°),
quantised away by the solver's 1° step. *My first reading — "pinned, does not
respond", and a "correction" of REVIEW-001 — was wrong and is corrected in
place; REVIEW-001's "quantised to the crank step" was right.*

---

## Session 4 — the handoff had drifted again

Measured at the start of session 4 against `git log` and `gh pr list`:

- `STATUS.md` on `main` was still the **session-2** version (2026-09-09): "no
  frontend code exists yet", PRs #8–#12 "open". The session-3 rewrite existed
  but sat unmerged in PR #15 — so the failure `CLAUDE.md` warns about happened
  to the very file that fixes it. **Merge the STATUS update in the same session
  that writes it.**
- The session-3 text below already assumed the stack was open; by the time it
  was read, #8–#14 and #16 (`CLAUDE.md`) had all merged.
- The chart-axis fix (next action 2 in session 3) had been written and pushed
  as `fix/dyno-axis-ticks` with **no PR**, and its own commit message said
  `build:pages` and e2e had not been run.
- Sessions 1–3 ran in a Linux dev container; session 4 runs on a local Mac
  (macOS, Python 3.12). Container-specific notes under Housekeeping are marked
  as such rather than deleted.

### What session 4 did

- **PR #15** (this file) rebased onto `main` and brought up to date; CI 4/4
  green. **Merging it needs a human**: Claude Code's permission check blocks
  merging a PR without review. The rule above is therefore "the human merges
  the STATUS PR before the session ends".
- **PR #17 — the dyno axis fix**, verified end to end on the Mac:
  `ng test` 14 passed; `build:pages` builds; e2e **12 passed, 0 failed** in
  real Chrome, with 800 / 2900 / 4600 rpm matching native Python (87.3 /
  223.2 / −25.1 N·m); screenshot shows 250 / 100 tops, round labels, shared
  gridlines, zero aligned.
- **The surviving tie-break mutant was untested code, not dead code.**
  Disabling it changes 48,280 of 437,736 layouts (11%), never lowering either
  curve's fill (7,695 equal, 385 better, 0 worse). New test added; mutation
  3 of 5 caught against a passing baseline. The two survivors both reduce to
  "most intervals wins a tie", which chose identically to "nearest five" on
  every input — equivalent over the measured range, recorded as such, not as
  caught.
- **PR #18 — `web/app` in CI**, stacked on #17: `ng test` + `build:pages`.
  Dry-run in a fresh clone; a broken spec and a type error each exit 1.
  E2e is not in CI yet.
- **Found:** `web/app` does not build unless `web/solver` has had `npm ci`
  (it compiles `../solver/src` and needs the `pyodide` types) — TS2307
  otherwise. Undocumented until now; the CI job does both.
- **FINDING-013** (PR #19), from re-measuring bug #3 — see the Findings table.
  The largest item is not the limiter: `crdi15` at 1650 rpm full-load fuel
  oscillates 211.6–237.9 N·m from 6 to 40 cycles and never converges, so
  "use `n_cycles >= 9`" does not hold everywhere.
- **Found:** `NATIVE_REF` for the e2e check was undocumented, and without it
  the check compares nothing against native Python and still passes (9
  checks, not 11–12). How to produce it is under Tests below.

---

## Phase 2 — state

**ADR-001 is validated by measurement.** The unmodified solver runs under
Pyodide 314.0.7 (Python 3.14.2, numpy 2.4.6); the full regression suite passes
there, identical to native. Single-point results agree with native CPython to
~1e-10 relative. Warm, ~1.7× slower than native; ~3.4× on a fresh worker's
first solve. `scipy` is never imported.

**The grid builds under Pyodide too.** The grid cell lives in
`dieselsim/grid.py`, shared by native and browser; a cell built under Pyodide
matches native to 4.8e-10 (performance) and 99.81% bit-identical float32
sources. Phase 2's exit criterion is met at cell level — not yet at full-grid
level in a real browser. *(Session 5: now met at full-grid level in real
Chrome, 816 of 816 values within 8.7e-7, and checked in CI; #48, REVIEW-004.)*

**The SolverPort exists** (`web/solver/`, ADR-010, Accepted). Main-thread
client → real worker loop → Pyodide → unmodified dieselsim. Typed errors,
cancellation per grid cell.

**Grids are cached** (REVIEW-001 M-2, M-3 closed). Keyed on engine + a
fingerprint of the physics sources; a hit never boots Pyodide (0.4 ms vs 8.8 s).

**The first web page exists** (`web/app/`, Angular 22.1.7, zoneless, signals,
OnPush). A dyno pull: pick an engine, torque and power draw in as each point is
solved by Python in a worker. Build with `npm run build:pages` — a plain
`build` renders a blank page on GitHub Pages. 11 e2e browser checks.

**CI runs** (`.github/workflows/ci.yml`: native Python 3.10 + 3.12, the suite
under Pyodide, the SolverPort end to end) on every PR, including stacked ones.
The handoff believed it had never run; PR mergeable states show it had: #13
`clean`, #14 `unstable`. #14 was failing — see *Session 3* below.
**`web/app` is not in CI**: neither `build:pages` nor the e2e checks.
*(Since fixed: #18 and #23 added them, and session 5 added the fixtures
and full-grid jobs.)*

### Session 3 — PR #14 was red, and CI had said so

#14 made `RuntimeInfo.preset_info` required but did not update the
`FakeSolver` in `web/solver/test/cache.test.ts`, so `tsc` failed before any
test ran (`TS2741`). The parent branch passes 20/20. CI caught it; nobody could
read the result with the token in use. Fixed, and `preset_info` — which the
dyno page uses to label engines and choose its rpm sweep — now has a native
test that cross-checks displacement against bore and stroke and each rpm field
against the spec. Mutation-tested: 4 of 4 applied mutants caught (an initial
version let `rated_rpm = max_rpm` through; tightened).

## Where things stand

Architecture is decided (ADR-001 to ADR-010, with ADR-006 on hold). The Python
physics has been through a review pass that produced twelve findings, nine
fixes, a regression suite and a standing audit tool.

### The pattern that came out of it

Five of the first six findings share one shape: **a mechanism fully built, correctly
wired, and fed a quantity that is effectively zero or pinned against a clamp.
None raised an error.**

- `premix_fraction` sat on its 0.02 floor (FINDING-001)
- `sharp` sat on its 3.0 ceiling (FINDING-003)
- every acoustic amplitude was normalised away (FINDING-004)
- the roller-follower branch never accumulated boundary friction (FINDING-005)
- `h_min_ring` was always its 12 nm clamp (FINDING-006)

`tools/audit_dead_signals.py` exists to catch the sixth. **Run it after any
physics change, and port it alongside the solver** — the same failure in
TypeScript would be far harder to find, and Phase 3 ports the whole real-time
loop.

Latest audit: 102 scalars over 8 operating points — **0 dead, 2 frozen
(`fric.h_ring` and `op.h_ring_tdc`: one 12 nm clamp exposed twice), 1 tiny
(`Pb_valvetrain`)**. *(Session 4: this line said "1 frozen (the
now-honestly-named `h_ring_tdc`)"; the audit on unmodified `main` reports 2 —
a miscount, not a change.)*

---

## Findings

| # | Issue | Status |
|---|---|---|
| 001 | `premix_fraction` pinned; Watson correlation out of domain at modern common-rail delays | P-1 and P-2 fixed |
| 002 | `dp/dθ` peaks 10° *before* ignition, so it measures compression; clatter was driven by it | fixed |
| 003 | clatter high-mode weight pinned at its ceiling; divisor 3 orders of magnitude out | fixed |
| 004 | every physical amplitude discarded by two normalisation stages | fixed |
| 005 | roller-follower branch never accumulated `Pb_vt`; cam wear structurally impossible | fixed, **but insufficient** — the rest explained by FINDING-015 |
| 006 | `h_min_ring` always its clamp, and exposed as a headline field | fixed |
| 007 | bug #8 audit; `fuel_for_torque` returned 8.7% different fuel depending on cache warmth | fixed |
| 008 | `theta` indexes two references — per-cylinder local vs global engine angle | **fixed (option D, #30)**: `CycleTraces.theta_global`. *(Was: "documented; roll sign fixed".)* |
| 009 | bug #4 overstated — light-load gap is ~29%, not 2× | measured; no fix needed |
| 010 | bug #2 overstated — the loop converges; real gap is missing p_max/T_exh limits | **limits added (#44)** |
| 011 | the real-time grid was the least accurate part — worst −10.06% | **fixed** — per-cell fresh engines at `n_cycles=9`; now exact vs reference |
| 012 | `transient()` floor sat inside the solver's NaN region and could not catch NaN | **fixed** — stall detection; root cause as first recorded was wrong |
| 013 | bug #3 understated: limiter fitted with EGR on, judged with it off; EGR valve opens 25% for any command; `crdi15` never converges at 1650 rpm | item 1 fixed (#21); **item 2 fixed (#40)**; item 3 **deferred to Phase 3** (caveat online) |
| 014 | `render_transient`: crank phase restarts every chunk; each cross-fade deletes 20 ms (bug #10) | **fixed (#29)**. *(Was: "measured, not fixed — PR #24".)* |
| 015 | cam film ~780× too thick (pressure-viscosity counted twice) + two kinematic errors — why cam wear is negligible | **fixed (#28, #35); wear calibrated (#38)**. *(Was: "measured, not fixed — PR #25".)* |
| 016 | FINDING-001/002 guards rode a 1° ignition-delay step; the real response (~0.2° over 90 K) is quantised by the 1° crank step | **fixed** — PR #27 (ignition resolved within the step) |
| 017 | slap and tick normalised away in the mechanical sub-mix; mechanical-lash presets seat valves off the closing ramp | **fixed (#34, #37, #43)**; by-ear sign-off in Phase 4 |
| 018 | cam lift stepped 4× where the ramps meet the flank (2.0 mm on `hd_i6`), since the first commit | **fixed with option C′ (#42), confirmed by the owner (session 5, part 2)**. *(Was: "owner to confirm", left stale in this table after the confirmation.)* |
| 019 | the aged `crdi15`'s torque gain | a fast-path artifact, not a wear bug; `durability_run` moved to 9 cycles (#45) |
| 020 | the converter's lock-up clutch was numerically unstable, pinned at its clamp (bug #11's jolts) | **fixed (#54)** |
| 021 | `play.py`'s real-time sound was a stale copy; slap, exhaust flow and seating moved it 0.0000% | **fixed (#59)** |
| 022 | intake loudness and turbo boost term normalised away in `render()`, so also in the synth | **fixed with option A (#64)**. *(Was: "open: known defect, the owner's call with the listening review".)* |
| 023 | the synth's slap input (skirt film) sits on its clamp in 240/240 cold cells, 115/240 warm | **open, option A chosen (2026-09-30)**, with the ramp-height parameter in one rebuild. *(Was:)* known defect; the owner chose to do it after 022, in its own rebuild |

### Still open inside those

- **FINDING-005 is not closed.** `Pb_valvetrain` is now nonzero but runs 1e-5
  to 1e-8 of total. The flat-tappet case is *lowest* at 3.9e-7 W — the case
  that should wear most. Cam wear is still negligible and lash still does not
  grow at 8000 h. Suspects: `sigma_cam`, or entrainment velocity at nose
  reversal. Untested. *(Session 4: measured — neither suspect is the main
  cause; the cam film is ~780× too thick. FINDING-015, PR #25.)*
- **FINDING-004 has not been listened to.** Every judgement was band ratios and
  RMS. It changes the character of every rendered sound. Four WAVs were
  produced for A/B; the warm-vs-cold pair at load 0.6 is the one that matters.

---

## Known bugs — status

| # | Issue | Status |
|---|---|---|
| 1 | `n_cycles=6` not converged | **measured 10.8% drift**, worse than documented; test added |
| 2 | Fuelling open-loop on rpm | **measured — loop converges, no instability.** Real gap was missing p_max/T_exh limits: **added (#44)**. FINDING-010 |
| 3 | Torque limiter ±3% | **re-measured in session 4 — understated.** At n=9: `crdi15` −4.3…+6.8%, `crdi_1p5` −0.9…+5.5%. Not only "a symptom of #1": a systematic EGR-schedule bias. FINDING-013. *(Was: "partly addressed by the FINDING-007 cache fix; re-measure".)* |
| 4 | Light-load fuel understated ~2× | **measured — does not reproduce at 2×; real gap ~29%.** FINDING-009. **Closed as a claim fix:** the economy is a steady-state figure, and pages must say so (PLAN Phases 5/6) |
| 5 | `operating_point` path-dependent | **fixed (#41)**: `warm_start=False` resets the turbo and the limiter's calibration starts cold; bit-identical to a fresh engine. *(Was: "root cause found — the API itself still leaks".)* |
| 6 | `l` key dead in DCT | **fixed** — now reports why instead of silently no-opping |
| 7 | No cold-temperature combustion | root-caused through FINDINGs 001–004 |
| 8 | Unknown-provenance code in `engine.py` | **closed** — FINDING-007; found a real cache bug |
| 9 | Worn-vs-new audio pair suspect | root-caused — FINDING-004 and 005 |
| 10 | `render_transient` seams | **measured (session 4)** — FINDING-014, PR #24: phase resets every chunk, and each cross-fade deletes 20 ms. *(Was: "still unmeasured — blocked by FINDING-012".)* |
| 11 | Coast downshift calibration | **fixed in Phase 3** — root cause was the lock-up clutch's numerical instability (FINDING-020); coast downshifts also stretch both phases. *(Was: "deferred to Phase 3".)* |
| 12 | Grade small-angle form | **already correct** — `atan`/`sin`/`cos` all present; entry was stale |

---

## Also found, not yet actioned

*(Session 5: all three items below are done. FINDING-008 is fixed with
`theta_global` (#30); ADR-006 is superseded by ADR-011; the fitted-scalars
claim is corrected in PROJECT_CONTEXT §1.3 (#46). Kept as history.)*

- **Trace arrays index two crank-angle references** — diagnosed as FINDING-008
  (per-cylinder local vs global engine angle). The fix is an API-contract
  decision. **Resolve before the Angular cycle page consumes traces.** Options
  written up in PR #22 (recommended: keep storage, add a per-cylinder
  `theta_global` axis, plus a firing-order guard test).
- **ADR-006 is on hold** and should be reassessed now that FINDINGs 001–004
  have changed the numbers it was decided on.
- **`SPL_CAL` and the 5.0e9 clatter divisor are chosen constants.** The package
  advertises exactly two fitted scalars (`NOX_CAL`, `SOOT_CAL`). That claim is
  no longer accurate; either derive the constants or update the claim.

---

## Tests

```
python3 tests/test_physics.py                    # #81: 70 passed, 0 failed, 2 known with scipy; 65 + 4 skipped without
python3 tools/audit_dead_signals.py              # 0 dead, 2 frozen (the h_ring clamp, known), 0 tiny
python3 tools/validate_table.py [--aged]         # PROJECT_CONTEXT §1.5 re-check: 12 of 12 in band
python3 tools/fixtures/gen_fixtures.py --check   # golden fixtures current (regenerate without --check)
cd web/physics && npm ci && npm test             # TypeScript ports vs fixtures: 5 checks
cd tools/pyodide && npm ci && npm run suite      # the same physics suite under Pyodide
cd web/solver && npm ci && npm test              # 20 cache + 8 live-grid scheduler + 22 round-trip checks through a real worker
cd web/solver && npm run test:live-real          # manual, ~7 min: a 2x2 drivable grid built by 2 Pyodide workers vs the native tool's (see the file's header)
cd web/app && npm test -- --watch=false          # 54 unit tests (vitest)
cd web/app && npm run build:pages                # never plain `build`
cd web/app && CHROME_PATH=... npm run e2e        # dyno pull in Chrome vs native (computes its own reference)
cd web/app && CHROME_PATH=... npm run e2e:grid   # full 8 x 6 grid in Chrome vs native, cell for cell (~9 min)
cd web/app && CHROME_PATH=... npm run e2e:drive  # /drive: prebuilt grid, 60 Hz, 60 s script vs native Python
cd web/physics && npm test                       # 60 checks: fixture ports, 7 live drives, the synth, 8 vehicles + their keys
cd web/app && CHROME_PATH=... npm run e2e:enjoy  # /enjoy: multi-touch on an emulated landscape Pixel, 16 checks
cd web/app && CHROME_PATH=... npm run e2e:sound  # /drive with sound: worklet output, firing harmonics, pitch, mics
python3 tools/fixtures/gen_fixtures.py --only live   # regenerate live drives after a live.py change (~4 min)
python3 tools/build_live_grids.py                # rebuild the prebuilt converged grids after a SOLVER change (~57 min)
```

On macOS, `CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"`.
Golden points are locked at **1e-5** (was 0.5% until session 5; REVIEW-003 m-1),
stored to 9 significant figures, with every re-baseline explained inline.
Known defects report as KNOWN, not FAIL. When one is fixed the suite reports
UNEXPECTED PASS, which is the signal to promote it to a real assertion.
Mutation runs: always `PYTHONDONTWRITEBYTECODE=1`, and a reused pool worker
keeps module-level changes (session 5's EGR slip), so set constants per job.

---

## Branches

Merged branches are **not** auto-deleted: after merging a parent, retarget
its child PR to `main` (`gh pr edit <n> --base main`), or merge top-down.

Checked on 2026-09-28 by content, not commit ancestry. The question asked
of each branch: "does merging it into the roll-up change the tree?"
- **24 branches:** contained, so safe to delete once #65 is on `main`.
- **3 closed-PR docs branches**
  (`diag/bug-10-render-seams`, `diag/finding-005-cam`,
  `docs/finding-008-options`): superseded. Every line is in `main`'s later
  copies, except one pre-fix line in a diag script.
- **`fix/steady-state-controllers`** (closed PR #20): the abandoned
  FINDING-013 option A experiment, 558 lines (`steady_ctrl`), in nothing
  else. It is the only record of that attempt: keep it, or tag it
  (`archive/steady-state-controllers`) before deleting.

Session 4's branch table is in git history.

---

## Next actions

1. ~~**Owner:** merge #50, then #51 → #58, then #59 → #64, retargeting each
   child to `main`.~~ Done (#50, #65, #71). ~~**Now: merge #72 → #76 in
   order**~~ done 2026-09-30. ~~**Now: merge #77 → #78 → #79 → #80 in order**~~
   done 2026-10-02. **Now: merge #81** (it targets `main` directly).
2. **Owner: listen.** On `/drive`: Sound on, keys 1–5 for the mics, "Record
   10 s (WAV)". Or `python3 play.py`. Listen for:
   - `hd_i6`'s tick dominance (13×);
   - a cold start against a warm one;
   - FINDING-022's new balance: a quiet intake at idle, and the turbo
     rising with boost;
   - cold slap, which FINDING-023 still caps.

   ~~Then pick an option for 023 (recommended: A, a temperature-dependent
   clearance), which means one ~70 min grid rebuild. A ramp-height parameter
   separate from `ramp_fraction` is still open for the same review.~~
   Decided 2026-09-30: 023 option A **and** the ramp-height parameter, one
   rebuild of all 8 grids; then a before/after pair for the owner's ears.
   **Built (#78). Listen to `out/listen/review003m5_*.wav`** (or the app on
   the branch), and judge especially `hd_i6`'s idle tick, now 0.23× the
   loudest other source: it may have become too quiet for a mechanical-lash
   truck. `RAMP_SPEED` is the single knob.
3. **Phase 5 — Enjoy mode:** ~~the roster (OPEN-F), the dashboard, and the
   steady-state economy label~~ roster A, the dashboard and the label are
   done (#75, #76). Next: roster B (`v8hd`, an old NA single), and truck127's
   13 unsettled cells, if they show on the dials. Check live friction's cost and the synth's on a
   mid-range phone (REVIEW-005 m-5, REVIEW-006 m-1).
4. **Custom engines, drivable (owner's choice, 2026-10-01), after #78:**
   - a brochure-numbers form, plus JSON import/export in the
     `engines/*.json` format, on Dyno and Grid, through the solver's
     existing `{"headline": ...}` contract, showing achieved against
     requested;
   - then the converged warm+cold grid built in the browser so the engine
     can be driven, plus a vehicle choice. **Measure the in-browser build
     time first**: natively it is 15–20 min on 6 cores.
   - ADR-007 (project JSON) and the Derate-lamp threshold ride along.
5. Follow-ups:
   - a TCU engine-speed match on converter downshifts (REVIEW-005 m-3);
   - ~~`play.py` on `Adr011Grid` (m-6)~~ done in #69;
   - row-sharing the p_max / T_exh check;
   - a timing-based p_max limiter;
   - "life used" labelling.

---

## Housekeeping

- **The PAT has been pasted into chat in every session. Revoke it** and issue
  a fresh fine-grained token; keep it out of any handoff document. Give the
  next one **Checks: read** (and Actions: read) so CI results are visible.
- **Node on the Mac used from session 4:** `node` on PATH is Homebrew
  `node@20` (20.19.0) and Homebrew `node` is 24.2.0 — both below Angular 22's
  minimum (22.22.3 / 24.15.0), and the CLI refuses to start. Session 4 used a
  checksum-verified portable Node 22.23.3 in
  `~/.cache/dieselsim/node-v22.23.3-darwin-arm64/` (prepend its `bin` to PATH).
  System Node was left untouched; upgrading it is the owner's call.
- **scipy on the Mac:** not installed in the system Python, though
  `requirements.txt` lists it and `acoustics.py` renders with it. Session 4
  used an isolated venv, `~/.cache/dieselsim/venv` (numpy 2.1.0, scipy 1.18.1).
- **Git worktrees + Angular:** building `web/app` from a worktree creates an
  empty `.angular/cache/<version>` at the *main* checkout's root. Harmless;
  delete it (session 4 did, three times).
- **Mutation testing in Python: set `PYTHONDONTWRITEBYTECODE=1`.** Bytecode
  is validated by source mtime (seconds) and size; a same-length edit within a
  second otherwise runs stale code.
- **Waiting on a background job with `pgrep -f "<script>"`** matches the
  waiting shell's own command line and never ends — session 4 lost two loops
  to it. Match on something the waiter does not contain, or wait on the PID.
- **macOS `multiprocessing` spawns fresh interpreters:** a pool in a script
  piped on stdin respawns workers forever (they cannot re-import `<stdin>`).
  Put pool code in a file.
- **Dev-container notes (sessions 1–3; not re-measured on the Mac used from
  session 4).** The next two bullets were measured in that container.
- **Background jobs in the dev container must be detached with
  `setsid nohup … < /dev/null &`.** Plain `nohup … &` is killed when the tool
  call returns — measured in session 3 (a 30 s sleep did not survive; the
  `setsid` twin did). Earlier sessions' advice to use plain `nohup` is wrong.
- Solve time in the dev container is ~6.5 s against 1.47 s on developer
  hardware, one core. **Do not benchmark Pyodide here**, and never run two
  heavy jobs at once.
- The solver needs **numpy only**; `scipy.signal` is confined to `acoustics.py`
  and `play.py`. A test enforces this.
- `batch.py` imports `multiprocessing`, which does not exist in Pyodide.
- **Tool-call budget** *(hit in chat sessions 1–3; not yet observed in Claude Code)*. Chat caps tool calls per turn (the "reached its
  tool-use limit" banner); session 3 hit it by spending ~40 calls, many on
  polling. Rules: one call per long job — start it, wait, report in the same
  call, never separate sleep-and-check calls; batch related reads and checks
  into one script; test + commit + push in one call; aim for ~15 calls a
  turn, commit before nearing the cap, and end each turn with a written
  status so a cut-off lands between steps, not mid-step.
- Working style: measure before fixing; ask rather than assume; options come
  with trade-offs and positives; warn before context budget limits.
