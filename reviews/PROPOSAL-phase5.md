# PROPOSAL — Phase 5 (Enjoy mode): plan, and the roster (OPEN-F)

**Date:** 2026-09-29 (session 5, part 7)
**Status:** for the owner's decision. Nothing here is built yet.
**Lenses:** PM, LEAD, USR1/2, SW2, PHY2

PLAN.md's Phase 5: prebuilt grids, no Pyodide, no spec editing, instant
start. A dashboard with tachometer, speedometer, a gear indicator with
**shift phase**, warning lamps, vitals, thermal stack and a trip computer
whose economy is labelled **steady-state** (FINDING-009). **Exit criterion:**
loads and drives on a mid-range phone in landscape, with audio, without ever
fetching Pyodide.

---

## Where it stands, measured today

| exit-criterion part | state | evidence |
|---|---|---|
| no Pyodide | **holds** | `/drive` on an emulated phone (844 × 390, touch) made 7 requests: the page, its JS and CSS, the grid, the loop worker. 0 were Pyodide or solver files. |
| audio fits a mid-range phone | **holds, by emulation** | #68: the synth uses 8% of the audio thread at 4× CPU throttling (DevTools' "mid-tier mobile"), and 0–1 of 3,445 blocks run over. |
| loop fits | **holds at 4×** | Live friction takes 11 of 16.7 ms per friction frame at 4×, in the loop worker. At 6× it takes a whole frame (low-end phones only). |
| **drives on a phone** | **does not** | Throttle, brake, clutch and gears are keyboard-only. The only buttons on `/drive` are Restart, Sound and Record. **Touch controls are the largest missing piece, and PLAN.md does not list them.** |
| landscape layout, dashboard | not started | `/drive` is a minimal readout page (Phase 3's decision). |
| a real phone | not tested | Emulation is a stand-in. The exit needs a real mid-range phone. |

## The work, in order

1. **Roster (OPEN-F).** This decision is needed first, because each engine
   costs a vehicle, a tuning pass and a grid build (below).
2. **Touch controls.** An on-screen throttle and brake (hold to press,
   analogue by position), shift up/down, and clutch for the manual. Keys stay
   as they are. The loop already takes pedal positions, so this is UI only.
3. **Enjoy route.** A new `/enjoy` (or `/drive` reworked): pick an engine,
   start, and nothing to configure. `/drive` stays as the development page.
4. **Dashboard.**
   - tachometer and speedometer (canvas or SVG, drawn at the display rate
     from the 60 Hz state);
   - a gear indicator showing the shift phase (torque phase, then inertia
     phase), which the loop already tracks (`gb.phase`);
   - warning lamps (overheat, derate, low fuel, stall);
   - vitals (oil and coolant temperature, boost);
   - the thermal stack;
   - the trip computer, its economy labelled steady-state (FINDING-009).
5. **Landscape and mobile.** Layout, the audio-start gesture on iOS Safari,
   and a wake lock while driving.
6. **A real phone.** The exit check, with `npm run perf`'s numbers beside it.

## The roster: what each engine costs (measured)

| cost | per engine | evidence |
|---|---|---|
| a converged grid build, warm and cold | 3.5–15 min | the rebuilds of 2026-09-28: `single` 216 s … `hd_i6` 889 s |
| download | 0.9–1.4 MB gzip | crdi15 1,003 KiB; single 1,424 KiB |
| a vehicle | Python + TypeScript + fixture | `live.Vehicle` knows `hd_i6`, `ld_i4` and `crdi15`; **every other engine falls through to a "3 t utility tractor"** |
| a tuning pass | an hour or so each, by estimate | `verify()` today, below |

`verify()` on the two builder engines already in `engines/`, from brochure
numbers (ADR-008 requires this record):

| engine | requested | achieved | plateau held? |
|---|---|---|---|
| `crdi22`, 2.2 L I4 | 360 N·m, 110 kW, plateau 1750–2750 | 362.9 N·m (100.8%), 109.5 kW (99.5%) | **no**: 85% of the cap at 1,873 rpm (boost 1.73); full torque from ~2,380 |
| `v8hd`, 15 L V8 | 2600 N·m, 440 kW, plateau 1000–1450 | 2508 N·m (96.5%), 431 kW (97.9%) | **no**: 82% at 1,133 rpm; the peak is at 1,567, above the plateau |

The builder gets the peaks within 3.5%, but not the torque shape: both lose
low-end torque, as `builder.py` warns (`afr_limit`, `turbine_area_eff` and
`boost_map_rise` are the knobs). A roster engine that is meant to feel like
a diesel needs its low end tuned.

## Roster options

Each engine is built with `builder.py` from brochure numbers (ADR-008), not
from the development presets.

| option | engines | characters | cost | positives |
|---|---|---|---|---|
| **A. Three** | a 1.5 L I4 hatchback; a 2.2 L I4 SUV (`crdi22` exists); a 12.7 L I6 truck | small, mid, heavy | 3 vehicles (2 exist), 3 tunings, ~35 min of builds, ~3.5 MB | reaches the Phase 5 exit fastest; spans the range an enthusiast recognises; two of the vehicles exist already |
| **B. Five** | A + a 15 L V8 truck (`v8hd` exists) + an old naturally aspirated single-cylinder (a stationary or tractor engine) | adds an 8-cylinder cross-plane sound and a slow, thumping single with no turbo | 5 vehicles, 5 tunings, ~50 min of builds, ~6 MB | the characters differ most in *sound*: 1, 4, 6 and 8 cylinders; the NA single is the one engine with no turbo at all |
| C. Eight | B + a 3.0 L I6 pickup, a marine or genset engine, a tractor | breadth | 8 vehicles, 8 tunings, ~80 min of builds, ~10 MB | the widest choice; also the most tuning, and a larger download for anyone who tries them all |

**Recommendation: B, delivered as A first.** A is enough to meet the exit
criterion; B's two additions are the engines that *sound* most unlike the
others, which is what a roster is for (ADR-008: characters, "not the same
curve rescaled"). The V8 already has a builder file.

## Decisions needed

1. **The roster:** A, B, C, or your own list. With engines, name the
   vehicles too, e.g. "2.2 SUV, 2 t, 6-speed auto".
2. **Touch controls:** an on-screen pedal layout (recommended: throttle
   right, brake left, shift paddles at the top edge), or something else.
3. **The route:** a new `/enjoy` with `/drive` kept for development
   (recommended), or rework `/drive`.
4. **The phone:** which real device the exit is judged on.

Still open from Phase 4, and not blocking this: the listening sign-off, and
FINDING-023 (cold slap). Both are better settled before the roster is tuned
by ear.
