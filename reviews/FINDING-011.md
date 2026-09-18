# FINDING-011 — the real-time grid is the least accurate part of the package

**Opened by:** measuring known bug #5 (path dependence), which led to the grid
build in `play.py`
**Lens:** PHY1, QA2
**Status:** measured, not fixed — the fix has a cost that needs a decision
**Relevant to:** PLAN Phase 2, which ports this grid to the browser

---

## Bug #5 is real, and larger than "mild"

`PROJECT_CONTEXT.md` calls `operating_point` "mildly path-dependent". Measured
at `crdi15` 1800 rpm load 0.6, reaching the same point four ways:

| approach | torque | boost | turbo rpm |
|---|---|---|---|
| cold start | 124.391 | 1.8027 | 124,307 |
| from light load | 125.617 | 1.8191 | 125,719 |
| from full load | 125.987 | 1.8490 | 127,950 |
| from high rpm | 121.114 | 1.7790 | 122,437 |

**Torque spread 3.92%**, driven by turbo shaft state persisting across calls.
That is larger than known bug #3's ±3% limiter residual, and it is not mild
when the validation table quotes four significant figures.

## Where it compounds: the grid build

`play.py:210` builds the real-time grid with **one engine instance, iterated
sequentially, rpm-outer and load-inner, at `n_cycles=6`**.

Both known defects apply at once:

- `n_cycles=6` drifts 10.8% against 12 (bug #1, measured earlier this session)
- sequential reuse carries 3.92% path dependence (bug #5, above)
- the iteration order means each rpm row begins from the previous row's
  *highest* load, so the bias is systematic rather than random

### Measured grid error

Grid-style solve against a clean reference (fresh engine, `n_cycles=9`):

| point | grid | clean | error |
|---|---|---|---|
| 1200 / 0.2 | 35.70 | 35.57 | +0.36% |
| 1200 / 0.6 | 104.35 | 104.73 | −0.36% |
| 1200 / 1.0 | 190.98 | 198.10 | −3.60% |
| 1800 / 0.2 | 40.64 | 41.01 | −0.89% |
| 1800 / 0.6 | 116.30 | 124.39 | **−6.51%** |
| 1800 / 1.0 | 234.10 | 226.33 | +3.43% |
| 2400 / 0.2 | 38.66 | 38.20 | +1.20% |
| 2400 / 0.6 | 112.09 | 124.63 | **−10.06%** |
| 2400 / 1.0 | 230.58 | 233.45 | −1.23% |

**Mean −1.96%, worst −10.06%, spread 13.5 percentage points.**

The errors are not a uniform offset — they change sign across the map, so the
*shape* of the torque surface is distorted, not just its level. Mid-load is
worst, which is where a car spends most of its time.

## Why this matters more than it looks

Everything the user actually experiences in `play.py` is interpolated from
this grid. The carefully-solved physics is not what reaches the driver; a
6-cycle, path-contaminated sample of it is. And PLAN Phase 2 ports **this
grid** to the browser, so the defect propagates unless fixed first.

## Why it is not simply fixable

`batch.solve_points` avoids path dependence and parallelises, and `play.py`
already uses it for `--curve`. But `PointResult` is a flat scalar summary with
**no traces**, and the grid build needs `snd.build_sources(op)`, which requires
the full `OperatingPoint`. So batch cannot be dropped in as-is.

## Options

1. **Raise `n_cycles` to 9 and keep sequential.** One-line change. Removes the
   larger error term, leaves the 3.92%. Build time roughly ×1.5 on an
   already ~2-minute operation.
2. **Fresh engine per point.** Removes path dependence, loses warm-start, so
   each solve costs more. Combined with (1), build time perhaps ×2–3.
3. **Extend `batch` to build the sound sources in the worker** and return the
   compact float32 arrays the grid keeps. Avoids pickling traces entirely,
   fixes both defects, and parallelises — so despite more cycles the build
   could end up *faster* than today. Most work, best outcome.
4. **Do nothing and document the grid's accuracy.**

**Recommendation: 3, before Phase 2.** It is the only option that improves
accuracy and build time together, and the Phase 2 port has to touch this code
anyway. Doing it now means porting something correct rather than porting a
known-wrong grid and fixing it twice.

If 3 is too much, **1 is worth doing regardless** — it is one line and removes
the dominant term.

## Caveat

Nine points, one preset, one grid geometry. The 13.5 pp spread is specific to
this iteration order; a different order would redistribute it, not remove it.
Build-time multipliers are estimates, not measurements — this container's CPU
is ~7× slower than developer hardware, so timing here would mislead.
