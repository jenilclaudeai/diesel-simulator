# PROPOSAL — P14: add at least ten popular diesel engines

**Date:** 2026-10-28. **Status:** ~~measured; **four questions for the owner** (end).~~ **Decided (the owner, 2026-10-28): "Go with all your recommendations"** (ADR-023): the listed ten, N2, F2, V2, two unstacked PRs. Question by question, the same day: "Most popular onces / N2 / F2 / V2"; V2 is the pickup vehicle, which only the listed ten's pickups need, so that is read as the listed ten. Batch 1 merged (#147); batch 2 being built.
Nothing built in this proposal's PR: no file in `engines/`, `dieselsim/` or `web/` changes.
**The sheet's P14** (priority 1, no status yet): "Add few more engines: add atleast 10
popular diesel engines."
**Lenses:** PM, LEAD, PHY1, SW1, SW2, QA1, QA2, USR1
**Measured on** `main` at `df36a05` (#145). The scripts are in `tools/p14/` (README there),
so the build can rerun them.

---

## What "an engine" costs today

The Enjoy roster is five engines (ADR-008, ADR-012), each:
1. a brochure file `engines/<key>.json` (`builder.build_engine`'s headline numbers and
   optional tuning);
2. a tuning pass until `verify()` holds the plateau, recorded in `engines/ROSTER.md` and
   re-checked by `test_roster_engines_make_their_numbers`;
3. a vehicle: a `case` in `live.Vehicle` and in `web/physics/src/live/vehicle.ts`, and the
   vehicles fixture's keys (`gen_fixtures.py`);
4. a converged warm + cold 8 × 6 grid with its weather table (`build_live_grids.py`,
   then `--weather`), ~5.3 MB, 1.06 MB gzipped, in `web/app/public/grids/`;
5. a line in `web/app/src/app/enjoy/roster.ts` (`/enjoy`'s `<select>`) and in the test
   file's `ROSTER`.

No solver change is needed. A new `engines/*.json` is not hashed (`bridge.grid_hash`
covers `dieselsim/` only), so the ten shipped grids stay current.

## Can the builder make real engines' numbers?

The check is the roster test's own: at the plateau's start ≥ 95% of the rating cap, at
rated speed within 3% of the brochure power, fresh engine per point, 9 cycles. Each
candidate was run untuned and with the roster's usual tuning (`boost_map_rise` 0.12,
`afr_limit` 16 LD / 18 HD, ROSTER.md). **The five shipped engines were run alongside as
controls: 5 of 5 pass**, and hatch15 / crdi22 reproduce ROSTER.md's plateau-start
figures within 0.1 points (96.6 / 96.5% against 96.7 / 96.6%).

**The candidates' figures are from memory, not yet sourced.** The point is whether the
builder copes with each kind of engine, not the last newton-metre. The build sources each
from the maker's sheet first.

| key | engine | layout | best variant | plateau start % of cap | rated kW / brochure | pass |
|---|---|---|---|---|---|---|
| `vw19tdi` | VW 1.9 TDI (ALH), 90 ps, 210 N·m | I4, pump | untuned | 99.7 | 65.8 / 66 | yes |
| `ddis13` | Fiat 1.3 Multijet / Maruti DDiS 190, 75 ps, 190 N·m | I4 | (none) | 88.7 at best | 55.4 / 55 | **no** |
| `mhawk75` | Mahindra mHawk75 1.5 (Bolero), 75 bhp, 210 N·m | **I3** | tuned | 100.2 | 55.6 / 56 | yes |
| `revotorq105` | Tata 1.05 Revotorq, 70 ps, 140 N·m | **I3** | untuned | 100.0 | 52.0 / 51.5 | yes |
| `mhawk22` | Mahindra mHawk 2.2 (Scorpio-N), 175 ps, 400 N·m | I4 | tuned | 100.3 | 129.0 / 129 | yes |
| `gd28` | Toyota 1GD-FTV 2.8 (Fortuner, Hilux), 204 ps, 500 N·m | I4 | tuned | 99.5 | 150.7 / 150 | yes |
| `duratorq32` | Ford 3.2 Duratorq (Endeavour, Ranger), 200 ps, 470 N·m | **I5** | untuned | 99.9 | 146.2 / 147 | yes |
| `b57` | BMW B57 3.0, 265 ps, 620 N·m | I6 | 0.08 / 16.0 | 95.9 | 196.8 / 195 | yes |
| `om642` | Mercedes OM642 3.0, 258 ps, 620 N·m | **V6** | 0.08 / 15.5 | 97.4 | 190.8 / 190 | yes |
| `cummins59` | Cummins 5.9 12-valve (6BT), 215 hp, 597 N·m | I6, pump | untuned | 99.8 | 159.4 / 160 | yes |
| `cummins67` | Cummins 6.7, 370 hp, 1,152 N·m | I6 | tuned | 99.3 | 275.5 / 276 | yes |
| `duramax66` | Duramax 6.6 (L5P), 445 hp, 1,234 N·m | V8 | tuned | 102.0 | 330.6 / 332 | yes |
| `powerstroke73` | Power Stroke 7.3, 275 hp, 712 N·m | V8, no pilot | untuned | 99.6 | 204.5 / 205 | yes |
| `bullet325` | Royal Enfield Bullet Diesel 325 cc, 6.5 bhp, 15 N·m | single, NA | untuned | 99.5 | 4.8 / 4.8 | yes |

**13 of 14 pass:** six untuned, five with the roster's tuning, two (`b57`, `om642`) with
v8hd's harder `boost_map_rise` 0.08 and `afr_limit` 16.0 / 15.5. At 0.12 / 16 the B57 sat at
95.0% and the OM642 at 92.7%. "Best variant" is the least tuning that passes. 162 solves,
~3 min on 8 cores.

**Real geometry doesn't break it.** The screen used the builder's default stroke/bore 1.05
and compression ratio. It was re-run with approximate published bore × stroke and CR (also
from memory, a sensitivity check only) for nine of the recommended ten (not `mhawk75`,
whose geometry I don't know) and the OM642: **10 of 10 still pass**. The plateau start
moves by 0.9 points at most at the same tuning (`p14_geom_delta.py`).

**The 1.3 DDiS can't be made today.** At 2,000 rpm (Maruti quotes its 190 N·m there) the
best of six tunings gives 88.7% of the cap. Its fuel swept directly, bypassing the
calibration: 26 mg gives 116.6 N·m at AFR 22.7 and boost 1.40 (a VGT gives 1.48), where
190 N·m needs ~43 mg (the sweep's slope, extrapolated). crdi22 has boost ~1.9 at 1,873 rpm. So it is the air: the builder
sizes the turbo for rated flow, and on a small, high-revving engine that leaves too
little boost at 2,000. It is the wall hatch15 met (its plateau was moved from 1,750 to
2,000, ROSTER.md). Fixing it means changing `builder.py`, which is hashed: every grid goes
stale, so a ~7 h rebuild (~16 h once the roster has twenty). That is its own decision,
not P14's.

**Odd cylinder counts sound right.** The roster has only ever shipped 1, 4, 6 and 8
cylinders. Through the live synth (pure, as the app's port runs), the two I3s, the I5 and
the V6, against crdi22 as control: all finite, rms 0.039–0.098, and each spectrum's
strongest peak below 400 Hz is a whole harmonic of its own firing frequency (I3 ×2.00,
I5 ×2.00, V6 ×1.00, the I4 control ×3.01). One cell each, not a drive, and not the TS
synth: the build checks those.

### What the model can and can't represent

- **Faithfully:** direct-injection inline 1 to 6 cylinders, turbocharged (VGT or
  wastegate) or not, common rail or a pump (`pilot: false`, `rail_bar`). The builder
  already takes the bore/stroke ratio, CR, turbo type and firing order.
- **Approximately:** V engines. The firing interval is right, but there are no separate
  banks, so a cross-plane V8's burble is absent (stated in ROSTER.md for v8hd). A V6
  sounds like an I6 here, so `om642` is close to a second `b57`. HEUI injection (Power
  Stroke) is modelled as a pump without pilot. Twin and two-stage turbos are modelled
  as one turbo.
- **Not at all:** indirect injection (prechamber, swirl chamber). That rules out the
  Mercedes OM617, Toyota 1HZ, the old Ambassador/Indica-era diesels, and the IDI 6.9 / 7.3
  Fords. Ten or more cylinders would need an explicit firing order (the builder's table
  stops at 8).
- **Old engines run lean at full load.** `vw19tdi`, `cummins59` and `powerstroke73` sit at
  AFR 25.7–27.6 at the plateau start. Real ones run ~18–22. The brochure caps their fuel well
  below the smoke limit, as ROSTER.md says of single10.

### A trap found on the way (silent)

A roster grid doesn't record a vehicle. The worker takes it from the key, through
`live.Vehicle(preset)`, and **every key it doesn't know drives the 3 t utility
tractor**. Checked: `Vehicle("gd28")` and `Vehicle("cummins67")` both give "3 t utility
tractor, 3000 kg", with no error. The custom-engine path (`--engine`) records
`"vehicle"`, but the roster path doesn't. So every new roster key needs its `case`, in
Python and in TS, and the build adds a test that each roster key drives the vehicle its
JSON names (mutant: drop one `case`).

## What it costs

| | measured | for ten engines |
|---|---|---|
| tuning screen per engine | ~6–14 s a solve; the whole screen ~3 min | done here; re-run once the figures are sourced |
| grid build, native (this M2, 6 workers) | P09's per-grid log × R5's speed-ups (ADR-020) | I4 ~42 min, I3 ~32, I5 ~51, I6 ~57, V8 ~73; **the recommended ten ≈ 8.8 h** |
| **every later full rebuild** (a solver change) | R5's rebuild of today's ten: 7.2 h | **~16 h** for twenty |
| Pages and the phone | grids load one at a time when picked (`live-session.ts`); no service worker | the site +53 MB raw (1 GB limit); **a user still downloads only the engine they drive** (~1 MB gzipped) |
| repo | the whole pack is 18 MiB today | +~10 MB compressed per full rebuild of twenty |
| CI, physics jobs | of the 13 tests that read grids or the roster, only `test_roster_engines_make_their_numbers` grows: 72.3 s for five | **+~2.5 min** per job (this Mac) |
| CI, Pyodide (57.5 of its 60 min) | those tests SKIP there (no `engines/`, no grids) | **+0** |
| vehicles | a `case` per key (Python, TS); a new vehicle is ~20 lines each side plus the fixture | 0 new for engines that fit today's six vehicles; 1 for the pickups |

The rebuild is the cost that lasts. P13 (R5) made a grid ×1.34 faster, and P14 more than
doubles the count. `tools/rebuild_cold_cells.py` and `tools/restamp_grids.py` still cut
narrow changes short, as they do today.

## Options

### Which ten (question 1)

**Recommended, "a garage enthusiasts know", six on today's vehicles and four on one new
pickup:**

| | key | character | vehicle |
|---|---|---|---|
| 1 | `vw19tdi` | the 1990s TDI: pump, no pilot, light car | `hatch15` (1.3 t hatchback) |
| 2 | `mhawk75` | **first three-cylinder**, India's Bolero | `ld_i4` (1.75 t) |
| 3 | `mhawk22` | modern Indian SUV | `crdi22` (1.9 t SUV, 8-speed) |
| 4 | `gd28` | Fortuner / Hilux | `crdi22` |
| 5 | `duratorq32` | **first five-cylinder**, Endeavour / Ranger | `crdi22` |
| 6 | `b57` | premium smooth six | `ld_i4` |
| 7 | `cummins59` | the 12-valve legend: pump, clatter | **new: full-size pickup** |
| 8 | `cummins67` | modern torque monster | new pickup |
| 9 | `duramax66` | modern V8 | new pickup |
| 10 | `powerstroke73` | old V8, no pilot | new pickup |

- **Positives:** six new characters (I3, I5, a pump I4, a car I6, pickup I6, pickup V8);
  India's market and the US pickup icons both covered; every one passes measured.
- **Costs:** two V8s that differ by injection more than by layout (no banks); the four
  pickups need a vehicle that doesn't exist.

**Alternates, any of them for any of the ten:**
- `revotorq105`: a second I3, close to `mhawk75` in sound;
- `om642`: the V6, close to `b57` here;
- `bullet325`: a cult classic, but it needs a **motorcycle** vehicle (~190 kg, a 4-speed,
  chain), a new kind;
- `ddis13`: needs the builder change above.
- Or any engine the owner names, checked the same way in minutes.

### Names (question 2)

- **N1, real names as the label** ("Toyota 1GD-FTV 2.8, 204 ps").
  - Positives: recognisable, which is the point of "popular", and enthusiasts search for
    them.
  - Costs: a maker's trademark on a product that is heading for paid app stores; it
    implies a fidelity the model doesn't have (scaling-law hardware, generic sound
    shaping), and invites "my Fortuner doesn't sound like that".
- **N2, a descriptive label plus the source** ("SUV · 2.8 L four, 204 ps", and under it
  "modelled on the published figures of Toyota's 1GD-FTV").
  - Positives: still recognisable; honest about what it is; consistent with today's
    roster labels.
  - Costs: one more line on `/enjoy`; it still names the maker, by reference.
- **N3, descriptive only**, as today.
  - Positives: no brand question at all.
  - Costs: most of "popular" is lost; the ten read like more of the same.

Recommended **N2**. Whether naming a maker by reference is fine in a paid app is a
question for legal advice before an app-store release, not one this proposal can answer.

### Fidelity (question 3)

- **F1, the brochure only**, as the roster does today (displacement, cylinders, rated
  speed, peak torque and power, plateau). Positives: what's measured above; quickest.
  Costs: every engine gets the builder's default bore/stroke and CR.
- **F2, the brochure plus published hardware**: bore × stroke, CR, VGT or wastegate, pump
  or common rail, pilot. These are all builder parameters already, so no code changes.
  Each figure is sourced and cited in ROSTER.md. Positives: closer to the real engine, and
  measured above to keep every pass. Costs: a source per engine, maybe an hour each.

Recommended **F2**.

### Vehicles (question 4)

- **V1, today's six only.** The pickups would drive the 1.9 t SUV, and a Cummins 6.7 in it
  would be absurdly quick. Not recommended.
- **V2, one new vehicle**, a full-size pickup (~3.2 t, 6-speed automatic, ~0.41 m wheel,
  CdA ~1.6, all to be sourced), for the four pickup engines; the rest reuse today's.
  Positives: one vehicle's work (Python, TS, fixture); every engine in a plausible body.
  Costs: the SUVs share one vehicle, so `gd28` drives a 1.9 t SUV, not a 2.2 t Fortuner.
- **V3, a vehicle per engine**, as ADR-012 did for the first five. Positives: most
  faithful. Costs: ten vehicles' work; each moves the vehicles fixture.

Recommended **V2**.

### Delivery (stated, not a question)

Two PRs, **not stacked** (stacked merges have landed on dead branches here before):
batch 1, the six on today's vehicles (~4.4 h of building); then, once it has merged,
batch 2, the pickup vehicle and its four (~4.4 h). Each is drivable on the live site as
soon as it merges.

## Acceptance, per engine (for the build)

1. Its figures sourced and cited in ROSTER.md; `verify()`'s achieved against requested
   recorded there, with the tuning and the reason for it.
2. `test_roster_engines_make_their_numbers` covers it (plateau start ≥ 95%, rated ±3%).
3. Its grid: `test_roster_grids_match_their_engine_files` and
   `test_shipped_grids_cold_friction` (≤ 4×) pass; the unsettled cells and the Leh check
   are stated. Another misfire cliff like single10's 36% (FINDING-027) is reported to the
   owner, not shipped silently.
4. The new test: each roster key drives the vehicle its JSON names, held to TypeScript.
   Mutants: drop a `case`; point a key at the wrong vehicle. Both must be caught against a
   passing baseline.
5. `/enjoy`'s list grouped (`<optgroup>`: cars and SUVs, pickups, trucks, tractor), and
   the e2e opens every new engine once and drives off.
6. The owner listens on the phone, as for P10.

## Lens review

- **PM:** the ten fit a week of evenings, mostly unattended building. The lasting cost is
  ~16 h per full rebuild from now on, so take P14 *after* any solver change already in
  view (the cold-start ECU is `live.py` only, so it doesn't collide). Two batches give
  something drivable after the first.
- **LEAD:** no ADR is reopened. ADR-008 (a curated roster built with `builder.py`, each
  `verify()`-checked) and ADR-012's pattern carry over. V2 is a smaller step than
  ADR-012's one vehicle per engine, so it should be recorded in the ADR that P14 gets.
- **PHY1:** 13 of 14 hold the roster's bar. Two needed harder tuning, and the DDiS's
  shortfall is air, measured. V engines without banks and IDI are honest limits, and the
  lean old engines should be stated. A sourced CR may move each engine's knock (P09),
  and the listen covers that.
- **SW2:** the silent tractor fallback is the one real hazard; the vehicle test closes
  it. Keep the candidates out of `engines/` until sourced: the directory is
  auto-registered.
- **SW1:** `roster.ts` plus an `<optgroup>`; `vehicle.ts` gets a `case` per key and one
  new vehicle.
- **QA1/QA2:** acceptance above. The roster test grows ~2.5 min per physics job, and
  Pyodide is unaffected.
- **USR1** (advisory, see TEAM.md): fifteen engines in one unlabelled list is a wall.
  Group them, and put the vehicle in each label ("Pickup · ...").

## Questions for the owner

1. **Which ten?** The recommended ten above, or swap in any alternate (the second I3,
   the V6, the Bullet with a motorcycle vehicle) or an engine you name.
2. **Names:** N1 real names, **N2 descriptive plus "modelled on …" (recommended)**, or N3
   descriptive only?
3. **Fidelity:** F1 brochure only, or **F2 brochure plus published bore, stroke, CR and
   hardware (recommended)**?
4. **Vehicles:** **V2, one new pickup vehicle (recommended)**, or V3, one per engine?
