# STATUS history: Session 10 (2026-10-19 to 2026-10-22)

Moved verbatim from `STATUS.md` at `a57a6fd`, its lines 24-377, by step A1 of
`reviews/PROPOSAL-modularize.md` (2026-10-28). **This is history, not the present**:
`STATUS.md` is. Struck-through text and in-place corrections are as they were written.
`python3 tools/check_verbatim_move.py history/` proves the copy.

<!-- verbatim: STATUS.md@a57a6fd 24-377 -->
**Session 10, #139 brought up to `main` after #138 (2026-10-22):** the owner asked for the
conflicts to be resolved. Merged `main` (`ac3c15e`) in, no rebase, no force-push.
- **Conflicts, each kept both sides:**
  - `enjoy.html`: P06's route and goal pickers, then P01's switch with its Test button and
    note;
  - `enjoy.ts` and `vibration.spec.ts`: both imports. The spec keeps P06's breaker test, and
    the shake test takes #139's title (its body was already #139's driving shake);
  - STATUS.md: both entries.
- **One check broke after the merge, not the app:** `e2e:enjoy`'s Test tap. P06's pickers make
  the start screen scroll (481 px in 342 at 412 px high), and Test sat below the fold at
  y 410, so the touch landed off screen. The check now scrolls to Test and back up to Start.
  Mutant (Test unwired): caught, 39/1.
- **Verified (local, Node 24.15):**
  - units **164** (29 files; main's 162 + #139's 2), also with `physics-version.ts` aside;
  - `build:pages` builds (`enjoy.css` 5.62 kB, over its 4 kB warning, under the 8 kB error);
  - **`e2e:enjoy` 40/0** (main's 38 + #139's 2).
- **CI on #139 at `fb00d89`: 10 of 10, every job read.**
  - Web e2e: `e2e:enjoy` **40/0** with the four P01 checks (Test tap, events and idle shake,
    driving on-times 33 and 25 ms); the job's other suites 15, 11, 6, 11, 18, 6, 5, 0 failed.
  - Units 164 in 29 files. Physics 102/0/3 on 3.10 and 3.12, Pyodide 81/0/2 (21 skipped).
  - Grid, custom, fixtures and SolverPort passed.
  - **Ready to merge.**
- **Next:** #140 (B-07) conflicts with `main` too; it gets the same merge after #139 merges.

**Session 10, P01 widened: vibration while driving (2026-10-21), `fix/p01-driving-vibration`**
(from `main` at `173a65f`, after #137):
- **The owner: "The vibration is not working."** Measured before touching code:
  - the live site is current (Pages deployed #135-#137; the live `main-RE23DFRX.js` has the
    switch and the `navigator.vibrate` call);
  - on `main` the e2e's P01 check passes (13 calls: the start's shudder, the idle shake
    `12,38`, the shift's jolt);
  - Chromium's source: Android Chrome drops every call on Mute (`VibrationManagerAndroid.java`,
    ringer mode SILENT) with no error, and Blink plays each on-time as its own motor call;
  - 8 of the 10 roster engines idle above 12 Hz firing, so they got 12 ms on / 38 off.
- **The owner's answers:** not muted, Chrome on the S9+; the events and idle are felt, but they
  **expected it while driving**. Chose a Test button plus a stronger shake, and "follows load".
- **Built:**
  - the shake runs whenever the engine does: on-time per 50 ms 15 + 20 × pedal; idle 20 (was 12);
    lugging 35 (was 25); the single's firing pulse 30 + 25 × pedal (idle 35, lugging 55 as
    before);
  - a **Test** button beside the switch: a 300 ms buzz and a note (no API / refused / sent,
    "on Mute, Chrome stays still").
- **Verified (local, Node 24.15 via npx):**
  - app units **147 passed** (27 files), also with `physics-version.ts` moved aside as CI does;
  - unit mutants **8 of 8** caught, baseline passing, all compiled;
  - **e2e:enjoy 33 passed** (31 + 2 new: the Test tap sends `[300]` and shows its note; driving
    on-times 33 and 25 ms); e2e mutants **2 of 2** caught (button unwired, idle-only shake);
  - `build:pages` builds (enjoy.css 4.31 kB, over its 4 kB *warning*, was already 4.16; error
    at 8 kB).
- **Not verifiable here:** the feel on the S9+, and the battery cost of a continuous buzz.
  The switch turns it off.
- ~~**Next:** PR, read every CI job, the owner tries it on the phone after the merge.~~
  **PR #139; CI at `a901895`: 10 of 10, every job read.** Units 147 (27 files); check:labels
  6 of 10; e2e enjoy **33/0** (36 vibrate calls; the Test tap and driving on-times 33, 25 ms),
  drive 11, sound 6, dyno 15, cycle 11, spec 18, sweep 6, durability 5; physics 3.10, 3.12,
  Pyodide, fixtures + TS ports, SolverPort, grid and custom e2e pass (no physics changed).
  **Next:** the owner merges, then tries it on the S9+ (tap Test first, then drive).

**Session 10, #138 brought up to `main` (2026-10-21):** #137 merged at 13:40 UTC, after #136.
- **The conflicts:**
  - Code, resolved by keeping both:
    - `live.py` and `driveline.ts`: the driveline keeps P06's road fields and #137's
      `rho_air`. Drag is `0.5 · rho_air · CdA` times P06's wind-aware air-speed term, so a
      climb's thinner air now reaches drag and the radiator too;
    - `hints.ts`: P06's breaker rule, then `TOUCH`, then #136's `hintInUnits`;
    - both specs.
  - `FINDING-032.md`: `main`'s (fixed) text.
  - STATUS: both sides kept.
  - `live.json`: regenerated from the merged code.
- **Proof, the fixture against P06's pre-merge one:**
  - the eight drives with no route at standard air: 0 values changed;
  - the weather, waxed and limp drives changed by exactly #137's counts (10,710 / 61 /
    11,028);
  - the two route drives changed (6,781 / 11,828): a route's altitude moves the air, which
    now reaches drag and the radiator;
  - added: `dl.rho_air` and #137's fan drive.
- **Verified (local):**
  - suite **97 passed, 0 failed, 3 known, 4 skipped** (96 + #137's test);
  - TS live 68/0, both pars equal to Python;
  - units 162 (160 + #136's 2);
  - e2e: enjoy 38/38 (the goal run; the par in 2.4 s), drive 11/11 (Leh's worker equals
    native Python, worst 0; the US °F check);
  - fixtures current; audit 0 DEAD, 2 FROZEN.
- ~~**Next:** CI on #138, every job read; then it is ready for the owner.~~ **CI on #138
  (`8e631bf`): 10 of 10, every job read.**
  - physics 102/0/3 on 3.10 and 3.12; Pyodide 81/0/2/21 skipped;
  - units 162; check:labels 6 of 10;
  - TS 5 + 68 + 12 + 11; SolverPort 20 + 15 + 30;
  - e2e enjoy 38, drive 11 (the US wax check); grid 9; custom 7.
  - The fixtures job took 19 min 17 s: inside the new 25-minute limit, past the old 15.
  - **Ready to merge.**
- **Owner, on the S9+:** a route's feel, the breaker buzz, a goal run, and P01's vibration;
  the Phase 5 phone re-check. **Open for the owner:** FINDING-033 (recommended A, stall
  an automatic that can't hold its speed, after P06).

**Session 10, #138's fixtures job hit its time limit (2026-10-21):**
- **What happened:** CI's "golden fixtures + TypeScript ports" job was cancelled at 15:17
  against `timeout-minutes: 15`, still generating; not a failure of any check. The other 9
  jobs passed (physics 101/0/3 on both Pythons, Pyodide 80, units 160, e2e enjoy 38,
  drive 10).
- **Measured:** Python runs a par at about real time (66 frames/s).
  - par_city cost 75 s, par_pass 243 s, par_random_leh 542 s (600 s capped, though at 60 rpm
    by 30 s).
  - The live check took 1,189 s on this Mac.
  - #137's fixtures job alone took 13.5 min of the 15.
- **Fixed:**
  - par_pass dropped: the route drives check the hills frame by frame;
  - the Leh par capped at 90 s, still unfinished;
  - the live check takes 556 s now;
  - the job's limit raised from 15 to 25 minutes (`ci.yml`, with the reason);
  - ADR-022 corrected in place.
- **Rechecked:** TS live 63/0, both pars equal to Python; par mutants 8 of 8, the cap
  mutant included.
- **#137:** CI after the merge with #136: 10 of 10, every job read (physics 99/0/3 on both
  Pythons, Pyodide 79, units 145, TS live 56, e2e drive 11 and enjoy 31). **Ready to merge.**
- **#138 conflicts with `main`** since #136 merged. It gets resolved once, after #137 merges.

**Session 10, PRs (2026-10-21):**
- **#135 (P01 vibration) merged** by the owner, 2026-10-20 21:27 UTC.
- **#136 and #137 conflicted with it.**
  - The owner reported it; the conflicts were docs only: STATUS.md in both, and CLAUDE.md's
    units paragraph in #136.
  - Resolved by merging `main` in, keeping both sides; no rebase, no force-push.
  - #136's merged tree: units 145 (P01's 143 + 2), and the build passes.
  - #137's: TS live 56/0, units 143.
  - Both MERGEABLE again. ~~CI rerunning.~~ **CI after the merge: 10 of 10 on both, every job
    read.**
    - #136: physics 98/0/3 on 3.10 and 3.12; Pyodide 78; units 145; TS live 51; e2e drive
      11 (the US wax check passes), enjoy 31; grid 9; custom 7.
    - #137: physics 99/0/3; Pyodide 79; units 143; TS live 56; e2e drive 10, enjoy 31;
      grid 9; custom 7.
    - **Both ready to merge, #136 first.**
- **#138 (P06, tiers 1 and 2) opened**, with `main` merged in. Only P06's commits remain.
- **Merge order: #136, #137, then #138.** #138 will conflict with both (`enjoy/hints.ts`,
  `live.py`, `engine.ts`, `driveline.ts`, `gen_fixtures.py`, `live.json`, `FINDING-032.md`,
  STATUS, CLAUDE.md).
  - Then: merge `main` in, keep both sides, take #137's FINDING-032 text, and regenerate
    `live.json` (`--only live`, after clearing `__pycache__`).
  - Then rerun the TS tests, the suite and e2e:enjoy before saying #138 is ready.

**Session 10, P06 tier 2 built (2026-10-21), on `feat/p06-roads`** (ADR-022). Its PR still
waits for #135.
- **Built:**
  - goals in /enjoy: a Time trial (the fastest lap on the par's fuel) or an Economy run (the
    least fuel within the par's time), chosen beside the route and carried in the link
    (`?route=city&goal=time`);
  - the par, a ghost lap at a steady 70 % in Auto: `live.par_run`, `parRun`, run in
    `par.worker.ts` from `make-engine.ts`, which the drive worker now shares;
  - +5 s for each breaker taken too fast; a stop on overheat or running dry fails a run;
  - personal bests per browser, keyed by engine, route, goal, place and gearbox;
  - the logic in `enjoy/goals.ts`.
- **One change from the proposal (ADR-022):** every par is computed in the browser, at the
  driver's own air and fuel. A shipped par would be right only at standard air.
- **Found:**
  - **FINDING-033** (latent, for the owner): on the fixture's small grid a cold start at
    Leh drags the automatic to its 60 rpm floor, and it stays there "running", never
    stalled. No shipped grid reaches it (40 runs, lowest 561 rpm). Recommended: A, stall
    it so Enjoy offers Restart, after P06.
  - `--check` crashed on the new `pars` key (`compare_live` read it as a drive). Fixed;
    nudging a par's fuel by 0.1 % or its hits by one makes it report stale (see the PR).
  - A par mutant ("the fuel from zero") survived on fresh engines. The tests now use a used
    trip meter.
- **Verified (local):**
  - Python suite **96 passed, 0 failed, 3 known, 4 skipped** (95 + `test_p06_par_run`);
  - TS live 64/0, three pars equal to Python *(since cut to two: see the entry above)* (the city and the pass to the frame; the
    stuck Leh par at its 600 s cap);
  - par mutants 8 of 8 (4 Python, 4 TS); goals mutants 9 of 9;
  - app units 160/160, also with `physics-version.ts` moved aside;
  - e2e:enjoy 38/38: the par in 6.2 s in Chrome; a flat-out city lap was 101.0 s with
    6 breakers on 0.417 L against the par's 0.305 L, so "over the par's fuel";
  - fixtures current; audit 0 DEAD, 2 FROZEN; check:labels 6 of 10.
- **#137 (FINDING-032, the place's air density):** CI 10 of 10, every job read (physics
  99/0/3 on both Pythons, Pyodide 79, units 137, TS live 56, e2e drive 10 and enjoy 29).
  **Ready to merge**, as is #136.

**Session 10, P06 tier 2 measured (2026-10-20), on `feat/p06-roads`** (docs only):
`reviews/PROPOSAL-P06-goals.md` and `reviews/FINDING-032.md`. ~~**Questions for the owner.**~~
**Decided (2026-10-20): every recommendation** (B with C; overheating dropped as a goal;
+5 s a breaker; FINDING-032 A as its own PR). Next: FINDING-032's fix, then the goals.
- **The goals as ADR-016 named them can't be won and lost on their own.**
  - "Reach the pass without overheating": four of five engines peak at 90-96 °C against a
    100 °C warning, flat out, in 42 °C desert, even on a 15 km, 7 % climb. Only single10
    overheats, and it can't climb the pass.
  - A time alone is won flat out, and economy alone by going slower.
  - A time limit plus a fuel budget is a real trade-off, but "beat the par on both" ranges
    from narrow (hatch15, 1 s and 1.7 %) to near-impossible (truck127).
- **Recommended:**
  - B: one score with the par's limit on the other (a time trial on the par's fuel, an
    economy run in the par's time), with personal bests (C);
  - overheating dropped as a goal (a stop on overheat fails any run);
  - +5 s per breaker taken too fast.
- **Measured on the way:** the TS loop reproduces Python's full laps exactly and runs at
  23x real time headless. Named routes can ship pars; a random route's par would compute
  during the first lap.
- **FINDING-032:** the live loop's radiator and fan use sea-level air density everywhere
  (`rho_air = 1.20`). The place's density would add at most 3.2 °C, and no run crosses the
  warning either way. Recommended: A, fix it as its own PR (the live fixtures move at
  non-standard air; no grid goes stale).
- **Elsewhere:** #136 (the wax hint in the driver's units) passed CI 10 of 10, every job
  read (physics 98/0/3 on 3.10 and 3.12, Pyodide 78/0/2/20, units 139, e2e drive 11 and
  enjoy 29). It is ready to merge.

**Session 10, P06 tier 1 built (2026-10-20), `feat/p06-roads`** (3 commits, pushed;
branched from #135's `feat/p01-vibration`, so **its PR waits until #135 merges**, which
avoids a stack). ADR-021, `reviews/PROPOSAL-P06.md`.
- **The owner's choices (2026-10-19):** Enjoy only; tier 1 first, then goals; everything
  in PLAN; named routes and random ones shared by their seed.
- **Built:**
  - routes in the live loop (`live.py`: `Route`, `random_route` by mulberry32,
    `ROUTES` pass/city/desert, `route_from`; `set_route`, `_road`), mirrored in
    `web/physics/src/live/route.ts`;
  - what the engine feels: grade, surface (rolling resistance x 1.0/0.9/2.0/2.6), wind on
    air speed, a breaker's 0.15 s pulse (6 % of speed x j, j from 15 to 50 km/h) and its
    hint, and ISA altitude through the weather table;
  - Enjoy: a route picker (Open road, three named routes, or Random with a seed and New
    road). The picker sets `?route=` in the address, which is the link to share; a note
    gives length, highest point and breakers;
  - Enjoy: a road-ahead strip (1.5 km of profile, surfaces, breakers, and a line with
    grade, surface, wind, height and the next breaker);
  - Enjoy: a two-bump buzz for a breaker taken too fast, and the breaker hint in the
    driver's units.
  - **No grid goes stale**: `live.py` is outside the grid hash.
- **Measured on the way:**
  1. A climb leaked into the grid's shared spec. Mutants found it; `set_route` now
     copies `spec` and `spec.thermal`.
  2. CPython's `**` and V8's differ in the last bit at 1,958 of 20,000 altitudes. The
     ISA power is now a series on both sides.
  3. The DCT on random:1234 is knife-edge: a 1e-9 nudge in Python alone moves an event
     12 frames. That fixture drive uses the converter box.
  4. A `page.goto` late in the Enjoy e2e lost touch emulation. The link check opens its
     own tab.
  5. A strip test passed on all-`NaN` values (its mutant survived). It is fixed.
  All five are in the proposal; traps 1, 2, 3 and 4 are in CLAUDE.md.
- **Verified (local):**
  - Python suite **95 passed, 0 failed, 3 known, 4 skipped** (scipy-gated sound
    tests; was 93 plus the two P06 tests);
  - TS physics 5 + 61 + 12 + 11, 0 failed (route drives per step 2.9e-14, every event
    on the same step);
  - TS mutants 7 of 7 caught; app units 153/153, also with `physics-version.ts` moved
    aside; app mutants 10 of 10 non-equivalent caught;
  - e2e:enjoy 36/36; e2e:drive 10/10; check:labels 6 of 10; audit 0 DEAD, 2 FROZEN
    (the known h_ring clamp); fixtures current.
  - **CI not yet run** (no PR).
- **Next:**
  - open the P06 PR once #135 merges, read every CI job;
  - then tier 2 (goals on a route), with its own short proposal;
  - owner: merge #135; feel P01 and the breaker buzz on the S9+; the Phase 5 phone
    re-check.

**Session 10, B-07 fixed (2026-10-21), `fix/b07-engine-stop`, PR #140** (from `main` at
`173a65f`; independent of #138 and #139):
- **The sheet's B-07** (/enjoy, all engines): "Engine doesn't stop even when we stop the
  engine", sometimes, no steps. Taken by this session; the B-08 session (the sound's spikes,
  synth only) found it in the sheet.
- **Measured before the fix** (headless Chrome, the built app, scratch `b07_repro.mjs`):
  - **The sound outlived Stop:** 1 of 40 Start/Stop tries unthrottled, 2 of 40 at a 4× CPU
    throttle. It was still playing 6 s later at rms ~0.027 (an idle's level), until the next
    Start.
  - **Manual tapped while "Starting…":** at 4×, 6 of 6 stuck there for good; unthrottled,
    1 of 6 drove anyway, in Auto with Manual shown.
  - A double tap on the first Start: 0 of 16. Not fixed; a MINOR note (SR1): it could make a
    second AudioContext.
- **Causes:**
  - the worklet plays its last frame until a `'reset'`. The reset (node port) and the frames
    (their own channel) travel unordered, so a stopping worker's late frame set the sound again;
  - `stop()` did nothing to a load in progress.
- **Fixed** (app only):
  - the worklet takes frames only from its current loop channel, and `'reset'` closes it;
  - `LiveSession.stop()` ends earlier loads (a generation after the fetch), returns `'loading'`
    to `'idle'`, and ignores a stopped worker's messages.
- **Tests:** `e2e:enjoy` +5 on a fresh page, each race forced: `terminate` held back 150 ms;
  the grid's fetch or the worker's `'ready'` held 1.5 s.
  - **Mutants 6 of 6 caught**, baseline 36/0, every run to its totals.
  - The first version's two survivors (rejecting the wait on Stop, a catch-side check) had no
    visible effect and were removed.
- **Verified (local, Node 24.15):** units 145 (also with `physics-version.ts` aside);
  `e2e:enjoy` 36/0; `e2e:drive` 11/0; `build:pages` builds.
- **CI on #140 at `feb0606`: 10 of 10, every job read.** Web e2e: `e2e:enjoy` 36/0, the five
  B-07 checks among them; the job's other suites 15, 11, 6, 18, 6, 5, 0 failed. Units 27 of 27
  files. Physics 99/0/3 on 3.10 and 3.12, Pyodide 79/0/2 (20 skipped); grid, custom, fixtures
  and SolverPort passed. **Ready to merge**, in any order with #138 and #139 (keep both sides
  of STATUS.md's top, and the CSV's rows in ID order).
- **Next:** the owner tries Stop on the phone after the merge. Then, the owner's pick: the
  cold-start ECU proposal (FINDING-031 C, PLAN's "next proposal", docs only) or FINDING-033 A
  (stall an automatic held at its 60 rpm floor; after #138, which changes `live.py` too).

**Session 10, FINDING-032 fixed (2026-10-20), `fix/finding-032-air-density`** (from `main`
at `4c2a301`; independent of #135, #136 and P06):
- **The finding:** the live loop's radiator, fan and aerodynamic drag used 1.20 kg/m³
  everywhere. Found while measuring P06's goals.
  - The owner chose A (fix it), then widened it to the drag.
  - Measured: cooling up to +3.2 °C peak, never crossing a warning; top speed at Leh +3.5 %
    (hatch15) to +6 % (truck127), the desert +1 %.
- **Fixed:**
  - `live.air_density(thermal)` = 1.20 × (p / 101325) × (298 / T), exactly 1.20 at the
    rating's air;
  - the radiator's ram air, the fan's mass flow and the drag all follow it
    (`Driveline.rho_air`, pushed each frame);
  - mirrored in `web/physics`;
  - a new live fixture drive, `adr011_weather_fan` (Leh with the fan running), because no
    drive ran the fan at non-standard air.
- **Proof at standard air:** the live fixture's seven standard-air drives: 0 of about
  172,000 values changed; only `dl.rho_air` was added. The weather, limp and waxed drives
  changed (10,710 / 11,028 / 61 values).
- **Verified (local):**
  - Python suite **94 passed, 0 failed, 3 known, 4 skipped** (main's 93 + 1);
  - `test_finding_032_the_air_density` 5 of 5 parts, mutants 5 of 5 caught; TS live 56/0
    (+ 5, 12, 11), TS mutants 4 of 4 caught. "The fan unscaled" survived until the fan
    drive was added;
  - fixtures current; audit 0 DEAD, 2 FROZEN (the known clamp);
  - e2e:drive 10/10: Leh's worker equals native Python (worst 0), and Leh still ends
    slower than standard air, 68.0 against 77.0 km/h.
- **A trap, written into CLAUDE.md and memory:**
  - A same-length mutant (`(a / b)` to `(b / a)`), restored within a second, left a
    `.pyc` that Python still trusted. One fixture regeneration ran on the mutant.
  - The TS port disagreeing caught it. Caches were cleared and every later check redone.
  - Mutant runs now use `PYTHONDONTWRITEBYTECODE=1`.
- **When P06 meets this:** `live.py`, `engine.ts`, `driveline.ts`, `gen_fixtures.py` and
  `live.json` conflict.
  - Keep both, then regenerate `live.json` with `--only live`.
  - P06's routes change `spec.thermal` with altitude, and `step()` reads it each frame, so
    the drag and the radiator then follow a climb too.
  - `reviews/FINDING-032.md` conflicts as well: keep this branch's (fixed) text.

**Session 10, the units toggle finished (2026-10-20), `fix/units-wax-hint`** (from `main`
at `4c2a301`; independent of #135 and of `feat/p06-roads`):
- **The owner: "Go ahead with the units toggle first."** Checked first: the toggle was
  already merged (#134, 2026-10-19 21:20 UTC) and live. The Pages deploy of `4c2a301`
  succeeded, and the live bundle has the selector and both mpg labels.
- **Found one gap the toggle missed:**
  - The live loop's waxed-fuel hint ("this diesel gels below 18 C") is a string built in
    `live.py` and the TS port, so it stayed Celsius in US units on both Drive and Enjoy,
    while the fuel note beside it said "CFPP 64 °F".
  - No other loop message carries a unit. Checked: every `hint` and `overheat_msg` in
    `live.py`, and Drive's template. On `feat/p06-roads` the breaker hint does, and
    Enjoy already converts it.
- **Fixed:**
  - `units.hintInUnits` rewrites "N C" in the driver's units. Every fuel's CFPP is a
    whole °C, so it gives the same °F as the note: 64, 43, −26.
  - Enjoy's `touchHint` and Drive's status line use it. Metric now reads "18 °C" (was
    "18 C"). The loop's own string is unchanged, so no fixture moves.
- **Verified (local):**
  - app units **139 passed** (137 + 2), mutants **5 of 5** caught;
  - **e2e:drive 11 passed** (a new US check: "gels below 64 °F", matching the note); its
    mutant, Drive showing the raw hint, fails 2 checks;
  - e2e:enjoy 29 passed; check:labels 6 of 10.
  - ~~CI: the PR's checks, read job by job, are reported in the next entry.~~ **CI on
    #136 (`ba877b4`): 10 of 10, every job read.** Physics 98/0/3 known on 3.10 and 3.12;
    Pyodide 78/0/2/20 skipped; units 139 (26 files); check:labels 6 of 10; TS ports
    5 + 51 + 12 + 11; SolverPort 20 + 15 + 30; e2e drive 11 (the US wax check
    passes), enjoy 29; grid 9; custom 7. **Ready to merge.**
- **When `feat/p06-roads` meets this:** `enjoy/hints.ts` conflicts. Keep both: the
  breaker rule and the `hintInUnits` fallback.

