# Enjoy test report: 2026-10-31, ~13:50–14:50 IST (UTC+5:30)
**Build:** https://jenilclaudeai.github.io/diesel-simulator/enjoy?e2e · **Browser:** Chrome 154.0.0.0, macOS (MacIntel) · **Tester:** Claude in Chrome
**Summary:** 18 findings (0 blocker, 3 major, 14 minor, 1 cosmetic); sections passed 4/14.

<!-- The owner's Claude in Chrome run, handed over verbatim on 2026-11-01. The verdicts on each
     finding are in reviews/ENJOY-TEST-2026-10-31.md; this file is left as received. -->

## Coverage
| Section | Result | Notes |
|---|---|---|
| A. Load and start | PASS | 11 roster engines in 3 groups (plus an extra "Your engines: 2.0 L four, 140 ps" entry, which was there even after clearing localStorage). Start took 2085 ms (showed "Starting…", then the dash). rpm 777 vs idle 800, hz 60, level −34.8 dB. t went 7.2 → 9.2 in 2 s. No console errors, no Pyodide requests. |
| B. Roster idle | PASS | All 11 idle within 7.5 % of idle_rpm. None stalled. Dials are scaled per vehicle (trucks go to 160, tractor to 60). |
| C. Automatic | PARTIAL | Upshifts 1→6 in order, no hunting (0 flips), shows "shifting: torque/inertia phase". Paddle, m and "back to auto" work. l toggles lock-up. Cruise refuses at 10 km/h and cancels on brake. Grade works. Downshifts under braking are late (ENJ-07). Cruise settles below the speed it was set at (ENJ-11). |
| D. Manual | PASS | Pulls away cleanly. Stall gives the lamp, Restart and touch-worded messages. Restart without the clutch says "Hold the clutch, then tap Restart"; with the clutch it returns to 783 rpm. Shifting without the clutch says "Hold the clutch to change gear". Limiter ~4395 rpm (ENJ-08). |
| E. Touch pedals/paddles | PASS | Throttle follows height (0.25→0.20, 0.5→0.50, 0.75→0.80, 0.95→1.00) and springs back to 0. Real mouse drag peaked at 0.71. Clutch eases back from 1.00 to 0 over ~1.5 s. Paddles are disabled at the start screen. |
| F. Dashboard truth | FAIL | Digits match snap() and the needles match the digits. Redline starts at 4000. Trip average and range arithmetic are correct. "Now" is broken while coasting (ENJ-01). |
| G. Places/fuel/units | PARTIAL | Units convert correctly (99.7 km/h = 62 mph, 18 °C = 64 °F). Gelled fuel gives no feedback on the dash (ENJ-04). Hot run lit Fan at 95.1 °C but didn't reach Overheat in 3.5 min. |
| H. Roads and goals | PARTIAL | Route notes and ?route= work. Seed 1234 gives the same road after reload. Breakers count correctly. Time-trial verdict works. Previous best is never shown (ENJ-05), lap clock starts before the throttle (ENJ-06), invalid seeds are handled silently (ENJ-12). |
| I. Sound | PARTIAL | Mic cycle and keys 1–5 work. Off sets the level to null and disables the Mic button. 15 Start/Stop cycles were clean. level() keeps its last value after Stop (ENJ-09). |
| J. Vibration | PARTIAL | On by default. Start [60,40,60,40,140], gear [45] and breaker [54,70,33] seen. When off, no entries, and it stays off after reload. The max-rpm pattern never fires (ENJ-08). Stall pattern not isolated. |
| K. Persistence | FAIL | Place, fuel, units, vibration (storage) and route + goal (URL) are kept. Gearbox is not (ENJ-02). /drive and back keeps the shared choices. |
| L. Phone layout | FAIL | 846×411 is fine. 846×340 and 846×300 break (ENJ-03). Portrait message shown at 500×683 (Chrome's minimum width). |
| M. Accessibility | PARTIAL | Labels read well: "Engine speed 3337 rpm", "Speed 62 mph", "Warning from 212 °F, derate from 224 °F". Unlit lamps are hidden from screen readers. Pedals can't be reached with Tab (ENJ-17). Full Tab walk not done. |
| N. Import/projects | NOT TESTED | No files attached. |

## Findings
### ENJ-01: Trip "Now" shows astronomically large values while coasting
- **Severity:** Major
- **Confidence:** Confirmed
- **Where:** F, Hatchback 1.5 L, Auto, Standard air, Sold here, Metric and US, Open road
- **Steps:** 1. Start. 2. Full throttle (space) for 14 s. 3. Throttle off (x) and coast.
- **Expected:** "Now — L/100 km" while coasting or stopped.
- **Observed:** Metric: "Now 7181742366938674176.0 L/100 km · range 564 km". Six readings 0.5 s apart rose from 3.475e+22 to 8.350e+23 at 55→52 km/h with thr 0.00 (screenshot ss_2743k7dnd shows 1.663e+22). US: "Now 0.0 mpg (US)" at 68.5 km/h coasting. Creeping at 3.1 km/h: "Now 146.3 L/100 km" instead of "—".
- **Frequency:** every coast I checked (2 metric runs, 1 US)

### ENJ-02: Gearbox choice isn't saved
- **Severity:** Major
- **Confidence:** Confirmed
- **Where:** K, start screen
- **Steps:** 1. Click Manual. 2. Reload.
- **Expected:** Manual is still selected.
- **Observed:** Auto aria-pressed=true, Manual false. localStorage keys after the change are only dieselsim-goal-bests, -units, -drive-fuel, -vibration and -drive-environment (no gearbox key).
- **Frequency:** 2 of 2

### ENJ-03: On short phones the stall message covers Restart and the bottom row is cut off
- **Severity:** Major
- **Confidence:** Confirmed
- **Where:** L, Manual, stalled, viewport 846×340 and 846×300
- **Steps:** 1. Manual, Start. 2. Stall in 1st. 3. Tap Restart without the clutch so "Hold the clutch, then tap Restart" shows.
- **Expected:** The message doesn't cover the middle column, and every row is visible.
- **Observed:** At 340 the message overlaps the lower half of Restart (Restart y 190–222, message ~216–242; ss_3683b2li5). At 300 it hides Restart completely (Restart y 172–204, message ~182–210; ss_4246wmgaz plus a zoomed shot). The "Boost · friction" line and the FINDING-009 label are clipped at the bottom edge. Taps still reach the button (elementFromPoint returns BUTTON.restart), so this is visual only. 846×411 is fine (ss_6063eolko). No horizontal scroll at any size.
- **Frequency:** 2 of 2 at 300, 1 of 1 at 340

### ENJ-04: Gelled fuel cranks forever with nothing on the dash
- **Severity:** Minor
- **Confidence:** Seen once
- **Where:** G2, Hatchback, Arctic winter, Summer diesel (CFPP 18 °C), Metric
- **Steps:** Choose Arctic winter and Summer diesel, then Start, then full throttle after 20 s.
- **Expected:** waxed true, less power, and a message on the dash.
- **Observed:** The start-screen note is correct: "…at -20 °C: it gels, and the engine won't start…". view().hint is "fuel waxed: this diesel gels below 18 C…", but no message appeared on the dash. For 28 s: rpm 60, kmh 0.2, torque −86, stalled false, stopped false, no lamps lit (ss_221883mtv).
- **Frequency:** 1 of 1

### ENJ-05: Previous personal best is never shown
- **Severity:** Minor
- **Confidence:** Seen once
- **Where:** H5, City streets, Time trial
- **Steps:** Drive a full lap (4:04.2 gave "a new best!"). Reload, Start, drive again.
- **Expected:** The earlier best is shown.
- **Observed:** localStorage has {"hatch15|city|time|standard|tc":…}, but neither the goal note, goalText nor the start screen mention a best. It only appears as "· a new best!" at the end of the second lap (3:32.6).
- **Frequency:** 1 of 1

### ENJ-06: Lap clock starts without any throttle
- **Severity:** Minor
- **Confidence:** Confirmed
- **Where:** H5, Auto, City, Time trial
- **Steps:** Start and don't touch the throttle.
- **Expected:** "the clock starts with the throttle".
- **Observed:** lap {"phase":"running","time_s":5.05} with throttle 0 (car creeping). On the second run, time_s was 1.7 about 3 s after Start.
- **Frequency:** 2 of 2

### ENJ-07: Auto downshifts late under braking, and rpm sinks below idle
- **Severity:** Minor
- **Confidence:** Confirmed
- **Where:** C2, Hatchback, Auto, Open road
- **Steps:** Get up to about 135 km/h, throttle off, hold b.
- **Observed:** `107.9,6,2944,135.5 … 112.4,6,1051,48.4 | 112.9,5,830,39 | 113.9,5,762,20.7 | 114.4,4,759,12 | 115.4,4,762,0.1 | 115.9,3,762,0.2` (t, gear, rpm, km/h). The car stops in 3rd/4th. Idle is 800.
- **Frequency:** 2 of 2

### ENJ-08: Limiter tops out ~200 rpm below max_rpm, so the max-rpm vibration never fires
- **Severity:** Minor
- **Confidence:** Confirmed
- **Where:** D5, Hatchback, Manual
- **Observed:** Full throttle in 1st peaks at 4396 rpm (torque 3 Nm); in neutral at 4410. info().max_rpm is 4600. No [30,30,30,30,30] entry ever appears in vibes().
- **Frequency:** 2 of 2

### ENJ-09: level() keeps its last value after Stop
- **Severity:** Minor
- **Confidence:** Confirmed
- **Where:** I4
- **Observed:** After Stop, the level reads −13.34 dB at once and again 1.5 s later. In all 15 cycles the "after" value equals the last running value (e.g. −7.2 / −7.2). soundError is null.
- **Frequency:** 16 of 16

### ENJ-10: Exhaust-tip mic is the quietest at idle
- **Severity:** Minor
- **Confidence:** Confirmed
- **Observed:** Idle levels: Exhaust tip −44.1, Intake −30.6, Engine bay −15.6, Cabin −32.0, Outside 7 m −34.9 dB. Same through keys 1–5: −44.3 / −30.9 / −15.9 / −32.4 / −36.7.
- **Frequency:** 2 of 2

### ENJ-11: Cruise settles below the speed it was set at, and the set speed isn't shown
- **Severity:** Minor
- **Confidence:** Seen once
- **Observed:** Set at 116.7 km/h: dipped to 113.5 and settled at 114.5–114.7 for 20 s (thr 0.27). Five taps of + gave 144.3 after 10 s and ten taps of − gave 115.1. The set speed isn't shown anywhere.

### ENJ-12: Invalid seeds are handled silently
- **Severity:** Minor
- **Confidence:** Seen once
- **Observed:** 1000000 is clamped to 999999 (good). For 0 and abc the field empties; for −5 it stays (the browser marks it invalid). In all three, ?route= is dropped from the URL, the route note disappears and no message is shown.

### ENJ-13: Road-strip grade differs from snap().grade
- **Severity:** Minor
- **Confidence:** Seen once
- **Where:** Mountain pass, route_s 687
- **Observed:** Strip read "grade 6.0 % · asphalt · headwind 7 km/h · +0 m" while snap().grade was 0. By route_s 888 both read 0.06.

### ENJ-14: Derate below 1 with the Derate lamp off
- **Severity:** Minor
- **Confidence:** Seen once
- **Where:** G4, Truck 15 L V8, Desert summer, Mountain pass, 2nd gear
- **Observed:** derate 0.95–0.98 from t = 2.9 s to about 175 s with coolant 43–90 °C and charge air 64–84 °C. The Derate lamp never lit. It returned to 1.000 once charge air fell to 63 °C.

### ENJ-15: Mic keys work while Sound is off
- **Severity:** Minor
- **Confidence:** Seen once
- **Observed:** With Sound off (Mic button disabled), pressing 1 changed the mic to "Exhaust tip".

### ENJ-16: Open road shows no route note and no ?route=
- **Severity:** Cosmetic
- **Confidence:** Seen once

### ENJ-17: Pedals can't be reached with the keyboard
- **Severity:** Minor
- **Confidence:** Seen once
- **Observed:** Clutch, Brake and Throttle are role="slider" with tabIndex −1. Restart has tabIndex 0.

### ENJ-18: Arctic cold start takes about 15 s to reach idle
- **Severity:** Minor (may be intended)
- **Confidence:** Confirmed
- **Where:** Hatchback, Arctic winter, Sold here fuel
- **Observed:** rpm 60 → 103 → 334 → 491 → 638 → 733 at t = 0.5 / 3.5 / 6.5 / 9.5 / 12.5 / 15.5 s. fmep 6.96 bar. No message. Not stalled.
- **Frequency:** 2 of 2

## Measurements
**B. Roster:** engine | idle_rpm | rpm seen | vehicle | gears | vmax km/h | dial max | Start ms
- Hatchback 1.5 L 115 ps | 800 | 778 | 1.3 t hatchback | 6 | 206 | 240 | 155 (2085 on a cold first load)
- SUV 2.2 L 150 ps | 760 | 743 | 1.9 t SUV, 8-sp auto | 8 | 195 | 200 | 1125
- Hatchback 1.9 L 90 ps (VW 1.9 TDI ALH) | 750 | 730 | 1.3 t hatchback | 6 | 188 | 200 | 2349
- Car 1.5 L three 75 bhp (Mahindra mHawk75) | 720 | 696 | 1.75 t car | 6 | 168 | 200 | 2250
- SUV 2.2 L 175 ps (mHawk 2.2) | 700 | 680 | 1.9 t SUV | 8 | 205 | 240 | 1801
- SUV 2.8 L 204 ps (Toyota 1GD-FTV) | 680 | 664 | 1.9 t SUV | 8 | 217 | 240 | 414
- SUV 3.2 L five 200 ps (Ford 3.2 Duratorq) | 600 | 582 | 1.9 t SUV | 8 | 215 | 240 | 983
- Car 3.0 L six 265 ps (BMW B57) | 800 | 785 | 1.75 t car | 6 | 222 | 240 | 1381
- Truck 12.7 L 530 hp | 600 | 575 | 40 t tractor-trailer | 6 | 141 | 160 | 1031
- Truck 15 L V8 600 ps | 600 | 576 | 40 t tractor-trailer | 6 | 148 | 160 | 975
- Tractor 1.0 L single 15 hp | 600 | 555 | 3 t utility tractor | 4 | 45 | 60 | 1176

**G. Places (Hatchback 1.5, 2nd gear, full throttle for 10 s):** place | idle rpm | Tcool at start | boost
- Standard air | 778 | 24.9 °C | 1.86 at the limiter (peak not captured)
- Desert summer | 781 | 42.1 °C | 1.86 at the limiter. Note: "Jaisalmer, Rajasthan, May afternoon: 98.7 kPa, 42.0 °C."
- Arctic winter | 155 at 4.5 s (see ENJ-18) | −19.9 °C | peak 2.18 (only 2244 rpm, 27 km/h after 10 s). Note: "Rovaniemi, Finland, a cold January morning: 98.9 kPa, -20.0 °C."
- High plateau | 775 | 20.1 °C | peak 2.53
- Humid tropics | 779 | 29.1 °C | peak 2.40
- info().weather_check_pct was 2.383 for every place.

**G4. Hot run (Desert, Truck 15 L V8, Mountain pass, 2nd, full throttle):** t / coolant / oil: 2.9 s 42.9/44.0 · 50.9 s 54.0/62.2 · 100.9 s 69.1/79.8 · 150.9 s 85.6/96.4 · 206.9 s 95.1/110.8. Fan lit at 95.1 °C (fan_on 94.85). No Overheat, Derate or Engine off lamp by 3.5 min.

**I. Sound:** idle level by mic is in ENJ-10. Full throttle: Exhaust tip −18.5, Outside 7 m −14.9, Engine bay −6.0 dB (idle −44.7 / −37.2 / −15.6). 15 Start/Stop cycles: Start 86–265 ms (last one 100 ms), hz always 60, no console errors, JS heap 38 MB afterwards, no slowdown.

**J. Vibration:** first 12 entries: [60,40,60,40,140], then [20,30]×8 repeated. Other patterns seen: [45] (gear change), [54,70,33] (fast breaker), and the shake set [35,15]×8 / [15,35] / [26,24] / [31,19] / [28,22] / [25,25] / [21,29] / [29,21] / [18,32] / [23,27]. Test note: "Sent: a short buzz. Felt nothing? On Mute, Chrome stays still: switch the phone to Vibrate or Sound, and check its vibration settings."

**H. Goals:** City par 75.8 s + 6 breakers × 5 s = 105.8 s, fuel 0.305 L. parMs 2371 ms. Lap 1: 4:04.2 on 0.225 L, "within the par ✓ · a new best!". Lap 2: 3:32.6 (+5 s, 1 breaker) on 0.229 L, ✓. score = time_s = 212.6, so I couldn't tell whether the 5 s penalty is included in the time.

## Not tested
- N (import and projects): no files attached.
- L at 125 % zoom: the browser tool doesn't support zoom shortcuts.
- Portrait at exactly 411×846: Chrome's minimum width gave 500×683.
- Holding two controls at once (clutch pedal plus Restart) on touch: the tool has one pointer, so I held z on the keyboard instead.
- M: the full Tab walk, and Enter/Space on the paddles and Restart.
- J: the stall pattern wasn't isolated in vibes().
- G4: Overheat and Engine off weren't reached within 3.5 min.

## Console and network
- 4× "ERROR NotFoundError: Failed to execute 'setPointerCapture' on 'Element': No active pointer with the given id is found." (main-I7ULBUMY.js, e.down). These were caused by my synthetic pointer events in E, not by the app.
- No other errors or warnings, including none matching NaN or undefined.
- No requests for "pyodide" or ".whl" on /enjoy, including after returning from /drive.
