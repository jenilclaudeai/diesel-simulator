# docs/p14-engines (P14 feasibility)

**2026-10-28:** the owner said "Start with P14". P14 is a new row on the sheet's Feat Prop
tab ("Add few more engines: add atleast 10 popular diesel engines", priority 1), and it
isn't in the repo anywhere else. Measured first, as for P08, P09, P10 and P13:
`reviews/PROPOSAL-P14.md`. PR #146 (draft), from `main` at `df36a05`, not stacked. Docs and `tools/p14/`
only: no file under `engines/`, `dieselsim/` or `web/` changes, so no grid, fixture or
hash moves.

- **13 of 14 real engines make their numbers** by the roster test's check (plateau
  start ≥ 95% of cap, rated within 3%). The five shipped engines ran alongside as controls,
  5 of 5, and hatch15 / crdi22 match ROSTER.md within 0.1 points. Six pass untuned, five
  with the roster's tuning, and the B57 and the OM642 with v8hd's harder knobs.
- **The 1.3 DDiS fails:** 88.7% at best. Its fuel swept directly shows the cause is the
  air (boost 1.40–1.48 at 2,000 rpm). That is the builder's turbo sizing, the wall hatch15
  hit, and fixing it is a hashed change.
- **Approximate real geometry keeps every pass** (10 of 10, ≤ 0.9 points).
- **3- and 5-cylinder and V6 engines sound right** through the live synth: finite, and
  each peak sits on a whole firing harmonic.
- **Costs:** ~8.8 h of building for the recommended ten. Every later full rebuild takes
  ~16 h instead of 7.2. CI physics +~2.5 min (only `test_roster_engines_make_their_numbers`
  grows, 72.3 s for five); Pyodide +0 (it SKIPs). Users download only the engine they
  drive.
- **A silent trap:** a roster key that the vehicle switch doesn't know drives the 3 t
  tractor (`Vehicle("gd28")` checked), with no error. The build adds a test for it.
- **Corrected before commit:** the geometry effect was first written as "within 1.6 points"
  by eye; the script says 0.9.
- **The candidates' figures are from memory, not sourced.** Kept out of `engines/`, which
  is auto-registered.

**CI on #146:** ~~not yet read~~ **at `665f14b` (run 40625704242): 10 of 10 passed, every
job's log read**, and every count is `main`'s: physics 103 / 103, Pyodide 82 (21 skipped),
fixtures + TS 5 / 68 / 13 / 11, SolverPort 20 / 15 / 30, app units 164, e2e 15 / 11 / 6 / 45 /
11 / 18 / 6 / 5, grid 9, custom 7.

**Batch 1 is #147** (`feat/p14-batch1`, from `main`, not stacked), with its own status
file. CI 10 of 10, every job read.

**Not run:** the suites. Nothing they test changed: docs, plus new scripts in
`tools/p14/` that no test imports.

~~**For the owner, four questions** (end of the proposal): which ten; names (N2
recommended: descriptive plus "modelled on …"); fidelity (F2: published bore, stroke, CR
and hardware); vehicles (V2: one new pickup vehicle). Legal advice on naming makers is
needed before an app-store release.~~ **Answered 2026-10-28: "Go with all your recommendations"** (ADR-023, on this PR). Batch 1 is built on its own branch from `main`, `feat/p14-batch1`, not stacked on this one.

**Housekeeping noticed, not done here:** `status/docs-a2-reviews-index.md` is still in
`status/` although #145 merged; A0 moves it to `history/` in the next modularize step.

**2026-10-28, later:** the owner answered question by question, "Most popular onces / N2 / F2 / V2". That is the same as ADR-023: V2 (the pickup vehicle) is needed only by the listed ten's pickups, so "most popular" is read as the listed ten. Recorded in ADR-023 and the proposal. **#147 (batch 1) merged** 14:47 UTC, Pages deployed `2aa1710`. Batch 2 is next, on its own branch from `main`.

**2026-10-31:** batch 2 is built and open as **#148** (`feat/p14-batch2`, from `main`, not
stacked). Four lines here said "batch 2 being built" (ADR-023's status, the proposal's
status, PLAN.md's P14, `reviews/INDEX.md`'s P14 row); each is struck through and now reads
"built, #148 open". This PR is taken out of draft: ADR-023, which #148 cites, exists only
here, so it should merge with or before #148. The two touch no file in common.
