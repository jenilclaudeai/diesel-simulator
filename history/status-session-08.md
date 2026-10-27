# STATUS history: Session 8 (2026-10-07 to 2026-10-11)

Moved verbatim from `STATUS.md` at `a57a6fd`, its lines 1495-1855, by step A1 of
`reviews/PROPOSAL-modularize.md` (2026-10-28). **This is history, not the present**:
`STATUS.md` is. Struck-through text and in-place corrections are as they were written.
`python3 tools/check_verbatim_move.py history/` proves the copy.

<!-- verbatim: STATUS.md@a57a6fd 1495-1855 -->
**Session 8, start (2026-10-07):** `main` is `ea88e5f` (#107 merged 09:27
UTC). No PR is open. Phase 7 steps 1–3 of 7 are merged (#105–#107).
- The bug sheet, read through the Drive connector: **no new bugs** (B-05
  onward are empty), and no note yet of the B-01/B-02 re-check, so Phase 5
  is still open on REVIEW-007 M-1.
- **New since ADR-016: a sixth "Feat Prop" row**, "Randomness in drive
  mode": "terrain, desert, speed breaker, traffic with visuals", priority
  2. It reuses the ID **P05** (the AWS Lambda row is P05 too). Not in
  ADR-016 or PLAN, so nothing is built. Item 6 below asks.
- Next, by ADR-016's order: **step 4, the Drive correction table**.
  - **Paused 2026-10-08 on FINDING-026** (`reviews/FINDING-026.md`). Step
    4's measurement, redone on today's code (312 converged `crdi15`
    solves): the proposal's 1.15% doesn't hold any more. A 12-air table
    is 20.3% off in torque, and 15.4% across cells. Read cell by cell, the
    worst cells are a defect in #107's modern ECU. Off the rating's air
    the boost target passes the compressor's limit wherever EGR is on, and
    the VGT jams on its minimum. At Leh, light load: −74% to −76% torque
    on crdi15, truck127 and v8hd; standard air untouched; live on the
    solving pages' "High plateau" preset. And at high rpm and full load
    the shaft rides the solver's numeric clamp on every VGT engine.
  - **Fix A** (the cap applies to the target the VGT actually chases) is
    measured in a scratch copy: v8hd 1959/0.2 −76% → −6%, truck127
    1860/0.2 −67% → −12%, crdi15 4057/0.6 −30% → −2%; identical at
    standard air in 25 of 25 cells. **B** (a VGT speed limit) is
    dismissed: the vanes are already wide open where the shaft pins.
    **Decided 2026-10-08:** C declined (no fuel cut), D stated (item 2
    below). *(Was: "For the owner: C (a turbo-overspeed fuel derate) and D
    (state the light-load residual, crdi15 4057/0.2 still −37%). My
    recommendation: A now, then C measured, then D, then step 4
    re-measured.")*
  - The `hatch15` table run was stopped part-way: it measured the
    defective code.
  - **Fix A built** on `fix/finding-026-cap` (PR stacked on #109):
    - at the rating's air, 21 of 21 replies are identical (the new
      `tools/ab_rating_air.py`, itself mutation-tested);
    - grids re-stamped `0f1cc94c` → `172454a3` with `restamp_grids.py`'s
      proof;
    - `test_modern_cap_holds_with_egr_on`: baseline 5 of 5, 3 of 3 mutants
      caught. The first mutant run was void (a symlinked `tests/`) and was
      redone; see the finding.
    - Fixtures: 7 of 7 current. Audit: 0 dead, 2 frozen (known), 0 tiny.
    - Suite (scipy venv, this Mac): 81 passed, 0 failed, 3 known, 16.3
      min.
    - **CI on #110: 9 of 9 green**, every job read. Pyodide: 68 passed, 0
      failed, 2 known, 13 skipped; the new test gives the same numbers
      there.
    - **Pyodide took 42.5 min against its 45-minute limit.** Over 22
      passing runs it took 14.3–42.5 min, the last four 37.7–42.5, and the
      same docs-only tree 20.4 and 37.8. So the limit is now **60**, in
      this PR.
    - #108's "grid in Chrome" job failed twice, both times on Puppeteer's
      30 s Chrome-launch timeout ("waiting for the WS endpoint URL"),
      before any check ran. #109 and #110 contain #108's commits and
      passed that job. ~~**Follow-up:** raise the e2e launch timeout if it
      recurs.~~ **It recurred on #115 (2026-10-09), a third time. Every
      e2e launch now gives Chrome 120 s** (#115).
- **Waiting on the owner (session 8):**
  0. **Now (2026-10-10): merge #119 (step 7) and #118 (benchmark docs), in
     either order.** #119 contains #116 (cold-flow), which contains #112–#115,
     so merging it closes all six. Each merges cleanly with `main` and with
     the other (checked on throwaway merges). Then check `main` by content.
     **CI, every job read, each run on its PR's current head:**
     - #118 (`40ec459`), #116 (`f05a27f`) and #119 (`c0b5a29`): 9 of 9 each.
     - #119's counts: physics 87 / 0 / 3 on 3.10 and 3.12; Pyodide 71 / 0
       / 2 with 16 skipped; units 130; TS ports 51 + 10 + 11; e2e spec 18,
       drive 10, enjoy 23, custom 7, grid 9.
     - Pyodide took 47.4 min on #116, against the 60-minute limit.
     *(Was: "merge #115", below; #116 then carried it.)*
  0a. *(2026-10-09)* **Merge #115.** It carries #112 (D), #113 (the
     table proposal) and #114 (humidity), all open and all targeting
     `main`, so merging #115 alone brings all four. CI on #115's code
     (`25ebbaf`): 9 of 9, every job read. Then check `main` by content.
     Also open for the owner:
     - FINDING-027 (the NA single's ignition cliff in cold, thin air):
       A, state it (recommended now), or B, with step 6.
     - The sheet's P06 rename; the Phase 5 phone re-check;
       `~/Documents` access for Claude Code.
       - **Diagnosed 2026-10-11.** The owner had granted access, but each
         time a different program asked. macOS privacy is per program,
         and Claude Code installs every update as its own binary.
         `~/.local/share/claude/versions/` holds 2.1.291, 2.1.292 and
         2.1.293; this session ran from 2.1.292, under
         `ClaudeCode.app`.
       - Every program in the session was still refused: `ls`, `cat`,
         Python and Node each got "Operation not permitted".
       - Fix offered: Full Disk Access for `ClaudeCode.app`, or move the
         repo out of `~/Documents`. Until then the work runs in the clone
         under the job's `tmp/`.
     - ~~**Next by ADR-016's order: step 6, cold-flow**~~ **Step 6 built
       (2026-10-10, `feat/cold-flow`, from #115's head, into `main`).**
       - **The owner's decision:** a fuel picker; every place sells the
         right fuel, so nothing would wax otherwise (ADR-016 addendum).
       - Fuel beside Place on `/drive` and `/enjoy`'s start screen: sold
         here, summer (CFPP 18 °C), winter (6 °C), arctic (−32 °C).
         `fuels.json` is generated with the places.
       - The live loop: the fuel's own temperature; the filter's share
         (1 at CFPP + 2 K, 0 at −6 K) caps the governor's demand; below
         12% it's waxed out (no fuel, the reason said, restart refused).
         A part-waxed engine that can't start says so after 3 s
         standing.
       - Sanity on hatch15: summer diesel at −20 °C never fires.
         −8 °C at the filter's 75% starts and runs capped, then warms
         −8 → 4.5 °C in 3 min, full flow from about 90 s. At 37% it
         won't start and says why. Arctic at −20 °C runs.
       - **Corrected in place:**
         - my first part-waxed message fired at the first step, before
           the engine could catch; now it waits 3 s;
         - then it fired while a car coasted (rpm reads 60 through the
           DCT's coast, with or without a CFPP); now the car must stand.
       - With the five places every grade either flows or gels: the
         limp band is reached only in tests and the fixture, until P06's
         roads.
       - Tests, read from finished runs on this Mac:
         - `test_cold_flow_in_the_live_loop`: 7 parts, 7 of 7 mutants.
         - The live fixture gains `adr011_waxed` and `adr011_limp`; the 8
           existing drives are identical apart from the five new state
           keys. TypeScript vs Python: per step ≤ 5.8e-15, every event
           and message at the same step, 3 of 3 TypeScript mutants.
           **Corrected in place:** the first waxed drive sat at 0%, where
           the cap alone gives no fuel, so a "waxed fuel still flows"
           mutant went unseen. It now sits at 5% (CFPP −14.4 °C at
           −20 °C), and the mutant is caught.
         - Units 122 (+3); e2e drive 10 (+1, Rovaniemi with summer
           diesel) and enjoy 23 (+1, the fuel on the start screen), each
           mutant caught.
         - Suite 86 / 0 / 3; fixtures 7 of 7; audit unchanged; places,
           fuels and schema files current; grid hash unchanged
           (`70fdc89e`).
       - ~~Then step 7, projects.~~ **Step 7 built (2026-10-10,
         `feat/projects`, PR #119 into `main`).**
         - **The owner's choice:** a "Drive with" box on `/spec`
           (gearbox, place, fuel), over the engine and environment only,
           or capturing Drive's last settings unseen. ADR-016 addendum.
         - The project file, version 1: the engine (base + edits) and the
           drive (`spec/project.ts`).
           - A newer version is refused, saying so.
           - An old spec file opens as the engine only, and the page says
             the drive settings stayed as they were.
           - Every field is checked, and refused in words.
         - On `/spec`, Save and Open project replace Export/Import spec.
         - The gearbox joins the place and the fuel in `DriveEnv`, kept
           per browser (a new CLAUDE.md trap for e2e).
         - `/drive` and `/enjoy` open a project:
           - an unedited engine selects the preset, if the page has it;
           - an edited one selects its grid in "Your engines", or says to
             build it on `/spec` first;
           - Enjoy drives a DCT project as Auto, and says so.
         - Tests, read from finished runs on this Mac:
           - units 130 (+8, `project.spec.ts`), 7 of 7 mutants;
           - e2e:spec 18 (+4: open on `/spec`, Save project's file
             text, `/drive` and `/enjoy` starting with the choice and
             opening projects), 4 of 4 mutants, every one compiled;
           - e2e:drive 10 and e2e:enjoy 23, unchanged; e2e:custom
             7 / 0 (its file unchanged by step 7);
           - suite 87 / 0 / 3 (no Python change in step 7); build:pages
             clean.
         - **Phase 7's seven steps are all built.** Next by PLAN: Phase
           8 (polish and host), including P01 (vibration) and P06's
           proposal.
  1. ~~**Merge #111**~~ **Done 2026-10-08 06:37 UTC.** `main` (`9582848`)
     equals the tested tip `4795cb3`, 0 files differing. CI on #111: 9 of
     9, every job read; Pyodide 42.7 min (limit now 60). **Next: merge
     #112** (D, into `main`; CI 9 of 9 on its code). *(Was: "Merge #111,
     then the D PR, both into `main` (neither is stacked, so no
     retargeting; merging D's PR first would bring #111's commits too).")*
     - *What happened (2026-10-08 05:44–05:49 UTC):* #108 merged into
       `main`, but #109 merged into `docs/session8-start` and #110 into
       `docs/finding-026`, not retargeted (memory: stack-merge-trap). So
       `main` (`b8f80b8`) had neither FINDING-026 nor fix A. **#111**
       brings both, from `fix/finding-026-cap` (`4795cb3`, the tree CI
       passed 9 of 9 on #110).
     - *(Was: "Merge, in order: #108 (docs) → retarget #109 to `main` →
       merge #109 (docs, FINDING-026) → retarget #110 → merge #110 (fix A).
       Then check `main` by content (memory: stack-merge-trap). #108's red
       check is the Chrome-launch flake above.")*
  2. ~~**FINDING-026 C and D**~~ **Decided 2026-10-08: "C: No don't cut the
     fuel. then D."** D is built on `fix/finding-026-state`: the thin-air
     note on the solving pages' picker and on `/spec`'s ambient-pressure
     and ECU fields. Units 112 (6 of 6 mutants caught); e2e:cycle 10 and
     e2e:spec 13 (+1 each, each mutant caught). FINDING-026 is closed.
     *(Was: "a turbo-overspeed fuel derate (C)? State the light-load
     residual (D)? My recommendation: C measured next, then D. Step 4 (the
     weather table) waits for these.")*
     - ~~**Next: step 4, the weather table, re-measured**~~ **Re-measured
       2026-10-08: the table's shape needs your decision**
       (`reviews/PROPOSAL-weather-table.md`). 624 converged solves
       (crdi15, hatch15). Felt torque error, as a share of full-load
       torque at that rpm:
       - the 12-air table at the presets: 2.0–2.35%; at any air down to
         52 kPa, 3.8–5.2%;
       - but blending from coarse cells to the others costs 7.8–10.2%
         (the smoke-limit knee);
       - no correction (Drive today): 32.6–35.3% at Leh.

       The options: A1 coarse cells; A2 all cells × 11 airs; **A3 all
       cells × 8 airs (recommended: 2.4–3.6% at the presets, ~1.3 h extra
       in a browser for a custom engine)**; A4 all cells × the presets
       only (exact there, but Drive limited to five places, which P06's
       climbing roads can't use). *(Was: "Next: step 4, the weather
       table, re-measured on the fixed code (the table measurement first,
       as before building).")*
     - **Decided 2026-10-09: A3** ("A3, go ahead"; ADR-016 addendum).
       **Being built on `feat/weather-table`** (from #114's head, into
       `main`):
       - `bridge.live_weather_plan` / `live_weather_cell` /
         `live_weather_assemble`: 384 pieces plus 6 Leh checks per grid,
         the same pieces natively and in a browser.
       - `live.WeatherTable`, used in `LiveEngine._perf` off the
         standard air (skipped at it).
       - `tools/build_live_grids.py --weather` adds the table to an
         existing grid file and refuses a stale grid.
       - The grid hash is unchanged (`70fdc89e`): `bridge.py` and
         `live.py` are excluded from it.
       - **Progress (2026-10-09):**
         - Python, TypeScript, Drive and Enjoy, and the browser build are
           all built and tested (the commits on `feat/weather-table`).
         - The ten tables are being built natively, roster first, from a
           frozen copy of the tree (`$CLAUDE_JOB_DIR/tmp/buildtree`, log
           `weather_build.log`). **`hatch15` is done:** 390 solves in 46
           min, 13 unsettled, Leh check 2.35% of full-load torque (the
           proposal measured 2.35%). `tmp/scripts/copy_back.py` copies
           each table in and proves only the `weather` key was added (its
           `build_s` dropped).
         - Tests:
           - Python: the live-loop table test 6 parts, 7 of 7 mutants;
             the pieces test, a standard-air piece = the grid cell
             exactly (0.0). Its fuel-ignoring mutant is equivalent within
             tolerance (3e-7: it recalibrates the same limit), so it is
             recorded, not counted.
           - TypeScript loop vs Python: 9.9e-15 per step, 49 events
             identical, 2 of 2 mutants.
           - Scheduler 15, 3 of 3 mutants; units 119, 7 of 7 compiled
             mutants (two broken ones redone so they compile).
           - e2e:drive 9: at Leh the page's worker vs native Python on
             hatch15's table, 59 events identical and 3.55e-16 final;
             Leh's 60 s drive ends at 71.9 km/h against 79.1.
             **Corrected in place:** the first run read 5.3e-7, because I
             gave native a rounded 65764.1 Pa while the page used
             environments.json's 65764.0576. The test now reads the
             page's own numbers.
         - ~~Still to do: the other nine tables (about 45 min each); the
           browser-vs-native table (`test:live-real`, manual, once the
           CPU is free); CI; STATUS for the PR.~~ **Done 2026-10-09:
           all ten grids carry a table.** Each one's own Leh check (6
           held-out cells, % of full-load torque):

           | grid | Leh check | unsettled / 390 | build |
           |---|---|---|---|
           | hatch15 | 2.35% | 13 | 46 min |
           | crdi22 | 2.75% | 19 | 56 min |
           | truck127 | 2.46% | 67 | 67 min |
           | v8hd | 2.78% | 60 | 85 min |
           | single10 | **7.20%** | 1 | 17 min |
           | crdi15 | 2.04% | 17 | 52 min |
           | crdi_1p5 | 1.52% | 68 | 51 min |
           | ld_i4 | 2.35% | 8 | 51 min |
           | hd_i6 | **4.72%** | 1 | 72 min |
           | single | 0.30% | 1 | 18 min |

           - The two outliers are measured, not guessed. single10
             misfires in the model at 58 kPa / −20 °C (FINDING-027, open
             for the owner). hd_i6's smoke limiter binds at 58 kPa but
             not at Leh, a knee between pressure nodes, within A3's
             measured 5.2–5.5% anywhere.
           - truck127, v8hd and crdi_1p5 have many unsettled solves in
             thin air (their VGT/EGR loops oscillate), period-averaged as
             FINDING-013 does; their checks are still 1.5–2.8%.
           - copy_back.py proved for each file that only the `weather`
             key was added.
         - Suite 85 / 0 / 3 (+3); fixtures 7 of 7; audit 0 dead, 2 frozen
           (known), 0 tiny; units 119; the generated places and schema
           files current. In all ten shipped tables the standard-air node
           equals the grid's cells in every one of the 480 cells.
         - `test:live-real` (manual), the browser's 2 × 2 grid with its
           table against native: numbers within 1.35e-12 (the table
           included), and 42 pieces counted. **One structural failure,
           fixed:** the browser's file put the table before the spec and
           engine view, and the native file after them.
           `live_grid_assemble` now puts it last. **Rerun: 4 of 4**,
           the same structure (27 fields, keys in order), numbers within
           1.35e-12, built in 22 min on 2 Node Pyodide workers.
         - **PR #115's first CI: 8 of 9.** The fixtures job called the
           live fixture stale at one value: `adr011_weather`, snapshot
           12's converter slip, 0.0 on the Mac and about 5.7e-14 on Linux.
           The check's relative floor of 1e-9 made that 5.7e-5. It is now
           1e-6 for the live module, with the measurement in its comment;
           anything above 1e-6 is judged as before. The check still
           catches a real change: a ×1.001 weather mutant is stale (an
           event moves a step). Every other value and module was within
           tolerance on Linux. Rerun: the fixtures job passed.
     - #112's CI on its final commit: 9 of 9. **Pyodide took 46.0 min**:
       the old 45-minute limit would have cancelled it. #113's CI: 9 of 9.
     - **While step 4 waits on the shape: step 5, humidity, built**
       (`feat/humidity-nox`, a PR into `main` containing #112 and #113).
       It is ADR-016's next decided step and doesn't depend on step 4.
       - `thermal.ambient_humidity` (g/kg, default 10.71) corrects
         reported NOx only. The form is 40 CFR 1065.670's, normalised to
         ISO 8178's 10.71 g/kg: humidity-only, so intake temperature isn't
         counted twice (ADR-016 addendum; ISO 8178 itself is paywalled).
       - It reproduces the regulation's worked example (700.5 → 736.2).
       - The presets set it: Mumbai NOx ×0.858, Leh ×1.047, Jaisalmer
         ×1.046, Rovaniemi ×1.187 (very dry: an extrapolation). Standard
         air sets exactly 10.71.
       - The picker and `/spec` say it's a correction on NOx only.
       - At the rating's air nothing moves: 21 of 21 replies identical.
         Grids re-stamped `172454a3` → `70fdc89e`.
       - Tests:
         - `test_humidity_corrects_reported_nox`: 8 parts, 6 of 6
           mutants caught;
         - units 114 (+2; 5 of 5 mutants);
         - e2e cycle 11 and spec 14 (+1 each; each mutant caught);
         - dyno 15, sweep 6, durability 5;
         - suite 82 / 0 / 3; solver: cache 20, scheduler 12, round trip
           30;
         - fixtures 7 of 7; audit 0 dead, 2 frozen (known), 0 tiny.
       - Field-count guards moved deliberately: 189 → 190 fields, 181 →
         182 editable.
  3. **The sheet:** rename Feat Prop A7 from P05 to P06 (the connector
     can't edit cells).
  4. **This Mac:** `~/Documents` is unreadable to Claude Code since
     2026-10-08 (above); work continues in a clone under the job directory.
  5. Still open from before: Phase 5's phone re-check (REVIEW-007 M-1),
     the Features tab copy, and the `hd_i6` listening question.
  - **Decided 2026-10-08:** custom engines get the table too, built in the
    browser, as resumable pieces a server can run later (ADR-016 addendum;
    the owner plans to move heavy processing server-side in v2).
- **The randomness row, discussed 2026-10-08** (the owner: "the whole idea
  of randomness is to keep the user engaged and make it interesting").
  **Decided 2026-10-08 ("Agreed, tiers 1–2 in v1, rename it P06"; ADR-016
  addendum, PLAN Phase 8):** tiers 1–2 are v1, tier 3 is v2, the ID is
  P06. *(Was: "My recommendation, not yet decided (item 6):")* The
  recommendation as accepted:
  - Measured: `/enjoy` has no road at all; it's a flat, endless road. The
    only grade control is `[`/`]` on `/drive`
    (`web/physics/src/live/engine.ts:511`). No wind, nothing random, in
    either loop.
  - Tier 1, v1: a **seeded random route** the engine feels: hills (grade
    by distance), surfaces (`Crr`: tarmac, gravel, sand), headwind, and
    altitude along the route through step 4's table (a pass where power
    fades as the air thins). A 2D "road ahead" strip. Speed breakers as a
    slow zone plus a jolt (phone vibration, P01), with no suspension, and
    the page says so.
  - Tier 2, v1: goals on a route (reach the pass without overheating, an
    economy run, a time to beat), from outputs the loop already has.
  - Tier 3, v2: drawn traffic and scenery (a renderer, near PLAN's
    out-of-scope 3D). A lead car to follow, shown as a gap readout, is 1D
    and could come earlier.
  - Constraints: one PRNG in both Python and TS, so the fixture holds
    (ADR-004); sand is rolling resistance only, no grip (ADR-002).
  - Proposed order: after step 4, with its own short proposal and
    measurements first.
- The main checkout on this Mac was on the stale `docs/pages-live`
  (2026-10-05); this session works in a worktree off `main`.
- **2026-10-08: `~/Documents` became unreadable** to this session ("Operation
  not permitted" for `ls`, the shell and the file reader alike, while
  `~/.claude` still works): most likely macOS's Files and Folders
  permission for Documents. Nothing was lost (all pushed). Work continues in
  a fresh clone under the job's own directory. To restore it, check System
  Settings → Privacy & Security → Files and Folders (or Full Disk Access)
  for the terminal app running Claude Code.

