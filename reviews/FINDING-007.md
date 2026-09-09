# FINDING-007 — audit of known bug #8, unknown-provenance code in `engine.py`

**Status:** audited; one real bug found and fixed, two items cleared
**Closes:** known bug #8

Known bug #8 flagged three things in `engine.py` and `config.py` as code the
author did not write and did not trust. Each is resolved below.

---

## 1. The AFR-headroom block in `fuel_for_torque` — **keep, but it hid a bug**

The block solves once at the raw fuel limit, measures the resulting AFR, and
raises the fuelling ceiling by the measured headroom:

```
op0      = self.operating_point(rpm, fuel_mg=f_max, n_cycles=self.cal_cycles)
headroom = clip(op0.cycle.afr / spec.afr_limit, 1.0, 2.2)
f_ceiling = f_max * headroom
```

**The reasoning is sound and the comment is accurate.** `fuel_limit_raw()`
builds its pressure ratio from an open-loop rpm schedule (known bug #2), so on
a well-matched turbo it leaves air unused — AFR comes out above the smoke limit
and the engine is fuel-starved for no reason. Measuring rather than assuming is
the right correction, and closing the loop here is safe precisely because the
torque cap bounds the result.

On `crdi15` at 1800 rpm the effect is real: measured AFR 23.32 against an
`afr_limit` of 17.5, giving headroom 1.333 and lifting the ceiling from 55.97
to 74.59 mg. Torque at the raw limit is 255.2 N·m; at the ceiling, 318.0 N·m.

Verdict: keep. This is a partial, bounded answer to bug #2, applied only during
calibration.

### But the cache and the calibration clipped against different ceilings

The calibration raised its own ceiling to `f_ceiling`. The cached path clipped
against `fuel_limit_raw`. So `fuel_for_torque` returned a **different answer
depending on whether its cache was warm**:

| `crdi15`, 1800 rpm, target 286.6 N·m | fuel |
|---|---|
| first call (cold cache, calibration path) | 61.31 mg |
| second call (warm cache) | 55.97 mg |
| divergence | **−8.71%** |

55.9677 mg is exactly `fuel_limit_raw(1800)` — the cached path was silently
clipping to a ceiling the calibration had already decided was too low.

**Consequences.** The first call after construction or `reset_torque_cal()`
disagrees with every subsequent call. Any grid or curve built by calling
`fuel_for_torque` across speeds carries one calibration for its first point at
each cached key and another afterwards. It compounds known bug #5 (path
dependence) and plausibly contributes to known bug #3, the ±3% torque-limiter
residual.

**Fixed** by storing the ceiling alongside the fit — `(a, b, f_cap)` — so both
paths clip identically. Divergence is now 0.000%.

---

## 2. The duplicate `self.cal_cycles` — **dead code, removed**

```
self.cal_cycles = 10     # comment: 6 is unconverged, use more
self.cal_cycles = 8      # comment: calibrate at the convergence you judge at
```

Two assignments, two comments arguing opposite cases, the second silently
winning. The first was dead.

**Kept 8.** It is the value that was actually in force, so every number in the
validation table was produced with it, and its argument is the better one: a
limiter fitted at a different convergence than it is evaluated at carries that
bias into the fit.

Recorded in the code that this interacts with known bug #1 — `n_cycles=6`
drifts 10.8%, and 8 is not fully converged either.

---

## 3. `compact_crdi_i4` / the `crdi_1p5` key — **legitimate, keep**

Not corrupt and not a fragment. It is a complete, coherent engine that differs
from `crdi15` in 41 numeric fields, all small and all plausible: slightly
smaller turbine area, tighter bearings, lower alternator load, 1.48 L against
1.50 L.

Solved at 2000 rpm full load:

| preset | name | disp | torque | power | BSFC | p_max |
|---|---|---|---|---|---|---|
| `crdi15` | CRDi-I4 1.5L 115ps | 1.50 L | 230.5 N·m | 48.3 kW | 229 | 145 bar |
| `crdi_1p5` | CRDi-I4 1.5L | 1.48 L | 213.0 N·m | 44.6 kW | 233 | 140 bar |

Both sane. It reads as an earlier or alternate tune of the same engine.

One asymmetry worth knowing: **`crdi15` has `torque_limit = 0.0` while
`crdi_1p5` has `214.0`.** So the two behave differently under the rating cap,
which is a real difference in behaviour rather than a spec detail.

Verdict: keep, but it needs a docstring saying what it is and how it differs,
or a future reader will flag it as unknown again. `PROJECT_CONTEXT.md` §2.2
lists four presets and does not mention it.

---

## Caveat

"Provenance" cannot be established from the code — this audit assesses whether
each item is *correct and coherent*, not who wrote it. Two of three are fine on
their merits. The third concealed a real bug that had nothing to do with
provenance and everything to do with two code paths clipping against different
bounds.
