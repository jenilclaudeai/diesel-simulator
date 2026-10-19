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
sh buildgrid/build.sh my.json                   # P13 N: the same, cells + weather, one command, own venv
                                                # (Windows: buildgrid\build.bat); then the app's Import grid
python3 tools/build_live_grids.py --weather [key]    # add the weather table to grid files (~45-85 min each)
python3 tools/rebuild_cold_cells.py <pre-change dir>  # only the grids' cold cells, after a change that
                                                # reaches only cold friction (asserts it; ~80 min for ten)
python3 tools/environments_json.py --check           # the places file Drive and Enjoy read is current
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
sh bench/run_bench.sh [--full]                  # hardware benchmark: a drivable grid's build time (bench/README.md;
                                                # Windows: bench\run_bench.bat). Quick reads low on a laptop that throttles
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
- `dpdtheta_max` measures compression; read **`dpdtheta_comb`**. For the
  knock's sharpness read **`dpdtheta_knock`** (P09, FINDING-029): it is
  computed from the burn law, while `dpdtheta_comb` differentiates the 1°
  trace and swings 16% with a small shift in injection timing.
  `acoustics.build_sources` reads `dpdtheta_knock`.
- **The grid's cold cells are a true cold start** (P09, ADR-019): every
  wall, plus the coolant, at 273 K (`engine.cold_start_walls`). Before P09
  the walls followed the coolant by `WALL_FOLLOW`. For a cold test call
  `cold_start_walls(T)` and set cold oil too. **Friction keeps the
  `WALL_FOLLOW` liner** (FINDING-030, `_friction_liner`): `friction.py`'s
  film offsets (skirt at liner − 20 K) assume a hot running liner, and fed
  a 273 K one they gave 6–140× warm FMEP. Setting the liner by hand after
  `cold_start_walls` reaches the combustion only; `_apply_thermal_state`
  drops the friction liner.
- **The live loop blends warm and cold at `LiveEngine.T_chamber`**, not at
  `T_coolant`. The chamber walls warm with a 60 s time constant and cool
  with a 600 s one. A test that warms the coolant to get a warm engine
  must set `T_chamber` too (the warm fixture drives start at 361 K).
- **The knock the synth hears** (P09): `live.LiveEngine._knock()` sends
  `dpdt_max` (the blend at `T_chamber`, plus the weather table's change)
  and `dpdt_ref` (the warm blend at standard air). The synth multiplies
  combustion by their ratio to the power `KNOCK_GAIN_EXP` (4, chosen by
  ear; a playback gain, not physics). The gain lives in unhashed
  `livesound.py`, and `KNOCK_REF` in hashed `acoustics.py`. Mirror both in
  `synth.ts`. The weather table's keys (`bridge.WEATHER_KEYS`) include
  `dpdt_max`: a grid whose table lacks it plays no altitude knock, and
  raises no error.
- Off the rating's air (101325 Pa / 298 K), a modern ECU (`spec.ecu_modern`,
  ADR-016) targets absolute boost and caps each cycle's fuel at
  trapped air / `afr_limit`. There, **`op.fuel_mg` is the fuel injected,
  not the pedal's command**. The calibration always runs at the rating's
  air (FINDING-025), so at standard air nothing changes.
- Humidity (`thermal.ambient_humidity`, g/kg) corrects **reported** NOx
  only: `op.nox_ppm` and `op.nox_g_kwh` carry 40 CFR 1065.670's factor;
  `op.cycle.nox_ppm` is the cycle's own, uncorrected. Nothing else reads
  humidity (ADR-016 item 3). The helper lives in hashed `engine.py`, not
  in `environment.py`, which no cell solve may import.
- Read `h_ring_mid`, not `h_ring_tdc` (always its 12 nm clamp).
- Use `n_cycles >= 9`; at 6 the drift is 10.8%.
- **A converged solve stops once settled** (P13, ADR-020): `CONVERGED_CYCLES`
  is a ceiling, `op.cycle.n_cycles_used` says how many ran. To compare with
  a full 200-cycle solve set `DieselEngine.EARLY_STOP = False`. The cycle
  that may end a stop is run as the last one (the traces and the knock are
  recorded only then): code that reads `last` must allow a last cycle that
  is followed by another.
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
- The automatic's schedule (P08, ADR-017) reads the engine's map through
  `Gearbox.econ`, which `LiveEngine` sets. A `Driveline` or `Gearbox` made
  on its own keeps today's rpm schedule (`_power_schedule`), with no error.
  Changing any `ECO_*` constant changes the live fixtures: regenerate
  (`--only live`) and re-match the TS port.
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
  `tools/ab_rating_air.py <tree>` prints sha256s of 21 bridge replies at
  the rating's air; diff an old tree's against the new one's (FINDING-026).
- Every shipped grid carries a **weather table** (Phase 7 step 4, the
  file's `weather` key). A full grid rebuild (`build_live_grids.py` without
  `--weather`) writes a fresh file **without** it, so after a solver change
  run `--weather` too: 384 + 6 converged solves per grid, about 8 h for all
  ten on this Mac. A re-stamp (`restamp_grids.py`) keeps the table. It is
  built from the same code as the cells, so the one stamp covers both. The
  table only corrects the live loop (Drive, Enjoy); the solving pages solve
  the air directly.
- **The build tools' pool fails loudly** (`build_live_grids.SafePool`, P13):
  `multiprocessing.Pool` replaces a killed worker and its `map` then waits
  forever (a weather pass sat at 0% CPU for 55 h, 2026-10-16). A
  `BrokenProcessPool` from a build means a worker was killed: rerun it
  (`--weather` alone if the cells are built).
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
- ~~At idle the solver's port mass flows (`mdot_exh`, `mdot_int`) zig-zag at
  its 1° step's Nyquist (FINDING-028), in the shipped grids' idle rows too.~~
  Since P09 (ADR-019) the port flow is semi-implicit wherever an explicit
  step would overshoot (`cycle.implicit_flow`), and the zig-zag is gone:
  crdi15's idle ripple dropped from 0.80 to 0.022. The grids lose it at
  P09's rebuild.
  The sound still averages them over 2° (`acoustics.smooth_port_flow`, in
  `render` and `LiveSynth.set_sources`) before differentiating; anything new
  that differentiates a port flow should too. A test still checks that the
  averaging removes a synthetic zig-zag. The source balance and each
  mic's loudness are `SOURCE_BALANCE` and `MIC_TRIM` (ADR-018) in hashed
  `acoustics.py`: mirror them in `web/physics/src/audio/synth.ts`,
  regenerate `--only sound`, and re-stamp the grids.
- e2e touch via CDP: a `touchMove` that leaves a finger out does **not**
  lift it, and `touchEnd` lifts every finger. `at(sel, h)` is the fraction
  *up* the pedal, so 0.95 is full throttle. The stall test leaves `/enjoy`
  in Manual.
- Since Phase 7 step 7, Drive's gearbox is kept per browser
  (`DriveEnv.gearbox`, localStorage), like the place and the fuel, and
  `/enjoy` starts in Manual when it is `manual`. Opening a project also
  sets `/spec`'s edits. One e2e browser carries all of it from page to
  page; clear `localStorage` before a check that assumes the defaults.

## Decisions

`DECISIONS.md` holds ADR-001 to ADR-020 (ADR-013: the personas are review
lenses; ADR-014: custom engines, drivable; ADR-015: Phase 6's scope, staged;
ADR-016: Phase 7's six decisions, and v2 as a separate list; ADR-017: P08, the automatic shifts by the fuel map; ADR-018: P10, the sound's
balance and loudness, and FINDING-028 hidden in the synth; ADR-019: P09, the
port flow and the knock fixed, the knock at altitude and on a cold start; ADR-020: P13, a
native build in one command and converged solves that stop once settled). Don't reopen one without a
measured reason. The ones most easily undone by accident: the Python solver
runs **unmodified** under Pyodide (ADR-001); audio is a TypeScript
AudioWorklet with no `SharedArrayBuffer`, so no COOP/COEP headers, so GitHub
Pages hosting works (ADR-003); Angular pinned, standalone, signals, OnPush,
no NgRx (ADR-005). ADR-006 is superseded by ADR-011 (live friction from
the cells' traces, a warm/cold grid pair).
