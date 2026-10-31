# fix/enjoy-test-findings (the owner's Claude in Chrome test of /enjoy, 2026-10-31)

**PAUSED by the owner, 2026-10-31, mid-triage. No app code changed yet.** From `main` at
`2aa1710` (#147). The owner ran a Claude in Chrome test plan (sections A–N) on the live
site and handed back a report with 18 findings, ENJ-01 to ENJ-18 (3 major, 14 minor,
1 cosmetic). This branch triages each one (code read and/or measured) before any fix.

Scratch scripts are in `reviews/enjoy-test-2026-10-31/`: `harness.py` builds a
`LiveEngine` as `web/app/src/app/drive/make-engine.ts` does; run them with the repo root
as the argument (`python3 reviews/enjoy-test-2026-10-31/enj08.py "$PWD"`).

## Triage so far

| ID | Verdict | Evidence |
|---|---|---|
| ENJ-01 "Now" ~1e24 L/100 km coasting | **Real, confirmed** | Python loop, hatch15: on overrun `fuel_kg_h` is exactly 0.0, so `live._totals` feeds `inst` = 0 into a 0.8 s filter that only decays: `inst_kmpl` 4.9 → 8.9e-3 → 1.6e-5 → … → 3.1e-19 over 35 s; the page's `100/inst_kmpl` reads 3.2e20. `economy.ts nowL100` meant "null when coasting" but its `inst_kmpl > 0` test never fires. Planned fix (page only, no fixture change): null when `fuel_kg_h` is at the loop's own 1e-6 L/h cut. |
| ENJ-02 gearbox not kept | **Real** (code) | `enjoy.ts setManual` never calls `DriveEnv.setGearbox`; only `/drive` and `/spec` write it. Planned: Manual writes `manual`; Auto writes `tc`, but keeps a stored `dct` (Enjoy has none). |
| ENJ-03 toast over Restart at 846×340/300 | Not yet reproduced here | Next: headless Chrome at the three heights. P14's status already noted the Start button squashed at 846×300. |
| ENJ-04 gelled fuel: 60 rpm, "running", no message | Likely **FINDING-033**, reached by a shipped grid | FINDING-033 said "latent, no shipped grid reaches it"; waxed fuel does. To measure; the toast's absence too. |
| ENJ-05 previous best not shown | UX, by the code | `lapBest` is set only from a finished lap's verdict. Owner's call. |
| ENJ-06 lap clock starts with no throttle | **By design** | `LapRun.feed`: "from the first throttle (or the car's first metre)"; an automatic creeps. |
| ENJ-07 late downshifts braking | **Confirmed, minor** | Python, hatch15 from 135 km/h, full brake: 5th down to 38 km/h (998 rpm), stops in 3rd at 757 rpm; 1st within 3 s at rest; pull-away in 1st is clean. P08 schedule (ADR-017): owner's call. |
| ENJ-08 limiter vibration never fires | **Real, all 11 engines** | Full-throttle peaks are 0.938–0.960 × `max_rpm` (neutral; 1st the same); P01's `LIMITER` needs 0.985 ×. Dead signal. Candidate: rated + 0.4 × (max − rated) (single10 clears it by 42 rpm, the rest by 60–150). Needs the owner's OK on the threshold. |
| ENJ-09 level() stale after Stop | Test hook only | Not on screen; check B-07's e2e doesn't read it. |
| ENJ-10 exhaust tip quietest at idle | Owner's sound choice (ADR-018, matched at a cruise) | Not to change without a listen. |
| ENJ-11 cruise settles 2 km/h low | **Not reproduced** in Python | hatch15, flat, set 117.06: 116.94–117.44 for 90 s. To try in the browser. |
| ENJ-12 invalid seed silent | UX, minor | Owner's call. |
| ENJ-13 strip grade ≠ snap().grade | **Not a bug (likely tool timing)** | Strip and loop both read `route.at(route_s)`; Pass is flat for 0–800 m. To confirm by sampling both in one tick. |
| ENJ-14 derate < 1, lamp off | Partly by design (`lamps.ts`: density term ignored) | Python v8hd/desert/pass/auto: charge air peaked 89.5 °C (a transient near 10 s), so the lamp should light then. The agent held 2nd; to reproduce that case. |
| ENJ-15 mic keys with sound off | Harmless (picks the mic for later) | Probably no change. |
| ENJ-16 open road: no note | **By design** (`''` is the open road) | |
| ENJ-17 pedals not tabbable | Real a11y gap | `role="slider"` with tabindex -1; the keys cover keyboard use. Owner's call. |
| ENJ-18 Arctic start 15 s to idle | **Known: FINDING-031**, cold-start ECU planned | |

Also from the report: "Your engines: 2.0 L four" survives `localStorage.clear()`: the
engine library is IndexedDB, by design. The `setPointerCapture` errors were the agent's
synthetic events (it says so).

## Next (on resume)

1. Reproduce ENJ-03, -04, -11 (browser), -14 (2nd gear) and confirm -13 in headless Chrome.
2. Fix ENJ-01 and ENJ-02 with tests, mutation-tested against a passing baseline.
3. Ask the owner: ENJ-08's threshold, ENJ-07, -05, -12, -17, and FINDING-033's option A.
