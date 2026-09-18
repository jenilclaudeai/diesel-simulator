# FINDING-009 — bug #4 does not reproduce at ~2×; the real gap is ~29%

**Opened by:** known bug #4, "light-load fuel consumption is understated,
probably by ~2×. Cruise economy reads 26 km/L at 90 km/h on the 1.5 L"
**Lens:** PHY1
**Status:** measured, not fixed — the fix is a calibration judgement

---

## The bookkeeping is exact

First check was whether `fuel_kg_h` disagrees with `fuel_mg`, which is what
`PLAN.md` said to measure. It does not.

| rpm | load | fuel_mg | expected kg/h | `op.fuel_kg_h` | ratio |
|---|---|---|---|---|---|
| 1500 | 0.10 | 4.842 | 0.8716 | 0.8716 | **1.000** |
| 1500 | 0.25 | 12.106 | 2.1790 | 2.1790 | **1.000** |
| 1500 | 0.50 | 24.212 | 4.3581 | 4.3581 | **1.000** |
| 1800 | 0.15 | 7.320 | 1.5812 | 1.5812 | **1.000** |
| 2000 | 1.00 | 46.713 | 11.2110 | 11.2110 | **1.000** |

Expected is `fuel_mg × 1e-6 × n_cyl × (rpm/2) × 60`, four-stroke. Exact at
every point. **There is no unit slip and no conversion error.**

## The road load, computed rather than driven

`crdi15` vehicle: 1500 kg, CdA 0.7, Crr 0.0092, r_wheel 0.315, final 4.3,
top gear 0.58.

At 90 km/h (25 m/s):

```
F_aero = 262.5 N     F_roll = 135.4 N     total = 397.9 N
road power  = 9.95 kW at the wheels
crank power = 10.20 kW at eta 0.975
engine       1890 rpm, 51.5 N.m
```

Solving that point directly: 11.60 mg, 2.630 kg/h, **3.50 L/100km (28.6 km/L)**
at BSFC 256 g/kWh.

## The gap is 29%, not 2×

| | L/100km |
|---|---|
| solver | 3.50 |
| real 1.5 L diesel, steady 90 km/h | 4.5–5.5 |
| ratio | **1.29–1.57×**, not 2× |

The bug report's 26 km/L matches what the solver produces (28.6 here), so the
observation was right. The **inference of ~2× was not** — the comparison was
against mixed real-world consumption, which includes stop-start, gradients,
wind and accessory duty that a steady-state point does not.

To hit 4.5 L/100km at this operating point the engine would need **330 g/kWh**
against the 256 it reports.

## Where the remaining 29% plausibly sits

Not one error. Three candidates, none individually damning:

**1. Light-load BSFC is optimistic.** 256 g/kWh at 51.8 N·m on a 1.5 L — about
20% of rated torque — against a best of 229. Real diesels at that load
typically show 280–320. So the map is perhaps 10–20% optimistic at the light
end, which is most of the gap.

**2. Accessory load is thin.** At cruise the parasitics total 1215 W, 11.9% of
brake power, and 1069 W of that is the alternator. `aircomp_load_W = 0.0` and
`fan_duty = 0.1`. A real car cruising has climate control, lights, infotainment
and a fan doing more than 10%. Not wrong for a defined steady-state
measurement; wrong as a proxy for real driving.

**3. The vehicle is slippery.** CdA 0.7 and Crr 0.0092 are optimistic-but-
defensible for a small hatch. Not the main term.

## Options

1. **Recalibrate light-load BSFC.** Closest to the real cause, but it is the
   combustion and friction models jointly, and it would move the validation
   table. Needs real part-load data to calibrate against, which we do not have.
2. **Raise accessory loads to a realistic cruise duty.** Cheap, defensible,
   and moves economy the right way without touching combustion. But it makes
   the engine look worse at every operating point, including the rated ones in
   the validation table.
3. **Change nothing; fix the claim.** The solver is a steady-state engine
   model and its economy figure is a steady-state figure. Label it as such in
   the UI and stop comparing it to brochure consumption.

**Recommendation: 3, then 1 if part-load data ever becomes available.** A 29%
gap between a steady-state point and mixed real-world driving is expected, not
a defect. The genuine finding is that bug #4 overstated the problem by roughly
double and would have sent someone hunting a factor-of-two error that is not
there.

## Caveat

One vehicle, one speed, one gear. Economy at other speeds is untested, and the
light-load BSFC claim rests on general knowledge of diesel part-load maps
rather than on measured data for this engine. If part-load data exists, that is
the thing to check before recalibrating anything.
