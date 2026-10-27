# STATUS history: Session 6 (2026-10-05/06)

Moved verbatim from `STATUS.md` at `a57a6fd`, its lines 2293-2516, by step A1 of
`reviews/PROPOSAL-modularize.md` (2026-10-28). **This is history, not the present**:
`STATUS.md` is. Struck-through text and in-place corrections are as they were written.
`python3 tools/check_verbatim_move.py history/` proves the copy.

<!-- verbatim: STATUS.md@a57a6fd 2293-2516 -->
## Session 6 (2026-10-05/06): Phase 6, stage by stage

*(Moved here from "Waiting on the owner" when REVIEW-008 closed the phase.
The text is unchanged; the sweep, durability and schematics PRs, #96–#98,
came after it, and their records are in the PRs and REVIEW-008.)*

**Phase 6, stage 1, in progress** (branch `feat/solve-cycle`, stacked on #89):
- **Done: `bridge.solve_cycle` and `solveCycle` through the port.** Cylinder
  1's traces in its own crank angle, manifolds in engine angle (phase 0,
  returned), events, summary, n_cycles ≥ 9, NaNs refused anywhere.
  `test_solve_cycle` 7 parts (5 of 5 mutants); round trip 24 (+2): real
  Pyodide worker vs native within 2.25e-7 (2 of 2 mutants). 6.1 s natively
  per point, so ~16 s in the browser; 109 kB of JSON.
- **Found and fixed on the way: FINDING-024.** MFB50 counted combustion
  before TDC last, so it was late by up to 7°. It's a reported figure only.
  The 10 grids were re-stamped (`dee93a17` → `a442cfb3`) with proof: the
  pre-fix tree hashes to `dee93a17` exactly, `mfb50` has no grid-path
  reader, a shipped cell recomputes with 0.00e+00 difference, and in each
  file only the 64-byte hash changed. Branch `fix/mfb50`, stacked on #90.
- **Done: the cycle page, `/cycle`** (branch `feat/cycle-page`, stacked on
  `fix/mfb50`):
  - p–V log-log, p–θ, heat release and valve lift, with events marked and
    the cycle's numbers in a table (BSFC steady-state); cylinder 1's crank
    angle said on the page.
  - `e2e:cycle` (8 checks, in CI's browser job) matches native Python: 140.1
    bar at +10°, MFB50 +12.0°, IMEP 11.07 bar at crdi15 2700 rpm / 60%,
    solved in ~12 s. 2 of 2 e2e mutants caught.
  - Units 68 (+10).
- **Done: durability stepped from the browser** (branch
  `feat/durability-call`, stacked on `feat/cycle-page`):
  - `durability_run`'s loop is now the generator `durability_blocks`, with
    old and new logs identical by `repr`, 225 values across 2 oil changes.
  - `bridge.durability_start/_next/_stop` keep one run in the worker's
    Python; `durabilityCall` behind an allowlist.
  - Round trip 27 (+3): a 50 h block matches native within 5.48e-13. Python
    `test_durability_steps` 4 parts; mutants 3 of 3 (Python), 1 of 1 (TS).
  - Grids re-stamped `a442cfb3` → `15593c2d` with proof, now by
    **`tools/restamp_grids.py`**, which asserts the proof and refuses a
    stale re-stamp.
  - Suite 74 / 0 / 3 (scipy); audit 0 / 2 / 0; fixtures 7 of 7.
- **Sweep needs no new call:** the bridge's `overrides` plus `solvePoint`,
  one point per value, as the Dyno pull loops over rpm (progress and Stop
  come free). The sweep page is stage 2.
- **Done: the spec editor, `/spec`** (branch `feat/spec-editor`, stacked
  on `feat/durability-call`):
  - `bridge.describe_spec` (188 fields; every editable one round-trips
    through `overrides`).
  - A generated schema (`tools/spec_schema.py --check`), so the editor's
    field list can't drift from `config.py`.
  - Curated groups, order, labels and units on top (`spec/spec-meta.ts`,
    tested).
  - Edits (overrides on a base engine) are shared with the cycle page,
    which solves them; JSON export and import.
  - `e2e:spec` 7 checks, in CI: compression ratio 17 solved at native
    Python's 148.9 bar (140.1 unedited). Mutants: Python 3 of 3, e2e 2 of
    2.
  - Units 78 (+12); the units pass without `physics-version.ts`, as on CI.
- **Stage 1 is complete.** The stack: #89 ← #90 (solve_cycle) ← #91
  (FINDING-024) ← #92 (cycle page) ← #93 (durability) ← the spec-editor PR.
- **Stage 2, in progress** (the owner, 2026-10-06: "complete the phase 6",
  taking the recommended option wherever input was wanted):
  - **Done: spec edits on every solving page, and the invalidation
    banner** (`feat/edits-everywhere`, stacked on the spec-editor PR).
    - Dyno, Grid and Cycle solve the edits on their engine. `SpecStatus`
      says which edits apply, and "these results are out of date" with
      Solve again / Run the pull again / Rebuild the grid.
    - `LastResults` keeps each page's results across navigation; without
      it the banner could never show, since edits happen on another page.
    - `e2e:spec` 8: the kept 148.9 bar result is flagged after a CR 18
      edit, and re-solved at native Python's 157.5. Mutants 2 of 2, after
      a fix: they first crashed the test instead of failing a check, and my
      runner counted a crash as "survived". Both now report cleanly.
    - Dyno e2e 15, unchanged.
  - Next: the sweep page; the durability page; the four schematics; then
    REVIEW-008.

---

## Session 6 (2026-10-05): the Android bugs, the bug sheet, the grid-build plan

*(Moved here from "Waiting on the owner" when #86–#88 merged; the text is
unchanged.)*

**Waiting on the owner:**
1. **The Android bug list.** The owner did the Android check (reported
   2026-10-05) and found a few bugs. Phase 5 stays open until they are
   fixed. Then write REVIEW-007, the Phase 5 exit review.
   - **The bug sheet:** "diesel-simulator: Android bugs (Phase 5)",
     https://docs.google.com/spreadsheets/d/1giP18zulUFOkOyXFj7sj0JRSGR8SydxNb2owMN0COV8/edit
     It was created 2026-10-05 through the Google Drive connector, in the
     connector's Drive. The owner first made a sheet, `1gta1hA0…`, that the
     connector couldn't see; it was empty and this one replaces it.
   - **Bugs tab:** the owner's. One row per bug, IDs `B-01`…`B-40`.
     Read it with the connector's `read_file_content` (file ID above).
   - **Tracker tab:** ours. The connector can't edit cells, so the tab
     `IMPORTDATA`s **`reviews/ANDROID-BUGS.csv` from `main`**. Update the
     CSV, not the sheet. Columns: ID, Verdict (Confirmed / Partly / Not
     reproduced / Needs info), Measured, Cause, Fix (PR), Status (New /
     Measuring / Fixing / In PR / Fixed on live site / Won't fix + reason),
     Updated. It shows only what has merged, which is what the live site
     runs. The Bugs tab's green Status column looks each ID up in it.
   - **The bugs (listed 2026-10-05):** B-01, Restart after a stall does
     nothing (S9+); B-02, text overlaps when shifting without the clutch
     (S9+); B-03, a console error, from a local dev server with a Chrome
     extension and the text cut off (needs the full error); **B-04, a
     custom-engine build stuck at 0 for over an hour with Stop not
     working ("Can't drive"): first.** Rows are in
     `reviews/ANDROID-BUGS.csv`.
   - **Measured 2026-10-05 on the dev server** (the owner: B-04 and B-03
     were on local `npm start`; B-03 doesn't happen on Pages). A full-size
     custom build in headless Chrome:
     - **Stop reproduced.** Pressed at 367 s, still building 30 s later.
       Stop is checked only between pieces, and a running Python piece
       can't be interrupted (no `SharedArrayBuffer`, ADR-003).
     - **The ETA bug reproduced.** "258 min left" at the first piece
       (156 s) of a ~19 min build.
     - **Not reproduced:** stuck at 0 (first piece at 156 s), and B-03 (no
       errors; the owner's log points at a Chrome extension).
     - Repro script: `web/app/e2e/out/repro-b04.mjs` (gitignored;
       `URL=… WATCH_S=…`).
   - **Fixed in #88 (`fix/b04-stop-eta`, stacked on #87):**
     - **B-04 Stop** answers at once: the pool is raced against the abort
       signal, and `SolverService` terminates the workers. Dev server, Stop
       mid-row: "Stopped" in 0.5 s.
     - **B-04 ETA:** `etaSeconds` spreads the worker-seconds left (a row
       counts as 4 cells until both are timed) over the workers. Dev
       server: 11 min at the first piece (was 258).
     - **B-01:** Restart acts on press; `/enjoy` words the loop's keyboard
       hints for touch (`enjoy/hints.ts`).
     - **B-02:** the hint is a toast out of the column's flow; stalled,
       Restart takes the rpm line's place. The dial row can't shrink below
       its content (`min-height: min-content`), and a dash too tall for the
       screen overflows at the bottom (`safe center`, `overflow-y: auto`),
       so the strip scrolls and nothing overlaps.
       **Correction:** the first version (a 2rem gear floor, measured to
       hold "down to 846×300, not at 280") leaned on the Mac's font. CI's
       Linux font ran the column 64 px into the strip. Now verified with
       the Mac font and Verdana at 411/340/300, and the e2e rules hold at
       846×300 with 125% text. *(Was: "the gear floor is 2rem. It holds
       down to 846×300, but not at 280. Stalled at 300, Restart's bottom 3
       px meet the strip's edge; taps still land.")*
     - Tests: scheduler 12 (+4), cache 20; units 58 (+2); e2e:enjoy 21
       (+2). Mutants: scheduler 3 of 3, units 1 of 1, e2e 3 of 3 (then 2 of
       2 against the B-02 layout rules), every one compiled. e2e:custom gained a "Stop < 5 s" check.
     - **The new ETA over a whole real build** (production build, full
       8×6, this Mac, 27.5 min; part 17 measured 21.5, so load varies):
       0.63× the real time left at the first piece (optimistic: until a
       cell is timed, a cell counts as a quarter of a row), then
       0.84–0.98× from the 5th piece on. The old formula read ~20× high
       there. Not tuned on one run. *(A first attempt was killed at 9 of
       104 by a dev-server live reload that my own file edits triggered.)*
     - e2e:custom 5/5 with the new Stop check (72 ms); its mutant (Stop
       awaiting the pool) fails it at 69.7 s.
     - **PR #88**, stacked on #87. **CI 9/9 green on `1e2b520`**,
       including Linux's B-01 (782 rpm) and B-02 rules (dials 177–303,
       column 183–296, strip from 309) and Stop (40 ms). Python 71/0/3
       known; Pyodide 59; solver 20 + 12 + 22.
   - **Next for the owner:** merge #86 → #87 → #88, retargeting each child
     to `main`. Then re-check B-01 and B-02 on the phone (the live site
     updates on merge). B-04's "stuck at 0" needs the circumstances
     (which browser, tab in front, Mac asleep?), or it stays not
     reproduced. B-03 looks like a Chrome extension.
   - Repro for B-01/B-02: `web/app/e2e/out/repro-b01-b02.mjs` (`H=300`).
   - **Features tab:** the connector can't add a tab to an existing
     sheet, and rebuilding the sheet would lose B-03's full log (the
     connector's view truncates it). So it's a self-contained template,
     "diesel-simulator: Features tab (copy into the tracker)"
     (`12mLsfoFBwh_5Zqai6zpHpv3yZSBx45jvFgf3ZnYZyNY`), for the owner to
     copy in (tab menu → Copy to → Existing spreadsheet). Blue columns are
     the owner's ideas, F-01…F-40. Green columns are looked up from
     **`reviews/FEATURES.csv`** on `main` (ID, Assessment, Plan, Status,
     PR, Updated), imported into a grey block from column R.
   - Measure each entry before fixing it, as with every bug list here.
   - Live friction's cost on a low-end phone was left to wait for this
     check: see whether the sheet mentions stutter.
   - *(Was: "The Android check, Phase 5's exit criterion: open
     https://jenilclaudeai.github.io/diesel-simulator/enjoy on a mid-range
     Android in Chrome, landscape, and tap Start engine. Judge smoothness,
     sound (crackle?), the pedals and paddles; try the truck and the single.
     Then write REVIEW-007 (the Phase 5 exit review).")*
2. **The grid-build plan: decide on `reviews/PROPOSAL-grid-build.md`**
   (2026-10-05, **#87** on `docs/grid-build-plan`, stacked on #86). The owner
   measured 5+ min for a grid on a Samsung phone, and a 2–3+ h ETA for a
   drivable grid on an M2 MacBook. Measured since:
   - **Corrected the same day:** B-04 (stuck at 0 for over an hour) means
     the M2's long build was **not** just the misleading ETA, as first
     written. The proposal is corrected in place.
   - **The ETA formula misleads early, by up to 20×.** It counts all 104
     pieces as equal, and the 8 row calibrations (~4× a cell) finish
     first. On 6 workers it reads ~5 h at the first piece, of a ~18 min
     build. Not yet confirmed: the owner's browser, and whether the build
     was left to finish.
   - **All the time is the pure-Python crank-step loop.**
   - **Converged solves always run 200 real-time cycles.** Of 11 cells, 9
     pass the tail test at cycles 25–134 (2 never do), at most 0.25% from
     the 200-cycle value. Stopping early with a margin: ~1.8–2.5×.
     Chaining cells: not worth it.
   - Recommended: A, an honest ETA (now); B+C, early stop plus `thermo.py`
     speedups, one solver change and one rebuild; E, phones get prebuilt
     (E1) or derived approximate (E2) grids rather than building. The
     owner decides the order, E1/E2, and whether a coarser grid (D) is
     acceptable.
   - Open questions put to the owner: the M2's browser, and whether that
     build finished; which page took 5+ min on the phone; whether phone
     users should make their own engines.
3. **Listening:** the before/after pairs in `out/listen/review003m5_*.wav`.
   - They are local files on this Mac, gitignored. Each is 4 s before, a
     gap, then 4 s after, rendered by `EngineSound.render` on the
     exterior mic.
   - Before is `main`'s physics ahead of #78 (rendered just before #77
     merged; #77 was docs only, so `512683a` is the same physics). After is
     #78.
   - The clips: crdi15 idle warm and cold, hd_i6 idle and 1250 rpm at half
     load, single at 2000 rpm, truck127 idle.
   - The one-off script that made them was not kept. If they are lost,
     render the same points on both commits.
   - The open question: is `hd_i6`'s idle tick, now 0.23× the loudest other
     source, too quiet for a mechanical-lash truck? `RAMP_SPEED` is the
     single knob.
4. **Merge #86** (docs only; CI 9/9 green on `1fcf32e`), then retarget `docs/grid-build-plan`'s PR to `main`.


---

