<!-- The owner's second Claude in Chrome run (iPhone emulation), handed over verbatim on
     2026-11-01, the agent's notes first. Verdicts: reviews/ENJOY-TEST-2026-10-31.md, "The mobile run". -->

I re-ran the tests on the iPhone screen in your browser (852×393, landscape). This run found five more major problems, all affecting phone users.

- **Simulated taps:** the browser tool's real clicks and drags kept failing in iPhone mode. So I simulated finger taps in the page, and each tap first checks which element is actually under the finger. That's how I could tell when something was hidden or covered.
- **One screen size:** I could only test the one size your browser was set to. I can't rotate it to portrait or try other phones from here. On a real iPhone, Safari's address bar makes the screen shorter, and the earlier desktop run showed the layout breaks at those heights.
- **Not every test was repeated:** the 4-minute lap, the hot run and all 5 places weren't run again, because they behave the same on any screen size.
- **Your tab:** I moved the tab you had open from the Dyno pull page to the Enjoy page.

# Enjoy test report (mobile): 2026-11-01, IST (UTC+5:30)
**Build:** https://jenilclaudeai.github.io/diesel-simulator/enjoy?e2e · **Browser:** Chrome 154 DevTools iPhone emulation (iOS 18.5 UA, 852×393 landscape, DPR 3, coarse pointer) on macOS · **Tester:** Claude in Chrome
**Summary:** 12 findings (0 blocker, 6 major, 5 minor, 1 cosmetic), counting 2 repeats from the desktop run (ENJ-01, ENJ-02); sections passed 3/14.

## Coverage
| Section | Result | Notes |
|---|---|---|
| A. Load and start | PASS | A finger tap on Start shows "Starting…" then Stop; the dash appears in 635 ms. rpm 777 (idle 800), hz 60, −35.0 dB, t advanced 2.0 s in 2 s. No Pyodide or .whl requests. |
| B. Roster idle | PASS | All 11 engines idle within 7.5 %. Start times 190–695 ms. Nothing overlaps on the start screen or the dash for any engine. |
| C. Automatic | PARTIAL | Holding the throttle pedal: shifts 1→6 in order, "shifting:" phases shown, no hunting. Pedal springs back to 0. "+" switches to manual-shift mode and "back to auto" works. Downshifts under braking are still late (6th down to 59.8 km/h, then 5th at 823 rpm). Cruise and lock-up can't be done by touch (MOB-03). |
| D. Manual | PARTIAL | Holding the clutch with one finger and tapping Restart with another works. Paddles shift twice per tap (MOB-04). There's no way to reach Neutral by touch (MOB-03). |
| E. Touch pedals/paddles | PASS | Pedals respond to finger height and spring back. Paddles are disabled at the start screen. |
| F. Dashboard truth | FAIL | ENJ-01 again: "Now" climbs from 476.0 to 14656259892.4 L/100 km while coasting (82–107 km/h, throttle 0.00). It shows "—" only when stopped. |
| G. Places/fuel/units | PARTIAL | US labels fit (mph, °F, mi, gal, mpg (US)). Places and the hot run weren't re-run. |
| H. Roads and goals | PARTIAL | Route and goal break the layout (MOB-01, MOB-02). The breaker message has no unit (MOB-08). The lap wasn't re-run. |
| I. Sound | PARTIAL | Mic tap cycles all 5 mics (Exhaust −43.6, Intake −30.2, Engine bay −15.5, Cabin −31.9, Outside −35.9 dB). Full throttle −16.9 dB. The Sound button can't be tapped when a goal is set (MOB-01). The level still sits at the last value after Stop. |
| J. Vibration | PARTIAL | Test note shown; unchecking works and is kept after reload. The note doesn't suit iPhone (MOB-09). |
| K. Persistence | FAIL | ENJ-02 again: Manual comes back as Auto after reload. Place, fuel, units, vibration and route/goal are kept. |
| L. Phone layout | FAIL | Fine in free drive. Overlaps and clipping appear once a route or goal is set (MOB-01, MOB-02). Portrait and other phone sizes couldn't be tested. |
| M. Accessibility / ease of use | PARTIAL | Invisible labels (MOB-05) and small tap targets (MOB-07). |
| N. Import | NOT TESTED | No files attached. |

## Findings
### MOB-01: With a route and a goal, the bottom of the dash falls off the screen, and Sound on can't be tapped
- **Severity:** Major
- **Confidence:** Confirmed (2 of 2 starts, 3 of 3 taps)
- **Where:** L/H/I, Hatchback, Auto or Manual, US units, City streets, Time trial, 852×393
- **Steps:** 1. Choose City streets and Time trial. 2. Start.
- **Expected:** The whole dash fits on screen while driving.
- **Observed:** The road strip (y 290–309) and the goal line (311–330) push the temperatures (336–413), trip computer (336–411) and Sound on (373–405) below the 393 px screen. The dash panel becomes scrollable (353 of 323 px). A tap in the middle of Sound on lands on the page background, not the button, so 3 taps out of 3 did nothing. With Free drive everything fits.

### MOB-02: With a route, the stall and breaker messages cover Restart and both dials
- **Severity:** Major
- **Confidence:** Confirmed
- **Where:** D/H, City streets, Manual and Auto, 852×393
- **Observed:** "Hold the clutch, then tap Restart" (y 221–250) overlaps Restart (196–228) by 57×7 px and each dial by 27×29 px. "Speed breaker at 27 mph: take them at 9" (234–250 × 221–250) overlaps both dials by 49×29 px. Without a route the stall message sits at y 267, clear of Restart (≤251) and the trip computer (≥306). Screenshots saved this session.

### MOB-03: Many features can only be reached with a keyboard
- **Severity:** Major
- **Confidence:** Confirmed
- **Observed:** While driving, the only touch controls are the two paddles, Auto/Manual, Stop, Mic, Sound and the three pedals. Cruise (+/−), Neutral, lock-up, engine brake, refuel, trip reset, car reset and auto-clutch only work from a keyboard. Shifting down from 1st stays in 1st (2 of 2), so a phone user can never select Neutral.

### MOB-04: A tap on a paddle shifts two gears
- **Severity:** Major
- **Confidence:** Confirmed in emulation (2 of 2); needs a check on a real phone
- **Observed:** From N, one tap (pointerdown, pointerup, click) gives 2nd, seen twice. Testing the parts separately: click alone N→1, pointer alone 1→2, both together 2→4. A real phone sends all three for one tap, so I'd expect gears to be skipped there too.

### MOB-05: The Place, Fuel and Units labels are invisible
- **Severity:** Major
- **Confidence:** Confirmed (also true on desktop)
- **Observed:** The label text is rgba(34,48,57,0.78) on a rgb(34,48,57) background, a contrast ratio of 1.00:1. The three dropdowns look unlabelled.

### ENJ-01 (repeat): "Now" fuel figure explodes while coasting
- **Severity:** Major
- **Confidence:** Confirmed
- **Observed:** 476.0, then 2073291.7, then 14656259892.4 L/100 km at 107→82.5 km/h with throttle 0.00. The text wraps to two lines.

### ENJ-02 (repeat): Gearbox choice isn't saved
- **Severity:** Major
- **Confidence:** Confirmed
- **Observed:** After choosing Manual and reloading: Auto aria-pressed=true. There's no gearbox key in localStorage.

### MOB-06: Start screen settings are hidden below the fold
- **Severity:** Minor
- **Confidence:** Confirmed
- **Observed:** On a 393 px screen, Route, Vibration, Test and the help text (y 367–527) sit below the fold inside a scrolling panel, with nothing showing it scrolls. Scrolling down to reach them moves Start engine off screen (top at −101).

### MOB-07: Tap targets smaller than Apple's 44 px guideline, and small text
- **Severity:** Minor
- **Confidence:** Confirmed
- **Observed:** Vibration checkbox 18×18, file pickers 22 px tall, Mic 109×32, Sound 109×32, back to auto 83×32, Restart 57×32, Test 47×40, Stop 50×40, Auto 51×40. Lamp text is 11.5 px and pedal labels are 10.3 px.

### MOB-08: Breaker message has no unit in US mode
- **Severity:** Minor
- **Confidence:** Seen once
- **Observed:** "Speed breaker at 27 mph: take them at 9", with no unit after the 9.

### MOB-09: Vibration test note doesn't suit iPhone
- **Severity:** Minor
- **Confidence:** Seen once
- **Observed:** On an iPhone, where vibration never works, the note says "On Mute, Chrome stays still: switch the phone to Vibrate or Sound…". The checkbox label already says "(Android)".

### MOB-10: Start engine button sits flush against the top bar
- **Severity:** Cosmetic
- **Confidence:** Confirmed
- **Observed:** Start engine (y 60–100) starts right at the panel top (60), and its label sits low in the button.

## Measurements
Roster on the phone (idle → seen, start ms): Hatch 1.5 800→778 (190), SUV 2.2 150 ps 760→743 (559), Hatch 1.9 750→730 (610), Car 1.5 three 720→696 (695), SUV 2.2 175 ps 700→680 (608), SUV 2.8 680→664 (549), SUV 3.2 600→582 (552), Car 3.0 six 800→785 (572), Truck 12.7 600→575 (564), Truck 15 V8 600→576 (421), Tractor 600→555 (558). Speed dial maxes: 240/200/200/200/240/240/240/240/160/160/60.

## Not tested
- Portrait, other phone sizes, and Safari's shorter screen with toolbars: the tool can't change the DevTools device or rotate it.
- Real clicks and drags: the browser tool's click and drag commands fail in iPhone mode, so I simulated touch taps in the page and checked which element was under each one.
- Full City lap, hot run, all 5 places, the 15× Start/Stop loop, and full accessibility (M): these don't depend on screen size and were covered in the desktop report.
- N: no files attached.

## Console and network
No console errors or warnings after the last reload. No Pyodide or .whl requests.

The fixes that would help phone users most: keep the whole dash on screen when a route or goal is set, add touch buttons for cruise and Neutral, make a paddle tap shift only once, and make the start-screen labels readable. Checking the double shift on a real iPhone would confirm MOB-04.
