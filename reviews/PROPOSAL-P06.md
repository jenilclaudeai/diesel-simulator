# PROPOSAL — P06 tier 1: random roads in /enjoy

**Date:** 2026-10-20 (session 10). **Status:** decided by the owner before the build (2026-10-19, "Merged 134!
Continue"), built on `feat/p06-roads` (ADR-021). Tier 2 (goals on a route) is next.
**The owner's answers:** where: **Enjoy only**; order: **tier 1 first, then goals**; scope: **everything in
PLAN** (hills, surfaces, headwind, altitude through the weather table, a road-ahead strip, speed breakers as a
slow zone plus a jolt); routes: **both** named routes and random ones with a shareable seed.
**Lenses:** PM, LEAD, PHY1, PHY2, SW1, QA1, USR1

---

## What was built

**The route** (`dieselsim/live.py`, mirrored in `web/physics/src/live/route.ts`):

- A `Route` is a list of segments (length, grade, surface, wind) plus breaker positions. It repeats
  (lap after lap, each lap adding its net climb).
- `random_route(seed)`: 12 km, built by **mulberry32**, the generator livesound already uses.
  - Lengths are 200–800 m, rounded to 10 m.
  - Grades follow a damped random walk within ±8 %, rounded to 0.5 %, kept between 0 and 2,500 m.
  - Surfaces: 70 % asphalt, 12 % concrete, 12 % gravel, 6 % dirt.
  - Wind is ±8 m/s, rounded to 0.5.
  - A paved segment has a breaker one time in four. Over 20 seeds that averaged 4.65 breakers a route.
- Three named routes: `pass` (9.3 km, up to 267 m), `city` (2.5 km, six breakers), `desert` (11 km, wind and
  loose surfaces).
- `route_from('random:1234')` is the key the worker loads and the `?route=` link carries.

**What the engine feels** (`LiveEngine._road`, after each frame's substeps):

| | how | measured (Python, hatchback, after 25 s flat out) |
|---|---|---|
| grade | the driveline's existing `grade` | flat 140.2 km/h, 6 % 114.7 |
| surface | rolling resistance × 1.0 / 0.9 / 2.0 / 2.6 (`SURFACES`) | gravel 136.3 |
| wind | aero on the air speed, `v_r·|v_r|` with v_r = v + wind | 8 m/s headwind 132.0 |
| breaker | a resistive pulse for 0.15 s, worth 6 % of speed × j, j = (km/h − 15)/35 clipped to 0–1; a hint | jolt 1.00 at 50+ km/h |
| altitude | ISA from the start's air: p ∝ (1 − 2.25577e-5 h)^5.25588, T − 6.5 K/km | the weather table corrects the cells |

**The page** (`/enjoy`):
- A route picker under the place: Open road (flat), the three named routes, or Random road. Random shows a
  seed box and a New road button.
- The picker rewrites the address (`?route=city`, `?route=random:4242`), so the address is the link to share,
  and opening it restores the choice.
- A note under the picker gives the lap length, the highest point and the breakers.
- While driving, a **road-ahead strip** sits between the dials and the panel. It shows the next 1.5 km of
  profile (height scaled to fit, at least 40 m top to bottom), surface bands, breakers as amber dashes, and one
  line: grade, surface, wind, height above the start, the next breaker.
- The breaker hint is shown in the driver's units. A breaker taken too fast buzzes twice (P01), stronger for a
  harder jolt.

## What it does not do (stated, as PLAN says)

- **No suspension.** A breaker is a slow zone and a speed loss, felt in the phone, not a bounce of the car.
  ADR-002's out-of-scope list stands.
- **Altitude reaches the engine only through a grid's weather table.** Every shipped grid has one. A custom
  grid built without it drives the hills' grade but not their thin air, and the dash already says "no table"
  for such a grid (Phase 7 step 4).
- **The grade is a step per segment**, not a smooth curve. The altitude is continuous, but the grade jumps at
  each segment boundary. That is fine for the driveline (it already took grade steps from `/drive`'s keys) and
  visible as corners in the strip.
- **Breakers below 15 km/h do nothing.** There is no state for a gentle bump, so the phone buzzes only for
  breakers taken too fast.
- /drive and play.py take no route. Enjoy only, by the owner's choice.

## Measured on the way

1. **A climb leaked into the grid's shared spec.**
   - `set_route` first changed `spec.thermal` in place. That `spec` is the grid's, so one drive's altitude
     moved the next drive's air.
   - Mutants found it. `set_route` now copies the spec and its thermal block, and a test drives twice to check
     nothing carries over.
2. **CPython's `**` and V8's differ in the last bit.**
   - Over 20,000 altitudes (0–7,400 m), `(1 − k h) ** 5.25588` differed in the last bit at 1,958.
   - The ISA power is now `exp(n · ln x)` by series on both sides. The series use + − × ÷ only, which IEEE
     makes bit-identical.
   - This was right, but it did not cure the first fixture failure, which was item 3.
3. **The dual clutch is knife-edge on random route 1234.**
   - Python and TS agreed to 8e-13 for 1,500 frames, then split in one frame at the clutch-sync threshold.
   - In Python alone, T_oil 373 against 373 + 1e-9 moves the same event from frame 3096 to 3108. That is the
     frame TS's last-bit friction noise moved it to.
   - So this is not a port error; the threshold amplifies any last-bit difference. The fixture drives that
     route on the converter box (60 events, robust to the same nudge).
   - The DCT's step is still checked frame by frame by the per-step comparison.
4. **The e2e lost touch on a reload late in its run.**
   - After many viewport changes, a `page.goto` left Chrome turning CDP touches into clicks. Buttons still
     worked; the pedals heard nothing.
   - In a fresh browser the same reload kept touch (3 of 3), and re-enabling touch emulation did not help.
   - The link check now opens its own tab.
5. **A test that tested nothing (caught by its mutant).**
   - The strip's "a flat road draws flat" check passed with the minimum-rise floor removed: the profile became
     all `NaN`, and a set of `NaN`s has one member.
   - It now asks for a finite middle height, and that the city's 6 m rise stays under 16 % of the strip.

## Checks

- **Python:** `test_p06_routes` (9 parts) and `test_p06_the_engine_feels_the_road` (8 parts).
- **TS port:** two route drives in `live.json` (the city on the plain grid, random:1234 on the weather grid).
  - Per step: worst 2.9e-14 against a bound of 1e-12. Every event lands on the same step. Finals agree within
    2e-15.
  - TS mutants: 7 of 7 caught, each only in the route checks.
- **App units:** 153 of 153. App mutants: 10 of 10 non-equivalent ones caught. One more was equivalent: the
  loop steps by laps from the breaker's first position anyway, so it was replaced.
- **e2e:** Enjoy 36 of 36 (five new P06 checks); Drive 10 of 10.

## Lens review

- **PM:** tier 1 is closed without goals; tier 2 gets its own small proposal (what a goal is: reach the top, a
  fuel budget, a time). No timebox ran over.
- **LEAD:** the route is in the live loop (`live.py`, not hashed), so **no grid goes stale**. ADR-004's fixture
  holds the port. ADR-003 is untouched: no server, and the seed is the share.
- **PHY1:** the breaker is an impulse, not a model. Its 6 % comes from no measurement and is called a tuning
  constant. Wind on air speed and ISA altitude are standard.
- **PHY2:** a grade step per segment puts a step into the driveline's load. The live loop already takes
  steps (keys on /drive), and nothing new integrates the grade.
- **SW1:** the route is computed from a key on both sides, never sent as data, so a link is a few bytes. A
  state snapshot (`getState`) carries `route_s` and `route_alt`, and `setState` re-derives the air.
- **QA1:** every new mechanism has a mutant that a test catches. The e2e reload trap is written into
  CLAUDE.md.
- **USR1:** the strip costs 48 px on a 300 px tall phone. The panel below already scrolled at that height
  (B-02) and nothing overlaps. Still to do: feel it on the owner's S9+.
