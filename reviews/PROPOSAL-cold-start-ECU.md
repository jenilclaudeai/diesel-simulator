# PROPOSAL — a cold-start ECU in the live loop (FINDING-031 option C)

**Date:** 2026-10-22 (session 11). **Status:** measured; **questions for the owner** (end).
Nothing shipped is changed.
**Asked for by the owner** (2026-10-16, deciding FINDING-031): P09 merged with the cold creep
stated (A), and "C (a cold-start ECU: fast idle, the pedal's fuel covering the extra friction)
comes as its own proposal". PLAN lists it as the next proposal.
**Lenses:** PHY1, PHY2, SW1, QA1, QA2, USR1, PM
**Measured on** `main` at `173a65f` (after #137), with today's grids (P13's rule R5, #133).
FINDING-031 was measured on P09's grids before R5, so its numbers were re-measured here, by a
different measure: time to 10 km/h, not "breaks free" (1.3 × idle).
**Scratch scripts** (the session's job directory): `ecu.py` (the prototype, below),
`ecu_check.py`, `launch.py`, `table.py`, `idle.py`, `warmup.py`, `excess.py`, `probe.py`.

---

## The problem today

The pedal is a **fuel fraction**: 20% pedal is 20% of full-load fuel, warm or cold. A cold engine
needs more of that fuel just to turn itself:
- **its friction is higher** (cold oil): crdi15 at 800 rpm / 20%: 16.0 N·m warm, 20.5 at 25 °C,
  31.1 at 0 °C;
- **its walls take more heat** (P09's true cold start): indicated torque 25.2 warm, 21.6 at
  25 °C, 20.1 at 0 °C.

So 20% pedal gives crdi15 **9.2 N·m** of brake torque warm, **1.1** at 25 °C and **−11.0** at
0 °C. Launches from rest, 60 s, pedal pressed at 0.5 s:

| 20% pedal | warm | 25 °C | 0 °C |
|---|---|---|---|
| crdi15 TC | 7.4 s to 10 km/h, 57 km/h at 60 s | **never** (6 km/h) | **never** (6) |
| crdi15 DCT | 7.0 s, 58 | 14.3 s, 45 | **never** (0) |
| crdi22 TC | 5.0 s, 57 | 9.4 s, 45 | **never** (6) |
| crdi22 DCT | 5.1 s, 58 | 9.1 s, 45 | **never** (4) |
| hatch15 TC | 5.7 s, 68 | 54.4 s, 20 | **never** (6) |
| hatch15 DCT | 5.4 s, 69 | 14.7 s, 48 | **never** (0) |

At 30% pedal all of them move, but cold takes 1.3–12× the warm time (hatch15 TC 0 °C 42.3 s
against 3.5). In all, **7 of the 24 cold cases never reach 10 km/h in a minute**, every one at
20% pedal.

Idle is not the problem: `main`'s idle governor is stiff (proportional, 0.010 load per rpm), so
a cold engine idles only ~10–20 rpm lower than a warm one (crdi15 at 0 °C 770–779 rpm against
787 warm; hd_i6 572–581 against 591).

## What a real diesel ECU does

From Saab's workshop description of its Bosch **EDC16** diesel management (a torque-based ECU):
- "The pedal position together with the engine speed gives a requested torque using a
  matrix", and the torque request "is converted to a fuel quantity request".
- "The engine has its own torque consumption that principally comprises its internal friction
  and pump losses. To compensate for this, the function will usually request torque",
  calculated from coolant temperature, oil temperature and engine speed (and two pump-loss
  inputs).
- "Nominal idling speed with warm engine is 850 rpm. The nominal idling speed is dependent on
  the coolant temperature. The idling speed is higher for a cold engine." No table is given.
- "Idle speed control is active when the accelerator pedal is not pressed."

MathWorks' model of Bosch's torque structure likewise scales friction torque by a function of
coolant temperature. I found no published cold-idle table: a forum figure of 1000–1100 rpm for a
Mercedes diesel (warm ~800) is anecdote, so the fast idle's size below is a choice, not a
calibration.

Sources: [Saab EDC16, detailed description](https://saabwisonline.com/9-3-9440/2007/2-engine/4-cylinder-diesel/edc-16-engine-management-system/technical-description/detailed-description-engine-management-function);
[MathWorks, SI engine torque structure](https://www.mathworks.com/help/autoblks/ug/si-engine-torque-structure-model.html).

## The prototype

`ecu.py` subclasses `LiveEngine` and copies `main`'s `_sub` with hooks. **With every hook off
it equals `LiveEngine` on 0 of 24,000 values** (crdi15 TC, hatch15 DCT, crdi22 manual; 40 s
drives from 0 °C with a pedal script).

1. **The cover (FF), friction:** whenever the demand (pedal or idle governor) is above 0, add the
   load whose indicated torque covers the live friction's excess over the warm cells' friction
   at that rpm and demand. The warm cells' friction is the ECU's "warm map"; the live friction is
   ADR-011's (oil and coolant at their live temperatures). The excess is clamped at 0 (a hotter
   than calibrated engine is not leaned out).
2. **The cover (WALL), cold walls:** also add the warm cell's indicated torque minus the
   indicated torque at the live `T_chamber`. With both, **the pedal gives a cold engine the
   warm engine's brake torque**, which is what a torque-based ECU aims for.
3. **The gate:** the cover is multiplied by 1 below 40 °C coolant, 0 above 70 °C, linear
   between.
4. **Fast idle (FI):** the governor's target is `idle_rpm + FI × g`, with g 1 at 0 °C and 0 at
   40 °C coolant; **only while the pedal is up**, as EDC16 does it.

The added load is found by inverting the grid's indicated torque in load (piecewise linear, two
or three secant steps), capped at full load. The largest seen: 0.34 (hatch15 TC, 0 °C). Pedal 0
above idle (overrun) adds nothing: the fuel cut stays.

## What was measured

### The 24 cold launches, nine variants

Time to 10 km/h / speed at 60 s / fuel over the minute. A selection (the full table is
`launch_all.json` in the job directory):

| 20% pedal | `main` | τ 15 s (option B) | FF | FF+WALL | FI 200 alone | FF+WALL+FI 200, pedal-up | warm `main` |
|---|---|---|---|---|---|---|---|
| crdi15 TC 25 °C | never / 6 / 14 mL | 38.9 s / 33 / 22 | 10.4 s / 55 / 39 | 7.6 s / 59 / 43 | 12.6 s / 44 / 32 | 7.5 s / 59 / 44 | 7.4 s / 57 / 36 |
| crdi15 TC 0 °C | never / 6 / 19 | never / 6 / 18 | 13.0 s / 52 / 46 | 7.9 s / 58 / 53 | never / 7 / 21 | 7.9 s / 58 / 53 | 7.4 s / 57 / 36 |
| crdi15 DCT 0 °C | never / 0 / 17 | never / 0 / 16 | 10.1 s / 54 / 47 | 7.4 s / 59 / 52 | never / 8 / 21 | 6.3 s / 60 / 53 | 7.0 s / 58 / 36 |
| crdi22 TC 0 °C | never / 6 / 27 | never / 6 / 26 | 6.8 s / 55 / 70 | 5.4 s / 59 / 76 | 33.8 s / 24 / 39 | 5.3 s / 59 / 76 | 5.0 s / 57 / 51 |
| hatch15 TC 25 °C | 54.4 s / 20 / 19 | 32.4 s / 42 / 29 | 7.6 s / 63 / 48 | 5.9 s / 68 / 53 | 11.4 s / 49 / 37 | 5.8 s / 68 / 53 | 5.7 s / 68 / 47 |
| hatch15 TC 0 °C | never / 6 / 23 | never / 6 / 22 | 9.2 s / 59 / 54 | 6.3 s / 68 / 63 | never / 7 / 25 | 6.3 s / 68 / 63 | 5.7 s / 68 / 47 |
| hatch15 DCT 0 °C | never / 0 / 21 | never / 0 / 20 | 7.8 s / 60 / 54 | 5.9 s / 69 / 62 | 59.9 s / 10 / 25 | 4.8 s / 70 / 63 | 5.4 s / 69 / 46 |

Over all 24 cases:
- **Every variant with the cover moves every case.** `main` leaves 7 stuck; option B (a 15 s
  chamber constant) leaves 5; fast idle alone leaves 3.
- **FF+WALL gives a cold engine the warm launch at light pedal:** in every 20% case it reaches
  10 km/h 0.1–0.7 s after warm and is −0.4 to +3.0 km/h from warm at 60 s, for 11–51% more
  fuel than the warm launch (crdi15 TC 0 °C 53 mL against 36). It is never quicker than warm.
  At 30% it ends up to 9 km/h slower at 60 s (hatch15 99–101 against 108–110). *Traced*
  (`gap30.py`, hatch15 TC, every 5 s): the engine gives the warm torque, ~2 N·m more (80 N·m
  against warm's 78 at the same rpm), but **the automatic upshifts earlier when cold**: gear
  index 2 against 1 at 10 s, index 5 from 45 s against warm's 4 to the end (index 0 is
  first gear). The engine runs at
  ~2,000–2,150 rpm instead of ~2,800, so less power from the same torque. P08's schedule
  (ADR-017) reads the map at the live chamber temperature (`_econ_map`), so with the cover it
  shifts as if the engine were still weak. See question 4.
  Friction alone (FF) is slower than warm (crdi15 TC 0 °C 13.0 s against 7.4).
- **Fast idle with the pedal down overshoots:** cold launches become quicker than warm (crdi15
  TC 0 °C 4.3 s, crdi22 3.2 s), because `main`'s governor also acts under the pedal and adds up
  to 0.75 load whenever rpm is under its target. **With the pedal up only**, every TC launch
  equals FF+WALL's. On the DCT it is ~1 s quicker (6.3 s against 7.4), from the harness: the
  pedal goes down 0.5 s after the start, when fast idle has already raised the rpm. The speed
  at 60 s is the same.

### Twelve minutes from 0 °C, and warm invariance

crdi15 TC, 30% pedal for 30 s then lifted for 10 s, repeated, 12 min; and the same from a warm
start (coolant 361 K, oil 373 K), FF+WALL+FI 200:

| gate | 0 °C: fuel, 12 min | at 29 s | warm drive: values differing from `main` |
|---|---|---|---|
| `main` (no ECU) | 0.447 L | 8.5 km/h | — (warm `main`: 0.479 L) |
| coolant 40–70 °C | 0.508 L | 60.2 km/h | **0 of 259,200** |
| oil 60–90 °C | 0.510 L | 60.2 km/h | 234,600 |
| none | 0.509 L | 60.2 km/h | 248,328 (+0.4% fuel) |

- The added load falls from 0.10 at 29 s to 0.03 at 3 min and ~0.001 by 7–9 min.
- **The coolant gate keeps warm driving bit-identical.** It drops at most ~0.008 load of
  cover during the warm-up, and the speeds match the other gates within 1–2 km/h.
- *My first guess was an oil gate* (the friction excess at coolant 70 °C with the oil at 42 °C
  is 6–54 N·m across the roster). In the live loop the oil does not lag: it runs ~2 K ahead of
  the coolant. And a warm engine's oil cools to ~85 °C on this drive, which wakes an oil gate in
  warm driving. Measured and dropped.

### Idle, all ten engines

120 s in neutral, `main` against FF+WALL+FI 200 (rpm at 2 s → 120 s; fuel):

PENDING_IDLE

Warm, the ECU equals `main` to every digit on every engine (the gates are shut).

### A 20% launch, all ten engines (each on its own box)

PENDING_LAUNCH

## What it would touch

- **`live.py`** (unhashed: `GRID_HASH_EXCLUDES`), so **no grid rebuild and no re-stamp**. About
  40 lines in `_sub` and a helper, plus four constants.
- **`web/physics/src/live/engine.ts`**: the same; `Adr011Grid.blendPerfT` already exists.
- **The live fixture:** the drives that start at the ambient change (`tc`, `dct`, `manual`,
  `tc_kickdown` through fast idle only, since they run the plain grid with no live friction;
  `adr011_cold`, `adr011_waxed`, `adr011_limp`; P06's route drives once #138 merges).
  **The warm drives must not move** (`dct_hot`, `adr011_warm`, `adr011_weather`,
  `adr011_weather_fan`): a test that asserts it, with a mutant (the gate opened) that it
  catches.
- **Cost:** up to four extra bilinear blends per substep while cold, none when warm (the gate
  returns first). Holding the cover at the friction's 10 Hz instead would be cheaper; `npm run
  perf` decides.
- **What the driver sees and hears, when cold:**
  - more fuel on the trip computer, the real direction (crdi15: +45% over a cold minute against
    a warm one, +14% over a cold 12 min against `main`'s cold run);
  - with fast idle, a faster idle note and P01's idle shake at the higher firing rate;
  - a higher load, so a cold engine sounds as loaded as the warm one at the same pedal.
- **Not touched:** the warm engine in every respect; the solving pages (Dyno, Sweep and the
  rest solve cells, not the live loop); the full-pedal launch (the cover is capped at full
  load, so a cold engine at full pedal is still weaker than a warm one, as a real one is);
  the waxed-fuel cap (applied after the cover, so wax still starves it); the overrun fuel cut.
- **Interplay:**
  - **FINDING-033** (an automatic held at its 60 rpm floor): the cover makes a weak engine
    stronger only when cold. It does not fix FINDING-033, and doesn't conflict with its
    option A.
  - **#138 (P06)** changes `live.py` and `engine.ts` too. Building after it merges avoids a
    second fixture regeneration.

## Options

| option | positives | costs |
|---|---|---|
| **A. Keep today's behaviour** (FINDING-031 A, already stated) | nothing to build or review | 7 of 24 light-pedal cold launches don't move; on an automatic at 25 °C, crdi15 doesn't move at 20% pedal |
| **C1. The cover: friction + cold walls**, coolant gate | a cold engine launches like a warm one at light pedal, for the fuel a cold engine really burns; warm driving bit-identical; no rebuild; the EDC16 structure | 11–51% more fuel than warm in a cold minute; the cold fixtures move; ~4 more blends per substep while cold; an automatic still shifts as if cold (P08 reads the cold map), so at 30% it is up to 9 km/h behind warm at 60 s |
| **C1′. The cover, friction only** | the smallest change; ECUs do model friction explicitly | cold launches stay ~1.5–2× slower than warm (crdi15 TC 0 °C 13.0 s against 7.4) |
| **C2. Fast idle, pedal up** (with C1) | the cold idle and its sound; a real ECU's behaviour; quicker warm-up of the cabin heat (not modelled) | its size is a choice (no published table); +9–23% idle fuel over 2 cold min; changes the idle note and the vibration's rate when cold; does nothing for the launch on a TC |
| **B. A faster chamber warm-up** (FINDING-031's B) | one constant | measured not to work: 5 of 24 still stuck |

## Lens review

- **PHY1:** C1 is the torque-based ECU's structure. Using the live friction model as the ECU's
  friction map is a **perfect calibration**: a real map is coarser. Stated, not hidden. The
  wall term (WALL) is less standard than the friction term; it is what makes "the pedal means
  the same torque cold" hold. NOTE.
- **PHY2:** the cover inverts a bilinear interpolation; capped at full load; no new state, so
  no new stability question. The 40–70 °C gate is a choice; the warm-up drive shows the
  cover is ~0 by 70 °C anyway. NOTE.
- **SW1:** a direct port; mind the order (the cover before the rated droop and the wax cap).
  MINOR: perf on a phone, measured before merging.
- **QA1/QA2:** the warm-invariance test (warm fixture drives byte-identical) with the gate
  mutant; FINDING-031's matrix as a regression test (a few cases, since each costs ~1.5 s of
  CPU per simulated second in Python); the TS port against regenerated fixtures. MAJOR if
  missing.
- **USR1:** a car that won't pull away at light pedal on a 25 °C day reads as broken; with C1
  it pulls away. Whether a fast cold idle *sounds* right is the owner's ear. Advisory.
- **PM:** a day's build after #138 merges; no rebuild. No blocking findings.

## Recommendation

**C1 (friction + walls, coolant gate 40–70 °C), with C2 (fast idle, pedal up) at +150 rpm at
0 °C**, built after #138 merges. C1 is the fix. C2 is cheap and real, but its size is a guess,
so I'd keep it modest and let the ear decide.

## Questions for the owner

1. **C1 as measured:** the cover for friction and the cold walls (a cold engine answers the pedal
   like a warm one, burning more fuel), or friction only (C1′, still slower than warm)?
2. **Fast idle:** yes or no, and how much at 0 °C (+100, +150 or +200 rpm; it fades out by
   40 °C)? It changes the cold idle's sound and the phone's idle shake.
3. **When:** after #138 merges (recommended, one fixture regeneration), or now?
4. **The automatic's schedule when cold:** P08 reads the engine's map at the live chamber
   temperature, so with the cover it still upshifts as if the engine were weak (hatch15 at 30%:
   gear index 5 at ~2,100 rpm, against warm's 4 at ~2,800). Keep that, which is P08 as decided and
   reads like a "cold economy" mode, or let the schedule read the covered (warm) map, which
   moves P08's cold fixtures too? Not measured yet; I'd measure it in the build.
