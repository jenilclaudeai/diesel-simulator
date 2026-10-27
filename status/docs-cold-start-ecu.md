# docs/cold-start-ecu (#142, draft: a proposal with questions for the owner)

**2026-10-28:** brought up to `main` (STATUS.md was the only conflict) and, under A0
(CLAUDE.md, landing with #143), this branch's STATUS.md entries moved here verbatim.
STATUS.md is `main`'s byte for byte. ~~**Next:** the owner answers the proposal's
questions (`reviews/PROPOSAL-cold-start-ECU.md`).~~
**2026-10-28: answered** (recorded in the proposal): C1; no fast idle, extra fuel and glow
plugs when cold instead (glow plugs are new physics, measured before they are built);
keep P08. **Next:** the owner merges this proposal; the build is its own PR.

## Moved verbatim from STATUS.md (A0, 2026-10-28)

**Session 11, the cold-start ECU measured; four questions for the owner (2026-10-22),
`docs/cold-start-ecu`** (from `main` at `173a65f`; docs only, nothing shipped changes):
- **The proposal:** `reviews/PROPOSAL-cold-start-ECU.md`. Recommended: C1 (the pedal's fuel
  covers the cold friction's excess and the cold walls' indicated deficit, gated 40–70 °C
  coolant) with C2 (fast idle, pedal up only) at +150 rpm at 0 °C. ~~built after #138~~
  #138 merged mid-session (2026-10-21 21:34 UTC); `main` is merged into this branch (one
  conflict, this file's top, both kept). `LiveEngine._sub` is byte-identical across #138,
  so the measurements stand; buildable now.
  - C1 moves every stuck cold launch (`main`: 7 of 24 in the matrix; 7 of 16 over the
    roster's eight engines that launch warm). A light-pedal cold launch becomes a warm one's:
    0.1–0.7 s slower to 10 km/h, 11–51% more fuel.
  - Warm driving is bit-identical (0 of 259,200 values; idle and launch on all ten engines
    equal `main` to every digit). `live.py` is unhashed, so no rebuild.
  - At 30% an automatic still trails warm by up to 9 km/h at 60 s: P08's schedule reads the
    cold map and upshifts early (question 4).
  - **Questions:** (1) friction + walls, or friction only; (2) fast idle and its size;
    ~~(3) when (after #138 recommended);~~ (answered by #138's merge) (4) the automatic's
    schedule when cold. New in the merge: P06's `par_random_leh` (FINDING-033's reproduction)
    starts cold, so the cover may lift it off the 60 rpm floor; not measured.
  - *Two more of my claims corrected the same day, in the proposal:* the route drives start
    warm (I first wrote cold), and the cover reads no weather table (I first wrote it did).
- *Process note, owned:* I told the owner "9 of 24" mid-session from reading a table by eye;
  the data says 7. Every count in the proposal is now recomputed from the runs' JSON.
- **PR #142** (draft, docs only, `docs/cold-start-ecu` → `main`). The first push got no CI:
  #138 merged and it conflicted. After merging `main` in, **CI at `d7ea5ef`: 10 of 10, every
  job read.** Physics 102 / 0 / 3 known on 3.10 and 3.12; Pyodide 81 / 0 / 2 known / 21
  skipped; units 162 (29 files) and prepare-assets offline 4 / 0; golden fixtures + TS ports,
  SolverPort, the three e2e jobs and claude-review pass. The counts equal #138's, as a docs
  change should.
- **Next:** the owner's three answers, then the build. Still waiting from
  before: merging #139–#141 (#138 merged), #141's listen, FINDING-033, and P07/P11/P12 (never looked at).

*(Was: "Session 11, the cold-start ECU proposal being measured", the entry below.)*
- *The in-progress record:*
- **Start of session:** the four open PRs (#138 P06, #139 P01 driving, #140 B-07, #141 B-08)
  are each CI 10 of 10 and wait on the owner (#141 also on the owner's ear, `out/b08/`). The
  bug sheet has no new rows (B-09 on empty). Its Feat Prop tab has three priority-1 rows never
  looked at: **P07** (multi-parameter sweep), **P11** (number of gears), **P12** (vehicle
  weight).
- **Taken:** PLAN's "next proposal", FINDING-031 C (the owner, 2026-10-16), a cold-start ECU.
  FINDING-033 A waits for #138 (both touch `live.py`).
- **Measured so far** (scratch `ecu.py`, a `LiveEngine` subclass with three hooks; with them
  off it equals `LiveEngine` on 0 of 24,000 values, three engines and boxes):
  - 24 cold launches (crdi15/crdi22/hatch15, TC/DCT, 25/0 °C, 20/30%) × 9 variants, on
    today's (R5) grids. `main`: ~~9~~ **7** of 24 never reach 10 km/h in 60 s (*corrected
    the same day: I miscounted from the table; `claims.py` counts it from the data*). Every variant with the
    friction cover (the pedal's fuel raised by live friction minus the warm cells') moves
    all 24 (crdi15 TC 0 °C 20%: never → 13.0 s; with the cold walls' deficit too 7.9 s).
    Fast idle alone, or a 15 s chamber constant (option B), leaves most 0 °C / 20% stuck.
    Fuel over the minute: ~2.5–3× the stuck baseline.
  - The friction excess at coolant 70 °C with the oil lagging (42 °C) is still 6–54 N·m
    across the roster; at a warm engine (88 / 100 °C) it is −0.02 to −0.27 on all ten. ~~So
    the gate should read **oil**, not coolant (being measured).~~ *Corrected the same day
    (my hypothesis was wrong):* in the live loop the oil does not lag; it runs ~2 K ahead of
    the coolant (crdi15 TC, 0 °C start, 30% / lift for 12 min). A warm engine's oil cools to
    ~85 °C on that drive, so an oil gate (60–90 °C) wakes in warm driving: 234,600 of
    259,200 warm values change (ungated: 248,328, +0.4% fuel). **The coolant gate (40–70 °C)
    keeps warm driving bit-identical (0 of 259,200)** and drops at most ~0.008 load of cover
    by minute 7. 12 min from 0 °C: 0.508 L covered, 0.447 `main`, 0.479 warm.
  - **The warm reference** (same harness): crdi15 TC 20% warm 7.4 s / 57 km/h at 60 s /
    36 mL; at 0 °C with the cover (friction + walls) 7.9 s / 58 / 53 mL. The cover gives a
    cold engine a warm one's launch for ~45% more fuel. **Fast idle +200 overshoots** (4.3 s,
    quicker than warm), because `main`'s governor acts with the pedal down too (up to 0.75
    load below target). EDC16's idle control acts only with the pedal up; that variant is
    being measured. *(Measured: with the pedal up only, every TC launch equals the cover
    alone; the ~45% is 11–51% over the 20% cases.)*
- ~~**Running:** all ten engines' idle and 20% launch; the 24 cold launches with pedal-up fast
  idle.~~ Done; in the proposal.
