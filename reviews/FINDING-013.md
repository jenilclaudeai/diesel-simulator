# FINDING-013 — bug #3 understated: the limiter is fitted with EGR on and judged with it off, and `crdi15` never converges near 1650 rpm

**Opened by:** known bug #3, "torque limiter residual error ±3% across the
plateau (was 11%). Symptom of #1, not a separate bug"; re-measure after
FINDING-007, listed as next action 6 in `STATUS.md`
**Lens:** PHY1 (lead), PHY2, QA2
**Status:** measured, not fixed. Item 3 measured further in session 4 — it is
**not** local to `crdi15`, and at part load it merges with item 2; see
*Item 3, measured* at the end. The fix needs a design decision.
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

> *Correction (session 4, later the same day):* "fresh engine per row" is
> true but misleading. On a capped preset, `operating_point(fuel_mg=F)` first
> calls `fuel_limit()` to compute `load_est`, which runs the limiter
> calibration: three 8-cycle solves at other fuellings. Each row's solve
> therefore warm-starts from the same deterministic 24-cycle calibration
> state. The conclusion stands, because every row starts from an identical
> state, but the rows were not cold starts. The same applies to the first
> table and to the web app, whose every capped point runs that calibration.

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

---

## Item 3, measured — the solver's two control loops do not reach steady state in 9 cycles

*Added in session 4, after the options above were written. The options for
items 2 and 3 are superseded by the ones below; the text above is kept.*

Reproduce: `python3 tools/diag_convergence.py --accel | --map | --candidates`.

### The mechanism of the limit cycle: `spool_accel`

`CycleSolver.run()` advances the turbo shaft **and the VGT integral
controller** 14× faster than real time on every cycle but the last two, while
the manifold pressures the controller reads still fill in real crank time.
From the controller's point of view its sensor lag is 14× longer than
physical, and an integral controller with lag oscillates. Per-cycle trace
(`tools/diag_torque_limiter.py --trace`, final solve only): the vanes swing
between the closed clamp (0.32) and ~0.79 every cycle, boost 2.16–2.64, with
an 8-cycle period.

Same point (`crdi15` 1650 rpm, limiter fuelling, EGR off), same simulated
turbo time, fresh engine:

| `spool_accel` | cycles | boost spread, last 8 accelerated cycles | torque |
|---|---|---|---|
| **14 (shipped)** | 40 | **20.33%** | 237.06 |
| 8 | 68 | 23.06% | 216.07 |
| 4 | 135 | 1.25% | 230.20 |
| 2 | 268 | 0.00% | 231.41 |
| 1 | 534 | 0.00% | 232.10 |

### Where it happens

`--map`: boost spread over cycles 30–37 of a 40-cycle solve, 5 presets × 6
speeds × 4 loads. **21 of 120 points exceed 1%**, up to 30.7%:

- `crdi15`: 9 of 24, at full load 1450–2700 rpm and at part load 2100–4000 rpm
- `crdi_1p5`: 8 of 24, mostly **part load** (load 0.25 at every speed from
  1450 to 4000 rpm, 20–31%)
- `hd_i6`: 2 (1.6% at 1100 rpm); `ld_i4`: 1 (1.2%); `single` has no turbo.

`crdi_1p5` looked converged at 1650 rpm full load only because its vanes sit
on the fully-open clamp there.

### How wrong the shipped solve is

Against a converged reference — `spool_accel = 1` for 534 cycles; boost
spread over its last 20 cycles ≤ 0.001% at every point — with identical
fuelling and schedules (the limiter cache is pre-seeded, so no calibration
re-runs):

| point | reference N·m | shipped n=9 | shipped n=12 |
|---|---|---|---|
| `crdi15` 1450 / 1.0 | 215.77 | +0.59% | −1.57% |
| `crdi15` 2100 / 0.75 | 180.35 | **−12.94%** | −0.66% |
| `crdi15` 4000 / 0.25 | 36.05 | −1.11% | **−20.09%** |
| `crdi_1p5` 2100 / 0.5 | 110.14 | **−16.89%** | −9.44% |
| `crdi_1p5` 3350 / 0.25 | 43.48 | **−43.58%** | −23.96% |
| `hd_i6` 1100 / 1.0 | 1757.38 | −0.56% | +2.38% |
| `hd_i6` 1300 / 1.0 (converges in --map) | 2015.33 | +1.36% | +0.99% |
| `ld_i4` 2100 / 0.5 (converges in --map) | 164.19 | −2.87% | −1.26% |
| `crdi15` 800 / 1.0 (converges in --map) | 88.55 | −1.44% | −1.44% |

RMS error at n=9 is **16.2%**. More cycles do not reliably help (n=12 is worse
at two points). Even points that do not oscillate are 1.4–2.9% off: they have
not finished converging either.

### At part load it is the EGR loop (item 2)

| point | EGR delivered, shipped n=9 | converged | target | vanes, shipped / converged |
|---|---|---|---|---|
| `crdi_1p5` 3350 / 0.25 | **27.93%** | 13.13% | 13.12% | 0.260 (clamp) / 0.634 |
| `crdi15` 2100 / 0.75 | **13.18%** | 4.47% | 4.71% | 0.320 (clamp) / 0.502 |

The model's steady state hits the EGR target to 0.01 points. At 9 cycles it
delivers 2.1–2.8× the target, because the valve starts 25% open (item 2) and
trims in real time, with the vanes shut on their clamp. Items 2 and 3 are one
problem: **neither control loop reaches its steady state in 9 cycles.**

### Four VGT-only fixes were tried; none works

Applied from outside the solver by wrapping `Turbocharger.step`. The wrapper
was checked first: in "shipped" mode it reproduces the unwrapped solver
bit-for-bit at two points, and its controller-override path matches to 4.9e-9
(a limit cycle amplifies rounding). Each candidate changes only the
accelerated cycles, so real-time (1×) behaviour — the physical turbo lag —
is untouched.

| candidate | worst, n=9 | RMS, n=9 | worst, n=12 | RMS, n=12 |
|---|---|---|---|---|
| shipped: shaft 14×, controller 14× | −43.58% | 16.21% | −23.96% | 10.95% |
| C1: controller at 1× | −26.80% | 11.94% | −53.52% | 18.77% |
| C2: both ramp 14× → 1× | −43.65% | 18.18% | −76.59% | 26.52% |
| C3: controller capped at 2× | −38.13% | 15.58% | −71.93% | 24.74% |
| C4: both 4× | −40.17% | 16.49% | −76.53% | 26.10% |

They cannot work at part load, because they leave the EGR loop as it is.

### Consequences

- **The real-time grid and the web app carry these errors.** Both solve at
  `n_cycles=9` on fresh engines. `crdi15` is the app's default engine.
- **The golden points lock in unconverged values.** They are 9-cycle solves;
  `crdi15` 1800 / 0.6 is a part-load point with EGR active.
- **Item 1's numbers were measured on unconverged solves**, so item 1 has to
  be re-measured after this is fixed; its mechanism (fit with EGR on, judge
  with it off) is unaffected.
- Known bug #1 ("use `n_cycles >= 9`") is a symptom of this, not a rule that
  can be satisfied by picking a larger number.

### Options (supersede the item 2 and 3 options above)

| option | positives | trade-offs |
|---|---|---|
| **A. Solve for the controllers' steady state.** In the accelerated cycles, replace the two continuous integral controllers with a once-per-cycle update on cycle-mean boost and burnt fraction (damped secant toward the target, clamp-aware). The last two cycles and all 1× (transient) running are unchanged. | Keeps the cost at ~9–12 cycles. Principled: a steady state does not depend on how the controller got there. Fixes VGT and EGR together. | New solver code in `cycle.py`/`turbo.py` needing its own convergence proof across the map. Moves every part-load number and some full-load ones: golden points re-baselined with justification, the 2310 N·m validation re-checked, every cached grid invalidated (automatic via the physics fingerprint). |
| B. Run to convergence at 1× | correct by construction; no new control code | 10–60× slower: grid builds go from minutes to hours; unusable in the browser |
| C. Warm-start actuators from a neighbouring converged cell | cheap in grid sweeps | reintroduces the path dependence FINDING-011 removed; does not help single points |
| D. Document it and flag it in the UI | nothing moves | part-load numbers up to 44% wrong on the default engine; against the governing principle in PLAN.md |

Recommended: **A**, prototyped behind a flag first, judged against the 1×
reference on the nine points above and on `--map`, and only then made the
default. Then re-measure item 1.

---

## Option A, attempted (session 4) — full load converges, part load does not

*Draft PR #20, behind `steady_ctrl` (off by default; with it off the solver is
bit-identical, suite 18/0/2, audit identical to `main`). Scored with
`python3 tools/diag_convergence.py --fix` against the 1× reference.*

| variant | worst n=16 | RMS n=16 | kept? |
|---|---|---|---|
| shipped | −28.34% | 11.38% | — |
| per-actuator secants, VGT held (shaft free) | — | 27.43% at n=9 | no: the shaft lags ~5 cycles at 14×, so per-cycle updates oscillate |
| + shaft held; EGR secant on burnt fraction | — | — | no: fights the boost loop, 56% EGR at one point |
| **Broyden on (speed, VGT) + flow-ratio EGR** | **−16.83%** | **8.51%** | **yes (in #20)** |
| + plenum burnt fraction set to its equilibrium each held cycle | +35.96% | 12.26% | no: reverted |

Full load converges with the kept variant — within 0.4% by n=12–16 at
`crdi15` 1450 and 800 and `hd_i6` 1300 — and the limit cycle is gone. Part load
with EGR does not. Per-cycle means (`CycleResult.cycle_means`, added for this)
show why at `crdi15` 2100 / 0.75: the solve is still moving when the held
cycles run out — the first 3–4 cycles are spent spinning the shaft up from a
fresh engine's 12,000 rpm — so the last held step is large and uncorrected,
and EGR flow collapses in the two free cycles (7.5 → 1.2 → 0.5 g/s).

**Correction to the options table above:** option A was described as keeping
the cost at ~9–12 cycles. That estimate was not supported: with shaft, VGT and
EGR coupled, no variant tried reaches the stopping rule set for the attempt
(RMS < 1% within 16 cycles).

### Option A with an adaptive cycle count (session 4, third attempt)

`n_cycles` becomes a minimum; held cycles are added until the cycle means stop
changing (`_steady_converged`: work and boost 0.1%, shaft speed 0.2%, burnt
fraction 0.0005), up to 40. The shaft starts near its running speed instead of
12,000 rpm. The Broyden (speed, VGT) step was replaced: shaft speed ↔ boost by
1-D secant; VGT ↔ net power by a fixed conservative gain, because net power
responds to the vanes with a ~1-cycle lag and a learned slope made the vanes
wander (0.32–0.60) without settling.

| point | vs reference | cycles | converged |
|---|---|---|---|
| `crdi15` 1450 / 1.0 | +0.29% | 11 | yes |
| `hd_i6` 1100 / 1.0 | −0.11% | 14 | yes |
| `hd_i6` 1300 / 1.0 | −0.14% | 15 | yes |
| `crdi15` 2100 / 0.75 | −0.71% | 26 | yes |
| `crdi_1p5` 2100 / 0.5 | −1.34% | 38 | yes |
| `ld_i4` 2100 / 0.5 | −2.86% | 40 | no |
| `crdi15` 4000 / 0.25 | +4.63% | 40 | no |
| `crdi15` 800 / 1.0 | **+10.99%** | 40 | no — shipped n=9 is −1.44% here |
| `crdi_1p5` 3350 / 0.25 | +11.57% | 40 | no |

RMS 5.6% (shipped n=9: 16.2%; Broyden n=16: 8.5%). The timebox set for this
attempt — the nine points within 1% inside 40 cycles — is not met, so it stops
here. Converged points still sit 0.1–1.3% from the reference, consistent with
the EGR flow formula's fixed point ignoring manifold backflow.

Also found: `CycleResult.converged` was set `True` unconditionally at the end
of every solve, so every solve claimed convergence without checking; the
dead-signal audit listed it as expected-constant. Nothing read it. It is now
`False` unless a `steady_ctrl` solve met the convergence test.

---

## Converge offline, caveat online (session 4) — chosen after three attempts at option A

The owner chose: solve offline builds (Enjoy mode's prebuilt grids, ADR-008)
at real time until converged; keep the fast path in the browser with a stated
accuracy. PR #21.

### How many real-time cycles

`tools/diag_convergence.py --validate-n`: all 120 `--map` points at real time
for 400 cycles, fixed fuelling; gross work at cycle k against the mean of the
last 10.

| k | worst point | 95th percentile |
|---|---|---|
| 150 | 0.46% | 0.22% |
| **200** | **0.36%** | **0.11%** |
| 300 | 0.15% | 0.03% |

(excluding the one point below). `CONVERGED_CYCLES = 200`.

### One point has no steady state even at real time

`crdi_1p5` 1450 rpm / 0.5 never settles: work swings 372–432 (±7.5%) in a
21-cycle sawtooth, still 14.3% peak-to-peak over cycles 391–400. The per-cycle
means show the mechanism: the VGT and EGR integral controllers fight through
the exhaust-to-intake pressure difference. Boost falls below its
EGR-adjusted target (≈1.89) → vanes close to their stop → exhaust pressure
rises → EGR flow surges (11 g/s) and the burnt fraction overshoots to 0.29
against 0.12 → the turbo spools (132k → 177k rpm), boost overshoots to 2.2 →
vanes open → the pressure difference collapses, EGR flow falls to 1.2 g/s with
the valve opening wide → repeat. A controller-tuning property of the model,
not something a production calibration would do; changing it changes
transient behaviour, so it is left for decision.

### Cells that have not settled are period-averaged and flagged

At 200 cycles, 115 of 120 cells settle (last cycle within 0.22% of the
cycle-400 value). Five do not — all `crdi_1p5` part load: four are damped
ringing that settles later, one is the limit cycle above. For those,
`grid.settle_or_average()` averages torque (through IMEP), boost and bsfc over
whole oscillation periods (autocorrelation after detrending; a period counts
only after the autocorrelation first goes negative, so a settling series reads
as none) and sets `settled = 0`, `osc_period`, `osc_spread` in the cell:

| cell | period | last cycle alone | period average |
|---|---|---|---|
| `crdi_1p5` 1450 / 0.25 | 17 | −0.016% | +0.007% |
| `crdi_1p5` 1450 / 0.5 | 21 | **−5.602%** | +0.203% |
| `crdi_1p5` 2100 / 0.25 | 24 | +0.465% | −0.106% |
| `crdi_1p5` 2100 / 0.5 | 33 | −0.115% | −0.024% |
| `crdi_1p5` 2700 / 0.25 | 29 | −0.010% | −0.011% |

So a converged offline cell is within ~0.2% everywhere, including the point
with no steady state.

### Item 1 with every solve converged

`tools/diag_torque_limiter.py --converged` — the limiter's residual against its
cap with converged calibration and evaluation, before and after calibrating
under the evaluation's schedules:

| preset | before | after |
|---|---|---|
| `crdi15` plateau, 1650–4000 rpm | +0.25 … **+3.03%** | −0.30 … +0.29% |
| `crdi_1p5` plateau, 1650–4000 rpm | −1.00 … +0.77% | −0.74 … +0.35% |

(1250 rpm is air-limited in both presets and both variants.) Most of the
+6.8% the fast path showed was non-convergence; the genuine limiter bias was
≈3%, and item 1 removes it. `crdi_1p5` at 4000 rpm (−0.74%) is inside the
calibration's own 1% tolerance.

### Item 1 moved two regression guards

See FINDING-016: they had been passing on a switch of the main ignition delay
between two values, which the corrected fuelling no longer triggers.

### Caveat online: what the dyno page's fast solve is worth

`tools/diag_torque_limiter.py --pull` — every preset's 10-point full-load pull
as the page solves it (fresh engine, load 1, n_cycles 9, item 1 applied)
against converged solves. Physics build `64c825e675fc`; re-run on the final tree (`b11877338e84`, after the `seed_fuel_limit` change) gave identical rows.

| preset | worst gap, positive torque | governed end (negative torque) |
|---|---|---|
| `crdi15` | −5.9% at 1650 rpm | 2.0 N·m |
| `crdi_1p5` | −8.5% at 1200 rpm | 20.1 N·m |
| `hd_i6` | −3.3% at 1950 rpm | 14.2 N·m |
| `ld_i4` | −3.8% at 2600 rpm | 5.1 N·m |
| `single` (no turbo) | 0.0% | 0.0 N·m |

The page now states its engine's figure under the table
(`web/app/src/app/dyno/accuracy.ts`, generated from this run by
`--write-accuracy`). The table carries the physics build it was measured on;
on any other build the page says the accuracy has not been measured rather
than showing a stale number.

### Cost of a converged grid (measured)

`play.py`'s `EngineGrid(converged=True)` (`--converged-grid`): one converged
limiter calibration per rpm row, shared by its cells, then every cell at real
time for 200 cycles. `crdi15`, 8 × 6 cells, 6 workers, this Mac:

| build | time | unsettled cells | peak torque |
|---|---|---|---|
| fast (default) | 55 s | — | 224.2 N·m |
| converged | **544 s (9.1 min)** | 4 of 48, period-averaged and flagged | 222.0 N·m |

About 10× the fast build — affordable for Enjoy mode's prebuilt roster
(ADR-008), out of the question in the browser.
