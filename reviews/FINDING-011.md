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

---

## Resolution — option 3, with one design change

Implemented the recommended option: the grid is now solved per cell in
workers, at `GRID_CYCLES = 9`, via the existing `--jobs` flag. `CACHE_VERSION`
bumped 5 → 6 so stale grids rebuild.

### Why one fresh engine per cell, not per row

The obvious cheaper design was one engine per rpm row with
`warm_start=False`, which would keep `fuel_for_torque`'s per-rpm calibration
cache. **Measured, that does not work.** After driving the engine through
high-rpm points, a `warm_start=False` solve at 1800 rpm / 0.6 is still
**−3.89%** off the fresh-engine value.

The reason is the real root cause of known bug #5. `Turbocharger` holds
**shaft speed (`n_rpm`) and VGT position (`vgt_pos`) as instance state**,
mutated during every solve at `turbo.py:171` and `:195`. `warm_start=False`
resets only the cycle's gas state (`state0`); the turbo carries on at whatever
speed the previous call left it. So the flag does not mean what its name says.

It is also **never called anywhere** in the package — dead API that promises
isolation it cannot deliver. Left unchanged here to keep this fix narrow, but
worth fixing before Phase 2's `SolverPort` reaches for it expecting a clean
solve.

A fresh engine per cell is therefore the only clean definition, and it is
exactly how the regression suite's golden values are produced. Parallel
workers pay for the lost calibration cache.

### Other choices

- Workers receive the **spec object**, not a preset name, so
  `--torque-limit` / `--power-limit` overrides reach them and nothing depends
  on the preset registry being rebuilt inside a spawned process.
- `spawn` context, matching `batch.py`.
- `jobs == 1` runs in-process with no pool — same fresh-engine-per-cell
  semantics, no spawn overhead, and usable anywhere multiprocessing is not
  (which includes Pyodide).

### Verified

**Correctness.** 3×3 `crdi15` grid built with the new code against a
fresh-engine `n_cycles=9` reference:

| rpm | load | grid | reference | diff |
|---|---|---|---|---|
| 800 | 0.0 | −17.631 | −17.631 | 0.0000% |
| 800 | 0.5 | 42.802 | 42.802 | 0.0000% |
| 800 | 1.0 | 87.276 | 87.276 | 0.0000% |
| 2700 | 0.0 | −15.007 | −15.007 | 0.0000% |
| 2700 | 0.5 | 102.490 | 102.490 | 0.0000% |
| 2700 | 1.0 | 229.907 | 229.907 | 0.0000% |
| 4600 | 0.0 | −26.458 | −26.458 | 0.0000% |
| 4600 | 0.5 | −16.726 | −16.726 | 0.0000% |
| 4600 | 1.0 | −25.129 | −25.129 | 0.0000% |

**Exact on every cell**, where the old build was off by up to −10.06%.

**Parallel path.** A 2×2 grid built with `jobs=2` through the `spawn` pool is
bit-identical to `jobs=1` in-process — both performance values and crank-angle
sources. Pickling and worker construction work.

**Speed — not measured.** This container has one core and runs ~7× slower than
developer hardware: 9 cells took 52 s, about 5.8 s each. A default 8×6 grid is
48 cells. On a multi-core machine the build should end up comparable to or
faster than the old ~2 minutes despite 9 cycles instead of 6 and no shared
calibration, but that is an estimate and needs timing on real hardware.

### Observation, not a finding

The top rpm row (`max_rpm` = 4600) is negative torque at every load. That is
the governor: above rated, droop pulls `fuel_limit` toward zero, so "full load"
there is almost no fuel and the engine is motoring. Physically reasonable, but
it means the grid's highest row describes a governed-out engine, which matters
for how the real-time loop interpolates near redline.
