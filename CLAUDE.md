# dieselsim — instructions for Claude Code

A physics-based diesel engine simulator, moving from a Python package
(`dieselsim/`) to a standalone Angular browser app for diesel enthusiasts.
The repo is the handoff: code, plan, decisions and findings all live here.

## Start of every session

Read, in order, before doing anything: `STATUS.md` → `PLAN.md` →
`DECISIONS.md` → `TEAM.md` → `reviews/*.md`. Don't ask me to re-explain
what's in them. Then tell me what you'd do first.

At the end of a session, update `STATUS.md` so the next one starts from the
truth. A stale STATUS.md is the failure this setup exists to prevent.

## How I work — as important as the code

- **Measure before you fix.** About a third of the original bug list was
  overstated, stale or wrong, and two entries understated real problems.
  Verify every claim before acting on it — including mine and a previous
  session's.
- **Prove it, don't assert it.** Show numbers: "0 of 64 values differ", not
  "should be fine".
- **Test your tests.** Mutation-test anything that guards against
  regression, always against an unmutated baseline that passes, and treat a
  compile failure as broken, not "caught". Several past tests silently
  tested nothing.
- **Own mistakes in place.** Correct findings visibly, keeping the old text;
  don't quietly rewrite them.
- Ask rather than assume. Options come with trade-offs **and** positives.
- The twelve-persona team in `TEAM.md` is a set of **review lenses** applied
  at decision points, not agents in every reply.
- Commit and push early; end each chunk of work with a written status.
- **At the end of every response, update the context files that went
  stale**: `STATUS.md` always, and `PLAN.md`, `CLAUDE.md`, `DECISIONS.md`
  or `reviews/` when the response changed what they say (owner's
  instruction, 2026-10-05). Not only at the end of a session.

## Git

- GitHub Flow: a branch per change, push, open a PR (`gh pr create`).
- Stack PRs when changes build on each other: each targets the branch below
  and shows only its own commits.
- **The repo does not auto-delete merged branches.** After merging a parent,
  retarget its child PR (`gh pr edit <n> --base main`) or it merges into a
  dead branch.
- Read CI with `gh pr checks <n>`. Never put a token in a file, commit or chat.

## Running things

```bash
python3 tests/test_physics.py          # regression suite; see STATUS.md for expected counts
python3 tools/audit_dead_signals.py    # run after ANY physics change
python3 tools/fixtures/gen_fixtures.py --check   # golden fixtures current? (regenerate without --check)
cd web/physics && npm ci && npm test            # TypeScript ports vs fixtures (ADR-004), incl. the live loop
python3 tools/fixtures/gen_fixtures.py --only live   # after changing dieselsim/live.py
python3 tools/build_live_grids.py               # after a SOLVER change: prebuilt converged grids (~2 h, 10 grids)
python3 tools/build_live_grids.py --engine my.json   # a custom engine's grid -> out/grids/ (ADR-014)
cd tools/pyodide && npm ci && npm run suite     # the same suite under Pyodide
cd web/solver  && npm ci && npm run test:fast   # cache tests, seconds
cd web/solver  && npm test                      # + live-grid scheduler + round trip through a real worker
cd web/solver  && npm run test:live-real        # manual ~7 min: browser-built grid vs native (see the file's header)
cd web/app     && npm test -- --watch=false     # unit tests (vitest)
cd web/app     && npm run build:pages           # NEVER plain `build`: blank page on Pages
cd web/app     && npm run check:assets          # prepare-assets on a network without the Pyodide CDN
cd web/app     && npm run check:labels          # every fuel figure labelled steady-state (FINDING-009)
cd web/app     && npm run perf                  # synth/loop/friction cost under Chrome CPU throttling (reports only)
cd web/app     && npm run e2e                   # browser checks (also e2e:grid, e2e:drive, e2e:sound, e2e:enjoy, e2e:custom,
                                                # e2e:cycle, e2e:spec, e2e:sweep, e2e:durability)
```
The app is live at https://jenilclaudeai.github.io/diesel-simulator/,
published from `main` by `.github/workflows/pages.yml` on every merge.
Angular needs Node ≥ 22.22.3. If npm 10 crashes resolving Angular's peer
deps, use `npx -y npm@11 install`. The project supports Python 3.10 —
3.12-only syntax has slipped in before.

## The pattern to watch for

Five of the first six findings had one shape: **a mechanism fully built,
correctly wired, and fed a quantity that was zero or pinned against a clamp,
raising no error.** `tools/audit_dead_signals.py` exists to catch the next.
It checks **outputs** that never vary; it cannot see an **input** that
nothing reads. FINDING-025 was one: the spec's ambient fields were editable
on `/spec`, but `operating_point` ran at fixed defaults. For a spec field,
grep its readers and solve with it changed.

## Traps in the code — all fail silently

- Wall temperatures come from `self.T_coolant` via `_apply_thermal_state()`;
  mutating `spec.thermal.coolant_T` after construction does nothing.
- Oil temperature is separate state (`oil.cond.T_oil`). A cold-engine test
  needs cold oil **and** cold coolant, or it misses a 255% friction effect.
- `warm_start=False` isolates a solve since session 5 (bug #5, PR #41): it
  resets the turbo's shaft speed and VGT position too, and the limiter's
  calibration chain starts cold. Before that it reset only the gas state and
  only a fresh engine was clean. A cold solve on a used engine still differs
  from a *warm* one on a fresh engine -- compare like with like.
- `dpdtheta_max` measures compression; read **`dpdtheta_comb`**.
- Read `h_ring_mid`, not `h_ring_tdc` (always its 12 nm clamp).
- Use `n_cycles >= 9`; at 6 the drift is 10.8%.
- `CycleTraces.theta`: per-cylinder arrays are in that cylinder's own crank
  angle, manifold traces in global engine angle. Don't overlay naively;
  never `ravel()` a 2D field and index `theta` with the result.
- The real-time loop (vehicle, gearbox, driveline, `LiveEngine`, driver
  keys) lives in `dieselsim/live.py`, not `play.py`: it is the Python
  reference for the TypeScript port. `play.py` is the terminal front end.
- The solver needs **numpy only**. Never import `scipy` at module level in
  `dieselsim/` (a test enforces it). `batch.py` imports `multiprocessing`,
  which Pyodide lacks.
- Full-load dyno pulls end in negative torque: above rated speed the
  governor pulls fuel to 4% at `max_rpm`. That is intended.
- The Pyodide suite (`tools/pyodide`) copies only `dieselsim/` and
  `tests/`. A test that reads `web/app`, `tools/` or `engines/` must SKIP
  there (or leave those parts out and say so), or CI's Pyodide job goes red
  while every local run passes: it did, on six PRs (REVIEW-008 M-1). Read
  every job in `gh pr checks`, not just the ones you expect.
- WebCrypto needs a secure context: over plain http on a LAN address the
  grid cache switches itself off by design.
- `npm start` downloads the numpy wheel once (`prepare-assets.mjs`). Behind a
  proxy, Node's fetch ignores `HTTPS_PROXY` unless `NODE_USE_ENV_PROXY=1`;
  offline, use `PYODIDE_WHEEL_DIR`. Without the wheel `npm start` carries on
  (Drive works; Dyno and Grid say numpy is missing), but builds and CI stop.
- The grid hash (`bridge.grid_hash`) covers every `dieselsim/*.py` except
  `GRID_HASH_EXCLUDES` (`live.py`, `livesound.py`, `bridge.py`). An edit to
  any other file, **`builder.py` included**, makes every prebuilt grid
  stale. Re-stamp only with proof that no cell can change (the static
  import walk, identical specs), asserting that only the hash string
  differs. **`tools/restamp_grids.py <dir of pre-change files>`** asserts
  the mechanical half: the pre-change tree hashes to the grids' stamp, and
  each file changes only by the hash. It refuses otherwise. The "can't
  reach a cell" half is yours: a grep, and
  `test_live_grid_pieces_match_the_shipped_grid`.
- A roster engine's file must be **`engines/<key>.json`**. Under any other
  name its grid records no engine-file fingerprint, and the tests do not
  find it. `load_engine_dir` registers every file in `engines/`, so
  `build_live_grids.py` with no arguments builds all of them, untuned ones
  too.
- `web/app/src/app/solver/physics-version.ts` is generated by
  `prepare-assets` and gitignored. CI runs the unit tests **before**
  generating it, so a spec must not import `solver.service.ts`, even
  transitively. To reproduce CI, run the units with the file moved aside.
- Floating point differs across platforms (Linux CI against this Mac,
  Pyodide against CPython): about 1e-13 for a converged cell, about 1e-6
  through the limiter's calibration chain. Never compare against a shipped
  grid exactly; use `GOLDEN_TOL`.
- e2e touch via CDP: a `touchMove` that leaves a finger out does **not**
  lift it, and `touchEnd` lifts every finger. `at(sel, h)` is the fraction
  *up* the pedal, so 0.95 is full throttle. The stall test leaves `/enjoy`
  in Manual.

## Decisions

`DECISIONS.md` holds ADR-001 to ADR-016 (ADR-013: the personas are review
lenses; ADR-014: custom engines, drivable; ADR-015: Phase 6's scope, staged;
ADR-016: Phase 7's six decisions, and v2 as a separate list). Don't reopen one without a
measured reason. The ones most easily undone by accident: the Python solver
runs **unmodified** under Pyodide (ADR-001); audio is a TypeScript
AudioWorklet with no `SharedArrayBuffer`, so no COOP/COEP headers, so GitHub
Pages hosting works (ADR-003); Angular pinned, standalone, signals, OnPush,
no NgRx (ADR-005). ADR-006 is superseded by ADR-011 (live friction from
the cells' traces, a warm/cold grid pair).
