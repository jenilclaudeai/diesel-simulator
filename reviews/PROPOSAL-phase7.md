# PROPOSAL — Phase 7 (Environment and projects): plan and scope

**Date:** 2026-10-06 (session 7)
**Status:** for the owner's decision. Nothing here is built yet.
**Lenses:** PM, LEAD, PHY1, PHY2, SW1, SW2, QA1, QA2, USR1/2 (advisory)

PLAN.md's Phase 7:
- **Environment:** country/season presets → ambient temperature, pressure,
  altitude, fuel cetane and cold-flow. "Very close, not perfect" is the
  accepted bar.
- **Humidity** affects NOx and is not in the solver today: add it, or state
  its absence.
- **Projects:** save/load as JSON (OPEN-C, decided by ADR-007: engine spec +
  vehicle + gearbox; the grid is not bundled).

Also routed here: REVIEW-008 m-3 (spec edits are lost on reload), and
FINDING-025's open question (the ECU at altitude). The owner's new feature
proposals (the bug sheet's "Feat Prop" tab) are covered in their own
section, because four of the five are outside v1 as PLAN defines it.

---

## Where it stands, measured today

All numbers are crdi15, through `bridge.solve_point` as the app calls it,
on #101's code (FINDING-025 fixed), unless marked.

| piece | state | evidence |
|---|---|---|
| ambient pressure and temperature, solving pages | **works once #101 merges** | before #101 an edit moved 0 of 8 outputs (FINDING-025). After: 2000 m −6.7% torque at full load, soot +88%; −10 °C +1.3%; 40 °C −0.4% |
| ambient, the live loop (Drive, Enjoy) | **partly** | `live.py` reads `ambient_T` for the cold start, the radiator and the charge-air cooler, and derates torque by charge-air density (`_protect`, clamped ≤ 1: it can't add torque). `ambient_p` reaches nothing live. The roster's grids are solved at 101325 Pa / 298 K |
| altitude | via pressure only | no altitude field; pressure is the input. A preset would give both (≈ 101325·(1 − 2.26e-5·h)^5.26) |
| cetane | **works, small** | 40 → 55: torque and BSFC under 0.3%, NOx +6.6% / −7.5% (lower cetane, longer ignition delay, more NOx: the right direction). Its visible effects (hard cold starts, white smoke, knock) are not modelled |
| cold-flow (CFPP, waxing) | **absent** | no solver or live-loop reader |
| humidity | **absent** | no field; PLAN says add it or state it |
| the ECU at altitude | **uncompensated** (#101) | the rating is calibrated at standard air; the same pedal gives the same fuel in any air. At 3000 m: 198 N·m (−12%), soot 2.9×. The smoke map assumes 101325 Pa (`cycle.fuel_smoke_limit`) |
| project file (ADR-007) | **pieces exist** | "Export spec (JSON)" on `/spec`; a brochure engine's JSON and its grid file on `/drive`. There is no single file with spec + vehicle + gearbox (+ environment) |
| persistence (m-3) | **custom engines only** | "Your engines" persist in IndexedDB (`my-engines.ts`). `/spec` edits and the last results live in memory: a reload loses them, and the page doesn't say so |

### Three measurements that shape the design

**1. Can Drive correct a standard-air grid for the weather, rather than
rebuild it?** A naive density ratio cannot: at 2000 m and 40 °C it predicts
−25% torque at every cell. The converged solver says −9.4% to +4.7%, because
the turbo makes up most of the loss. A per-cell table fitted from three airs (79.5 kPa;
263 K; 313 K) and checked on two held-out airs (79.5 kPa + 40 °C; 90 kPa +
10 °C), over 9 cells (1200/2000/2800 rpm × 30/70/100% load):

| solves | fitted table, worst error | density ratio, worst error |
|---|---|---|
| fast (9 cycles, as the solving pages) | 3.76% | 32.6% |
| **converged (200 cycles, as Drive's grids)** | **1.15%** | 28.7% |

*(2026-10-08: true of #101's code, which this measured. On `main` after
#107, a 12-air table is 20.3% off in torque, mostly from FINDING-026, a
defect in the modern ECU. Step 4 re-measures it after the fix.)*

**2. On the fast pages, part-load "weather effects" can be convergence
error.** At 2800 rpm / 70%, the fast solve said a cool 90 kPa hill gives
**+12.4%** torque. Converged, 90 kPa gives −0.6% (159.6 → 158.6 N·m). The
fast solve at *standard* air is itself 11% low (141.5 vs 159.6), because its
EGR loop hasn't settled (9.5% EGR against 5.35% converged; exhaust 4.5 bar
against 2.47). This is FINDING-013's known part-load gap (RMS 13.5%, worst
−38.8%), not new. But it means a weather comparison at part load on Dyno,
Grid, Cycle or Sweep can show an artifact larger than the weather. Full-load
pulls are much closer, and the Dyno page already states its measured gap.

**3. Converged, light load still gains torque in thin air, and the boost
control is the reason.** At 2800 rpm / 30%, converged, a 90 kPa / 10 °C hill
gives **+8.2%** torque (54.8 → 59.3 N·m). Gross IMEP is flat (−0.3%); the
gain is all pumping (PMEP −1.07 → −0.69 bar).
- The VGT and wastegate hold a **pressure ratio**, `p_intake / p_amb`
  (`turbo.py:173`), so in thin air the absolute intake and exhaust pressures
  both fall: exhaust 3.61 → 2.88 bar.
- With EGR forced off the gain is +2.7%: EGR is why the exhaust is held
  high.
- Real ECUs target **absolute** boost pressure (a MAP sensor). This is a
  second ECU assumption FINDING-025 has made visible, next to the smoke
  map's fixed 101325 Pa. Both belong to the altitude decision below.
- Side note for PHY1, not measured against data here: at standard air the
  converged EGR costs 13% torque at fixed fuel at this point (BSFC 226 →
  261 g/kWh at 14% EGR). Published EGR fuel penalties are usually a few
  percent. Worth a look on its own.

## The work, in order

1. **Environment presets** (country/season), a small table in Python:
   ambient pressure (from altitude), temperature, fuel cetane, fuel grade
   (summer/winter/arctic CFPP). Shown with their numbers, editable.
   Physically a preset is just spec values (`thermal.ambient_*`,
   `inj.cetane_number`), plus a CFPP for the live loop.
2. **Environment on the solving pages:** a preset picker on Dyno, Grid,
   Cycle, Sweep and Durability. With #101 merged, it's spec overrides; no
   solver change. **Label part-load comparisons** with FINDING-013's
   measured gap (measurement 2), or restrict weather comparisons to full
   load, the converged-close case.
3. **Environment in Drive and Enjoy:** see options A–C below.
4. **The ECU at altitude** (FINDING-025): see options below.
5. **Humidity:** see options below.
6. **Cold-flow:** below the fuel's CFPP, the filter waxes and the engine
   starves. In the live loop: a fuel-flow cap that falls as the fuel
   temperature drops below CFPP, warming with the engine (a few lines in
   `live.py`, mirrored in the TS port with a fixture). Summer diesel at
   −15 °C won't start, or starts and dies, which is what really happens.
7. **Projects (ADR-007):** one JSON file: engine spec (as overrides on a
   preset or a brochure), vehicle, gearbox, environment, with a format
   version. Save, load and share. Loading a project with a custom engine
   says up front that the drivable grid must be rebuilt (ADR-007), unless
   it's already in the IndexedDB cache.
8. **Persistence (m-3):** autosave the current project, including `/spec`
   edits, to IndexedDB, and restore it on reload. Say so on the page.

## Options

### Environment in Drive and Enjoy

| option | how | costs | gives |
|---|---|---|---|
| **A. A correction table per engine (recommended: 1.15% worst, converged, measurement 1)** | per grid, a small table of torque factors at a few airs, fitted from converged solves at a coarse subset of cells, interpolated at run time like the derate already is | per engine: ~9 cells × 4 airs = 36 converged solves, ~14 min on one core natively (measured ~24 s each); a few kB per grid. In the browser on ADR-014's worker pool (104 converged pieces in 21.5 min on 8 cores), ~7–8 min; or skip it for custom engines and say so | every weather, on every roster engine, at the measured accuracy; sound and friction stay the grid's (standard air) |
| B. A grid per environment preset | build the 5 roster grids for each preset | about 1.2 h of native build and 26.5 MB in git per preset, per solver change (measured: 3.6–20.5 min and 5.3 MB per grid). Custom engines: 21+ min per preset in a browser | exact (converged) in each preset, sound included; but only the presets, and every solver change multiplies |
| C. Solving pages only | Drive and Enjoy stay at standard air; the environment shows on the analysis pages | nothing more | honest and cheap; but the drive, the part people enjoy, ignores the weather |

### The ECU at altitude (FINDING-025's question)

| option | behaviour at 2000–3000 m | gives |
|---|---|---|
| **1. Uncompensated (what #101 ships)** | same pedal, same fuel: torque falls 6–12%, smoke rises 2–3× | an old mechanical pump without an altitude compensator; simplest; the smoke is the lesson |
| 2. An ECU that knows absolute pressure | the boost target becomes absolute (MAP), and the smoke map reads absolute manifold pressure (not a scheduled PR × 101325 Pa): at altitude the turbo works harder up to a speed limit, fuel is trimmed to the air, smoke stays near sea level, and light load no longer gains torque (measurement 3) | a modern ECU with MAP and baro sensors; two changes (`turbo.py` boost control, `cycle.fuel_smoke_limit`) and their tests. Nothing moves at standard air if the absolute target equals the ratio × 101325 Pa, so the grids would be re-stamped, not rebuilt (to be proven, as for FINDING-025) |
| 3. Torque-based | the pedal asks for torque; fuel rises until the smoke limit binds | modern ECU feel (the engine "holds" torque at part load); the most change: the pedal map becomes torque, which touches the live loop and every grid |

Recommendation: **2 for the common-rail engines, 1 for the mechanical
single** (a per-engine "ECU: modern / mechanical" choice). Measurement 3
shows the uncompensated ratio control gives more torque from thinner air at
light load, which nobody would believe on a modern engine. 3 changes what
the pedal means everywhere, for little an enthusiast would notice that 2
doesn't give.

### Humidity

| option | costs | gives |
|---|---|---|
| **a. NOx humidity correction factor (recommended)** | ISO 8178's K_H factor (also in 40 CFR 1065) on reported NOx; one field (relative humidity) in the preset | NOx moves with humidity the way test cells correct it; nothing else changes; cheap and honest |
| b. Water vapour in the intake charge | composition, γ and dilution through the cycle; touches thermo and every golden value | the physical effect on everything (small on torque); a large change for a small effect |
| c. State its absence | a line on the page | PLAN allows it; but a preset with "humid" would then do nothing visible |

### The owner's feature proposals ("Feat Prop" tab, read 2026-10-06)

| proposal | owner's priority | fits v1? | what it would take |
|---|---|---|---|
| P01 Vibrations (mobile) | 3 | **yes** | `navigator.vibrate` in `/enjoy`, patterned on firing frequency and load (from the live loop's sources); Android Chrome only (iOS Safari has no Vibration API). A Phase 7 or 8 extra, a day or two |
| P02 Google sign-in | 2 | **no** (PLAN: accounts out of scope for v1) | an auth provider; a backend or a third-party BaaS; privacy policy |
| P03 Free/paid roles | 3 | **no** (payments out of scope) | P02 plus billing and entitlement checks |
| P04 Grid on a backend | 1 | **no** (backend out of scope; the grid-build plan is deferred until v1) | a build server, its cost and queueing; `PROPOSAL-grid-build.md` already weighs it |
| P05 Grid on AWS Lambda | 3 | **no** (same) | P04 on serverless: cold starts, 15-min limit per invocation (a grid is 3.6–20.5 min natively: it would have to be split per cell, which ADR-014's pieces already allow) |

Two questions before any of them: is 1 the highest priority or the lowest
(the empty rows default to 1)? And are P02–P05 a "v2" list, or a change to
v1's scope? The latter would reopen PLAN's out-of-scope list and ADR-003's
static hosting, so it needs its own decision.

## Lens notes

- **PHY1/PHY2:** environment changes the air, not the engine. Cetane and
  CFPP are the fuel's. Compare weather on converged solves or at full load
  (measurement 2). Name the reference air on every page that shows a
  weather delta. Humidity: say which factor, and that it is a correction,
  not a cycle effect.
- **SW1/SW2:** presets live in Python (one source), exported to the app via
  the bridge, like `describe_spec`. The correction table (option A) is data
  in the grid file, read by the live loop in both Python and TS, with a
  golden fixture. The project file gets a version number from day one.
- **QA1/QA2:** each preset gets a test that its numbers reach the solve
  (FINDING-025's lesson: grep the readers, then solve with it changed).
  Mutation-test the correction table's interpolation and the CFPP gate.
- **USR1/2 (advisory):** pick a place, not numbers: "Leh, winter" or "Dubai,
  summer", with the numbers shown and editable. The cold-flow stall needs a
  clear message ("fuel waxed: winter diesel needed below −5 °C"), or it
  looks like a bug.

## Decisions needed

1. **Environment in Drive and Enjoy:** A (recommended), B or C.
2. **The ECU at altitude:** 1, 2 for modern engines and 1 for the
   mechanical single (recommended), or 3.
3. **Humidity:** a (recommended), b or c.
4. **Cold-flow in the live loop:** yes (recommended) or no.
5. **Presets:** which places and seasons. A proposal: sea level temperate
   (standard), hot desert summer, cold continental winter, high plateau
   (≈ 3500 m), humid tropics. Five, each a real place.
6. **The "Feat Prop" list:** v1 or v2 for each; and the priority scale.
