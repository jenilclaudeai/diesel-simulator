# FINDING-027 — In cold, thin air the NA single's ignition is all or nothing

**Opened by:** session 8 (2026-10-09), reading `single10`'s weather table:
its own Leh check came out at 7.20% of full-load torque, where the four
turbo engines' checks were 2.35–2.78%.
**Lens:** PHY1 (lead), PHY2
**Status:** **open, for the owner.** Nothing is changed. The table and the
page state the measured 7.2% for this engine.
**Reproduce:** the session-8 scripts `diag_single10.py` and
`diag_misfire.py` (not kept; the numbers are below).

---

## What was measured

`single10` (the NA mechanical single) at 2254 rpm, full load, converged, on
its row's fuel (39.45 mg):

| air | peak pressure | gross IMEP | heat released | exhaust |
|---|---|---|---|---|
| standard | 46.8 bar | 6.78 bar | 1674 | 657 K |
| **58 kPa, −20 °C** | 28.2 bar | **−0.05 bar** | **0.0** | 444 K |
| 58 kPa, 25 °C | 26.8 bar | 5.21 bar | 1582 | 736 K |
| 72 kPa, −20 °C | 34.9 bar | 6.50 bar | 1673 | 665 K |

At the table's coldest, thinnest node the cycle doesn't ignite at all, at
2254 rpm (loads 0.4 to 1.0) and on its top rpm row at full load. 15 °C
warmer, or 14 kPa denser, it burns normally. No turbo engine shows this:
in all four turbo tables, no node with positive standard-air torque falls
below a quarter of it.

## Why it matters

- **The table:** Leh (65.8 kPa, 20 °C) blends that node with weight 0.048,
  which costs about 2.2 N·m at 2254 rpm full load. Concave curvature in
  pressure costs about 1.7 N·m more. Together they make the 7.2% (the
  weights reproduce the table's 45.20 N·m exactly). The lower rows are
  within 0.5%.
- **The physics:** a real engine near its cold-ignition limit runs rough
  first (long ignition delay, white smoke, some misfires) before it stops
  firing. Here it is a cliff. This matters for step 6 (cold-flow, cold
  starts) and for P06's climbing roads, which reach these airs.

## Options

| option | positives | costs |
|---|---|---|
| **A. State it (now)** | nothing changes; the page already shows each engine's measured Leh error (7.2% for single10) | the cliff stays in the corner |
| B. Look at ignition in cold, thin air (with step 6) | the cold-start physics step 6 needs anyway; a gradual misfire region instead of a cliff | a model change in a hashed file: a proposal, then measurement, then a rebuild or re-stamp |
| C. Leave non-firing nodes out of the table's blend | single10 at Leh near 3% | hides real model behaviour: the corner would then be wrong in the other direction |

**Recommendation:** A now, and B as part of step 6, which deals with
cold-flow and cold starts. C is not recommended: it hides physics.
