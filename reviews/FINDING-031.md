# FINDING-031 — Light pedal from a cold start: the car creeps, and at 0 °C does not move

**Opened by:** session 9 (2026-10-15, a second session), measuring P09's
true cold start after FINDING-030's fix, at the owner's request ("measure
more first").
**Lens:** the driver's view (lead), PHY1, PHY2
**Status:** **open, for the owner.** Nothing changed yet.
**Reproduce:** scratch scripts `creep.py` (live-loop launches) and
`decomp.py` (one cycle, wall by wall), in the session's job directory; the
numbers are below.

---

## What was measured

Launch from rest at a constant pedal, 60 s of the live loop (`LiveEngine`,
friction every second). "Breaks free" is the first time the engine passes
1.3 × idle. Starts: warm (coolant 361 K, oil 373 K, chamber 361 K), 25 °C
air (everything at 298 K) and 0 °C air (273 K). Grids: the fixed P09 grids
(FINDING-030 A) against `main`'s, both run by today's live loop.

| engine, box, start | 20% pedal, P09 | 20%, `main` | 30% pedal, P09 | 30%, `main` |
|---|---|---|---|---|
| crdi15 TC, warm | 5.7 s | 5.6 s | 3.2 s | 3.2 s |
| crdi15 TC, 25 °C | **never** (5.8 km/h) | 11.7 s | 4.8 s | 4.0 s |
| crdi15 TC, 0 °C | never | never | 28.1 s | 8.5 s |
| crdi15 DCT, 25 °C | 4.5 s | 2.3 s | 1.2 s | 1.1 s |
| crdi15 DCT, 0 °C | never (0 km/h) | never (0 km/h) | 6.6 s | 2.2 s |
| crdi22 TC, 25 °C | 7.8 s | 5.8 s | 3.6 s | 3.1 s |
| crdi22 TC, 0 °C | never | never | 13.3 s | 6.8 s |
| crdi22 DCT, 0 °C | 53.3 s | 27.6 s | 3.7 s | 1.9 s |
| hatch15 TC, 25 °C | **53.0 s** | 10.1 s | 4.3 s | 3.5 s |
| hatch15 TC, 0 °C | never | never | 40.7 s | 18.8 s |
| hatch15 DCT, 25 °C | 6.8 s | 2.5 s | 1.3 s | 1.1 s |
| hatch15 DCT, 0 °C | never (0 km/h) | never (0 km/h) | 24.8 s | 8.2 s |

Warm launches are unchanged (within 0.1 s). Two separate things:

1. **At 0 °C, 20% pedal never moves the car, before P09 too.** It is not
   P09's. The pedal is a fuel fraction. A cold engine's live friction
   (cold oil) eats most of 20% fuel's indicated torque at idle speed.
2. **P09 slows every cold launch 1.3–3×**, and pushes two cases over the
   edge: crdi15 TC at 25 °C (11.7 s → never; in a 120 s run it breaks free
   at 74 s) and hatch15 TC at 25 °C (10.1 → 53 s).

## Why P09 slows them: the piston's heat loss

crdi15, 800 rpm / 20%, one solve (9 cycles):

| walls | indicated torque | wall heat / fuel | delay |
|---|---|---|---|
| warm | 24.7 N·m | 48% | 1.78° |
| following a 273 K coolant (before P09) | 23.6 | 55% | 1.93° |
| a true cold start (P09) | 19.7 | **68%** | 2.27° |
| following, piston alone at 273 K | 20.7 | 64% | 2.12° |
| following, head alone at 273 K | 22.3 | 59% | 2.00° |
| following, liner alone at 273 K | 23.8 | 56% | 1.96° |
| following, exhaust port alone at 273 K | 23.7 | 54% | 1.94° |

The piston alone (510 → 273 K) is 75% of the loss, the head 33%. They
overlap, so the shares sum past 100%. The delay is not the cause at idle,
since the premix fraction sits on its 0.72 cap either way. So it is heat
transfer.

The live loop warms **every** wall as one lump (`T_chamber`,
`CHAMBER_TAU_RUN` 60 s), toward a target that stays near 340 K while the
coolant is cold. About a quarter of the cold cells' weight persists until
the coolant warms. A real piston crown is thin and sits in the flame. It
heats faster than the head and liner, but I have not checked by how much
(PHY2 to source).

**A 15 s chamber constant** (live-only) helps only partly: crdi15 TC
25 °C / 20% never → 37 s; hatch15 53 → 31 s; 0 °C / 20% still never.

## Options

| option | positives | costs |
|---|---|---|
| A. Accept; state it (ADR-019, Drive's help) | nothing to build; P09 merges as is; a cold diesel *is* slower | crdi15/hatch15 on an automatic at light pedal feel broken at 25 °C, which is a warm day |
| B. A faster chamber warm-up (`CHAMBER_TAU_RUN` 60 → ~15 s; live.py, unhashed, plus the TS port and live fixtures) | no rebuild; halves the 25 °C creep | a guess until PHY2 sources a piston time constant; leaves the 0 °C non-start; still one lump |
| C. A cold-start ECU in the live loop: fast idle when cold, and the pedal's fuel raised to cover the extra friction (what torque-based ECUs do) | fixes both, the pre-existing 0 °C case too; real behaviour | a design change, its own proposal (P-number) and TS port; the fuel figures change when cold (FINDING-009's labels) |

**Recommendation: A for P09's merge, with C as its own proposal next.** C
fixes the cause, which predates P09. B alone looks like a patch to me.
