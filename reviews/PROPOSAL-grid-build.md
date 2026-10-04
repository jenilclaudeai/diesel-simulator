# PROPOSAL — custom-engine grids that people will wait for

**Date:** 2026-10-05 (session 6). **For decision by the owner.**
**Lenses:** PM, LEAD, PHY1, PHY2, SW1, QA2, USR1/2 (advisory)
**Why now:** the owner measured, on real devices, a grid build of 5+ min on
a Samsung phone, and a drivable-grid ETA of **2–3+ h on an M2 MacBook**.
ADR-014 planned ~26 min on 4 workers and "hours on a phone". Nobody will
wait for that. This is the measured reason ADR-014 asks for before it is
revisited.

---

## What was measured (2026-10-05)

### 1. The ETA lies early, by up to 20×

`live-grid-build.ts` reports `elapsed / pieces finished × pieces left`. It
treats all 104 pieces as equal, but the first to finish are the 8 row
calibrations, each ~4× a cell (199 s against ~50 s under Pyodide,
ADR-014). Replaying the scheduler and the formula with those costs
(`$CLAUDE_JOB_DIR/tmp/eta_sim.py`, ±15% jitter):

| 6 workers | app's ETA | true time left |
|---|---|---|
| first piece, 3.0 min in | 304 min | 15 min |
| 6 pieces, 3.7 min | 60 min | 14 min |
| 20 pieces, 6.4 min | 27 min | 12 min |
| 60 pieces, 12 min | 9 min | 6 min |

The build itself takes ~18 min (21.5 min measured in Chrome, part 17). So
the owner's "2–3+ h" on the M2 is most likely the first minutes' ETA, not
the real duration. *Not yet confirmed: which browser, and whether that
build was left to finish.* Either way it's a defect: a user who reads
"3 hours" leaves.

### 2. Where the time goes

`cProfile` of one `hatch15` row calibration and one converged cell at
2971 rpm, natively: **all of it is the pure-Python crank-step loop.**
`cycle.py:run` and the scalar `thermo.py` helpers take 77 M calls each to
`_int_cp_air` / `_int_cp_burned` per row, and 190 M `math.exp`. There's
no single hotspot to remove; only the loop's size.

### 3. Most of the 200 real-time cycles confirm an answer already settled

Converged mode always runs `CONVERGED_CYCLES = 200` at real time and only
*checks* settling at the end. Per-cycle means for 11 cells and 3 row
calibrations (`hatch15` at 1343 and 3514 rpm, `truck127` at 1020), with the
first cycle at which the existing test (`_tail_converged`: work and boost
within 0.1% over 10 cycles) passes:

| | settled at cycle | at that point, off the 200-cycle value by |
|---|---|---|
| 11 cells, fresh engines | 25, 32, 37, 48, 64, 69, 79, 101, 134; **2 never** (both 60% load at low rpm, FINDING-013's VGT/EGR limit cycle) | work ≤ 0.13%, boost ≤ 0.25% |
| 3 rows, 11 calibration solves | 13–92 | work ≤ 0.009% |
| the same cells, each starting from its neighbour's settled state | 0–9 cycles sooner | adds path dependence up to 0.33% |

- **Stopping when settled cuts the work by ~2.5×**, not more: rows ~4×,
  cells ~2.2× on average, while the ones that never settle still need all
  200.
- **The early answer is not free.** At 3514 rpm part load it sits up to
  0.25% (boost) from cycle 200. That's the size of the error 200 cycles
  already carries against 400 (0.36% worst, FINDING-013). A stopping rule
  needs a margin (a tighter test, or extra cycles after it passes), so
  expect 1.8–2.5×.
- **Chaining cells is not worth it:** a few cycles saved, path dependence
  back (bug #5), and less parallelism.

### 4. Not measured yet

- A phone's per-core Pyodide speed. ADR-014 said "hours"; the owner's 5+ min
  is a different build (which page is still to be confirmed).
- The pure-Python speedups below.

---

## Options

Each comes with what it costs **and** what it gives.

### A. An honest ETA *(small, independent; recommended now)*
Weight pieces by cost (a row ≈ 4 cells), report a range until a few cells
have finished, and give an estimate **before** the build starts.
- **Gives:** the number a user decides on is right, within ~1.5× from the
  first minute. It also tells a phone user up front that this takes hours
  there.
- **Costs:** a day; UI and `web/solver` only, with no physics touched.
  Testable: replay the scheduler as above, and hold the ETA's ratio to the
  true time left.

### B. Stop converged solves once settled, with a margin *(recommended)*
`n_cycles = 200` becomes a ceiling. A solve stops after the tail test passes
plus a margin, chosen so every cell stays within today's accuracy.
- **Gives:** ~1.8–2.5× on every build, native too, so roster rebuilds
  drop from ~2 h to under 1 h.
- **Costs:** a solver change. It changes the grid hash, so every grid
  rebuilds and golden values move; it needs a physics review before
  merge. The margin has to be **proved** against the shipped grids over
  all 10 of them, not asserted. The cells that never settle are
  unchanged.

### C. Faster pure Python in `thermo.py` *(recommended, measure first)*
Hoist the constant `_int_cp_*(T_REF)` out of `u_mix` / `h_mix`
(bit-identical), and start `T_from_u`'s Newton from the last temperature
instead of 800 K (changes results within its 1e-6 K tolerance).
- **Gives:** an estimated 10–30%, everywhere: Dyno, Grid, every build,
  every test. Still the same Python under Pyodide, so ADR-001 holds.
- **Costs:** small, but it's a solver change: rebuild once, together with
  B.

### D. A coarser grid for custom engines
For example 6 rpm × 4 loads: 48 cells instead of 96, ~2× less work.
- **Gives:** with A–C, a laptop builds in roughly 3–5 min.
- **Costs:** reopens the owner's choice in ADR-014 (one 8×6 shape), so two
  shapes to support and a coarser map to interpolate. PHY1/PHY2: the map
  must stay smooth enough at the load edges (idle and full load), which
  needs checking.

### E. Phones don't build: they get prebuilt or derived grids *(recommended direction, owner's choice of form)*
Even with A–D, a phone is measured in tens of minutes, an estimate since
its speed is unmeasured. Two forms:
- **E1. A larger prebuilt library.** Many well-known real engines, each
  built natively (or by CI) and hosted on Pages like today's roster.
  - **Gives:** instant on any phone, exact, and driven with the full
    physics.
  - **Costs:** a vehicle, a tuning pass and a grid per engine (~15 min of
    machine time, plus tuning), and ~1 MB gzip each on Pages.
- **E2. A derived "approximate" grid**, made instantly from the nearest
  roster engine with the same cylinder count and aspiration. Torque and
  fuel are scaled to the custom engine's brochure, and the rpm axis is
  stretched to its idle–max range. It's labelled approximate in the UI, as
  PLAN's principle requires, and the exact build is offered on a laptop.
  - **Gives:** a custom engine on a phone in seconds.
  - **Costs:** a new model to defend (PHY1: BMEP and piston-speed scaling
    is defensible for similar engines, not across architectures), and
    the sound only roughly that engine's.

### F. Not recommended
- **Rewriting the loop in TypeScript or WASM:** reverses ADR-001, the
  solver being the product; it would mean months and a second solver to
  keep in step.
- **A build server:** v1 has no backend (PLAN); it would cost hosting,
  and break the "works offline from Pages" property.
- **Chaining cells:** measured above, not worth it.

---

## Lens review

- **PM:** A is a day and fixes the worst of the experience now. B+C is
  one solver change with one rebuild; don't split it into two rebuilds.
  E is the real answer for phones, and E1 is a content job that scales
  with effort rather than research.
- **LEAD:** B and C keep ADR-001; D reopens part of ADR-014, and E2 would
  need its own ADR.
- **PHY1/PHY2:** B is defensible only with a margin, proved per cell
  against the 200-cycle grids. E2's scaling holds within an
  architecture, not across one.
- **SW1:** A is contained in `live-grid-build.ts` and the Dyno page.
- **QA2:** B's acceptance: every cell of all 10 rebuilt grids within the
  stated margin of the shipped one, and the same unsettled count. A's: the
  replayed ETA within 1.5× of the true time left after the first 5% of
  pieces.
- **USR1/2 (advisory):** a phone user wants to pick an engine and drive.
  Waiting minutes is acceptable on a laptop with an honest bar; on a
  phone, any wait for a custom engine is a reason to stop.

---

## Recommendation

1. **Now:** A (honest ETA, and a phone told up front).
2. **Next:** B + C as one solver change, with one rebuild and one physics
   review: about 2–3× on every build.
3. **For phones:** E. **E1 if you want exact engines** (the roster grows
   to cover what people want to drive), **E2 if you want any custom
   engine on a phone now**, labelled approximate. Both can come, E1
   first.
4. **D only if** a laptop build is still too slow after A–C.

**For the owner to decide:** the order above; E1, E2 or both; and whether
D is acceptable.
