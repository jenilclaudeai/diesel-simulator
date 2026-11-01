# fix/enjoy-test-findings (the owner's Claude in Chrome test of /enjoy, 2026-10-31)

~~**PAUSED by the owner, 2026-10-31, mid-triage. No app code changed yet.**~~ Resumed
2026-11-01 and finished: **triaged, 3 fixed, 8 questions for the owner.** From `main` at
`2aa1710` (#147), not stacked.

## Done

- **Triage of all 18 findings:** `reviews/ENJOY-TEST-2026-10-31.md`, with the report as
  received in `reviews/enjoy-test-2026-10-31/report.md` and the measuring scripts beside it.
  3 fixed here, 8 for the owner, 7 not bugs (counted by script from the table).
- **Fixed:**
  - ENJ-01, "Now" ~1e24 L/100 km on a coast (`enjoy/economy.ts`);
  - ENJ-02, Enjoy's gearbox not kept (`enjoy/gearbox.ts`, `enjoy.ts`);
  - ENJ-09, the level standing after Stop, on /drive's meter too (`drive/sound.worklet.ts`).
- **FINDING-033 corrected in place:** not latent; waxed fuel reaches it on a shipped grid
  (ENJ-04). `reviews/INDEX.md` updated to match.
- **Not bugs, measured:** ENJ-13 (0 of 357 same-tick samples differ), ENJ-14 (every one of
  200 samples over 80 °C lit the lamp), ENJ-11 (no steady error; a +5.3 km/h overshoot).

## Verified locally (2026-11-01; Node 22.23.3 from `~/.cache/dieselsim`, Chrome)

- **Units: 170 passed** (31 files; `main` 167 in 30), also with `physics-version.ts` moved
  aside as CI runs them.
- **e2e:** enjoy **53** (`main` 51), sound **6**, drive **11**, all 0 failed. `check:labels`
  passes.
- **Mutants, each against a passing baseline, each failed by an assertion:** economy 2 of 2,
  gearbox 2 of 2, the ENJ-02 wiring 1 of 1 (e2e), the ENJ-09 worklet 1 of 1 (e2e).
- Nothing under `dieselsim/` changed: grids and fixtures stay current. The Python suite and
  the Pyodide job were not rerun locally (no Python changed). CI is the check for them.

## Waiting on the owner

The eight questions in `reviews/ENJOY-TEST-2026-10-31.md`, each with options and a
recommendation: ENJ-08 (the limiter buzz's threshold), ENJ-03 (a short phone: the toast and
the trip computer), ENJ-04 (FINDING-033 A plus a "Fuel gelled" lamp), ENJ-07, ENJ-11,
ENJ-05, ENJ-12, ENJ-17. Also: confirm that `ANDROID-BUGS.csv`'s B-07 and B-08 rows are
stale (#140 and #141 are merged).

## Notes for the next session

- A fresh worktree needs `web/app/e2e/out/` made by hand before `e2e:enjoy`, or the run
  stops at its first screenshot (ENOENT). It also needs `npm ci` in `web/solver`, for
  `pyodide`'s types, before `build:pages`.
- This Mac's Homebrew Node is 24.2.0, below Angular 22's 24.15; use the cached 22.23.3.
