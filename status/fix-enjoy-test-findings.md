# fix/enjoy-test-findings (the owner's Claude in Chrome tests of /enjoy, 2026-10-31 and 11-01)

~~**PAUSED by the owner, 2026-10-31, mid-triage. No app code changed yet.**~~ Resumed
2026-11-01 and finished: **triaged, 3 fixed, 8 questions for the owner.** From `main` at
`2aa1710` (#147), not stacked. **Then the mobile run (2026-11-01):** 3 more fixed, 5 more for
the owner (11 questions in all). `main` (#146, #148, #149) merged in at `2b8d067`, no
conflicts.

## Done

- **Triage of all 18 desktop findings:** `reviews/ENJOY-TEST-2026-10-31.md`, with the report
  as received in `reviews/enjoy-test-2026-10-31/report.md` and the measuring scripts beside
  it. 3 fixed here, 8 for the owner, 7 not bugs (counted by script from the table).
- **Fixed:**
  - ENJ-01, "Now" ~1e24 L/100 km on a coast (`enjoy/economy.ts`);
  - ENJ-02, Enjoy's gearbox not kept (`enjoy/gearbox.ts`, `enjoy.ts`);
  - ENJ-09, the level standing after Stop, on /drive's meter too (`drive/sound.worklet.ts`).
- **FINDING-033 corrected in place:** not latent; waxed fuel reaches it on a shipped grid
  (ENJ-04). `reviews/INDEX.md` updated to match.
- **Not bugs, measured:** ENJ-13 (0 of 357 same-tick samples differ), ENJ-14 (every one of
  200 samples over 80 °C lit the lamp), ENJ-11 (no steady error; a +5.3 km/h overshoot).
- **The mobile run** (`report-mobile.md`, verdicts in the review's "The mobile run"),
  checked at 852×393 with real CDP touches (`mob.mjs`). Its ENJ-01, ENJ-02 and level-after-
  Stop repeats are this branch's fixes, not yet live. 3 fixed, 5 for the owner, 2 not bugs
  (counted by script):
  - fixed: MOB-05 (the start screen's labels 1.00:1, now 7.26:1, `enjoy.css`), MOB-08 (the
    breaker hint's unit, `hints.ts`), MOB-10 (Start squashed to 40 px, now 61, `enjoy.css`);
  - not bugs: MOB-04 (real touches shift one gear a tap, 3 of 3; the agent's page-made
    click had `detail: 0`), MOB-09 (a real iPhone has no `navigator.vibrate`).

## Verified locally (2026-11-01; Node 22.23.3 from `~/.cache/dieselsim`, Chrome)

On the tree merged with `main` (`2b8d067`):
- **Units: 170 passed** (31 files). Before the merge, also with `physics-version.ts` moved
  aside as CI runs them.
- **e2e:** enjoy **59** (`main` 55: four new checks), sound **6**, all 0 failed. Before the
  merge: drive 11, `check:labels` passes.
- **Mutants, each against a passing baseline, each failed by an assertion:** economy 2 of 2,
  gearbox 2 of 2, the ENJ-02 wiring 1 of 1 (e2e), the ENJ-09 worklet 1 of 1 (e2e), the
  MOB-08 hint 1 of 1, the MOB-05 and MOB-10 CSS rules 2 of 2 (e2e, both out in one build;
  the two checks read unrelated properties).
- Nothing under `dieselsim/` changed: grids and fixtures stay current.

## CI

~~On #151 at `0e85ace` (run 41287259563): 10 of 10 pass, every job's log read~~ (before the
mobile fixes and the merge; physics 105 on 3.10 and 3.12, Pyodide 82 + 23 skipped, units 170,
e2e enjoy 53 and the rest all 0 failed). **At the merged head: not yet read.**

## Waiting on the owner

The eleven questions in `reviews/ENJOY-TEST-2026-10-31.md`, each with options and a
recommendation: ENJ-08 (the limiter buzz's threshold), ENJ-03 with MOB-01 and MOB-02 (a short
phone: the toast, the trip computer, Sound off screen on a route with a goal), ENJ-04
(FINDING-033 A plus a "Fuel gelled" lamp), ENJ-07, ENJ-11, ENJ-05, ENJ-12, ENJ-17, MOB-03
(touch controls for Neutral and cruise), MOB-06, MOB-07. Also: confirm that
`ANDROID-BUGS.csv`'s B-07 and B-08 rows are stale (#140 and #141 are merged).

## Notes for the next session

- A fresh worktree needs `web/app/e2e/out/` made by hand before `e2e:enjoy`, or the run
  stops at its first screenshot (ENOENT). It also needs `npm ci` in `web/solver`, for
  `pyodide`'s types, before `build:pages`.
- This Mac's Homebrew Node is 24.2.0, below Angular 22's 24.15; use the cached 22.23.3.
- A Claude in Chrome run that makes its own events in the page can fake bugs: a page-made
  `click` has `detail: 0`, which the paddles read as a keyboard press (MOB-04). Recheck any
  touch finding with CDP touches (`mob.mjs`, `e2e:enjoy`).
