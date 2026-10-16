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

---

## Update, P09's rebuild (2026-10-15): the cliff moved by one node, and the Leh check is now 36.08%

After P09's rebuild (ADR-019), single10's Leh check reads **36.08%** of
full-load torque, up from 7.20%. The other nine grids moved by 0.11 points
or less. Measured cell by cell (`out/p09_leh_check.py`, `out/p09_node.py`,
not kept):
- **Five of the six check cells** are within 2.3 N·m of a converged solve
  at Leh.
- **The sixth, 2254 rpm at full load,** reads 29.60 N·m from the table
  against 49.35 solved. Its 58 kPa / 25 °C node now **misfires on some
  cycles**: it reads 3.36 N·m, with the knock at 1.2e9 against 3.3e9 and
  the cycle unsettled. Before P09 it burned normally (gross IMEP 5.21 bar,
  above). Leh blends that node in.
- **Fresh solves reproduce the table's values exactly**, so the table is
  faithful to the solver. The solver's ignition edge has moved.
- **Torque along the pressure axis at 298 K:** 58 kPa 3.36 (unsettled),
  61 kPa 47.01, 65.8 kPa 49.08, 69 kPa 50.13, 72 kPa 50.94. So the cliff
  lies between 58 and 61 kPa.
- **Nodes under half the standard air's torque:** 8 before P09, 9 after.
  The new one is 2254 rpm, full load, 58 kPa, 25 °C.

Why the edge moved has not been measured. The first suspect is stage 1's
port flow, which changed this engine's VE by up to 10% (FINDING-028), and
so its trapped charge and compression temperature.

Drive and Enjoy show each engine's measured Leh error, so single10's place
field will show 36% instead of 7.2%. ~~**The options above stand, and the
choice is the owner's.**~~
**Decided (the owner, 2026-10-16): ship with the 36% stated** (P09, #131). The
misfire cliff itself stays open, with the options above.
