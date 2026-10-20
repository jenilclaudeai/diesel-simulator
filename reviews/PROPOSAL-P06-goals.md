# PROPOSAL — P06 tier 2: goals on a route

**Date:** 2026-10-20 (session 10). **Status:** ~~measured; **questions for the owner** (end).~~
**Decided (the owner, 2026-10-20), every recommendation:**
- **B with C:** a time trial on the par's fuel and an economy run in the par's time, with
  personal bests kept per browser;
- **overheating dropped as a goal:** a stop on overheat fails any run;
- **+5 s per breaker** taken too fast.
Being built on `feat/p06-roads`.
**From:** ADR-016's addendum: "goals on a route (reach a pass without overheating, an
economy run, a time to beat)", v1, after tier 1 (built, ADR-021).
**Lenses:** PM, PHY1, QA1, USR1, USR2
**Reproduce:** scratch scripts in the session's job directory: `p06_goals_measure.py`,
`p06_density_probe.py`, `p06_longclimb_probe.py`, `p06_par_probe.py`, `ts_speed.mjs`.
Every run is the live loop, from a warm start, with the automatic.

---

## The question

Can each goal be **won and lost**? A goal nobody can fail, or nobody can win, is this
repo's familiar failure in another form: a mechanism fully built, fed a quantity that
never moves.

## What was measured

**1. "Reach the pass without overheating" can't be lost in four of the five engines.**
Flat out up the Mountain pass (5 km, about 270 m up), at standard air and in 42 °C desert:

| engine | to the summit | peak coolant |
|---|---|---|
| hatch15 | 127–129 s | 90.6 °C |
| crdi22 | 137–140 s | 90.5 °C |
| truck127 | 371–375 s | 95.8 °C |
| v8hd | 305–310 s | 94.9 °C |
| single10 (11 kW tractor) | never (40 min cap, 2–5 km/h) | 119.9 °C, **stops** in the desert |

The warning is at 100 °C. A 15 km climb at 7 % (1,050 m up) in the desert or at Leh still
peaks at 95–96 °C. The fans hold full load in heat and thin air, which is how real cooling
is sized.

The density gap in the cooling (FINDING-032) adds at most 3.2 °C and changes none of
this.

**2. A time alone has one answer, flat out; economy alone has one answer, slower.** The
hatchback's summit at a constant throttle:

| throttle | 30 % | 45 % | 60 % | 80 % | 100 % |
|---|---|---|---|---|---|
| time | 323 s | 204 s | 167 s | 139 s | 127 s |
| fuel | 0.437 L | 0.479 L | 0.549 L | 0.638 L | 0.797 L |

Nothing on a route punishes flat out.
- The city's breakers cost 6 % of speed per hit at 50 km/h and above, which is won back in
  about a second at full throttle.
- Slowing to 15 km/h for each one costs several seconds.

By that arithmetic (not run), flat out wins a time trial through the breakers too.

**3. A time limit plus a fuel budget is a real trade-off, but how hard it is depends on the
engine.** A full lap of the pass (9.3 km), against a "par" run at a constant throttle. The
"driver" goes flat out uphill, off the pedal downhill, and at a set throttle on the level:

| | constant 70 % | constant 60 % | driver, 60 % level | driver, 50 % | driver, 40 % |
|---|---|---|---|---|---|
| hatch15 | 238 s, 0.855 L | 256 s, 0.801 L | 248 s, 0.801 L | 255 s, 0.787 L | 261 s, 0.775 L |
| truck127 | 504 s, 8.121 L | 573 s, 8.178 L | 510 s, 8.411 L | 521 s, 8.332 L | 534 s, 8.246 L |

- The hatchback **can beat a 60 % par on both** counts by simple good driving, narrowly:
  1 s and 1.7 %.
- No simple strategy beats a 70 % par on both.
- For the truck, constant 70 % beats every strategy tried on fuel, and constant 60 % loses
  on both time and fuel.

So "beat the par on time **and** fuel" is near-impossible in one engine and borderline in
another.

**4. Computing a par in the browser.**
- The TypeScript loop reproduces Python's laps exactly (238 s and 0.855 L; 504 s and
  8.121 L).
- Headless, it runs at **23× real time** on this Mac: a par lap takes 10–22 s here, and
  perhaps 30–110 s on a phone (an estimate, not measured).
- So named routes can ship precomputed pars. A random route's par would have to run in the
  background during the first lap.

## Options

**A, the par challenge:** win means beating a constant-throttle ghost on time **and** fuel.
- *Positives:* one clear target; works on any route.
- *Trade-offs:* measured to vary from near-impossible (truck) to narrow (hatchback). It
  needs each engine's par throttle tuned, plus a ghost run per random route.

**B, one score and one limit (recommended):** two goals per route.
- The goals:
  - **Time trial:** the fastest lap on at most the par's fuel.
  - **Economy run:** the least fuel within the par's time.
- *Positives:*
  - Each is a single number to improve.
  - The limit makes the trade-off real (item 3), and in every engine there is a way to
    meet it: drive like the par.
  - It is easy to say on a phone: "beat 4:18 on 0.80 L".
- *Trade-offs:* the same par runs as A (shipped for named routes, computed during the first
  lap for random ones), and two modes to pick between.

**C, personal bests only:** kept per browser, for each engine and route (the seed link
shares the route).
- *Positives:* no calibration, no ghost runs; it works for every engine and every random
  route from day one.
- *Trade-offs:* no target on the first run, and no "par" to talk about.

B and C combine well: B's goals, with C's personal bests kept beside them.

**Overheating as a goal:**
- *Drop it (recommended).* Instead, an engine that stops on overheat fails any run. The
  measured reason: four of five engines can't overheat even on a 1,050 m climb in 42 °C.
- *Keep it only where it can fail:* single10, or a future heavy-load scenario (no trailer
  exists today).

**Breakers in a timed run:**
- *+5 s per breaker taken too fast (recommended).* Without a penalty, flat out wins
  (item 2).
- *Count them only:* show the count, no penalty.

## Lens review

- **PM:** B with C is about two days. The par runs for named routes are an offline script
  (Python, ~10 min). A random route's par adds a background run in the worker.
- **PHY1:** every number above is the live loop itself. Nothing new is modelled; the goals
  only read `trip_L`, time, `route_s` and `breaker_hits`.
- **QA1:** each goal gets a test that it can be won (the par's own strategy wins) and lost
  (flat out busts the fuel limit; crawling busts the time limit).
- **USR1/USR2:** two numbers to beat is readable on a phone. "Par" is golf's word and may
  need a plain name (a "target").
