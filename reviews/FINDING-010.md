# FINDING-010 — bug #2's instability does not reproduce; the loop converges

**Opened by:** known bug #2, "fuelling is open-loop on rpm, not closed on
measured boost… closing the loop naively is unstable — it collapses to the
low-boost equilibrium at 1500 rpm (148 N·m) and runs away to 524 N·m (33 bar
BMEP) at 2500. Needs a rate-limited boost-follower."
**Lens:** PHY1
**Status:** measured. The stated fix is not the fix that is needed.

---

## What is true

`fuel_limit_raw` really is open-loop. Sweeping `turbine_area_eff` across
±50% at 1500 rpm full load:

| turbine area | boost PR | AFR | `fuel_limit_raw` |
|---|---|---|---|
| 2.87e-4 | 1.988 | 21.06 | **52.03** |
| 3.49e-4 | 2.071 | 20.31 | **52.03** |
| 4.10e-4 | 2.146 | 21.56 | **52.03** |
| 4.92e-4 | 2.286 | 22.62 | **52.03** |
| 6.15e-4 | 2.097 | 19.77 | **52.03** |

Flat to four significant figures while boost moves 15%. Confirmed.

## What is not true

**"Improving the turbo does not raise torque on its own."** It does — torque
goes 211.1 → 225.7 N·m (+6.9%) between the baseline and the best turbine area,
because `fuel_for_torque` closes the loop on *measured* AFR during calibration.

That is the AFR-headroom block — **the same code known bug #8 flagged as
untrusted, unknown-provenance**. Two bug entries describe the same block from
opposite directions: #8 says it should not be there, #2 asks for exactly what
it does. See FINDING-007, which assessed it as sound.

Also worth noting from that sweep: boost is **non-monotonic** in turbine area,
peaking at 4.92e-4 and falling by 6.15e-4. That is correct physics — too large
an area drops the expansion ratio across the turbine — and it means "improving
the turbo" is not a single direction.

## The instability does not reproduce

Naive fixed point, `f ← m_air / afr_limit`, from the raw limit:

**1500 rpm** — converges in 6 iterations, monotonically:

```
52.03 → 60.20 → 59.13 → 58.89 → 58.74 → 58.60 → 58.61   converged
                                        AFR 17.50, T 240.2 N.m
```

No collapse. **No 148 N·m equilibrium.**

**2500 rpm** — converges geometrically, successive deltas 8.6, 4.9, 1.8, 0.65,
0.22, ratio ≈ 0.35:

```
61.94 → 72.43 → 80.99 → 85.90 → 87.73 → 88.38 → 88.60   converging to ~88.7
```

**No runaway.** It settles at 394.7 N·m, which is 33.1 bar BMEP — the bug
report's 33 bar figure is right, but it is a *convergent* value, not a
divergent one, and the torque is 394.7 rather than 524.

## The real problem is a missing constraint, not instability

At the converged 2500 rpm point:

| | value |
|---|---|
| torque | 394.7 N·m |
| BMEP | **33.1 bar** |
| p_max | 181 bar |
| T_exh | **1046 K** |
| AFR | 17.52, exactly the smoke limit |

33 bar BMEP is unphysical for a 1.5 L passenger diesel, and 1046 K exhaust
would cook a turbine. The loop is not misbehaving — **it is obeying the only
constraint it was given.** The smoke limit alone does not bound a diesel; peak
cylinder pressure, exhaust temperature and the rating do.

And `torque_cap(2500)` already returns **220.6 N·m**, which binds hard at both
speeds. The rating cap the package already has would never let either
converged point reach the engine.

## What this changes about the fix

Bug #2 asks for a rate-limited boost-follower to stabilise a loop that is
already stable. That would add machinery to solve a problem that does not
exist, and would not address the one that does.

What is actually needed:

1. **Close `fuel_limit_raw` on measured boost.** The loop converges; the
   damping is for transient behaviour, not numerical stability.
2. **Add the constraints that actually bind** — p_max and T_exh limits
   alongside the smoke limit. This is the substantive gap.
3. **Verify `torque_cap` is applied on every path**, since it already bounds
   both converged points.

Item 2 is the real work and it is not what the bug says.

## Caveat

One preset, two speeds, steady fixed-point iteration. A fixed point converging
does not prove a *transient* controller is stable — that is a different
question and a rate limiter may still be wanted for drivability. But it is not
needed to stop divergence, because there is no divergence.

---

## Item 2 applied (session 5): p_max and T_exh limits

Owner's decision: add p_max and T_exh limits to the fuel limiter, set above
today's full-load points so no number moves.

- `EngineSpec.p_max_limit` [Pa] and `T_exh_limit` [K, exhaust manifold];
  `<= 0` means none.
- `DieselEngine.pressure_temperature_limit(rpm, fuel)`, applied last in
  `fuel_limit()`. It runs one check solve at full-load schedules; if either
  quantity is over, it runs a secant on fuel to 0.995 of the limit. The chain
  starts cold, so the answer depends on (rpm, fuel) only. The solver's gas
  and turbo state are restored afterwards, so the solve that follows is
  exactly what it would have been. The result is cached per speed.

**Limits, and why they don't bind today.** Full-load survey, 10 speeds per
preset, fresh engine, n_cycles 9:

| preset | full-load max p_max | limit | full-load max T_exh | limit |
|---|---|---|---|---|
| `crdi15` | 157.5 bar | 180 bar | 786 K | 1073 K (800 °C) |
| `crdi_1p5` | 154.3 bar | 180 bar | 929 K | 1073 K |
| `hd_i6` | 179.3 bar | 220 bar | 925 K | 1023 K (750 °C) |
| `ld_i4` | 166.5 bar | 190 bar | 1050 K (1057.6 K in a 50 rpm sweep, 3500–4450) | 1093 K (820 °C) |
| `single` | 132.2 bar | 150 bar | 682 K | 973 K |

The limits are typical design values for each class, not sourced figures.
They are chosen, like the rating caps.

**Proved not to move anything:** 100 of 100 points (5 presets × 10 speeds ×
loads 1.0 and 0.5) are bit-identical with limits on vs off in torque, p_max,
T_exh and BSFC. The suite's goldens are unchanged.

**Proved to bind:** with each limit set below `hd_i6`'s full-load point at
1700 rpm:
- p_max 178.8 → 160.1 bar (limit 160); torque 2313 → 989 N·m.
- T_exh 905.6 → 845.3 K (limit 850); torque 2313 → 2016 N·m.

**Caveat, a modelling limit:** a fuel-only p_max limit is severe. Lowering
`hd_i6`'s peak pressure by 11% costs 57% of its torque, because boost, and with
it compression pressure, falls with fuel. A real ECU holds peak pressure
mainly by retarding injection and trimming boost. Fuel is the last resort. The
T_exh limit (fuel derate for turbine protection) is how real engines do it.
If a preset ever runs into its p_max limit, a timing-based limiter is the
better model.

**Cost:** one extra solve per speed on a fresh engine. Measured per cell:
`crdi15` +14–18% (it already runs a 4–6 solve calibration), `hd_i6` +89%
(uncapped: one solve becomes two). Fast grids build a fresh engine per cell,
so they pay this per cell. A follow-up could share the limit across a grid
row. That would move grid numbers (each cell's warm start changes), so it
needs its own re-baseline.

Two design points, measured:
- Starting every check solve cold read p_max about 7% low: each 8-cycle solve
  from a fresh turbo is short of its boost, so the bound missed (170.9 bar
  against 160). The applied version starts cold once and warm-starts the
  secant steps.
- A missing state restore changed a non-binding solve by −0.07%. That is inside
  the 0.5% golden tolerance, so the test compares limits on vs off exactly.

Test `test_pressure_and_temperature_limits`: each limit bounds full demand
within 2%, with less torque, and non-binding limits leave `crdi15` 1800/0.6
bit-identical. Mutations: limiter not applied (both bounds fail); state not
restored (the bit-identity check fails). The unmutated baseline passes. Suite
45 passed, 0 failed, 2 known.
