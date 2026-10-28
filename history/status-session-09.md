# STATUS history: Session 9 (2026-10-11 to 2026-10-19)

Moved verbatim from `STATUS.md` at `a57a6fd`, its lines 378-1494, by step A1 of
`reviews/PROPOSAL-modularize.md` (2026-10-28). **This is history, not the present**:
`STATUS.md` is. Struck-through text and in-place corrections are as they were written.
`python3 tools/check_verbatim_move.py history/` proves the copy.

<!-- verbatim: STATUS.md@a57a6fd 378-1494 -->
**Session 9, P01 vibration built (2026-10-19), `feat/p01-vibration`** (on top of
`feat/phase8-units`, #134; its PR waits until #134 merges, to avoid a stack):
- **The owner's choices:** events (start, stall, gear change, the limiter) plus a shake
  while idling or lugging; on by default, with a switch on Enjoy's start screen.
- **Measured first:** the Vibration API (MDN, W3C) takes on/off durations only (no
  strength), needs a tap first, a new call replaces the running pattern; iOS Safari
  has none. A phone's motor can't follow 27 Hz (a 4-cylinder's idle firing), so the
  shake pulses at the firing rate up to 12 Hz (the single at idle, 5 Hz) and is a
  light buzz above (12 of every 50 ms; 25 when lugging).
- **Built:** `enjoy/vibration.ts` (patterns, the controller, the switch kept per
  browser), Enjoy's wiring (an effect on each frame), `DashInfo.cylinders` from the
  grid's spec.
- **Found by the e2e:** no start shudder: the page stopped the motor while the engine
  loaded, and that disarmed the start. Fixed; a unit test now guards it (its mutant
  caught).
- **Verified:** app units **143 passed**; mutants **8 of 8** caught; e2e:enjoy **31
  passed** (the switch on by default; the start's shudder, the idle shake and the
  shift's jolt recorded); TS physics 5 + 51 + 12 + 11. **Not verifiable here: the feel
  on a real phone** (the owner's S9+).

**Session 9, Phase 8's units toggle built (2026-10-19), `feat/phase8-units`** (from `main`
after #133):
- **The owner asked "are we good with the initial plan?":** phases 0-7 done; Phase 8
  open (units, P01 vibration, P06 random roads); Phase 5's exit waits on the owner's
  phone re-check (REVIEW-007 M-1). Then "Continue": the units toggle first.
- **The owner's choices:** driver pages only (Enjoy, Drive, their place notes; the
  engineering pages stay SI), and Metric / US / UK.
- **Built:** `units/units.ts` (exact factors; US: mph, mi, US gal, mpg (US), °F, psi,
  inHg; UK: mph, mi, litres, mpg (UK), °C, psi, hPa), a Units selector beside Place and
  Fuel (`DriveEnvPicker`, both pages), kept per browser (`dieselsim-units`); Enjoy's
  dash (the speedometer gets an mph scale, capped at 150), the strip and the trip
  computer; Drive's readouts; the place and fuel notes. Boost stays a ratio.
  **Correction (2026-10-20):** not quite every figure. The live loop's waxed-fuel hint
  stayed "N C" in US units on both pages. It was fixed on `fix/units-wax-hint` (the
  entry above).
- **Found and fixed:** `check:labels` lost /enjoy and still passed: it found fuel
  figures by the literal "L/100", now printed from units.ts (5 of 10 at a floor of 5).
  It now knows `U().econ`, and the floor is 6; the mutant (without it) fails.
- **Verified:** app units **137 passed** (130 + 7 new; run locally under Node 24.15
  via npx); mutants 7 of 7 caught; `check:labels` 6 of 10; `build:pages` builds;
  **e2e:enjoy 29 passed** (a new units check: US reads mph, mi, gal, mpg (US), °F,
  psi, kept per browser), its mutant (trip left in km) caught; **e2e:drive 10 passed**.
- **Next:** PR and CI; then P01 vibration, then P06's proposal (my recommended order, which
  the owner continued with).

**2026-10-19 — where things stand:** #131 (P09) and **#132 (P13 N) are merged**
(#132 at 2026-10-18 22:57 UTC), so the native one-command build is on `main`.
`main` is merged into `feat/p13-early-stop` (B + C, rule R5; the solver hash
is unchanged by the merge, `42073eceb02c`). **Running:** R5's weather pass
(restarted 2026-10-18 22:45 UTC after the first one hung). Then the acceptance
check, the accuracy table, the suite, and B + C's PR. Details: the
"P13 B + C built" block below.

**2026-10-18: `main` merged into #132 (`feat/p13-native-grid`).** #131 (P09)
merged 2026-10-16 16:19 UTC as `7a15f11`. The one conflict was this file's
top (both sides kept; #132's stale first line of the old **Updated:**
paragraph dropped, `main` rewrote it). `CLAUDE.md`, `tests/test_physics.py`
and `tools/build_live_grids.py` merged by themselves; `add_weather` keeps
both `main`'s `src_meta` and #132's progress callback. The tool now builds
on P09's solver: the merged tree's `grid_hash()` is `8a6fbfc806dd`, the
same as `web/app/public/grids/crdi15.json`'s stamp (inside its first 4 KiB)
and the live site's (read by `build_my_grid.site_stamp()`). The 84-min
full-size build below ran on pre-P09 code; P09's semi-implicit port flow
may change that time, not yet measured. **Checked on the merged tree:**
`test_build_my_grid_tool` passes; a real 2x2 build through
`build_my_grid.py` (hatch15's file plus `"vehicle"`, cells + weather) took
4.7 min, 8 cells and 32 weather solves, 0 unsettled, stamp `8a6fbfc806dd`,
weather table with all 7 `WEATHER_KEYS` (`dpdt_max` included); 0 duplicate
test names after the merge. The full Python suite was not run locally (CI
runs it).
**Next:** CI on the merge; the owner merges #132; mark
`reviews/PROPOSAL-P13.md` decided (N built); then P13 B + C on
`feat/p13-early-stop`.

**Session 9, P13 option N built (2026-10-16), `feat/p13-native-grid` (from `main`):**
- **The owner chose "both, go ahead with N first"** (P13: N, then B + C).
  ~~`reviews/PROPOSAL-P13.md` and PLAN's P13 entry are on #131's branch, not
  here; this branch is from `main` so its grids carry the live site's hash.~~
  *(Corrected 2026-10-18: #131 is merged and `main` is merged in, so both are
  here now, and the hash this branch carries is P09's `8a6fbfc806dd`, which
  the live site serves too.)*
- **Built:** `tools/build_my_grid.py` (engine file from Dyno -> Custom ->
  Export; cells then weather; checks the copy's solver against the live
  site's stamp by a 4 KiB range read; weighted progress with a wave-based
  estimate; prints what to import), `buildgrid/build.sh` / `build.bat`
  (own venv, numpy + certifi, as `bench/`), `buildgrid/README.md`.
  `build_live_grids.build` / `add_weather` take an optional progress
  callback (ordered `imap`, same results). Front end unchanged.
- **Found on the way:** python.org's macOS Python fails every https request
  (CERTIFICATE_VERIFY_FAILED) until its "Install Certificates" step; the
  wrappers install certifi and the check uses it. The first estimate
  (elapsed / done x left) read 344 min at the first row of a ~1 h build:
  replaced by waves (a unit = phase time / waves / weight, the rest over the
  workers).
- **Verified:** a 2x2 grid through `build.sh` from a fresh venv, imported on
  the **live site's /enjoy** and driven (711 rpm, 1st, Auto). New test
  `test_build_my_grid_tool` 7 of 7; mutants 7 of 7 caught (baseline
  passing). ~~**Running:** a full-size build …~~
- **Full size:** 494 solves in **84.4 min** on this M2 (23 min of cells, 61 of
  weather; my tests shared the CPU for the first ~20 min, and laptops throttle
  under long load). The 5.1 MB file **imported on the live site's /drive and
  ran** (746 rpm); at High plateau the page said the torque "follow[s] this air
  through the engine's weather table (measured within 2.7% ...)", the file's
  own check. The README now says 1-1.5 h on a laptop. (Your Drive place was
  put back to Standard air afterwards.)
- **The progress callback changes nothing:** the same engine (2x2, weather
  included) built by `build_live_grids.py` and by the script: **0 of 26 keys
  differ** (build time removed).
- **Python suite 86 passed, 0 failed, 3 known, 4 skipped. PR #132 opened;
  CI 10 of 10 at `78dcdd0`** (every job read; Pyodide 35.3 min). `build.bat`
  is not run (no Windows machine here).
- ~~**Next:** the owner merges #131 (P09, draft: its open questions) and #132
  (whichever is second fixes the STATUS conflict in its first push); then P13
  B + C as one solver change with one rebuild (~5 h with B); mark
  `reviews/PROPOSAL-P13.md` decided once #131 is in.~~ *(Superseded by the
  2026-10-18 note above.)*

**CI on PR #131 (2026-10-15, run 38721543892): three red jobs, one fixed.**
(1) `sweep.e2e.mjs` expected "5.8%"; `accuracy.ts` now says crdi15 -5.9, so
the page says 5.9%. Test changed to 5.9% (not yet re-run). (2) `web/solver`
`roundtrip.test.ts`: its native goldens (`NATIVE_TORQUE` 122.5803,
`NATIVE_CYCLE`, `NATIVE_DUR`) predate P09. Pyodide gave torque 122.4582
(rel diff 9.97e-4), p_max 129.2 bar (6.4e-3), durability 8.4e-4. NOT yet
re-baselined: they need native CPython values, not CI's Pyodide ones.
(3) `test_physics.py` "streaming sound matches the offline render" fails on
3.10 and 3.12 (source level 1.2% off, tolerance 0.03 is met; third-octave
1.24 dB is met; the shape check fails: rumble 1.63 dB vs the 1.5 limit).
NOT yet fixed; the 1.5 dB limit's comment says 1.52-1.56 was seen before.
*Resolved (the FINDING-030 session, same day):* (2) re-baselined from
native CPython (`main`'s tree still gives the old values to every digit);
full `web/solver` `npm test` 20 + 15 + 30, 0 failed. (3) is the noise:
over 12 seed pairs (3 synth x 4 render) the rumble's shape reads
1.02-2.58 dB on `main` (median 1.68) and 0.98-2.54 on P09; every other
source <= 0.68. `main` passed 1.5 dB by the seeds' luck (1.40). The rumble
now has a 3.0 dB limit, the rest stay at 1.5. Mutants 4 of 4 caught
(baseline passing): low edge 40 -> 60 Hz (by the mix's third-octave check,
2.54 dB; its rumble shape 2.34 is under 3.0), high edge 480 -> 320 Hz,
first order, firing modulation off. Run locally with scipy in a scratch
venv (this Mac's Python has none, so the suite SKIPs it).

**2026-10-16, the owner's answers for #131:** ship with single10's 36% Leh
check stated (FINDING-027), and FINDING-031's option A (the cold creep stated;
a cold-start ECU as its own proposal). #131 marked ready for review. P13: N is
#132 (CI 10 of 10); B + C on `feat/p13-early-stop`, rule being revised (see
that branch's STATUS).

**Updated:** 2026-10-15, session 9 (FINDING-030 fixed by option A, the owner's
choice: cold-cell friction at the running walls; the ten grids' COLD cells
re-solved by `tools/rebuild_cold_cells.py`, ~80 min, not a full rebuild; the
cold creep measured for the owner. On `feat/p09-cold-friction`, from
`feat/p09-knock`).
*(Was: "2026-10-15, session 9 (P09: the rebuild finished, but its
cold cells carry about 10× a real cold start's friction (FINDING-030),
which makes the automatic hunt on a cold start; and single10's Leh check is
36% (FINDING-027). Two questions for the owner; the rebuilt grids are NOT
committed. On `feat/p09-knock`).")*
*(Was: "2026-10-15, session 9 (P09: the rebuild finished; single10's
Leh check rose to 36% (FINDING-027's misfire edge moved one node), a
question for the owner; the suites and the PR next, on `feat/p09-knock`).")*
*(Was: "2026-10-15, session 9 (P09: the owner chose k = 4; ADR-019
written; the ten grids' rebuild running since 2026-10-14 22:01 UTC, about
8 h or more; then the full suite, CI and the PR, all on `feat/p09-knock`).")*
*(Was: "2026-10-14, session 9 (P09: the owner chose C; building it
found numerical limits at the 1° step and a ~~22%~~ 18% torque error on single10
(FINDING-028); two questions for the owner, round 2; all on #129, docs
only).")* *(Corrected later the same day: about 18%; the 0.25° solve it was measured against still zig-zags. See FINDING-028.)* *(Was: "P09 measured: FINDING-029 and `reviews/PROPOSAL-P09.md`,
three questions for the owner; on #129 with P10's merge record".)* *(Was: "P10 merged and live: #128 merged
2026-10-14 08:10 UTC, CI 9 of 9 read; Pages deployed `196f8d3`; the owner
listened and accepted it; #129, docs only, open".)* *(Was: "… next, the
owner listens on the phone".)* *(Was: "2026-10-14, session 9 (P10 decided and built: ADR-018, B with
loudness matched at a cruise, FINDING-028 hidden in the synth; on
`feat/p10-sound`, #128 open; #127 merged).")* *(Was: "2026-10-14, session 9 (P10: the owner's answers in, A/B/C
listening files sent; FINDING-028 opened, the solver's idle port flows
zig-zag at its step; all on #127, still open).")* *(Was: "2026-10-13, session 9 (P10, a bassier sound: measured,
feasible, `reviews/PROPOSAL-P10.md`; three questions for the owner. #126
merged).")* *(Was: "Phase 8 accessibility merged and
live: #124 and #125 merged 2026-10-12 UTC".)* *(Was: "Phase 8 started: accessibility,
measured and built on `feat/phase8-a11y`; #124 still open".)* *(Was:
"2026-10-13, session 9 (P08 merged and live: #121, #122,
#123 merged 2026-10-12; `main` equals the build branch)".)* *(Was:
"2026-10-12, session 9 (P08 decided (ADR-017) and built on
`feat/p08-shift-schedule`; #121 → #122 → the build, merge in that
order)".)* *(Was: "P08 measured and prototyped: `reviews/PROPOSAL-P08.md`, three
questions for the owner; #121 open".)*
Read this section first; the dated sections below it are history. *(Was:
"2026-10-12, session 9 (#118, #119 and #120 merged and live; a merge-made
duplicate test removed in #121)"; before that "2026-10-11, session 9 (B-05
and B-06 fixed, PR open; #118 and #119 still waiting to merge)"; before
that "2026-10-10, session 8 (Phase 7 step 7 built,
PR #119; all seven steps built)".)*

**Session 9, P13 B + C built (2026-10-16), `feat/p13-early-stop`** (from
`feat/p09-knock`; pushed, **no PR until #131 merges**, to avoid a stack; ADR-020):
- **B, rule R2** (`cycle.EARLY_STOP_KEYS`, `EARLY_STOP_HOLD` 10;
  `DieselEngine.EARLY_STOP`): the cycle that may end the stop runs as the
  last (traces and knock are recorded only then), the knock's peak restarts
  with each last cycle. **12 solves equal the old solver capped at R2's stop,
  bit for bit** (every perf, meta, waveform and trace value; 4 of them run
  all 200), so the proposal's numbers hold.
- **C:** `thermo._INT_CP_*_REF`; 24 replies byte-identical.
- **Test** `test_p13_early_stop` 6 of 6; mutants 6 of 6 caught, baseline
  passing. One equivalent mutant (a redundant guard) was removed from the
  code. The knock reset matters on 0 of 80 crdi15 cells, so the test forces
  a wasted last cycle (13.81 vs 13.69 without the reset).
- **Before the rebuild:** Python suite 89 passed, **3 failed** (exactly the
  three that read the stale grids and accuracy table), 3 known, 4 skipped;
  the 4 scipy tests in a venv pass; `web/solver` full 20 + 15 + 30, 0
  failed; audit 0 dead / 2 frozen (known) / 0 tiny.
- ~~**Running:** the rebuild …~~ **The rebuild ran 6 h 38 min** (P09's 9 h 39
  min: x1.46; cells x1.86, weather x1.40: each grid's never-settling weather
  pieces still run 200 cycles and the pool waits for them). Unsettled counts
  and Leh checks identical to P09's in all ten grids.
- **Acceptance, against the P09 grids:** cells fine (torque <= 0.025% of the
  engine's peak, EGR <= 0.05 pts, T_exh <= 0.22 K, 0 settled flips, slap
  pulses identical). *My criterion "0.05% of full load at that rpm" was
  ill-defined: at 4600 rpm the governed full-load torque is near zero and it
  read 0.07-0.29%.* **The weather tables are not fine:** torque corrections
  differ by up to 0.49% of peak (truck127) and 0.38% (v8hd). Against 400
  cycles, the worst pieces (hot, thin air, high load) are 0.50% / 0.41% off
  with the early stop and 0.01% / 0.03% with 200 cycles. **R2 stops on a slow
  creep** (under 0.1% within any 10 cycles, ~0.8% over 100). My 108-solve
  sample had cold thin air only, so "within 0.019%" was too general (*my
  miss*; to be corrected in PROPOSAL-P13 and ADR-020).
- **The R2 grids are not committed** (kept in scratch). ~~**Running:** 180
  solves of 400 cycles … to screen drift-aware rules~~
- **R5 replaces R2** (ADR-020 revised, PROPOSAL-P13 corrected visibly): the
  four keys plus the net IMEP, tolerance 2e-4 (was 1e-3), hold 10. Screened
  offline on 180 solves of 400 cycles, then checked on 108 held out: no stop
  worse than the 200-cycle answer beyond its own error and 0.05% of peak
  (worst excess 0.017%, the case R2 missed by 0.50%); x1.65 / x1.71 fewer
  cycles. Rejected on the same data: tighter R2 tolerances (3e-4 still 3
  bad), hold 30 (3 bad), R2 + a drift test (x1.51-1.61).
- **Proved:** 12 solves (8 stopping at 44-196, 4 at 200; hot thin air
  included) equal the old solver capped at R5's stop, bit for bit. **Test**
  7 of 7 parts (a hot-air case where the IMEP is the last key to settle);
  **mutants 8 of 8 caught**, baseline passing (incl. the R2 tolerance and the
  IMEP dropped).
- **Suite on R5:** 90 passed, 2 failed (the stale grids' checks), 3 known, 4
  skipped. The R5 rebuild's cells finished (2026-10-16 15:58 UTC; unsettled
  counts as P09's), but **the weather pass hung**: ~24 min in, all six workers
  were respawned within a minute (killed, most likely by the system), and
  `Pool.map` then waits forever for their tasks; found 55 h later at 0% CPU.
  Killed; **the weather pass restarted 2026-10-18 22:45 UTC**
  (`out/p13_weather.log`) with a watchdog (`HANG?` when the workers' CPU falls
  under 20%). A tool fix to consider: a pool that fails loudly when a worker
  dies (`concurrent.futures`' `BrokenProcessPool`) instead of hanging. **Done:**
  `build_live_grids.SafePool` (`ProcessPoolExecutor`, spawn), used by
  `build_live_grids`, `build_my_grid` and `rebuild_cold_cells`. A worker killed
  mid-task: SafePool raises `BrokenProcessPool` after 0.6 s; `multiprocessing.Pool`
  was still waiting after 30 s. The same 2x2 engine (cells + weather) with
  both pools: 0 of 26 keys differ. The tool tests pass (7 of 7, 6 of 6).
- **The R5 weather pass finished** 2026-10-19 04:26 UTC (5 h 40 min, no hang).
  Totals: cells 5,452 s (P09 9,653, x1.77), weather 20,410 s (P09 26,102,
  x1.28; crdi15's slowed by my identity test): **about x1.34 overall**.
- **Acceptance, all ten grids against P09's: pass.** Cells: torque <= 0.003% of
  peak, EGR <= 0.007 pts, T_exh <= 0.04 K, NOx <= 0.30%, 0 settled flips,
  unsettled counts, slap pulses and Leh checks identical. Weather tables:
  torque corrections <= 0.042% of peak (R2: 0.49%; truck127 0.017%, v8hd
  0.011%). Even the original, ill-defined criterion passes 10 of 10.
- **Accuracy table:** regenerated (`--pull`, `--write-accuracy`): rows
  unchanged, only `ACCURACY_SOLVER`. Fixtures all current; audit 0 dead / 2
  frozen (known) / 0 tiny. `main` (#132) merged in. **Suite: 93 passed, 0
  failed, 3 known, 4 skipped.** **PR #133 opened; CI 10 of 10 at `0768973`**
  (every job read; Pyodide 55.1 min of its 60, close to the limit). Waits for
  the owner.
- **#131 merged 2026-10-16 16:19 UTC** (`7a15f11`). **#132:** `main` was merged
  into it on 2026-10-18 (`d7254e4`, by another session; my identical merge
  was dropped), **CI 10 of 10 at `d7254e4`**; it waits for the owner. Then
  this branch's PR, onto `main`.

**Session 9, P13 feasibility (2026-10-15), docs only, on #131's branch:**
- The owner asked for P13's feasibility (the sheet: "Make the building
  drivable grid faster ... with script. Let the front end stay same for
  now"). Measured on today's code: `reviews/PROPOSAL-P13.md`.
- **The weather table is ~73% of a drivable grid** (the browser builds it by
  default): crdi15 958 s of cells + 2,532 s of weather = 58 min natively.
- **B (stop once settled):** the naive rule is unsafe (10.8% of full-load
  torque at margin 10, via flipped settled flags; EGR/NOx up to 22%). Rule
  R2 (work, boost, intake EGR, turbo speed held 10 cycles): ×1.91, 0 flips,
  torque ≤ 0.019% of full load, EGR ≤ 0.04 pts, NOx ≤ 0.52% over 108 solves.
  One slap pulse moved one 1° step in 1 of 90 cells (discreteness).
- **C:** ×1.083, byte-identical. **Chaining weather solves:** ×1.26 more,
  path dependence 0.15%; not worth it. **N:** the native pieces exist; a
  one-command script is missing.
- **Questions for the owner:** which reading of "with a script" (N, B + C,
  or both, recommended), and whether R2 is acceptable.

**CI on #131 at `8d22068`: 10 of 10 jobs passed** (every job read; physics
3.10 43.5 min, 3.12 41.3, Pyodide **57.5 of its 60 min**, close to the limit).

**Session 9, FINDING-030 fixed (2026-10-15), `feat/p09-cold-friction`** (a
second session; branched from `feat/p09-knock` `50746bc`, to be pushed onto it
as a fast-forward):
- **The owner chose option A** (asked by this session, which had found the
  same problem in crdi15's rebuilt file before reading FINDING-030).
  FINDING-030's "about 10×" is corrected there: over every cell of the ten
  P09 grids the cold/warm FMEP is **5.8–139×** (`main`: 1.08–2.84×).
- **The fix** (`engine.py`, hashed): `cold_start_walls` keeps the
  `WALL_FOLLOW` liner for friction (`_friction_liner`), `operating_point`
  uses it, and `_apply_thermal_state` drops it. Six converged crdi15 cells:
  warm 0 differences; cold gas side within 6.7e-16; cold FMEP = `main`'s
  (1343/0.2: 1.25 bar; P09 13.72).
- **Tests:** `test_cold_start_friction_sees_the_running_walls`,
  `test_shipped_grids_cold_friction` (≤ 4×). Mutants 5 of 5 caught, baseline
  passing. Committed `9429e9c`.
- **Cold cells only, not a 9.7 h rebuild:** `tools/rebuild_cold_cells.py`
  (new). It refuses unless the pre-change tree hashes to the stamp
  (`6ab9760d77b9`, checked) and each cold cell changes only in perf
  torque/power/bsfc/fmep/nox and meta Pb/load (measured: nothing else moves;
  traces and waveforms byte-identical). New hash `8a6fbfc806dd`.
  ~~**Running**~~ **Done**: 480 cold cells in ~70 min, no refusal; each
  grid's worst cold/warm FMEP is `main`'s again (1.78–2.84×; was 5.8–139×).
  Committed with the ten grids (`ecc9dc2`, the first commit of P09's
  rebuilt files).
- **The cold creep, measured for the owner** (P09 physics, untouched by the
  fix): crdi15 automatic at 20% pedal from a 25 °C start sits at 779 rpm /
  5.8 km/h for 74 s (old grid: 11 s). The cause is heat transfer, mostly
  the piston: at 800 rpm / 20% the indicated torque is 24.7 warm, 23.6
  walls-following, 19.7 true cold; wall heat 48% → 55% → 68% of the fuel;
  the piston alone at 273 K gives 75% of the loss, the head 33%, the liner
  and port ~0. The delay is not the cause at idle (premix on its 0.72 cap).
  The live loop warms every wall as one 60 s lump; a real piston crown
  heats faster (not yet sourced).
- **FINDING-031 (new, for the owner): light pedal from a cold start.**
  crdi15 / crdi22 / hatch15, TC and DCT, warm / 25 °C / 0 °C, 20% and 30%,
  fixed P09 grids against `main`'s. (1) At 0 °C, 20% pedal never moves the
  car **on `main` too**: the fuel-fraction pedal against cold-oil friction,
  not P09. (2) P09 slows cold launches 1.3–3×. Over the edge: crdi15 TC
  25 °C 11.7 s → never (74 s in a 120 s run), hatch15 TC 25 °C 10.1 → 53 s.
  A 15 s chamber constant helps only partly (37 s, 31 s; 0 °C still never).
  Options A (accept, state it) / B (faster warm-up) / C (a cold-start ECU:
  fast idle, pedal fuel covering the extra friction). Recommended A for
  P09's merge, C as its own proposal.
- **Verified on the final grids:** Python suite **91 passed, 0 failed, 3
  known, 4 skipped** (no scipy here); audit 0 dead / 2 frozen (known) / 0
  tiny; `gen_fixtures --check` all ok; TS 5 + 51 + 12 + 11 and solver
  20 + 15, 0 failed. **App units not run locally:** this Mac's Node is 20.19
  and 24.2, Angular needs >= 22.22.3 / 24.15; CI runs them (no app code
  changed; only grid data and the accuracy table's hash).
- **Pushed** onto `feat/p09-knock` (fast-forward from `50746bc`); PR to
  `main` opened as a draft. **Open for the owner:** single10's Leh check
  36% (FINDING-027, below), and FINDING-031 (A/B/C). The main checkout
  still holds the rebuild's uncommitted pre-fix grids: discard them there
  (checkout of `web/app/public/grids`) before pulling.
- **PR #131** (draft, `feat/p09-knock` -> `main`). First CI run: 6 jobs
  passed (both grid e2e, golden fixtures + TS ports, web app, web e2e,
  custom engine e2e); **SolverPort failed 5 of 30**: `web/solver`'s
  round-trip test pins native references (crdi15 1800 rpm / 60%) that
  P09's solver moved. Neither this session nor the last ran the full
  `web/solver` `npm test` (only `test:fast`): *a miss.* Re-baselined
  with the old values kept in the comments; `main`'s solver tree still
  gives the old ones to every digit. Local full run 20 + 15 + **30**, 0
  failed. **claude-review failed** on the workflow's bot rule ("initiated
  by non-human actor: claude ... Add bot to allowed_bots"), not on the
  code: the owner's call.
- **Next:** read every CI job of the new run; the owner's two answers.

**Session 9, the rebuild done (2026-10-15), `feat/p09-knock`:**
- **The rebuild** ran from 2026-10-14 22:01 to 2026-10-15 07:40 UTC (9 h
  39 min): the cells take 231–1509 s per grid and the weather 853–4550 s.
  Unsettled cells per grid: 0–22; weather pieces: 0–68.
- **The Leh checks moved by 0.11 points or less, except single10's: 7.20%
  → 36.08%.** It is FINDING-027's misfire cliff. Its 58 kPa / 25 °C node at
  2254 rpm and full load now misfires on some cycles: 3.36 N·m, unsettled;
  before P09 it fired. Fresh solves reproduce the table exactly. The cliff
  lies between 58 and 61 kPa. Five of the six check cells are within
  2.3 N·m. Recorded in FINDING-027 as an update. **Question for the owner:**
  ship with 36% stated, or more work first (see the reply).
- **Drive's place line was stale**: "Friction and sound stay sea level's".
  It now says the knock follows the air. The unit spec was updated, and a
  mutant (the old sentence) is caught, baseline 7 of 7. Units 130 of 130.
- **Audit:** 0 dead, 2 frozen (known), 0 tiny. **Solver fast tests:** 20 +
  15, 0 failed.
- ~~**Running:** the full Python suite, and the Dyno accuracy table (`--pull`,
  then `--write-accuracy`).~~
- **The full Python suite on the rebuilt grids: 74 passed, 15 failed, 3
  known.** Stage 2 had been checked with its own tests and mutants only.
  The full suite was not run after `40e0699`, and should have been. *(My
  miss.)* The 15:
  - the accuracy table: regenerated (`diag_torque_limiter.py --pull`, then
    `--write-accuracy`; rows within 0.2 points);
  - 9 golden points: stage 2 moved them. The stage-1 tree (`15a19a6`)
    still gives the old values to 6 decimals. Re-baselined with the reason
    (p_max +0.8 to +2.4%, torque −0.015 to −0.09%);
  - 2 weather tests read `dpdt_max` from `perf`; it is in the cell's meta
    table (`src_meta`). Fixed. The toy table gains a knock slope, and its
    linear check is relative past 1 (the knock is ~1e9);
  - the live synth test divided 0 by 0. Unstepped, it sits on the grid's
    no-fuel row, where the burn-law knock is 0 (FINDING-029; the old grid
    had 0.6–6.5e9 there, an artefact). Guarded;
  - ADR-011 live friction and P08: their helpers warmed the coolant but
    not `T_chamber`. Fixed: own-cell diff 0.0, and P08 7 of 7.
  Each fixed test passes on its own. The full suite has not been rerun yet.
- **FINDING-030 (new): the cold cells' friction.** `cold_start_walls` puts
  the liner at 273 K, and `friction.py` takes the skirt's film at liner
  − 20 K. crdi15 at 1343 rpm / 0.2: FMEP 13.73 bar (warm 0.98, cold before
  P09 1.26), with the skirt 19.1 kW. The driven torque is unaffected (the
  live friction), but P08's map reads the cells' brake torque. On a cold
  start crdi15 at 50 km/h hunts (7 shifts in 20 s at 120 s), and the gears
  differ from `main`'s for about 2 minutes. Options A/B/C in the finding;
  recommended A (friction at `WALL_FOLLOW`'s walls in the cold cells),
  which means another ~9.7 h rebuild.
- **A sound change to tell the owner:** with the knock from the burn law,
  the combustion part goes silent where no fuel burns (overrun, fuel cut).
  Before, the old measure played 0.6–6.5e9 there.
- **The rebuilt grids are left uncommitted** until FINDING-030 is decided:
  option A would replace them, and committing 50 MB twice bloats the
  history.

**Session 9, k chosen (2026-10-15), `feat/p09-knock`:**
- **The owner chose k = 4** (`KNOCK_GAIN_EXP`, `livesound.py` and
  `synth.ts`). Measured at idle (`tools/p09_listen.py` with k = 0 and 4;
  crdi15 and hatch15, cabin and intake): a cold start or Leh is +2.4 to
  +4.4 dB, both +8.7 to +10.2 dB. **Not answered:** whether the warm
  sea-level sound differs from P10's.
- **The sound fixture** gains a fifth segment with `dpdt_max` / `dpdt_ref`
  (×1.4), so the TS gain path is checked. `gen_fixtures --check`: all ok.
  TS: 5 + 51 + 12 + 11, 0 failed. **The gain-path mutants: 3 of 3
  caught** (baseline passing): T7, the gain off (it survived at k = 0), the
  ratio inverted, and k = 3. Each fails "the synth matches livesound's pure
  mode", and k = 3 also fails the constants check. The gap is closed.
- **ADR-019** written. CLAUDE.md gains the P09 traps (`dpdtheta_knock`, the
  true cold cells, `T_chamber`, the knock the synth hears); the
  FINDING-028 trap is struck through. PLAN's P09 entry is updated.
- **The cold-start model is narrower than round 2's wording.** The earlier
  chat said "Cranking speed won't be modelled", but the docs didn't record
  it. ADR-019 now does: cold walls plus a chamber warm-up, no cranking
  speed, and cold intake air via the manifold walls and the weather table.
- **The rebuild is running** (`out/p09_rebuild.sh`, log
  `out/p09_rebuild.log`): `build_live_grids.py`, then `--weather`. Started
  2026-10-14 22:01 UTC. `livesound.py` is unhashed, so k didn't wait for it.
- **Next:** when it finishes, run the full Python suite (the three grid
  tests should pass again), the accuracy table, audit_dead_signals,
  Pyodide, and the web suites; then push, open the PR, and read every CI
  job.

**Session 9, stage 2 built (2026-10-14), `feat/p09-knock` `40e0699`; ~~the
listening round is with the owner~~ (the owner chose k = 4 on 2026-10-15):**
- **The burn law** (`cycle.PREMIX_DELAY_EXP` 0.5, `D_PRE_FLOOR` 2°): no
  φ term, and faster by (delay / injection)^0.5 once the delay outlasts
  the injection. crdi15 at idle: Leh +17%, a cold start +17%, both +40%;
  1500 / 30%: +4%, +15%, +13%. Sea level, roster: full-load torque
  ≤ 0.53%, BSFC ≤ 1.2%, p_max −0.8% to +5%; the idle knock ×1.79. The
  exponent is chosen, not calibrated (b = 1 runs into the floor and goes
  flat).
- **The cold start:** the grid's cold cells have every wall at 273 K
  (`engine.cold_start_walls`). The live loop's `T_chamber` warms with a
  60 s time constant (cools with 600 s) toward the WALL_FOLLOW steady value
  (`chamber_follow`, crdi15 0.35), and every warm/cold blend uses it. The
  worker sends it to the worklet.
- **Hearing it:**
  - the weather table gains `dpdt_max`;
  - the live loop's `_knock()` sets `knock_live` (the blend at T_chamber
    plus the weather's change) and `knock_ref` (warm, standard air) each
    step;
  - the synth multiplies the knock by `(dpdt_max/dpdt_ref)^KNOCK_GAIN_EXP`;
    the exponent is 0 until the owner picks it;
  - `acoustics.KNOCK_REF` 7.5e9 (×1.5).
  - Python, TS and the fixtures all mirror it. The live fixture's grid
    carries synthetic knock tables, so the path is checked in both
    languages.
- **Tests:** 2 new Python tests, both passing; TS 5 + 51 + 12 + 11. ~~**TS
  mutants: T1–T5 caught so far** (running).~~ **TS mutants: 8 of 9 caught**
  (baseline passing). T7, the synth's gain switched off, survives, because
  `KNOCK_GAIN_EXP` is 0 (see the gap below). **Python mutants: 8 of 8
  caught** (baseline 2 / 0): the delay term off, the φ term back, cold
  walls following the coolant, the loop blending at the coolant, the
  chamber 10× slower, the synth's gain ignored, the weather dropping the
  knock, the chamber's target = the coolant.
- **Listening files sent** (`tools/p09_listen.py`, crdi15 and hatch15,
  cabin and intake, k = 0 / 3 / 5 / 8). At k = 3, a cold start or Leh is
  +1.5 to +3.3 dB and both +6.0 to +7.7 dB; at k = 5, +3.4 to +5.5 and
  +11.4 to +12.9 dB.
- ~~**Gap, for after the owner picks k:**~~ *(Closed 2026-10-15: the
  fixture's fifth segment; T7 caught.)* While `KNOCK_GAIN_EXP` is 0 the
  TS synth's gain path can't be checked by the sound fixture. Add a fixture
  segment with `dpdt_ref` once k is non-zero.
- **Then:** set k, rerun the suite, the rebuild (10 grids with weather
  tables, ~8 h+), CI, the PR.

**Session 9, stage 1 written into `dieselsim/` (2026-10-14), branch
`feat/p09-knock` (from #129's head; one branch for stage 1, stage 2 and
the rebuild; NOT mergeable before the rebuild, the shipped grids are stale):**
- `cycle.implicit_flow`: closed-form semi-implicit port flow, at the
  valves and at an NA engine's air-side orifices. It returns the explicit
  flow unchanged unless the step would overshoot.
- `cycle.wiebe_step`: the pilot and main burns integrated exactly over each
  step.
- `CycleResult.dpdtheta_knock`: the burn law's peak `(γ−1)/V × dQ/dθ`,
  8 samples a step, cylinder 1, last cycle; `acoustics` meta `dpdt_max`
  reads it. The references are unchanged: at full load it reads ~1.47× the
  old trace value, and ~1.03–1.06× at idle and cruise.
- **Measured:** 8 points take 29.0 s against 28.7 s today. single10 is
  identical to the prototype; crdi15 differs slightly because the pilot is
  now integrated exactly too.
- **Tests:**
  - new `test_port_flow_does_not_overshoot` (crdi15 and the built-in
    `single`, 1° against 0.5° at idle);
  - new `test_knock_from_the_burn_law` (spread over sub-degree SOI shifts
    0.9%; the old trace value 15.9%);
  - `test_port_flow_zigzag_is_not_heard` now requires the raw ripple
    < 0.1 (it is 0.037).
  - All three pass. ~~**Running:** 7 mutants against a baseline, and the
    full suite …~~ **Mutants: 7 of 7 caught** (baseline 3 / 0). M7 (the
    sound's averaging off) survived at first, because the solver no longer
    zig-zags; the test now also makes the averaging null a synthetic 1°
    zig-zag.
  - **Full suite on stage 1** (run before the test updates): 76 passed,
    14 failed, 3 known. Of the 14:
    - 9 golden points, re-baselined (`15a19a6`): p_max −1.5% to −2.0%,
      torque −0.04% to +0.004%;
    - FINDING-025's fuel `==`, which passed by luck (the limiter path's
      `cmd × 1e-6 × 1e6` round trip lands one ulp away for some commands);
      now relative 1e-12, with the reason;
    - the old zig-zag test (already updated);
    - 3 that compare against the shipped grids (the accuracy table's hash,
      cell from pieces, weather pieces): **stale until the rebuild**.
  - Audit: 0 dead, 2 frozen (known), 0 tiny. Fixtures: all current.
- **Found for stage 2:** the grid's "cold" cells are not a cold start.
  With the coolant at 273 K the walls follow it only partly (`WALL_FOLLOW`):
  crdi15's piston is at 510 K and its head at 395 K. Every wall at the
  air's temperature lengthens crdi15's idle delay +24% (sea level), +34%
  (−20 °C) and +30% (Leh), against +9% for the cold cell. With stage 1's
  burn law that is still only +8–11% knock. Also seen: at −20 °C with the
  oil at −20 °C, crdi15's idle torque reads −1561 N·m (oil friction; not
  looked into).
- **Running:** the owner's cases (warm and a true cold start, sea level
  and Leh) under stage 1, V1, and V4 with b = 0.5 and 1.0.

**Session 9, stage 1 (the numerics) started (2026-10-14), scratch only:**
- **Why brute sub-stepping is costly:** with 4+ cylinders some valve is
  always open, and single10's exhaust manifold (0.43 L) is smaller than
  its cylinder (1.0 L). So both the cylinder side and the manifold side are
  fast, and sub-stepping both is about ×2–4 solve time.
- ~~**Trying first, a flow limiter:** … **Running:** …~~ **The limiter
  failed:** it biased PMEP even at 2000 rpm, and it didn't touch single10.
- **What works, a semi-implicit flow** (`F28_IMP`, `F28_AMB`): where the
  explicit flow would carry Δp past zero within a step, it is solved
  against the end-of-step pressures. That covers the valves and the NA
  engine's plenum-to-air and manifold-to-air orifices. crdi15 idle ripple
  0.80 → 0.022, VE 1.2613 (0.25°: 1.2626). single10 ripple 0.98 → 0.04, VE
  1.012 → 1.263, consistent between 1° and 0.5°. Details in FINDING-028,
  where "22%" is corrected to **about 18%**: the explicit 0.25° solve still
  zig-zags on single10.
- **Stage 1 across the roster** (semi-implicit flow + exact burn integral
  + knock from the burn law; 6 engines, 24 points): full-load torque within
  0.27%, BSFC within 1% (single10 up to −4.8%), p_max 1–2% lower, knock +1%
  (single10 idle −20%). **Solve time +50%** (118.8 → 178.1 s).
- **Open:** PMEP converges only first-order (crdi15 idle 1788 / 3179 /
  3562 Pa at 1 / 0.5 / 0.25°; the Cycle page shows it). **Running:** each
  piece timed alone, with an Illinois root-finder in place of 40 bisection
  steps.

**Session 9, P09 round 2 (2026-10-14, later): two questions for the owner**
(the end of `reviews/PROPOSAL-P09.md`). Nothing in `dieselsim/` is changed.
The prototype is saved as `tools/p09_prototype.diff`, with its switches
documented; the scratch copy itself is gone with the session.
- **Fixed in the prototype:**
  - the knock now comes from the burn law (`(γ−1)/V × dQ/dθ`, 8
    sub-steps a step): 3.64 / 3.63 / 3.61 at 1.0 / 0.5 / 0.25°;
  - the burn is integrated exactly over each step.
- **Best law, V4 b = 0.5** (crdi15 idle, at 0.25°): Leh +12%, cold start
  +6%, Leh cold +11% (today −18%, +1%, −17%). Under 0.3 dB in the mix, so
  Enjoy hears it only through the synth's gain `k`.
- **FINDING-028 option B, first try (linear orifice): does nothing.** The
  cure is to sub-step the gas exchange.
- **New and serious, in FINDING-028:** single10's 1° grid is about ~~22%~~ 18% low
  on torque at 600 rpm and 40% load. Against 0.5° / 0.25°: VE 1.012 /
  1.147 / 1.265, torque 7.98 / 10.14 / 10.23 N·m. At 1100 rpm and 30% it
  is −3%.
- **At 1° the Leh-cold idle point is an outlier in every variant.**
- ~~**Asked:**~~ **Answered:** "Staged (Recommended)" and "Add a
  cold-start model". Stage 1 (the numerics, own PR) → stage 2 (P09, with a
  cold-start model) → one rebuild. *(Was: "Asked: 1. the order …; 2. the
  cold start …".)*

**Session 9, P09 decided: option C (2026-10-14), being designed:**
- **The owner's answers:** "1. C", "2. Hear in enjoy also", "3. modern
  CRDi at Leh and a cold start". The solver fix shares a rebuild with
  FINDING-028's option B (ADR-018).
- **Cold start, measured** (crdi15 idle, walls at 273 K as the grid's
  cold cells): the delay +9%, the knock +10% today (+17% with V1). But with
  V1 a cold engine at Leh knocks *less* than a warm one there (1.31
  against 1.39). At idle the premixed burn takes about 5°, near its 4°
  floor, and nothing lets the delay speed it up.
- **V3** (V1, plus `d_pre × (0.3 ms / τ)^a`) **behaves erratically**: at
  a = 1, crdi15's Leh idle knock falls to 0.41. ~~Suspected: a premixed
  spike 2–5° wide is barely resolved by the solver's 1° step. **Running:**
  the same points at 1.0 / 0.5 / 0.25° steps, for today, V1 and V3.~~
  **Found, two numerical causes:**
  1. **The sound's knock value depends on the step** (now in FINDING-029):
     `np.gradient`, a central difference, halves a one-step rise. V3 at
     Leh idle reads 0.41 / 1.69 / 2.40 at 1.0 / 0.5 / 0.25°, while the
     solver's forward-difference `dpdtheta_comb` reads 5.19 / 5.16 / 5.06.
     The fix: the forward difference. Part of today's −13% at Leh is this
     artefact; at 0.25° it is −7%.
  2. **The burn adds `rate × step`, with the rate sampled at the step's
     end.** For a premixed spike only a few steps wide, that depends on
     where the start of combustion falls inside the step. V4
     (`d_pre / max(1, τ/inj_dur)^b`, which acts only where the delay
     outlasts the injection) was still erratic with the forward difference
     (at b = 1 a cold engine reads below a warm one). **Prototyped:** the
     burn integrated exactly over each step (the cumulative Wiebe's
     difference). **Running:** its step test with V1 and V4 (b = 0.5, 1).
  - On the solver's stable number, V3 already does what the owner asked:
    crdi15 idle, cold +15%, Leh +37%, Leh cold +40%. But its fixed 0.3 ms
    reference made single10's burn 3× faster at sea level (knock ×3,
    p_max +24%), so it was dropped for V4.
- **FINDING-028 option B, prototyped** (scratch `thermo.py`, switch
  `F28_EPS`): `orifice_mdot` linear in Δp below `1 − pr = ε`, matched to
  the isentropic law there, so the flow's slope at Δp = 0 is finite.
  Test script ready (`f28_eps.py`: ripple, PMEP, VE, torque against a
  0.5° solve).
- **The sound side, designed (not built):**
  - the live loop carries a reference knock, `dpdt_ref` (warm, standard
    air, same cell);
  - the weather table gains a `dpdt_max` key (one more key from
    `solve_cell`'s `_meta`);
  - the synth applies `(dpdt_max / dpdt_ref)^k` to the knock, so warm
    standard air is unchanged bit for bit;
  - `k` is chosen by ear before the rebuild. It is a playback gain, not
    physics, and will be documented as such.
- Watson's (1980) premixed shape factors could not be verified (the paper
  is paywalled, and a thesis link was dead), so they aren't used.

**Session 9, P09 being measured (2026-10-14), scratch only so far:**
- The sheet's **P09**: "Knocking: Increased knocking on high altitude"
  (priority 2). Also new in the sheet: **P11**, "Number or gear selector:
  give an option to choose number of gears to user" (priority 1, "Into
  Consideration"); not looked at yet.
- **Measured (scratch `p09_measure.py`)**, at sea level, Leh (3500 m,
  20 °C) and 5000 m:
  - The ignition delay lengthens as it should (crdi15 idle 1.88 → 2.66 →
    3.60°; single10 1100/0.3 6.26 → 9.13 → 12.41°).
  - But **the knock the sound reads (`dpdt_max`) mostly falls**: crdi15
    −13% idle, −7% cruise and −12% full pedal at Leh; 6 of 9 points fall.
    ~~Only single10 at a cruise (+7%) and truck127 at full load (+6%, its
    smoke limiter cuts the fuel) rise.~~ Three rise, by 3–7%: single10 at
    idle (+3%; I left this one out at first), single10 at a cruise (+7%)
    and truck127 at full load (+6%, its smoke limiter cuts the fuel).
  - Two causes in `cycle.py`:
    - The premixed fraction is pinned at its 0.72 cap at every idle point.
    - The premixed burn's duration is `0.30 × burn_dur`, and `burn_dur`
      grows with φ, so the leaner air of altitude makes the premixed
      spike burn **slower**. The literature says the opposite (a longer
      delay makes the premixed burn more abrupt).
  - **And the live loop can't hear any of it:** the weather table's keys
    are `torque_ind, fuel_kg_h, boost, turbo_rpm, afr, T_exh`. The sound
    in Drive and Enjoy stays the grid's, at sea level.
- ~~**Running:** a prototype in a scratch copy of `dieselsim/` (V1: the
  premixed burn no longer slows with φ; V2: V1 plus the cap 0.72 → 0.95),
  with a switches-off run that must equal the baseline first.~~ **Done:**
  - The switches-off run equals the baseline at 27 of 27 points.
  - **V1 turns the trend:** crdi15 idle at Leh −13% → **+21%**, single10
    at a cruise +18%, truck127 at full load +14%. The turbo engines under
    load stay flat or slightly down.
  - **V1 at sea level, six roster engines:** full-load torque ≤ 0.6%, BSFC
    ≤ 0.5%, p_max up to +5.1%, but the knock moves −11% to +31%. That would
    change the ADR-018 sound unless the synth's knock reference is
    re-scaled.
  - V2's cap only makes idle louder at sea level.
  - **Not audible:** V1's ×1.14–1.21 knock is 0.0–0.4 dB at the cabin,
    intake and engine-bay mics, and ×2 is 0.1–2.0 dB. After P10 the
    exhaust carries the sound.
  - Literature: SAE 2013-01-1516 (idle, 550–4500 m), read from its
    abstract page: the delay is longer, the combustion **shorter**, and
    peak heat release rises up to 3300 m. The two MDPI papers returned 403
    and are unverified.
- **Written:** `reviews/FINDING-029.md` and `reviews/PROPOSAL-P09.md` (A
  record only, B physics at the next rebuild, C B + audible in Enjoy, D
  fake it in the synth; recommended A now, B at the next rebuild), plus
  `tools/p09_altitude_knock.py`. **Three questions for the owner** are at
  the end of the proposal.

**Session 9, P10 built (2026-10-14), `feat/p10-sound`:**
- **The owner's decisions:**
  - "B sounds better, go with C for findings": B for the sound, and
    FINDING-028's option C.
  - Loudness, asked separately: "Match at cruise".
  - All recorded as ADR-018.
- **Built:**
  - `acoustics.SOURCE_BALANCE`: exhaust ×8, clicks ÷3, combustion ×0.6,
    turbo ×0.4.
  - `HISS_WEIGHT` 0.18.
  - `MIC_TRIM`: exhaust tip 0.24, intake 1.73, engine bay 1.83, cabin 0.89,
    outside 0.79, the median over the roster from `tools/p10_trim.py`.
  - `smooth_port_flow` (2°), in `render` and `LiveSynth.set_sources`.
  - All mirrored in `synth.ts`; the sound fixture regenerated.
- **Measured** (crdi15, cabin):
  - centroid 852 → 483 Hz at idle, 707 → 426 at 2000 / 0.3, 746 → 216
    at full pedal;
  - level: idle −4 dB, cruise about the same, full pedal at rated rpm
    about +10 dB;
  - the exhaust-tip mic no longer saturates.
- **New, and to tell the owner:** revved, the exhaust dominates the tip,
  cabin and outside mics alike. At 4,376 rpm the tip and cabin are within
  0.5 dB of each other, and as bright. The intake and engine bay stay
  distinct. The sound e2e's mic check was therefore moved to idle, where
  they differ by 8–9 dB.
- **Grids re-stamped**, not rebuilt: `restamp_grids.py` changed only each
  file's 64-byte stamp, 70fdc89ed12d → b45ef76512c5, for the 10 grids and
  the accuracy table. No cell reads `render` or the mix; the cells come
  from `build_sources`, which is unchanged.
- **Tests:**
  - New: `test_port_flow_zigzag_is_not_heard` and `test_p10_deeper_sound`.
  - `test_livesound_matches_render` now compares the mix in steady state,
    over bands within 50 dB. Before, render's cold start showed between the
    exhaust's harmonics (6.88 dB at 31–40 Hz). Main, compared the same way,
    is 1.52 dB there and this branch 1.41: a thin margin under the 1.5 dB
    bar, from the rumble's two noise generators.
  - Mutants: Python 9 of 10 caught. The survivor, M5 (hiss 0.18 → 0.45),
    moves the intake centroid only 7–9%. TypeScript: 5 of 5 caught. Both
    against passing baselines.
  - Local results: TS physics 51 / 11 / 11 passed; app units 130 / 130;
    e2e:sound 6 / 6; e2e:enjoy 28 / 28.
  - The full Python suite, local with scipy: **90 passed, 0 failed, 3
    known defects** (main's 88 plus the two new tests). It started before
    the intake full-pedal check was added to `test_p10_deeper_sound`; that
    final version passed in the mutants' baseline run.
  - ~~#128 opened; its CI is not read yet.~~ **CI on #128 (`d075312`):
    9 of 9 green, every job read:**
    - physics 90 / 0 / 3 on 3.10 (36.3 min) and 3.12 (33.6 min);
    - Pyodide 73 / 0 / 2 / 17 skipped, 48.5 min of its 60 (both new
      tests run there);
    - ports 5 + 51 + 11 + 11; solver 20 + 15 + 30; app units 130;
    - e2e: dyno 15, drive 10, sound 6, enjoy 28, cycle 11, spec 18,
      sweep 6, durability 5, grid 9, custom 7.
- **Merged** by the owner, 2026-10-14 08:10 UTC, as `196f8d3`. `main`
  checked by content: its tree equals `d075312`'s (an empty diff), with
  `SOURCE_BALANCE`, `MIC_TRIM`, `HISS_WEIGHT`, `smooth_port_flow` and their
  TS mirrors present. Pages deployed `196f8d3` (success).
- ~~**Next, the owner:** listen on the phone, at the cabin and intake mics.
  Two things to judge: whether full pedal (about +10 dB) is too loud, and
  whether the tip, cabin and outside mics sounding alike when revved is a
  problem.~~ **The owner listened (2026-10-14): accepted.** Full pedal "is
  little louder. But fine I guess"; the mics sounding alike: "Nope". Nothing
  to change; recorded in ADR-018 and the proposal. **P10 is done**, apart
  from FINDING-028's solver fix at the next rebuild.
- **Left for later:** FINDING-028's solver fix (option B), at the next
  rebuild.

**Session 9, P10 listening round (2026-10-14), `docs/p10-feasibility` (#127, merged 2026-10-13 22:56 UTC):**
- **The owner's answers:** they listened on a phone speaker, at the cabin
  and intake mics; yes to A/B files.
- **Measured at those mics** (crdi15): the clicks are 65–80% of the idle mix
  and the exhaust 0.0–0.1%. The cabin mic's 1.9 kHz low-pass leaves a
  650–900 Hz centroid (the knock's 680 Hz mode, the 900 Hz slap), the band
  a phone plays well. Under load the intake mic is 85–91% above 2 kHz: the
  turbo's whine and the hiss.
- **FINDING-028 (new):** at idle, the solver's port mass flows zig-zag point
  to point at the 1° step's Nyquist (`reviews/FINDING-028.md`).
  - It is numerical: at 0.5° it vanishes on the cars, and on single10 it
    moves to the new Nyquist.
  - It is in the shipped grids: the idle row of crdi15, hatch15, crdi22 and
    ld_i4 (0.6–0.86 of the flow's RMS), and single10 up to about 1400 rpm.
  - Sound: it made the idle exhaust's centroid 2,159 Hz; averaged out, it
    is 208 Hz.
  - Physics at idle: PMEP is off by 30% (a small number), VE by 1.8%,
    torque and fuel by 1.4% or less.
  - **I first told the owner it was "a large part of why idle sounds
    high-pitched"; wrong, corrected in the same reply.** Today the exhaust
    is 0.1–0.2% of the idle mix, so it only matters once P10 raises the
    exhaust.
- **The proposal is corrected in place.** The "muffler low-pass" piece was
  really this zig-zag; a 300 Hz muffler low-pass adds little once it is
  gone. B is now: the zig-zag averaged out (2° moving average), exhaust
  ×8, clicks ÷3, combustion ×0.6, hiss ×0.4, turbo ×0.4. C is B plus a
  +9 dB peak at 200 Hz, a phone effect.
- **The files:** `tools/p10_ab.py` made six WAVs (three cars × cabin and
  intake), sent to the owner. crdi15 cabin, centroid A → B: 852 → 474 Hz
  at idle, 707 → 424 at 2000 / 0.3, 746 → 216 at full pedal. At the
  intake mic under load, hatch15 and crdi22 stay bright even in B (the
  turbo).
- **Waiting on the owner:**
  - A, B or C, per mic;
  - the intake mic's turbo whistle: keep it, or turn it down further;
  - FINDING-028: A, B or C (C recommended: hide it in the synth now, fix
    the solver at the next rebuild).
- #127's CI on its first commit: 9 of 9 passed, every job read.

**Session 9, P10 feasibility (2026-10-13), `docs/p10-feasibility`:**
- The owner asked for P10's feasibility. P10 is new in the sheet: "a
  little high pitch; real diesels are deeper and bassier (CRDi, DDiS, TDC)",
  priority 1. Also new there, not asked about: **P09**, "increased knocking
  at high altitude" (priority 2).
- **Measured** (`tools/p10_sound_split.py`, `tools/p10_rebalance.py`;
  `reviews/PROPOSAL-P10.md`):
  - crdi15 at the default mic: centroid 1,901 Hz at idle and 2,370 Hz at
    2000 / 0.3; 2.1–2.4% of the power below 250 Hz; the firing frequency
    is 24–37 dB under the strongest bin (907 / 666 Hz).
  - The cause, on all three car diesels: the exhaust (the low firing pulse)
    is 0.2% of the mix at idle and 1.0–1.6% at 2000 rpm. The mechanical
    clicks (valve tick, injector) are 78–82% at idle; combustion (~700 Hz)
    is 37–43% at 2000 rpm. The balance between sources is a set of
    constants (`MICS` gains, each law's reference), not a measurement.
  - A what-if in memory (exhaust ×10, mechanical ÷3) moves 2000 rpm's
    centroid 2,370 → 501 Hz (39.6% below 250 Hz), but idle only 1,901 →
    1,627: on crdi15 and hatch15 the exhaust is itself bright at idle (its
    muffler path is two −14 dB notches and a ~900 Hz low-pass).
- **Feasible.** Recommended option B: rebalance, plus a broadband muffler
  low-pass. Judge it by ear on A/B WAV pairs first. It touches the synth, its
  TS port and `acoustics.py` (in the grid hash, but no cell reads the mix:
  a proved re-stamp, not a rebuild). About one session plus listening.
- **Questions for the owner:** what they listened on (phone speaker or
  headphones: a phone speaker can't play the 25–67 Hz fundamental); which
  mic; go ahead with the A/B pairs?
- **#126 merged** (2026-10-13); `main` (`c3ec2ae`) equals its head, 0
  lines different.

**Session 9, Phase 8 step 1: accessibility (2026-10-13),
`feat/phase8-a11y`:**
- **#124 is still open** (checked 2026-10-13: `OPEN`, 9 of 9, mergeable).
  The owner said "Merged!"; the merges were #121–#123. This branch starts
  from #124's head and targets `main`, so merging it brings #124 too.
- **Measured first.** axe-core 4.10.3 (WCAG 2.0/2.1 A and AA rules, run
  from the scratchpad, not a dependency) on all eight pages of a
  `build:pages` bundle, and on Enjoy again while driving:
  - **7 pages: 0 violations.** Every chart (dyno, cycle, sweep,
    durability, the four schematics) already has `role="img"` and a text
    summary; errors are text.
  - **Enjoy: 22 nodes flagged, 4 real.** axe misreads the dash's
    opacity: computed as drawn, the 18 others are 4.80–8.76:1 (the
    trip note, at 60%, is the lowest).
  - **Found by hand, which axe can't see:**
    - the tach's text alternative read "Engine speed 781 ×1000 rpm", i.e.
      781,000 rpm;
    - a lit warning lamp (white on `#e0634f`) is 3.46:1, below 4.5 (axe
      never saw one lit);
    - the tach's red band differs from the track by colour only, at 1.97:1;
    - the coolant bar's warning and derate marks differ by colour only.
  - **Unlit lamps are 2.16:1.** The owner chose to keep them dim, as on a
    real dash (2026-10-13). Lit differs from unlit by a solid fill, and
    screen readers skip unlit lamps.
- **Built** (`d5540f7`):
  - the dials' text alternatives speak in rpm and km/h (the truck's ×100
    tach too);
  - a lit warning lamp is slate on `#ec7a66`, 4.87:1 for text and fill;
  - the redline is wider than the track (10 against 6), the owner's choice
    over "band plus ticks" and "leave it";
  - the derate mark is 4 × 16 px against the warning mark's 2 × 12, and the
    bar says "Warning from 100 °C, derate from 107 °C";
  - `enjoy.css` stays under its 4 kB budget (a lit lamp's border is now
    transparent over its own fill, so it looks the same).
- **Tests, read from finished runs on this Mac:** `e2e:enjoy` 28 / 0
  (+3); units 130; `check:labels` clean; `build:pages` with no budget
  warning. No Python or physics change.
- **Mutants, 6 of 6 caught** (baseline 28 / 0 first; each one built):
  the label back to the dial's unit (2 checks fail); stripping only
  "×1000" (the truck's ×100 check fails); the lamp back to white on
  `#e0634f`; the redline as wide as the track; the derate mark the same
  shape; the bar's words removed (each of the last four fails the one
  combined check, nothing else). Run by
  a scratch script that rebuilt and restored each file from git.
- **PR #125** (into `main`; brings #124's two STATUS commits with it).
  **CI on `6d3b774`: 9 of 9, every job read.** Physics 88 / 0 / 3 on 3.10
  and 3.12; Pyodide 71 / 0 / 2 / 17; ports 5 + 51 + 10 + 11; solver 20 +
  15 + 30; units 130; e2e **enjoy 28 / 0** (the three new checks pass on
  Linux with the same readings: 4.87:1, redline 10 vs 6, marks 2 × 12 vs
  4 × 16), dyno 15, drive 10, sound 6, cycle 11, spec 18, sweep 6,
  durability 5, grid 9, custom 7. As expected before the run.
- **Merged and live.** The owner merged #124 then #125 (22:19 UTC);
  `main` (`95bde19`) has the same tree as #125's head `6d3b774`, 0 lines
  different. This CI note was pushed to the branch a minute after the
  merge, so it comes in this PR. Pages deployed `95bde19`. The site's
  `main-NMHILWVW.js` carries `spokenUnit`, `#ec7a66` and "Warning from".
  **CI on `main` (`95bde19`): 9 of 9, every job read**, the same counts
  as #125 (physics 88 / 0 / 3 on both Pythons, Pyodide 71 / 0 / 2 / 17,
  enjoy 28 / 0). *(Was: "`main`'s own CI on `95bde19` was still running
  when this was written.")* #124's merge run (`2bb36ef`) ended cancelled,
  superseded by #125's.

**Session 9, P08 merged and live (2026-10-12/13):**
- The owner merged #121, #122 and #123 in order (2026-10-12). `main`
  (`f446ec2`) has 0 commits off any of the three branches, and its tree
  equals #123's exactly. The duplicate benchmark test is gone (one
  definition).
- **CI on #123 (`cca698f`): 9 of 9, every job read.** Physics 88 / 0 / 3
  on 3.10 and 3.12, the P08 test passing; Pyodide 71 / 0 / 2, 17 skipped
  (+1: the P08 test, no grids there); ports 5 + 51 + 10 + 11; solver 20 +
  15 + 30; units 130; e2e dyno 15, drive 10, sound 6, enjoy 25, cycle 11,
  spec 18, sweep 6, durability 5, grid 9, custom 7. As expected before
  the run.
- **Live:** Pages deployed `f446ec2` (18:27 UTC); the site's worker bundle
  carries the economy schedule. **CI on `main` (`f446ec2`): 9 of 9,
  every job read**, the same counts as #123 (physics 88 / 0 / 3 on both
  Pythons, Pyodide 71 / 0 / 2 / 17, enjoy 25, drive 10). *(Was: "CI on
  `main` itself was still running when this was written: read it next.")*
- **On the phone:** Enjoy's Auto now cruises 1–3 gears higher at light
  pedal; worth a listen with the Phase 5 re-check.

**Session 9, P08 built (2026-10-12), `feat/p08-shift-schedule`:**
- `live.py`: `Gearbox.update_schedule` is ADR-017's economy schedule;
  today's becomes `_power_schedule` (full pedal, kickdown, no map).
  `LiveEngine` hands it `_econ_map` (the grid's cell plus the weather
  table's change) and the warm full-load peak power. Ported line for line
  to `driveline.ts`/`engine.ts`.
- **Measured, as built** (`tools/p08_proto.py ... base`, all four
  vehicles):
  - **all 12 car cruises are in the least-fuel gear**, the same gears and
    L/100 km as the prototype's C4, with 0 late shifts;
  - full pedal is identical to today;
  - 20% pedal shifts at 2,141–2,384 rpm on the cars (crdi22 1,595–1,856),
    against today's 2,797–2,998;
  - **half pedal never later than today:** hatch15 0–100 in 21.1 s
    (today 21.2), crdi22 22.6 (22.6); crdi15 shifts earlier, 35.6 s against
    32.1;
  - tip-in at 60%: hatch15 29.5 / crdi15 19.4 / crdi22 26.5 / truck 8.0 km/h
    (today 30.9 / 23.4 / 29.5 / 7.9);
  - the truck at 90 km/h shifts twice in 50 s, as today.
- **Fixtures:** live regenerated; 7 of 10 drives change gear sequence (the
  manual, the waxed engine and the kickdown case don't).
  `gen_fixtures --check`: 7 modules current. `web/physics npm test` 5 + 51
  + 10 + 11, all pass.
- **New test** `test_p08_automatic_shifts_on_demand` (7 parts, ~42 s
  locally; SKIPs without grids or `engines/`). Mutants: 5 of 5 Python
  caught (symmetric 6% bar, economy at full pedal, no half-pedal rule, map
  not wired, highest gear instead of least fuel), each applied and
  parsing. 4 of 4 TS-port mutants caught by the fixture parity, each
  compiling.
- **Local:** physics 83 / 0 / 3, 4 skipped (no scipy here; with scipy one
  of those is two results, so CI should read 88 / 0 / 3); units 130;
  build:pages clean; e2e enjoy 25, drive 10.
- **Cost (`npm run perf`, 6×):** a loop step 0.14 → 0.17 ms mean on the
  main thread, 0.02 → 0.03 in the worker (budget 16.7 ms); p99 unchanged.

**Session 9, P08 (2026-10-12): the owner asked to continue with it.**
- **P08**, the sheet's "Practical torque converter" (priority 1, "Into
  Consideration"): shift on demanded torque, upshift early when there is
  torque to spare, and keep today's power schedule at full pedal. It is the
  automatic's schedule: Enjoy's Auto (`tc`) and Drive's `tc`/`dct`.
- **Measured today's box:** it upshifts at
  `0.86 × rated × (0.80 + 0.28 × pedal)`, about 2,800–3,000 rpm on the
  cars at 20% pedal, in every gear, though their torque peaks from ~1,750.
  Held cruises with every gear forced: **today's gear burns 3–43% more
  than the least-fuel gear below 110 km/h on the cars** (crdi22 at 30 km/h
  7.56 against 4.32 L/100 km). The truck hunts 5th ↔ 6th at 90 km/h.
- **The trap:** the pedal is a fuel fraction, so the reserve in the current
  gear is ~1 − pedal in every gear, and a reserve rule cascades. Demand is
  read as power instead (`pedal^k × peak power`), which carries across gears.
- **Prototyped six variants** (`tools/p08_proto.py`, patched in at run time,
  nothing in `dieselsim/` changed). B, the reserve alone, hunts: 27 shifts
  in 50 s. C, C2 and C3 each fixed one thing and broke another; each is
  recorded in the proposal. **C4** (the fuel map, an upshift at 1% saving
  and a downshift for fuel at 6%) puts **all 12 car cruises in the
  least-fuel gear** with no hunting, and full pedal is identical to today.
  Still open: half pedal is mixed, crdi15's tip-in is 17% softer, and the
  truck at 90 is as today.
- **Decided by the owner (ADR-017):** C4, all automatic boxes, half pedal
  never later than today. *(Was: "For the owner (PR open, docs and tools
  only): C4, B or A? All automatic boxes, or Enjoy's only? Half pedal:
  never later than today, pure fuel map, or sportier?")* The proposal and
  ADR are in #122; the build follows on its own branch. Building it means regenerating the live
  fixtures and re-matching the TS port; **no grid rebuild** (`live.py`
  is outside the hash).
- Measuring note: the Python loop runs at ~1.2–2 s per simulated second,
  mostly live friction (0.2 s per update, every 6 frames). The prototype
  updates friction once a simulated second, the same for every variant.

**Session 9, continued (2026-10-12):**
- **Merged by the owner** on 2026-10-11 (UTC): #116 21:58, #118 22:00,
  #119 22:02, #120 22:03. `main` checked by content: #118, #119 and #120
  have 0 commits off it; the only lines on `main` beyond #120's tree are
  #118's (`bench/README.md`, `tools/bench_grid.py` identical; its 2
  CLAUDE.md lines the same) and #117's test.
- **CI on `main` (`3047f95`): 9 of 9, every job read.** Physics 87 / 0 / 3
  on 3.10 and 3.12; Pyodide 71 / 0 / 2, 16 skipped; units 130; e2e enjoy
  25, dyno 15, drive 10, sound 6, cycle 11, spec 18, sweep 6, durability
  5, grid 9, custom 7; fixtures 5 + 51 + 10 + 11; solver 20 + 15 + 30.
  Pages deployed `3047f95` (22:09 UTC). **The live bundle carries the new
  layout** (the `.paddles` column, the name's `16cqi` fit, the new start
  hint), so B-05 and B-06 are "Fixed on live site" in the tracker, not
  yet tried on the phone.
- **Found on `main`: `test_grid_benchmark_schedule` defined twice**
  (lines 2435 and 2491), since #116's merge. Git's auto-merge `f8f99e8`
  ("Merge branch 'main' into feat/cold-flow") placed #117's test at two
  places; every branch had one copy. The copies are byte-identical and
  Python keeps the second, so nothing ran differently and the count was
  never off. It is dead code a later edit could split (edit one copy and
  the other wins). An AST scan of all 45 Python files on `main` finds no
  other duplicate; a grep of the TS/MJS finds none either. **#121**
  deletes the first copy: the module's AST equals the old one minus that
  copy, and the kept test passes alone (6 of 6 parts). **CI on #121
  (`915d99b`): 9 of 9, every job read**, the same counts as `main`
  (physics 87 / 0 / 3 on 3.10 and 3.12, Pyodide 71 / 0 / 2 / 16 in 32.4
  min, units 130, e2e enjoy 25 and the rest unchanged).
- **The Pyodide job's time is the runner, not the code:** over the last 30
  runs it is bimodal, 20–33 min or 38–49 min, with the same commit taking
  42.7 and 42.4 and a docs-only commit 26.8 then 47.5. The worst so far is
  49.3 min of its 60-min limit: ~11 min of headroom. Something to watch
  as the suite grows, not to fix now.

**Session 9 (2026-10-11):**
- **This Mac:** the repo now lives at `~/Projects/diesel-simulator`, out of
  `~/Documents`, so the permission problem below (items 0a and 4) is gone.
  Claude Code keys its memory by path, so the session-8 memories were
  copied from the old path's memory folder to the new one.
- **The bug sheet has new rows:** B-05 and B-06 (the pedal layout, dated
  2026-10-07, not in the tracker until now), and Feat Prop **P07**,
  "Option to select multiple parameters in sweep" (priority 1). P07 is not
  in ADR-016 or PLAN, so nothing is built: **v1 or v2 is the owner's
  call.** The P06 rename in the sheet is done.
- **CI:** #118 9 of 9 on `40ec459`; #119 9 of 9 on `8e0ca1c` (its last
  STATUS commit), every job read.
- **B-05 and B-06, measured, then fixed** (`fix/b05-b06-pedal-layout`,
  from #119's head, into `main`: merge #119 first). The owner chose
  option B ("B seems like a good option, also if gear paddles are
  reachable with right thumb, it would make easier, since it's unlikely to
  accelerate and change gear together") over A (paddles above the right
  pedals) and C (an automatic clutch dip).
  - **Before**, on an emulated S9+ (846 × 411/340/300, Manual): the brake
    sat beside the clutch on the left; the − paddle sat directly above the
    clutch, in the same column, for the same thumb. From a right thumb
    resting low on the throttle, − was 712–745 px away and the brake 722.
  - **The layout now:** clutch | dash | paddles | brake + throttle. The
    clutch is alone on the left; the brake sits beside the throttle; + over
    − in a narrow column between the dash and the brake, at the bottom,
    nearest the right thumb. The top bar spans the dash and the paddles.
  - **A cost found and reduced, before commit:** the first version
    narrowed the dash 518 → 440 px, the lamps wrapped to two rows, and the
    dash overflowed (scrolled) 0 / 42 / 71 px at 411 / 340 / 300, against
    0 / 1 / 24 before. With every pedal at the old brake/clutch width
    (~68 px; the throttle was 144) the dash is 525 px, and the overflow
    0 / 0 / 8. *The trade: the throttle is narrower than it was.*
  - Pedal names now shrink with a narrow pedal (`min(1em, 16cqi)`): at
    125% text "Throttle" clipped in its 68 px pedal, caught by the new
    check.
  - `enjoy.css` stays under its 4 kB budget (it went 44 bytes over; the
    duplicate `.gauges` rule merged, the paddle rules compacted).
  - *Owning a mistake:* my first downshift check expected − from 1st to
    give neutral. It can't: the manual box's − stops at 1st
    (`Driveline.select` clips at gear 0). The check now goes N → 1 → 2 → 1.
  - **Tests, read from finished runs on this Mac (final tree):**
    - `e2e:enjoy` 25 / 0 (+2): the layout at 846 × 411/340/300 with 125%
      text (sides, paddles on the right, no overlaps, every pedal name
      inside its pedal); with the clutch held, the right-hand paddles go
      N → 1 → 2 → 1. B-02's layout rules still hold.
    - Mutants, baseline 25 / 0 first, each compiled: brake on the left;
      paddles above the clutch (M2′); no label fit; − shifting up; the
      whole old layout. **5 of 5 caught by the new checks**, each failing
      exactly one check. *Recorded, not counted:* a first M2 (paddle
      column moved into the clutch's column) covered the clutch, so
      earlier checks failed and the run crashed at B-01 before the new
      checks ran; M2′ replaced it. M4's "not applied" guard grepped with
      an unescaped `$` and could never fire; its result (− went to 3rd)
      shows it applied.
    - Units 130; `check:labels` clean; `build:pages` with no budget
      warning. No Python or physics change, so the suite, fixtures and
      grids are untouched.
  - **PR #120** (into `main`; **merge #119 first**). The tracker CSV has
    B-05 and B-06 as "In PR".
    - **CI on `5b2ff9b`: 9 of 9, every job read.** Physics 87 / 0 / 3 on
      3.10 (30.3 min of 45) and 3.12; Pyodide 71 / 0 / 2, 16 skipped
      (26.8 min of 60); all identical to #119's. The e2e job's own log, on
      Linux's wider font: enjoy 25 / 0, both new checks passing with no
      pedal name clipped; dyno 15, drive 10, sound 6, cycle 11, spec 18,
      sweep 6, durability 5.
    - This STATUS commit reruns CI on docs only.
- **Waiting on the owner (session 9):**
  1. ~~Merge #119 and #118 (both 9 of 9), then #120 after #119.~~ Done
     2026-10-11. New: merge **#121** (the duplicate test, 33 lines
     deleted, the tracker and this file).
  2. **P07** (multi-parameter sweep, priority 1): v1 or v2?
  2a. ~~**P08** (`reviews/PROPOSAL-P08.md`): the approach (C4 recommended),
      which boxes, and the half-pedal rule.~~ Decided 2026-10-12 (ADR-017):
      C4, all automatic boxes, half pedal never later than today. Merged
      and live (#121, #122, #123).
  3. On the phone, **now possible (#120 is live)**: the new pedal layout, plus
     REVIEW-007 M-1 (B-01, B-02, sound, smoothness). That closes Phase 5.
     New since: P08's lower cruise rpm in Auto (listen at 30–80 km/h).
  4. FINDING-027: A (state it) or B (model the cold-ignition region).
     Step 6 shipped without B, so A is my recommendation now.
  5. Still open: the `hd_i6` listening question; the Features tab copy.
  6. **P10** (`reviews/PROPOSAL-P10.md`): ~~what you listened on, which mic,
     and go ahead with A/B WAV pairs?~~ Answered 2026-10-14. ~~Now: listen to
     the six files, then pick A, B or C per mic; decide the intake whistle;
     choose FINDING-028's option.~~ Decided (ADR-018) and built. Now: merge
     the build PR, then listen on the phone (full pedal is louder; revved,
     the tip/cabin/outside mics sound alike). (P09, knocking at altitude, is
     new in the sheet too; not looked at yet.)
- **Next:** the rest of Phase 8: the units toggle, P01 vibration and P06
  random roads' proposal, in an order the owner picks; or P07. *(Was:
  "Phase 8 (below), unless the owner picks P07.")* *(Was: "read
  `main`'s CI on `f446ec2`. Then Phase 8 …")* *(Was: "merge #121, #122, then P08's build PR; read
  its CI (expect 88 / 0 / 3 and Pyodide's skip count +1)".)* *(Was: "P08's build once those
  are answered (the owner asked to continue with it, so it goes before
  Phase 8).")* Then Phase 8 (polish:
  units toggle, accessibility, P01 vibration, P06 random roads' proposal).
  *(Was: "Next by PLAN after that: Phase 8 (…)".)*

**2026-10-10, the owner's priority request: a hardware benchmark. Merged
as #117** (10:16 UTC, at `1589f5f`).
- `tools/bench_grid.py` times a standard drivable grid (8 × 6, warm and
  cold, 104 pieces) on the machine's own pool. Quick mode (~4–5 min)
  estimates the build; `--full` builds it.
- `bench/run_bench.sh` and `bench/run_bench.bat` set up `bench/.venv`
  (numpy only) and run it. `test_grid_benchmark_schedule`: 6 parts, 4 of
  4 mutants. CI on #117: 9 of 9; Linux 82 / 0 / 3 with the new test
  passing, and Pyodide skipping it.
- **Measured on this M2:**
  - `--full` took 22.1 min; the schedule from its own piece times gives
    23.4 (+6%).
  - Quick said 16.8 (−24%): the pieces slow under sustained load.
  - Through `run_bench.sh` (Python 3.13, numpy 2.5.3), quick said 13.0.
  - So: `--full` for laptops that throttle, and the same Python on every
    machine.
  - **Corrected before merge:** the browser estimate first used ADR-014's
    ×2.65, which counts the load twice. It is now ×1.45–1.86, from the two
    measured Chrome builds.
- **#117 merged before my last three commits.** The docs went to **#118**
  (from `main`, merges alone). The third commit moved the test away from
  #116's hunks, so it never reached `main`, and **#116 conflicted with
  `main`**. Fixed by merging `main` into `feat/cold-flow` (`f05a27f`),
  keeping both sides. The merged suite read 87 / 0 / 3 (86 + the
  benchmark test).
- *Owning a mistake:* I first read #117's CI as the first push's run. It
  was `1589f5f`'s; the first push's run was cancelled.

