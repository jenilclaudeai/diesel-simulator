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
cd web/physics && npm ci && npm test            # TypeScript ports vs fixtures (ADR-004)
cd tools/pyodide && npm ci && npm run suite     # the same suite under Pyodide
cd web/solver  && npm ci && npm run test:fast   # cache tests, seconds
cd web/solver  && npm test                      # + round trip through a real worker
cd web/app     && npm test -- --watch=false     # unit tests (vitest)
cd web/app     && npm run build:pages           # NEVER plain `build`: blank page on Pages
cd web/app     && npm run e2e                   # browser checks
```
Angular needs Node ≥ 22.22.3. If npm 10 crashes resolving Angular's peer
deps, use `npx -y npm@11 install`. The project supports Python 3.10 —
3.12-only syntax has slipped in before.

## The pattern to watch for

Five of the first six findings had one shape: **a mechanism fully built,
correctly wired, and fed a quantity that was zero or pinned against a clamp,
raising no error.** `tools/audit_dead_signals.py` exists to catch the next.

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
- The solver needs **numpy only**. Never import `scipy` at module level in
  `dieselsim/` (a test enforces it). `batch.py` imports `multiprocessing`,
  which Pyodide lacks.
- Full-load dyno pulls end in negative torque: above rated speed the
  governor pulls fuel to 4% at `max_rpm`. That is intended.
- WebCrypto needs a secure context: over plain http on a LAN address the
  grid cache switches itself off by design.

## Decisions

`DECISIONS.md` holds ADR-001 to ADR-010. Don't reopen one without a
measured reason. The ones most easily undone by accident: the Python solver
runs **unmodified** under Pyodide (ADR-001); audio is a TypeScript
AudioWorklet with no `SharedArrayBuffer`, so no COOP/COEP headers, so GitHub
Pages hosting works (ADR-003); Angular pinned, standalone, signals, OnPush,
no NgRx (ADR-005). ADR-006 is on hold pending reassessment.
