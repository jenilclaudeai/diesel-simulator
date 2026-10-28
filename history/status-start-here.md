# STATUS history: "Start here", the standing summary of sessions 6 to 8 (2026-09-30 to 2026-10-08)

Moved verbatim from `STATUS.md` at `a57a6fd`, its lines 1856-2005, by step A1 of
`reviews/PROPOSAL-modularize.md` (2026-10-28). **This is history, not the present**:
`STATUS.md` is. Struck-through text and in-place corrections are as they were written.
`python3 tools/check_verbatim_move.py history/` proves the copy.

<!-- verbatim: STATUS.md@a57a6fd 1856-2005 -->
## Start here

**The app is live:** https://jenilclaudeai.github.io/diesel-simulator/
It is published from `main` by `.github/workflows/pages.yml` on every merge.
Pages: `/` (Dyno pull), `/grid`, `/drive` (engineering), `/enjoy` (phones,
landscape), and Phase 6's `/cycle`, `/spec`, `/sweep` and `/durability`.
*(Was: "Phase 6 adds … once its stack merges".)*

| phase | state |
|---|---|
| 1–3: physics truth, solver port, real-time loop | done (REVIEW-003 to -005) |
| 4: audio | done; the owner signed it off by ear 2026-09-30 (REVIEW-006) |
| 5: Enjoy mode | **exit-ready (REVIEW-007): one item left, the owner's re-check on the phone (M-1)** |
| 6: Expert mode | **done (REVIEW-008); all of #89–#99 on `main` and live** |
| 7: Environment and projects | **decided (ADR-016, 2026-10-07): building**, in the proposal's order; FINDING-025 and REVIEW-008 m-3 done on the way; steps 1–3 merged; **step 4 paused on FINDING-026** (2026-10-08) |
| 8: Polish and host | Pages hosting done early (#85); the rest not started |

**What Phase 5 has** (all merged):
- `/enjoy`: touch pedals, gear paddles, dials, lamps, temperatures, and a
  steady-state trip computer.
- The full roster (ADR-012): `hatch15`, `crdi22`, `truck127`, `v8hd` and
  `single10`; 1, 4, 6 and 8 cylinders, one without a turbo. The records
  are in `engines/ROSTER.md`.
- FINDING-023 (cold slap from a temperature-dependent clearance) and cam
  ramps with their own height (REVIEW-003 m-5), in one rebuild of every
  grid.
- **Custom engines (ADR-014):** brochure numbers or JSON on the Dyno and
  Grid pages, achieved against requested, then drivable.
  - The browser builds the converged grid with a worker pool: 21.5 min
    measured on an 8-core Mac.
  - Or natively: `tools/build_live_grids.py --engine`.
  - Saved under "Your engines" on `/drive` and `/enjoy`, with a grid-file
    download for phones.
- The Derate lamp means protection: charge air above 80 °C, or an overheat
  derate.

**Waiting on the owner:**
0. ~~**Merge #100**~~ Done 2026-10-06 17:39 UTC. *(Was: "Merge #96 once
   its checks are green" — done 06:30 UTC.)*
1. **Close Phase 5: REVIEW-007's M-1.** On the S9+, on the live site: after
   a stall, hold the clutch and tap Restart (B-01); shift without the
   clutch (B-02); and say whether the sound plays without crackle and the
   drive is smooth. Then Phase 5 is done.
   - The bug sheet: https://docs.google.com/spreadsheets/d/1giP18zulUFOkOyXFj7sj0JRSGR8SydxNb2owMN0COV8/edit
     The owner's Bugs tab, and a Tracker tab that `IMPORTDATA`s
     `reviews/ANDROID-BUGS.csv` from `main` (refreshed hourly; the first
     time it may need "Allow access"). **Update the CSV, never the
     sheet.** The Drive connector reads the sheet but can't edit cells.
2. ~~**Merge Phase 6's stack**~~ **Done 2026-10-06: #89–#99 are all on
   `main`** (#96 last, at 06:30 UTC, carrying #97–#99). `main` matched #99's
   tested tip by content. *(Was: "**Merge Phase 6's stack, in order:** #89 → #90 → #91 → #92 → #93 → #94 →
   #95 → #96 → #97 → #98 → #99 (REVIEW-008). After each merge, retarget the
   next PR to `main` (`gh pr edit <n> --base main`), then check `main` by
   content (memory: stack-merge-trap). Pages publishes each merge.")*
   - **What Phase 6 has** (REVIEW-008):
     - `/spec`: every field (188, 181 editable; 189 with Phase 7's `ecu_modern`) in 7 subsystem groups, with
       ADR-009's four live schematics and JSON export and import.
     - Its edits are solved on Dyno, Grid, Cycle, Sweep and Durability,
       with an "out of date" banner. **Drive it** builds an edited engine's
       drivable grid into "Your engines".
     - `/cycle` (p–V, p–θ, heat release, valve lift), `/sweep` (one field
       over a range) and `/durability` (life consumed, 0 = new). Each is
       checked against native Python in a browser.
     - FINDING-024 (MFB50 was late by up to 7°) is fixed, with the grids
       re-stamped with proof.
   - REVIEW-008 found and fixed four MAJORs:
     - CI's Pyodide job had been red since #91, which I'd missed;
     - the Dyno BSFC column was unlabelled;
     - an edited engine couldn't be driven;
     - the physics job's 20-minute timeout was too tight for the grown suite.
   - *(Was: "~~Decide Phase 6's plan.~~ Decided 2026-10-05: option B
     (ADR-015)…")*

3. **The grid-build plan is deferred by the owner until v1 is complete**
   (2026-10-05). Option A (the ETA) shipped in #88. *(Was: "Decide the
   grid-build plan".)*
3b. ~~**Decide Phase 7's plan**~~ **Decided 2026-10-07: all six
   recommendations accepted (ADR-016);** projects on `/spec`. *(Was:
   "Decide Phase 7's plan: `reviews/PROPOSAL-phase7.md` (#102, merged
   2026-10-06), six decisions.")* Nothing that depends on them is built
   until then. *(Was: "Nothing in Phase 7 is built until then." Too broad:
   projects and persistence were decided by ADR-007, so they went ahead.)*
   - **Started, needing no decision: REVIEW-008 m-3,** `/spec` edits kept
     across a reload (#103, branch `fix/m3-edits-kept`).
     - `SpecEdits` keeps base + overrides in `localStorage`, saved on every
       change and checked against the schema when restored.
     - The page says the results are solved again.
     - An unknown kept engine falls back to crdi15.
     - Units 104 (+3), with 8 of 8 mutants caught; e2e:spec +1 check
       (a real reload): 12 of 12 locally. With restore disabled, exactly
       that check fails ("0 fields changed, compression ratio 16") and
       the other 11 pass.
   - **Next, needing your call on the UX:** the project file (ADR-007:
     spec + vehicle + gearbox, versioned, environment later). Where should
     Save/Open live? One proposal: on `/spec`, replacing "Export spec",
     with `/drive` and `/enjoy` able to open one.
   - Weather in Drive: a per-engine correction table, measured within 1.15%
     of converged solves on held-out air (recommended); or a grid per
     preset; or solving pages only.
   - The ECU at altitude: the boost control holds a pressure ratio, so
     converged light load gains 8.2% torque on a 90 kPa hill.
   - Humidity, cold-flow, the presets, and your "Feat Prop" list.
   - It builds on #101 (FINDING-025), now merged. *(Was: "merge that
     first".)*
4. **Copy the Features tab into the bug sheet** (template
   `12mLsfoFBwh_5Zqai6zpHpv3yZSBx45jvFgf3ZnYZyNY`: tab menu → Copy to →
   Existing spreadsheet). Its status columns read `reviews/FEATURES.csv`.
5. **Listening:** `out/listen/review003m5_*.wav`; is `hd_i6`'s idle tick
   too quiet? (Details in the session 6 section below.)
6. ~~**Your "Feat Prop" tab: which are v1?**~~ **Decided 2026-10-07
   (ADR-016):** P01 vibrations is v1 (PLAN Phase 8). P02–P05 are v2, after
   v1, in the owner's order: priority 1 is highest, so P04 comes first.
   PLAN lists them. *(Was: "Your "Feat Prop" tab (new in the bug sheet,
   read 2026-10-06): which are v1?")* P01 vibrations (priority 3), P02 Google sign-in (2), P03 free/paid
   roles (3), P04 grid on a backend (1), P05 grid on AWS Lambda (3).
   - P02–P05 each need a server. PLAN puts "backend, accounts, payments,
     telemetry collection" **out of scope for v1** (`PLAN.md`, "Deliberately
     out of scope"), and the static, header-free hosting is ADR-003's
     design.
   - P04/P05 are also the grid-build plan you deferred until v1 is complete
     (item 3; `reviews/PROPOSAL-grid-build.md` already weighs a build
     server).
   - P01 fits v1 as it stands: phone haptics in `/enjoy` (Android Chrome has
     `navigator.vibrate`; iOS Safari does not).
   - Also: is priority 1 the highest or the lowest? The empty rows default
     to 1.
   - Nothing is started on any of them. (This is not item 4's Features tab;
     that one is still to copy.)
   - ~~**Open (session 8)**~~ **Decided 2026-10-08: P06, tiers 1–2 v1,
     tier 3 v2** (see "Session 8, start" above). **For the owner:** the
     sheet still says P05 in Feat Prop cell A7. The connector can't edit
     cells, so please change it to P06. *(Was: "Open (session 8): the new
     row, "Randomness in drive mode" (priority 2, ID P05 again). v1 or
     v2? And a new ID for it (P06)?")* The analysis at the time:
     What it touches: the live loop already has a grade (`live.py:679`,
     sin/cos form, ±20% from the keys) and a rolling resistance (`Crr`, a
     constant per vehicle), so random hills, and surfaces as a varying
     `Crr`, are within v1's physics.
     "Speed breakers" are a bump (suspension, out of scope) unless
     modelled as a short grade and a speed limit. "Traffic with visuals"
     needs a scene, near PLAN's out-of-scope "3D models".
7. ~~**Merge #101 (FINDING-025)**~~ Done 2026-10-06 17:41 UTC. Its open
   question is now decision 2 of the Phase 7 proposal (item 3b).
   The modelled ECU is now **uncompensated**: the pedal gives fuel, so at
   altitude torque falls and smoke rises. Keep that, or add a barometric
   derate, or torque-based control? (See Session 7 below.) *(Was: "…should
   the modelled ECU derate from a barometric sensor, or fuel like an
   uncompensated pump?" The first fix was neither; see FINDING-025's
   correction.)*

