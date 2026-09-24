# FINDING-013 — bug #3 understated: the limiter is fitted with EGR on and judged with it off, and `crdi15` never converges near 1650 rpm

**Opened by:** known bug #3, "torque limiter residual error ±3% across the
plateau (was 11%). Symptom of #1, not a separate bug"; re-measure after
FINDING-007, listed as next action 6 in `STATUS.md`
**Lens:** PHY1 (lead), PHY2, QA2
**Status:** measured, not fixed — every fix is a physics decision, see Options
**Reproduce:** `python3 tools/diag_torque_limiter.py` (≈2 min on 6 cores), then
`--egr-sweep` and `--converge`

---

## The residual is not ±3%

Only `crdi15` and `crdi_1p5` carry a rating cap. Fresh engine per point,
`operating_point(rpm, load=1, n_cycles=N)`, error against `torque_cap(rpm)`.
`n_cycles=9` is what the web app and the grid use; the limiter calibrates at 8.

| preset | range at n=8 | range at n=9 | range at n=12 |
|---|---|---|---|
| `crdi15` | −0.05 … **+11.28%** | **−4.31 … +6.84%** | −5.01 … +8.51% |
| `crdi_1p5` | −4.89 … +5.68% | −7.36 … +5.54% | −6.43 … +5.47% |

Two `crdi_1p5` points (1250, 1650 rpm) are **air-limited** — the limiter hit its
own AFR ceiling because the cap is out of reach — so their shortfall is the
engine running out of air, not limiter error. Excluding them, `crdi_1p5` runs
−0.94 … +5.54% at n=9.

The web app's e2e run of 2026-09-24 shows it directly: the `crdi15` cap is
220.6 N·m flat from 1500 to 2750 rpm, and the page reports 234.9 N·m at 2050 and
235.4 at 2500.

The table is not one error but three.

## 1. The fit is made under different schedules than it is judged under

`fuel_for_torque` calibrates by calling `operating_point(rpm, fuel_mg=f)` with
`_calibrating` set, so `fuel_limit()` returns `fuel_limit_raw()` and every
calibration solve sees

```
load_est = f / fuel_limit_raw(rpm)
```

The EGR, boost-target and SOI schedules are all functions of `load_est`. Once
calibrated, `fuel_limit()` returns the calibrated fuel itself, so the solve that
is actually reported always has `load_est = 1` — full-load schedules, **EGR
off**. Whenever the cap needs less fuel than the raw smoke limit
(`load_cal < 1`), the fit is made with part-load schedules and then applied with
full-load ones.

Decomposed at 8 cycles on fresh engines, same fuel `F`, as a share of the cap:

| `crdi_1p5` rpm | `load_cal` | EGR cmd at cal | conditions bias | of which EGR |
|---|---|---|---|---|
| 1500–1800 | 1.12–1.40 | 0 | **+0.00** | +0.00 |
| 2050 | 0.926 | 0 | +0.23 | +0.00 |
| 2250 | 0.898 | 0.0095 | **+5.53** | +5.09 |
| 2500 | 0.817 | 0.117 | +4.16 | +4.01 |
| 2750 | 0.773 | 0.166 | +3.67 | +3.61 |
| 2900 | 0.750 | 0.187 | +3.41 | +3.42 |
| 3350 | 0.717 | 0.199 | +3.09 | +3.40 |
| 4000 | 0.722 | 0.149 | +1.84 | +2.17 |

The signature is clean on `crdi_1p5`, where the solver converges (8→9 cycle
change ≤ 0.6% everywhere but 1250 rpm):

- **exactly +0.00** in every row where `load_cal ≥ 1`, because each schedule
  clamps `min(1, load)`;
- **positive in every row where the EGR schedule switches on** (`load_cal` below
  ≈ 0.905, where `1.15·x^1.4 = 1`), and EGR alone is almost all of it;
- always the same sign: the evaluation, with EGR off, makes more torque than
  the fit expected, so the limiter **overshoots**.

This is a mechanism, not noise, and it is why `crdi_1p5`'s rating carries a
hand trim: `config.py` sets its cap "~3 % low against the nameplate: the
limiter's affine fit lands slightly high". The trim compensates for this bias
with one constant, but the bias is 0 to +5.5% depending on speed.

## 2. Any EGR command, however small, opens the valve to 25 %

`cycle.py:271`:

```python
A_egr = 0.25 * A_egr_max if egr_target > 0 else 0.0
```

then a slow integral controller trims the area toward the target burnt
fraction. `--egr-sweep`, `crdi15` 1650 rpm, limiter fuelling (48.85 mg), fresh
engine per row, delivered EGR fraction:

| EGR cmd | target | n=9 | n=20 | n=40 |
|---|---|---|---|---|
| 0.001 | 0.02% | **1.57%** | 0.02% | 0.01% |
| 0.020 | 0.44% | 1.97% | 0.14% | 0.54% |
| 0.100 | 2.20% | 7.15% | 0.77% | 3.95% |
| 0.200 | 4.40% | 11.06% | 7.23% | 7.84% |
| 0.300 | 6.60% | 13.78% | 2.79% | 3.37% |

At the grid's 9 cycles a 0.02% target delivers 1.57% — **78× over**. The
controller has not settled at 40 cycles, and delivered EGR is not monotonic in
the command. This matters well beyond the limiter: **every part-load grid
cell** runs the EGR schedule at 9 cycles. It is the dead-signal pattern's mirror
image — a near-zero input producing a large output.

(This row is also contaminated by item 3: `crdi15` at 1650 rpm does not
converge at all, so read the n=20 and n=40 columns as indicative only.)

## 3. `crdi15` does not converge near 1650 rpm at full-load fuelling

`--converge`, limiter fuelling, EGR forced off, fresh engine per row:

| n_cycles | `crdi15` torque | boost | `crdi_1p5` torque | boost |
|---|---|---|---|---|
| 6 | 224.37 | 2.048 | 216.30 | 1.896 |
| 8 | 237.86 | 2.299 | 211.40 | 1.820 |
| 9 | 219.51 | 2.136 | 210.46 | 1.806 |
| 10 | 224.97 | 2.755 | 209.97 | 1.799 |
| 12 | 211.92 | 2.419 | 209.58 | 1.793 |
| 16 | 237.70 | 2.292 | 209.44 | 1.791 |
| 20 | 211.55 | 2.427 | 209.43 | 1.791 |
| 25 | 219.23 | 2.150 | 209.43 | 1.791 |
| 30 | 223.78 | 2.047 | 209.43 | 1.791 |
| 40 | 237.06 | 2.260 | 209.43 | 1.791 |

`crdi_1p5` settles to five figures by n=20. **`crdi15` does not settle**: torque
swings 211.6–237.9 N·m (±6%) and boost 2.05–2.76 with no trend out to 40
cycles. That looks like a limit cycle in the boost loop, not slow convergence.
Both presets are VGT. `crdi15` differs in `boost_map_rise` (0.45, reaching its
boost target early, against the default 1.0) and a higher boost set-point
(`wastegate_pset` 3.05 against 2.7). Either could be the cause; neither is
tested.

Consequences:

- Known bug #1's rule "use `n_cycles >= 9`" does not hold here: no cycle count
  is converged.
- The web app's 219.5 N·m at 1650 rpm is one phase of the oscillation.
- FINDING-011's grid "now exact vs reference" is exact against a reference
  solved the same way — at such a point both agree on an unconverged number.
- `crdi15`'s limiter columns at 1500–2250 rpm in the first table are dominated
  by this, which is why their 8→9 cycle change reaches −8.7%.

Measured at one speed. How much of the `crdi15` map oscillates is not yet known.

## Bug #3 was not "a symptom of #1"

Partly true. On `crdi15` near 1650 rpm, convergence dominates — worse than #1
describes. On `crdi_1p5`, which converges, the residual is a systematic
overshoot from item 1 that no cycle count removes: +5.54% at 2250 rpm at n=9,
+5.47% at n=12.

## Options

For item 1 (the limiter):

| option | positives | trade-offs |
|---|---|---|
| A. Calibrate with the schedules the evaluation will use: pass `load_est = 1` (or the same EGR/boost/SOI) into the calibration solves | removes the bias at its source; small, local change; the `crdi_1p5` hand trim can then go | every limiter-capped number moves by up to ~5%; golden points need a justified re-baseline |
| B. After calibrating, verify with one solve under evaluation conditions and correct once | keeps the fit as is; bounded cost (one extra solve per speed) | treats the symptom; still one secant step, so it may not land inside `tol` |
| C. Document it and keep the trim | no numbers move | the UI would show a cap it overshoots by up to 7% |

For item 2 (EGR valve): start the valve area from a value consistent with the
target (for example proportional to it) instead of a fixed 25 %, or warm-start
it from the previous solve. Either changes every part-load result; it needs its
own measurement pass.

For item 3 (convergence): first map where `crdi15` oscillates (and whether
other presets do), then decide between damping the boost controller, a
convergence criterion instead of a fixed cycle count, or averaging over the
cycle. This is a PHY2 question and should be answered before items 1 and 2 are
judged on `crdi15`.

Recommended order: **3 → 1 → 2**. Item 3 decides whether `crdi15`'s numbers mean
anything; item 1 is then small and well evidenced on `crdi_1p5`.

## Caveat

Two presets, one ambient, warm engine. The conditions-bias columns come from
fresh engines at 8 cycles, while the reported pull warm-starts from the
calibration's final state, so the parts do not sum exactly to the evaluated
error. The limit cycle is shown at one speed only. Nothing here changes code:
`tools/diag_torque_limiter.py` is diagnostic.
