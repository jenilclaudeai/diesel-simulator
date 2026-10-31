# ci/physics-timeouts (CI limits: physics 45 → 60 min, Pyodide 60 → 90)

**2026-10-31.** From `main` at `2aa1710`, not stacked. `.github/workflows/ci.yml` only (two
`timeout-minutes` and their comments); no code, grid or fixture changes.

- **Why:** #148's `physics (Python 3.10)` was cancelled at its 45-min limit twice
  (`d13294d`, run 40790346840, attempt 1 and the first rerun). No test failed; the suite
  prints only at the end, so a killed job shows nothing. The same tree passed in 26.4 min
  on a fast runner (`605e4a7`, run 40746197405).
- **Runner speed is bimodal.** Over the last 40 CI runs (2026-10-21 to 10-31), passing jobs,
  computed by script: 3.10 23.8–43.9 min (n 31, median 37.5, 12 of them ≥ 40); 3.12
  21.7–41.9 (n 32); Pyodide 28.9–58.5 (n 29, median 50.2, 15 of them ≥ 50). `main` itself at
  `2aa1710`: 3.12 in 22 min and, on `a57a6fd`, 39.
- **What #148 adds, measured on this Mac:** the four pickups add 59.0 s, all in
  `test_roster_engines_make_their_numbers` (11 engines 101.7 s, 15 engines 160.7 s); the
  other roster tests stay under 0.3 s. Pyodide SKIPs the roster.
- **The new limits:** physics 60 (about 16 min over the slowest pass), Pyodide 90 (about
  31 min over). Precedent: 30 → 45 (eb9a07f) and 45 → 60 (4795cb3), each for ~2× runner
  variance.

## CI

Not yet read.

## Next

After this merges, #148 needs `main` merged in (or a new push) to pick up the limits: a
rerun reuses the old merge commit's workflow.
