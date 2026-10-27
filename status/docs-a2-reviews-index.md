# docs/a2-reviews-index (A2 of the modularize plan)

**2026-10-28:** `reviews/INDEX.md`, one row per file in `reviews/` (56: 33 findings,
13 proposals, 8 reviews, 2 sheets). From `main` at `a57a6fd`, not stacked on #144 (A1).
Under A0 it touches neither `STATUS.md` nor the plan's table, which #144 edits: this file
carries its status until A1 merges.

- **Every status checked against a source**, not copied from the file's own status line:
  a PR (gh's merged list, its title or branch naming the id), a commit on `main`, an ADR,
  or the PLAN / REVIEW line that records it.
- **Checked by a script** (scratch, `check_index.py`): 56 files, 56 rows, 0 missing; every
  ADR named in a row cites that row's id (it caught one wrong cell, FINDING-030's ADR-019,
  removed); 15 rows flagged "line stale".
- **The 15 stale status lines**: FINDING-003, 004, 005, 008, 018, 028, 029 and the
  proposals phase5, phase6, phase7, weather-table, P06, P09, P13, cold-start-ECU. Left as
  written. **The surprise: FINDING-008** reads "diagnosed, not fixed", but option D
  (`CycleTraces.theta_global`) merged in #30 on 2026-09-25.
- **For the owner:** (1) FINDING-027 looks answered as A (shipped stated, 2026-10-16):
  confirm; (2) correct the 15 stale lines in place (struck through, the index's status
  after), or leave the index as the one place that says it.
- **PR #145. CI at `6948baf` (run 40581587689): 10 of 10, every job read**, the counts equal
  `main`'s at `a57a6fd` exactly, as a docs change should: physics 103/0/3 on 3.10 and 3.12;
  Pyodide 82/0/2, 21 skipped; TS ports 5/68/13/11; SolverPort 20/15/30; units 164 (29
  files); e2e dyno 15, drive 11, sound 6, enjoy 45, cycle 11, spec 18, sweep 6,
  durability 5; grid 9; custom 7; claude-review: no issues. This commit is this file only.
  #144 and #145 merge onto `main` in either order to the same tree (rechecked after
  #144's `82e0b0d`).
- **Next:** the owner merges #144 (A1) and this; then this file folds into `history/` and
  STATUS.md gets A2's line. Then A3 (DECISIONS.md).
