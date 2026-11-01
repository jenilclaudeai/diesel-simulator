# ENJOY-TEST-2026-10-31 — the owner's Claude in Chrome test of /enjoy, triaged

**Opened by:** session 11 (2026-10-31 to 2026-11-01), from the owner's test report.
**Lens:** the driver's view (lead), PHY1, A11Y, QA
**Status:** **3 fixed on `fix/enjoy-test-findings`** (ENJ-01, -02, -09); 8 for the owner
(questions below); 7 not bugs, by design or already known. **The mobile run (MOB-01 to
MOB-10, 2026-11-01):** 3 more fixed (MOB-05, -08, -10), 5 for the owner, 2 not bugs.
**Input:** `reviews/enjoy-test-2026-10-31/report.md`, the report as received (18 findings,
ENJ-01 to ENJ-18). Run on the live site, `main` at `2aa1710` (#147).
**Reproduce:** the scripts beside the report. `harness.py` builds a `LiveEngine` as
`web/app/src/app/drive/make-engine.ts` does (Python, the TS port's reference);
`python3 reviews/enjoy-test-2026-10-31/enj08.py "$PWD"` from the repo root. `br.mjs` drives
the live site in headless Chrome (`node br.mjs layout|wax|grade|cruise|derate2`; `W`, `H`
and `Q` set the viewport and extra query).

---

Every finding was checked before acting on it. The agent's report was good: 3 real bugs
it named are real, and it found a fourth (ENJ-09) that matters more than it said. Two of
its findings are measurement artefacts of its own slow steps, and one is a known finding
(FINDING-033) that was thought unreachable on a shipped grid.

## The verdicts

| id | what the report said | verdict | evidence |
|---|---|---|---|
| ENJ-01 | "Now" reads ~1e24 L/100 km coasting | **real, fixed here** | Python loop, hatch15, 14 s full then a coast: `fuel_kg_h` is exactly 0.0 on overrun, and `live._totals` feeds 0 km/L into a 0.8 s filter that only decays: 4.9 → 8.9e-3 → 1.6e-5 → … → 3.1e-19 km/L in 35 s, read as 3.2e20 L/100 km. The page's `inst_kmpl > 0` test never fired. |
| ENJ-02 | the gearbox isn't kept | **real, fixed here** | `enjoy.ts setManual` never wrote `DriveEnv.gearbox`; only `/drive` and `/spec` did. |
| ENJ-03 | the toast covers Restart on a short phone; the bottom row is cut | **real**, for the owner | Headless Chrome, Manual, stalled, Restart tapped: toast over Restart by 8 px at 846×340 (Restart 190–222, toast 214–243) and by 22 of 32 px at 846×300 (172–204 vs 182–211). 846×411 is clear (261 vs 285). Without a route the strip fits (ends 298 of 300); **with a route** the road row pushes it to 276–353 at 300 and 293–370 at 340: the trip computer is below the fold, reachable only by scrolling. |
| ENJ-04 | gelled fuel: 60 rpm, "running", no message | **real: FINDING-033, on a shipped grid**, for the owner | Winter + summer diesel, Auto: 60 rpm, 0.2 km/h, `stalled` false for the 50 s measured; the hint shows ~4 s, then nothing (no lamp, no toast, no Restart). FINDING-033 said "latent, no shipped grid reaches it"; waxed fuel does. |
| ENJ-05 | a stored best isn't shown before the lap | gap, for the owner | `goals.ts`: `lapBest` is set only from a finished lap's verdict. |
| ENJ-06 | the lap clock starts with no throttle | **by design** | `LapRun.feed`: "from the first throttle (or the car's first metre)"; an automatic creeps. |
| ENJ-07 | late downshifts braking | **confirmed, minor**, for the owner | Python, hatch15 from 135 km/h, full brake: 5th to 38 km/h (998 rpm), stops in 3rd at 757 rpm; 1st within 3 s at rest, and the pull-away in 1st is clean. The below-idle 757 is the converter's load at rest in gear. |
| ENJ-08 | the limiter vibration never fires | **real, all 11 engines**, for the owner | Full-throttle peaks are 0.938–0.960 × `max_rpm` (neutral and 1st alike; table below); P01's `LIMITER` needs 0.985 ×. CLAUDE.md's pattern: built, wired, fed a threshold it never reaches. |
| ENJ-09 | `level()` keeps its last value after Stop | **real, fixed here**; wider than the hook | The worklet sends no level while silent (`process` returned early), so the last engine's level stood: in the hook, and on **/drive's meter**, which shows `levelDb` as "… dBFS" with sound on. The sound itself was silent (B-07 holds). |
| ENJ-10 | the exhaust tip is the quietest mic at idle | owner's sound choice (ADR-018) | Loudness was matched at a cruise, by ear. No change without a listen. |
| ENJ-11 | cruise settles 2 km/h low | **not reproduced** as a steady error; for the owner | Browser, engaged as the agent did (pedal still at 1 at 117.1 km/h): overshoot to 122.4, dip to 116.0, then 116.9–117.1 from 35 s on. Python (engaged at 0.4): 116.9–117.4 for 90 s. The agent's 20 s window sat in the recovery. Two real points: the +5.3 km/h overshoot (the integral starts at the pedal), and the set speed shown nowhere. |
| ENJ-12 | an invalid seed is dropped silently | gap, for the owner | `routeKey` returns no route for 0, -5, "abc"; the page says nothing. |
| ENJ-13 | the strip's grade ≠ `snap().grade` | **not a bug** (the agent's timing) | Both read `route.at(route_s)` and `dl.grade`. Browser, the pass, both sampled in one tick every 250 ms: **0 of 357** differ. The pass is flat for 0–800 m, so 6 % at 687 m was the strip read ~10 s after `snap()`. |
| ENJ-14 | derate < 1 with the Derate lamp off | **by design** (`lamps.ts`) | Browser, v8hd, desert, pass, 2nd: derate 0.954–0.979 at 70–79 °C charge air, lamp off; **every one of 200 samples over 80 °C had it lit** (hottest 87.3 °C, lit). The density term is left out of the lamp on purpose (#76's history in `lamps.ts`). |
| ENJ-15 | mic keys work with sound off | no change | It picks the mic the sound will start with; harmless. |
| ENJ-16 | the open road has no note or `?route=` | **by design** | `''` is the open road, no route. |
| ENJ-17 | the pedals can't be reached by Tab | gap, for the owner | `role="slider"`, `tabindex=-1`; the keys (w/s, b, z) are the keyboard's way. |
| ENJ-18 | an Arctic start takes ~15 s to idle | **known: FINDING-031** | The cold-start ECU (its proposal, answered 2026-10-28) is the fix; not started. |

Also from the report, checked:
- "Your engines: 2.0 L four" after `localStorage.clear()`: the engine library is IndexedDB,
  by design.
- The 4 `setPointerCapture` errors: the agent's synthetic events, as it said.
- Two 404s on every load (not in the report): GitHub Pages serves `/enjoy` from `404.html`
  (`scripts/pages-404.mjs`), so the page loads with HTTP 404. By design of `build:pages`.

### ENJ-08's measurement (Python live loop, full throttle, 8 s neutral / 15 s in 1st)

| engine | rated | max | 0.985 × max | peak, neutral | peak, 1st | peak / max |
|---|---|---|---|---|---|---|
| hatch15 | 4000 | 4600 | 4531 | 4385 | 4390 | 0.953 |
| crdi22 | 3800 | 4370 | 4304 | 4165 | 4166 | 0.953 |
| vw19tdi | 3750 | 4312 | 4248 | 4073 | 4078 | 0.944 |
| mhawk75 | 3600 | 4140 | 4078 | 3931 | 3931 | 0.949 |
| mhawk22 | 3500 | 4025 | 3965 | 3849 | 3851 | 0.956 |
| gd28 | 3400 | 3910 | 3851 | 3741 | 3743 | 0.957 |
| duratorq32 | 3000 | 3450 | 3398 | 3295 | 3297 | 0.955 |
| b57 | 4000 | 4600 | 4531 | 4392 | 4399 | 0.955 |
| truck127 | 1800 | 2070 | 2039 | 1987 | 1980 | 0.960 |
| v8hd | 1900 | 2185 | 2152 | 2094 | 2088 | 0.958 |
| single10 | 2200 | 2530 | 2492 | 2374 | 1713 | 0.938 |

The governor pulls fuel from rated to `max_rpm`, so the free rev settles where the fuel
left meets friction: 53–69 % of the way from rated to max (single10 53 %, truck127 69 %).

## What changed (`fix/enjoy-test-findings`)

1. **ENJ-01** (`enjoy/economy.ts`): `nowL100` reads coasting from the fuel flow, at the
   loop's own cut (1e-6 L/h), and shows "—". The loop and its fixtures are untouched. After
   a 40 s coast the figure recovers fast: 179 for one frame, 29 at 0.12 s, within 1.5 of the
   true figure by 1 s (`enj01b.py`).
2. **ENJ-02** (`enjoy/gearbox.ts`, `enjoy.ts`): Auto/Manual writes the kept gearbox. Auto
   keeps a dual clutch chosen on /drive, since Enjoy has none.
3. **ENJ-09** (`drive/sound.worklet.ts`): the level is reported in silence too.

**Tests, each mutation-tested against a passing baseline** (every mutant failed by an
assertion, none by a compile error):
- units: `dash.spec.ts` (ENJ-01, with the loop's measured numbers): 2 of 2 mutants caught
  (the fuel check dropped; its comparison flipped). `gearbox.spec.ts`: 2 of 2 (Auto always
  `tc`; Manual returning the kept box). The old test `nowL100(0, 90)` is null had assumed
  the filter reaches 0, and passed while the page read 1e24.
- e2e:enjoy, two checks: "Manual is kept" (the wiring removed: it fails, `stored: null`,
  51 of 52 pass) and "ENJ-09: after Stop the level reads silent" (the old early return:
  it fails, level −32.0 dBFS, 0 reports; 52 of 53 pass).

**Verified locally** (Node 22.23.3, `build:pages`, Chrome): units **170 passed** (31 files;
`main` 167 in 30), also with `physics-version.ts` moved aside as CI runs them;
e2e enjoy **53**, sound **6**, drive **11** (`main` 51, 6, 11), all 0 failed;
`check:labels` passes. No file under `dieselsim/` changed: no grid goes stale and no fixture
changes.

## The mobile run (2026-11-01)

The owner reran the plan in Chrome's iPhone emulation, 852×393 landscape:
`reviews/enjoy-test-2026-10-31/report-mobile.md`, as received. It ran on the live site,
which is `main` without this branch. So its repeats of ENJ-01, ENJ-02 and the level after
Stop are this branch's three fixes, not yet live. The rest was checked with
`enjoy-test-2026-10-31/mob.mjs`: headless Chrome at 852×393 with an iPhone UA and
**real CDP touches**, not page-made events.

| id | what the report said | verdict | evidence |
|---|---|---|---|
| MOB-01 | with a route and a goal the dash falls off the screen; Sound can't be tapped | **real**, for the owner (with ENJ-03) | Reproduced to the pixel: road 260–330 (goal line 311–330), strip 336–413 of a 393 px screen, the dash scrolls (353 of 323), and `elementFromPoint` at Sound's centre is not Sound. Free drive: strip 306–383, Sound hit. |
| MOB-02 | with a route the toasts cover Restart | **real**, for the owner (ENJ-03's first part) | Route: toast 221–250 over Restart 196–228. Free drive at this size: clear (267 vs 251). The toast sits over the dials by design (B-02); over Restart it is not. |
| MOB-03 | cruise, Neutral and the rest are keyboard-only | **real** (a scope question), for the owner | ADR-012 gave touch the pedals and paddles only. `Driveline._select` clamps at 1st, so "−" never reaches neutral: only `n` does. |
| MOB-04 | one paddle tap shifts two gears | **not a bug** (the tool's events) | Real touches: 1→2, 2→3, 3→4, one gear a tap, 3 of 3. A tap's click arrives with `detail: 1`, which `keyTap` ignores by design (it acts only for a keyboard's `detail: 0`). The agent's page-made click had `detail: 0`, so it counted twice. `e2e:enjoy` checks the same with CDP touches ("gear 1 -> 2"). |
| MOB-05 | Place, Fuel and Units labels invisible | **real, fixed here** | 1.00:1, all three: the picker's `--slate-muted` was made for /drive's grey (5:1 there), and /enjoy is slate. Now 7.26:1. |
| MOB-06 | the start screen's settings sit below the fold | **real**, for the owner | 481 px of content in a 323 px panel; Vibration starts at 410. |
| MOB-07 | tap targets under 44 px, small text | **real**, for the owner | Apple's 44 pt and Android's 48 dp are guidelines; Phase 8's accessibility pass did not set one. |
| MOB-08 | the breaker hint's second speed has no unit | **real, fixed here** | `touchHint` dropped it; its test pinned the old string ("take them at 9"). |
| MOB-09 | the vibration Test note doesn't suit an iPhone | **not a bug** (emulation) | A real iPhone has no `navigator.vibrate`, and `testNote` then says "This browser has no vibration (iPhones and iPads have none)". Desktop Chrome's iPhone emulation keeps the function. |
| MOB-10 | Start flush with the top bar, its label low | **real, fixed here** | Squashed to 40 px against the 49 its padding and type need (P14's status noted it at 846×300). `flex-shrink: 0`: now 61 px. |

**The fixes' tests** (mutation-tested; every mutant failed by an assertion): `hints.spec.ts`
for MOB-08 (the old string put back: caught); `e2e:enjoy` for MOB-05 (labels ≥ 4.5:1) and
MOB-10 (Start's height ≥ its padding and type, on a start screen that overflows): with
both CSS rules taken out, both fail (1.00:1; 40 px of 49), 53 of 55 pass.

## Questions for the owner

1. **ENJ-08, the limiter buzz.** It needs a threshold the engines reach.
   - **A (recommended):** rated + 0.4 × (max − rated). Every engine crosses it at full
     throttle in neutral: single10 by 42 rpm, the rest by 79–152. The page has `rated_rpm`
     already (the redline). *Positives:* one line in `vibration.ts`, with a test per roster
     engine. *Trade-off:* a fixed fraction; a new engine with a much stiffer governor could
     miss it again (a test over the roster would catch that).
   - **B:** read the governor's fuel cut from the loop (a new view field). *Positive:* fires
     exactly when the governor bites. *Trade-off:* worker and protocol changes.
   - **C:** drop the limiter event. *Positive:* less code. *Trade-off:* loses one of the
     four events you chose for P01.
2. **ENJ-03 with MOB-01 and MOB-02, a short phone.** Two parts. On an iPhone in landscape
   (852×393) both happen only on a route, and with a goal the Sound button is off the
   screen too, so this matters on a common phone, not only at 300 px.
   - The toast over Restart. **A (recommended):** while stalled, show the hint as the Restart
     button's own second line ("Hold the clutch"), and no toast. *Positive:* the instruction
     sits on the thing to tap; nothing overlaps at any height. *Trade-off:* a taller button,
     to be measured at 846×300 before shipping. **B:** move the toast to
     the top of the dials' row while stalled. *Positive:* small CSS change. *Trade-off:* it
     covers the gear digit. **C:** a narrower toast beside the column. *Trade-off:* long
     hints wrap to three lines.
   - The trip computer off-screen on a route: it needs **53 px at 846×300 and 30 px at
     846×340** (measured). The road row is 49 px, of which its text line is about 19 (the
     row less its 28 px picture and the gap); the dials' row is 126 px at 300. **A
     (recommended):** below 360 px of height, drop the road's text line and lower the dials'
     cap until the strip fits, measured at both heights. *Positive:* the whole dash on
     screen while driving. *Trade-off:* smaller dials, and no grade or next-breaker words on
     a short screen. **B:** keep B-02's design, the strip scrolls. *Positive:* no change;
     the dials stay large. *Trade-off:* the trip computer is out of sight on a route.
3. **ENJ-04 / FINDING-033.** **A (recommended, as FINDING-033 says):** an automatic held at
   its 60 rpm floor stalls, so Enjoy offers Restart; and a **"Fuel gelled" lamp** while
   `fuel_waxed`, since the hint lasts only ~4 s. *Positives:* the driver sees why. *Trade-off:*
   A is in `live.py` (unhashed, no grid stale) with the TS port and `--only live` fixtures.
4. **ENJ-07, braking downshifts.** **Leave (recommended):** it is in 1st at rest and pulls
   away cleanly. Or a coast-down schedule (P08, ADR-017): more like a real automatic, but a
   change to the shift logic and its fixtures.
5. **ENJ-11, cruise.** **Show the set speed on the Cruise lamp (recommended):** page only.
   The +5 km/h overshoot when engaged with the pedal down: leave, or start the integral
   from a steady-state estimate (`live.py`, fixtures).
6. **ENJ-05, the best.** **Show the stored best on the goal line before and during a lap
   (recommended):** page only.
7. **ENJ-12, a bad seed.** **Say "Seed: 1 to 999999" (recommended):** page only.
8. **ENJ-17, the pedals and the keyboard.** **A (recommended):** focusable sliders that the
   arrow keys press. *Positive:* matches their role. *Trade-off:* a held key and a slider
   overlap; the keys already work. **B:** take the slider role off and name the keys in the
   start screen's hint. *Positive:* no new input path.
9. **MOB-03, controls a phone can't reach.** ADR-012 gave touch the pedals and paddles; on a
   phone there is no Neutral (once in gear), cruise, lock-up, engine brake, refuel or resets.
   **A (recommended):** an N button beside the paddles and a Cruise button with +/−, sending
   the keys the loop already has (`n`, `c`, `+`, `-`). *Positives:* page only, no fixture
   changes; covers what a driver needs while driving. *Trade-off:* two more controls on a
   crowded dash (to be fitted with question 2). **B:** "−" from 1st selects neutral.
   *Positive:* no new button. *Trade-off:* changes `live.py`'s manual box for /drive and
   play.py too, and the live fixtures. **C:** leave it: Enjoy stays the simple page ADR-012
   chose.
10. **MOB-06, the start screen below the fold.** **A (recommended):** below 420 px of height,
    put the pickers in two columns beside Start. *Positive:* Start and the settings in one
    view. *Trade-off:* a second layout to keep. **B:** a fade at the panel's bottom edge
    that says it scrolls. *Positive:* small. *Trade-off:* still a scroll.
11. **MOB-07, tap targets.** **A (recommended):** a 44 px floor for every button and the
    vibration switch on /enjoy, set with question 2's layout. *Positive:* fewer missed taps.
    *Trade-off:* about 12 px more per row on a dash that is already short. **B:** only the
    controls used while driving (Mic, Sound, Restart, back to auto).

Also stale, not changed here: `ANDROID-BUGS.csv` still says B-07 "Fixed in PR (not yet
merged)" and B-08 "Fix in PR #141 (draft)"; `main` merged both (#140, #141). The CSV is
the sheet's source, so it is the owner's to confirm (as with #145's stale status lines).
