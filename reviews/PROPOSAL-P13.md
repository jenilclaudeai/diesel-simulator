# PROPOSAL — P13: build a drivable grid faster, front end unchanged

**Date:** 2026-10-15 (session 9). **Status:** measured; **two questions for the owner** (end).
**The sheet's P13** (priority 1, "Into Consideration"): "Make the building
drivable grid faster: can we make drivable grid faster with script. Let
the front end stay same for now."
**Lenses:** PM, LEAD, PHY1, PHY2, SW1, QA2
**Builds on** `reviews/PROPOSAL-grid-build.md` (2026-10-05; deferred by the
owner until v1). Its numbers predate P09's solver, so everything below is
re-measured on today's code (`feat/p09-knock` at `8d22068`, the FINDING-030
grids). Scripts are scratch, in the session's job directory: `p13_settle.py`,
`p13_rules.py`, `p13_wxchain.py`, `slap_check.py`, `p13_profile.py`,
`c_hoist.py`.

---

## Where the time goes today

**A drivable grid is now mostly its weather table.** The app's browser
build includes it by default (`solver.service.ts`: `weather: opts.weather
?? true`). So a custom engine is 104 pieces (8 row calibrations + 96 cells)
**plus 390 weather solves** (48 warm cells × 8 airs + 6 checks). P09's
rebuild on this M2 (6 workers), per grid:

| | cells | weather | total, native | browser (× 1.45–1.86, bench/README) |
|---|---|---|---|---|
| crdi15 | 958 s | 2,532 s | **58 min** | ~1.4–1.8 h |
| the ten grids | 231–1,509 s | 853–4,550 s | 18–101 min | ~0.4–3.1 h |

Weather is about **73%**. Within each solve, a profile of one converged
crdi15 cell shows the same picture as on 2026-10-05: all of it is the
pure-Python crank loop. `cycle.run`'s own body is 25%, the `thermo.py`
helpers about 70% (30.8 M calls to `_int_cp_*`, 39 M `math.exp`), and
200 cycles × 720 steps. There is no single hotspot to remove.

## What was measured

### B. Stop a converged solve once it has settled

Every converged solve runs 200 real-time cycles and checks settling only at
the end. A real-time solve capped at N cycles is exactly what an early stop
at N gives, so each stopping rule was measured exactly: solve 200 cycles,
find the rule's stop, re-solve capped there, and compare **every field the
grid stores** (perf, the knock, the pressure trace, the six source
waveforms). That was 108 solves: crdi15, hatch15 and truck127 (the slowest,
with the most unsettled cells); rows 0/2/4/6 × loads 0.2/0.6/1.0; warm,
cold and the hardest weather air (58 kPa / −20 °C).

**Settling:** median at cycle 61–77, but up to 198. 4 of 108 never settle
(FINDING-013's limit cycle). **31 pass the test, then fail it again.**

**The naive rule (stop at the first pass + a margin) is unsafe.** At a
margin of 10, one cell's torque was off by **10.8% of full-load torque**.
Its truncated tail was failing at the stop, so it fell into the
period-averaging meant for limit cycles. Excluding those flips, the error
was ≤ 0.24%. EGR, NOx and soot moved up to 14–22%: the test watches only
work and boost, and the EGR loop settles more slowly.

**Rules that stop only after the test has held for H cycles** (they cannot
flip, by construction):

| rule | speed-up | stopped early | settled-flag flips | torque, worst (% of full load) | EGR | T_exh | NOx |
|---|---|---|---|---|---|---|---|
| R1: work + boost, H = 10 | ×2.24 | 98/108 | 0 | 0.19% | 0.92 pts | 3.1 K | 9.9% |
| **R2: + intake EGR + turbo speed, H = 10** | **×1.91** | 90/108 | **0** | **0.019%** | **0.04 pts** | **0.1 K** | **0.52%** |
| R3: as R2, H = 20 | ×1.77 | 89/108 | 0 | 0.009% | 0.00 pts | 0.0 K | 0.16% |

**Correction (2026-10-16), R2's rebuild:** the sample above had cold thin air
only. In hot thin air at high load R2 stops on a slow creep: the rebuilt
weather tables differed by up to 0.49% of peak torque, and the worst pieces
were 0.50% (truck127) and 0.41% (v8hd) from 400 cycles where 200 cycles is
0.01% / 0.03%. "Torque within 0.019%" was too general (*my miss*). **R5 replaces
it** (ADR-020): the same keys plus the net IMEP, at a tolerance of 2e-4. On
180 screening solves and 108 held out (400 cycles each), no R5 stop is worse
than the 200-cycle answer by more than 0.017% of peak torque beyond that
answer's own error; ×1.65-1.71 fewer cycles. The text below is as written.

For scale, 200 cycles already sits up to 0.36% from 400 (FINDING-013). R2's
other fields: boost 0.06%, AFR 0.07%, turbo 0.08%, pressure trace 0.05%,
exhaust-flow source 0.83%. One exception: the **slap** waveform differs by
15.6% of its peak in one of 90 stopped cells (crdi15 4057 rpm / 20% warm,
stop 183). It has the same 11 pulses, with one side-force crossing moved by
one 1° crank step. Slap events sit on the grid's samples where the side
force changes sign, so this is discreteness, not convergence; every other
cell is within 0.01%.

**Positives:** about ×1.9 on every converged solve: the browser build, the
native rebuild (about 10 h → about 5 h for the ten grids), the weather
table, the test suite's converged tests, CI's Pyodide job (now 57.5 of its
60 min). Front end untouched. ADR-001 holds (the same Python).
**Costs:** a solver change (`engine.py` / `cycle.py`, hashed), so the grid
hash moves and every grid rebuilds once (about 5 h with B itself). Golden
values move within the errors above. A physics review, and QA2's acceptance
over all ten rebuilt grids against today's.

### C. Hoist two constants in `thermo.py`

`u_mix` / `h_mix` recompute `_int_cp_air(T_REF)` and `_int_cp_burned(T_REF)`
on every call. Hoisted, a converged crdi15 cell: **×1.083, `live_cell`'s
JSON byte-identical** (best of 2: 20.30 → 18.74 s). It was ×1.107 before
P09. **Positives:** free, provably no physics change. **Cost:** `thermo.py`
is hashed, so the grids must be re-stamped (`restamp_grids.py`, proof as
CLAUDE.md asks) or rebuilt with B.

### Not worth it (measured)

- **Warm-starting each weather solve from its standard-air cell** (chaining):
  the median settle moves from 77 to 60 cycles, ×1.26 on top of B. But it
  adds path dependence (torque up to 0.15%, 2 settled-flag flips in 48),
  and it chains pieces that are independent today, which costs the
  browser's parallelism and resumability.
- **More workers on this Mac:** an M2 has 4 performance and 4 efficiency
  cores, and 6 workers already use every performance core. The cap
  (`min(6, cores)` native, `cores − 1` up to 6 in the browser) matters
  only on 10+ core machines. It is cheap to lift but unmeasured there.
- **Rewriting the loop (WASM, TypeScript, vectorised numpy):** as on
  2026-10-05. It reverses ADR-001 and means a second solver to keep in
  step.

### N. "With a script": a native build for a custom engine

The pieces exist (ADR-014): `tools/build_live_grids.py --engine my.json`,
then `--weather out/grids/<key>.json`, then the app's **Import grid**. The
front end is untouched. Natively it is ×1.45–1.86 faster than the browser
(bench/README), and it isn't throttled by a browser tab. What's missing is
the one-command form a non-developer can run. `bench/run_bench.sh` already
shows the pattern: it finds Python 3.10+, installs numpy into its own venv,
runs, and prints where the result is.
- **Positives:** no solver change, no rebuild, no hash. A day's work (a
  script for macOS/Linux and one for Windows, plus a README). Combined
  with B, a custom engine natively takes ~30 min instead of 1.4–1.8 h in a
  browser.
- **Costs:** the user needs Python and a terminal. The browser build stays
  as slow as today unless B lands too.

## Options

| | what | speed-up | solver change / rebuild | front end |
|---|---|---|---|---|
| **B** | stop converged solves once settled (rule R2) | ×1.9 everywhere | yes / one rebuild (~5 h) | unchanged |
| **C** | hoist the two constants | ×1.08, bit-identical | re-stamp only | unchanged |
| **N** | one-command native build for a custom engine | ×1.45–1.86 over the browser | none | unchanged (Import grid) |
| B + C | | ×2.06 | one rebuild | unchanged |
| B + C + N | | custom engine ~28 min natively (today 58 min natively, 1.4–1.8 h in a browser) | one rebuild | unchanged |

Still open from 2026-10-05, and not P13 (each changes the front end or a
decision): a coarser custom grid (D, reopens ADR-014's shape); presets-only
weather (half the weather solves, reopens A3); prebuilt or derived grids for
phones (E).

## Lens review

- **PM:** N is the quickest win for "with a script" and touches nothing.
  B is the real speed-up for everyone. Land it with C in one rebuild, and
  not mixed into P09's PR.
- **LEAD:** B and C keep ADR-001 and ADR-005 (front end unchanged). B
  changes a hashed file, so one rebuild. Sequence it after #131 merges.
- **PHY1/PHY2:** R2, not R1. R1's NOx and EGR errors are real (the EGR
  loop is slower than work and boost). R2's worst torque error is 20×
  under what 200 cycles already carries. The cells that never settle are
  unchanged.
- **SW1:** B is ~30 lines in `cycle.run` (a running count of consecutive
  passes; stop when it reaches H). C is 4 lines. N is two scripts and a
  README.
- **QA2:** B's acceptance: all ten rebuilt grids against today's, every
  cell, with torque ≤ 0.05% of full load, EGR ≤ 0.1 pts, T_exh ≤ 1 K, NOx
  ≤ 1%, the same unsettled cells; slap judged by its pulses, not
  pointwise. Mutants: H = 0; EGR left out of the test; a stop while
  failing.

## Recommendation

1. **N now** (no solver change). It is the literal "with a script".
2. **B (R2) + C** as one solver change with one rebuild, after #131 merges.
3. Lift the worker cap on many-core machines, measured on one first.

## Questions for the owner

1. **Which do you mean by "with a script"?** (a) N: a script you run on
   your machine for a custom engine, then Import grid; (b) B + C: the
   build itself made faster, in the browser too; (c) both (recommended).
2. **If B: is rule R2 acceptable?** Each grid would stop at about half its
   cycles, with the errors above (torque ≤ 0.02% of full load, EGR ≤ 0.04
   points, NOx ≤ 0.5%). Golden values move within those, and every grid
   rebuilds once.
