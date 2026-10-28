# Status

**The present only** (step A1 of `reviews/PROPOSAL-modularize.md`, 2026-10-28; at most
150 lines). Everything older is in `history/`, moved verbatim, one file per session
(`history/README.md` lists them). A PR branch never edits this file: it writes
`status/<branch>.md` (A0, CLAUDE.md).

## Now (2026-10-28)

- **`main` is `a57a6fd`.** The owner merged #141 (B-08), #143 (the modularize plan) and
  #142 (the cold-start ECU proposal) on 2026-10-27, 20:36 UTC, after #140 (B-07).
  Pages deployed `a57a6fd`, so the live site is current.
- **Open PRs, both docs only (no grid, fixture or code under `dieselsim/` or `web/`
  changes), not stacked; they merge onto `main` in either order to the same tree:**
  - **#144**, A1, this file (`docs/a1-status-history`);
  - **#145**, A2, `reviews/INDEX.md` (`docs/a2-reviews-index`; its status is
    `status/docs-a2-reviews-index.md`). It flags 15 files whose own status line is stale,
    FINDING-008 among them (fixed in #30, reads "not fixed").
- **In progress:** the modularize plan's Part A. A0 is done (#143); A1 and A2 are open.

## Last verified counts

CI on `main` at `a57a6fd` (run 40579632693): **9 of 9 passed**, every job read from its log:
- physics **103 passed, 0 failed, 3 known** on Python 3.10 and 3.12;
- Pyodide **82 passed, 0 failed, 2 known, 21 skipped**;
- golden fixtures + TS ports 5 / 68 / 13 / 11; SolverPort 20 / 15 / 30;
- web app: units **164** (29 files), prepare-assets offline 4;
- e2e: dyno 15, drive 11, sound 6, **enjoy 45**, cycle 11, spec 18, sweep 6,
  durability 5; grid 9 (Chrome against native); custom engine 7. All 0 failed.

CI's physics jobs have scipy; this Mac's system Python doesn't, so a local run SKIPs the
scipy-gated sound tests (#141's local run: 98 passed, 3 known, 4 skipped; 103 with scipy).
Not rerun locally for A1 (docs only).

## Waiting on the owner

1. **Phone checks on the S9+, on the live site** (none done since the merges):
   - B-08: open, close and reopen the throttle in /enjoy; no sound spikes;
   - B-07: Stop silences the engine, also when pressed while starting;
   - P01: vibration while driving (tap Test first; Chrome stays still on Mute);
   - P06: a route's feel, the breaker buzz, a goal run;
   - Phase 5's re-check (REVIEW-007 M-1): after a stall, hold the clutch and tap Restart
     (B-01); shift without the clutch (B-02); sound without crackle; a smooth drive.
2. **FINDING-033** (an automatic dragged to its 60 rpm floor stays "running"; latent, no
   shipped grid reaches it): recommended A, stall it so /enjoy offers Restart.
3. **FINDING-027** (single10's all-or-nothing ignition in cold, thin air): on 2026-10-16
   the owner chose to ship "with single10's 36% Leh check stated", which is option A. The
   finding still reads "open, for the owner". Confirm A (#145 asks too).
4. **The Feat Prop rows never looked at:** P07 (multi-parameter sweep), P11 (number of
   gears), P12 (vehicle weight), each priority 1.
5. **Still open when last listed (2026-10-12), not mentioned since:** copy the Features tab
   into the bug sheet (template below); rename Feat Prop cell A7 from P05 to P06 (the
   connector can't edit cells); the `hd_i6` idle-tick listen
   (`out/listen/review003m5_*.wav`).
6. **Order:** the cold-start ECU build (next steps, 3) against the rest of Part A. The
   owner's 2026-10-27 order covers A and B only.
7. **#145's question:** correct the 15 stale status lines in place, or leave the index as
   the one place that says it.

## Next steps

1. **Part A, one PR per step, not stacked**, each proven by
   `tools/check_verbatim_move.py`:
   - A2 `reviews/INDEX.md`, one line per finding and proposal (#145, open);
   - A3 DECISIONS.md as an index plus summaries, full texts to `decisions/`;
   - A4 PLAN.md, done phases one line each;
   - A5 nested CLAUDE.md files by area;
   - A6 the session-start rule (the owner's answer: STATUS plus the indexes);
   - A7 guards (STATUS within 150 lines; every finding indexed; both SKIP under Pyodide).
2. **Part B, after A:** B1 split `tests/test_physics.py` with discovery by name; B2 split
   `live.py` (unhashed); B3 refuse a `.py` in a subfolder of `dieselsim/`.
3. **The cold-start ECU, its own PR** (FINDING-031 C, `reviews/PROPOSAL-cold-start-ECU.md`).
   The owner's answers (2026-10-28): C1, the pedal's fuel covering the cold friction's
   excess and the cold walls' deficit, gated on 40-70 °C coolant; no fast idle; extra fuel
   and glow plugs when cold (glow plugs are new physics: measure them before building);
   keep P08's schedule. `live.py` is unhashed, so no grid goes stale.

## Where things are

- **The app:** https://jenilclaudeai.github.io/diesel-simulator/, published from `main` by
  `.github/workflows/pages.yml` on every merge.
- **The bug sheet:** https://docs.google.com/spreadsheets/d/1giP18zulUFOkOyXFj7sj0JRSGR8SydxNb2owMN0COV8/edit
  - the owner's Bugs tab, the owner's Feat Prop tab (feature requests, P01 on), and a
    Tracker tab that `IMPORTDATA`s `reviews/ANDROID-BUGS.csv` from `main` hourly;
  - **update the CSV, never the sheet**: the Drive connector reads the sheet but can't
    edit cells;
  - the Features tab's template, `12mLsfoFBwh_5Zqai6zpHpv3yZSBx45jvFgf3ZnYZyNY` (tab menu
    → Copy to → Existing spreadsheet); its status columns read `reviews/FEATURES.csv`
    (a header only, as of 2026-10-28).
- **The context:** PLAN.md (phases), DECISIONS.md (ADR-001 to ADR-022), `reviews/`
  (findings, proposals, reviews), TEAM.md (the review lenses), `history/` (old status).
- **This Mac:**
  - Node: the system has 20.19 and Angular needs 24.15. Prefix commands with
    `PATH=$(dirname $(npx -y -p node@24.15.0 -- which node)):$PATH`, or run
    `npx -y -p node@24.15.0 -- <cmd>`;
  - a fresh worktree: `npm ci` in `web/physics`, `web/solver` and `web/app`, then
    `mkdir -p web/app/e2e/out` before any e2e;
  - e2e: `CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    npm run e2e:enjoy` after `npm run build:pages`;
  - a worktree-isolated session refuses compound shell commands that mention `git`, and
    inline heredocs: put them in a script file;
  - the system Python has no scipy, so the suite SKIPs the scipy-gated sound tests. Run
    them in a venv (3.12) after any sound or solver change.

## How this file works

- At most 150 lines, the present only: open PRs, questions for the owner, the last
  verified counts, the next steps, where things are.
- A PR branch writes `status/<branch>.md` and nothing else of the status (A0). Once the PR
  merges, its file moves verbatim into `history/` (`git mv`, no edit), and what is still
  true goes into this file, by the next step of the modularize plan or the next session.
- A finished entry here moves to `history/` verbatim, never rewritten.
