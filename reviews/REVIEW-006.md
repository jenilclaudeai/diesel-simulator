# REVIEW-006 — Phase 4 exit (audio)

**Date:** 2026-09-27 (session 5, part 3)
**Scope:** PLAN.md Phase 4, on the stack #59 → #62 (on top of #58)
**Lenses run:** PM, LEAD, PHY2, SR1, SW1, SW2, QA1, QA2, USR1/2 (advisory)
**Reproduce:**
- `python3 tests/test_physics.py`
- `python3 tools/fixtures/gen_fixtures.py --check`
- `cd web/physics && npm test`
- `cd web/app && npm run build:pages && CHROME_PATH=… npm run e2e:sound`

---

## Summary

| Class | Count |
|---|---|
| BLOCK | 0 |
| MAJOR | 1 (M-1: the owner's listening sign-off, which the exit criteria require) |
| MINOR | 5 |
| FINDINGS | 021 fixed; 022 and 023 open (the owner's call, one rebuild) |
| NOTE | 3 |

**Phase 4 is exit-ready except for what only the owner can do:**
- listen and sign off (PLAN's third criterion);
- choose options for FINDING-022 and FINDING-023. They are best decided
  together, because either edit to `acoustics.py` forces one rebuild of the
  grids.

The two measurable criteria are met, and CI checks both.

---

## Exit criteria

**1. An I6 at 1400 rpm peaks at 70/140/210 Hz.** It is checked three times,
from the reference to the browser:

| where | how | result |
|---|---|---|
| `dieselsim/livesound.py` (the reference) | `test_livesound_firing_peaks_and_sources` | +31.7, +29.5, +25.6 dB over the neighbourhood |
| the TypeScript port (what the browser runs) | `web/physics` `sound.test.ts` | +38.3, +26.2, +25.8 dB over the half-way points |
| the drive page's AudioWorklet in Chrome (crdi15, an I4) | `e2e/sound.e2e.mjs`, captured from the audio thread | at idle (~780 rpm, firing 25.9 Hz), harmonics 2–4 at 9.7 dB or more over the floor in 6 runs of 6 (the fundamental sits below the model's own 35 Hz and 28 Hz high-passes); revved to 4,376 rpm (145.9 Hz), +24 to +46 dB, while the idle pitch has fallen to ≤ 5.8 dB |

The TypeScript port matches the Python in pure mode sample for sample: max
|diff| **2.2e-13 of peak** over 21,248 samples. The scenario includes:
- a run-up;
- a glide to a new point with a mic change and its reverb;
- a stall;
- a restart below the turbo's threshold on a third mic.

**2. Every source non-silent.**
- Every prebuilt grid: silent or non-finite waveforms: 0 of 2,880 (5 presets × 96 cells × 6).
- The streaming synth: 0 of 7 parts silent, in Python and in TypeScript.

**3. The owner has listened to, and signed off, every audio change since FINDING-004.** **Not yet: M-1.**
- The listening tool is the drive page: Sound on, five mics (keys 1–5), and "Record 10 s (WAV)".
- `play.py` plays the same synth in the terminal.

---

## The checklist

| PLAN item | done | where |
|---|---|---|
| TypeScript AudioWorklet port of the acoustics model (ADR-003) | yes. First, `dieselsim/livesound.py`: a streaming form of `render()`, verified against it. Then the port, held to it sample for sample. | #59, #61 |
| crank-angle synthesis resampled through instantaneous rpm | yes: rpm is ramped across each 128-sample block and the crank angle integrated, so pitch follows rpm with no pitch-shifting; the e2e shows it in the browser | #61, #62 |
| five mic positions | yes: `acoustics.MICS`; the port's copy is compared with the fixture; keys 1–5 as in `play.py` | #61, #62 |
| a gesture button for the autoplay policy | yes: "Sound on" (the click is the gesture), and it gives up focus afterwards (below) | #62 |
| no SharedArrayBuffer, so no COOP/COEP (ADR-003) | yes: the loop talks to the worklet over a transferred MessagePort | #62 |
| the owner's decisions | the warm and cold sources are in the grids; testing is sample-exact plus spectral; the port is faithful, to be judged by ear | #60–#62 |

---

## Findings of this phase

**FINDING-021 (fixed): `play.py`'s real-time sound was a stale copy.** It
predated FINDINGs 003, 004 and 017, so the slap, the exhaust mass flow and
the seating speed each moved its output by 0.0000%.

`dieselsim/livesound.py` replaces it. Against `render()`:
- worst source level: 1.2% off;
- mix, third-octaves: within 1.02 dB;
- each source's spectral shape: within 1.23 dB.

**FINDING-023 (open, the owner's call): the synth's slap input is pinned.**
It is the skirt oil film (FINDING-017's stand-in for clearance), and it
sits on its physical clamp (0.32 × clearance) in 240 of 240 cold cells and
115 of 240 warm. So cold slap cannot grow: cold oil alone moves it +0.0%
at idle. It is recorded as a known defect. The recommendation is to decide
it with FINDING-022, so there is one rebuild.

**FINDING-022 (open, the owner's call): the intake's loudness and the
turbo's boost term are normalised away**, in `render()` and so in the
synth. Doubling the mass flow moves the intake by 0.0000%; doubling the
boost moves the turbo by 0.0000%. A mutation test found it. It is recorded
as a known defect. The options are in the finding, and the recommendation
is to decide it with the listening review, so that the ~70 min grid rebuild
that any `acoustics.py` edit forces happens only once.

## Review findings

**M-1 (MAJOR) — the owner's listening sign-off.** The exit criteria require
it, and no test can stand in for it. Things to listen for:
- the `hd_i6` tick dominance (13×);
- the cold start: live friction reaches the rumble (−8.9% for cold oil),
  but the slap cannot follow (FINDING-023);
- FINDING-022's intake.
*(PM, USR)*

**m-1 (MINOR) — the cost on a phone is unmeasured.** In Node on the
development Mac, the synth takes:
- 0.37 ms per 128-sample block on average (12.7% of a core);
- 0.62 ms at p99, 2.3 ms at p99.9;
- 0 of 3,440 blocks over the 2.9 ms budget.

A phone may be three to five times slower. The first optimisations were
measured: an in-place glide and an inlined blend took p99 from 1.84 to
0.62 ms. The next would be preallocated block buffers. Check with REVIEW-005
m-5 (live friction), before Enjoy mode. *(SW2)*

**m-2 (MINOR) — the synth bound is 1e-8, not 1e-12.** libm differs from V8
by an ulp (17,458 of the noise table's 262,144 entries), and the rumble's
40 Hz band-pass amplifies that to 3.6e-12 of its peak, which is 1.6e-10 in
the floored-relative measure. Mutants still fail it by at least 5e6× (the
smallest miss is 4.9e-2 of peak). The pure arithmetic stays at 1e-12:
blends, filter design, the noise table's head. *(QA2)*

**m-3 (MINOR) — the grids grew from 784 KiB to 5,139 KiB each.** On the
wire (gzip) crdi15 goes from 547 to 1,003 KiB, because the summed
multi-cylinder sources repeat every firing interval; `single` goes to
1,424 KiB, with no repetition. The repository gains ~21 MB raw. The sources could be
stored per cylinder and summed in the browser if size matters. *(SW1)*

**m-4 (MINOR) — a stopped engine still sounds fuelled.** After an overheat
shutdown or an empty tank, the engine turns, dragged by the car, and the
synth plays the grid's sources, which include combustion. This matches
`play.py`'s rule (silent only when stalled). *(PHY2)*

**m-5 (MINOR) — the mic's high-pass hides an I4's idle firing
frequency.** crdi15 idles at ~26 Hz firing, and the default "Outside, 7 m"
mic high-passes at 60 Hz, so what is heard there is harmonics. That is
faithful to `acoustics.MICS`. The e2e listens at the exhaust tip (28 Hz).
*(USR)*

**N-1 — the bugs this phase found in its own work, each fixed where it was found:**
- #59 staled every prebuilt grid by adding a hashed file. CI's drive e2e
  caught it. The fix was an exclusion (read by the app from `bridge.py`,
  no second copy), a test that the cell solve imports no excluded file,
  and a re-stamp that the rebuild then confirmed value for value.
- The worklet scope has no `atob`: the grid failed to decode, and the
  message handler swallowed the error. The e2e found it. There is now a
  pure base64 decoder, and worklet message errors are reported.
- A clicked button kept focus, so space (full throttle) pressed it: it
  restarted the engine, or turned the sound off. The e2e found it, and it
  now guards against it.
- Three equivalent mutants, stated rather than counted as caught:
  - the rumble's divisor (removed);
  - the hiss's constant (FINDING-022);
  - the mic filters' order (LTI filters commute).

**N-2 — mistakes of mine, corrected in place:**
- Once I read an elapsed time as 35 min when it was 12. Checked before
  acting.
- My first debug instrumentation broke its own file.
- #59's first hash test used `subprocess`, which Pyodide lacks; CI's
  Pyodide job caught it. #60's grid tests then failed there too, because
  the Pyodide harness copies no data files; they now SKIP with that reason. It is now a static walk of the imports, which also
  sees lazy imports (a mutant adding one inside a function is caught).
- Two over-claiming tests in #60, corrected before commit:
  - "cold skirt film is thicker" (false in 115 cells);
  - a live-path test that the grid's cold cells could satisfy without the
    live path.
- A flaky e2e estimator, a single-bin floor, replaced by a median floor
  (#62).

**N-3 — what an enthusiast hears now:** `/drive`, then Sound on. A cold
start sounds different from a warm one, because the loop feeds the synth
its live friction.

---

## Suite on the final tree

Physics suite on this tree:
- **61 passed, 0 failed, 4 known defects, 0 unexpected passes** (with scipy);
- 56 passed, 4 skipped without.

The four known defects: n_cycles=6 convergence, cold-start dp/dθ (both
older), and FINDINGs 022 and 023. Also on this tree:
- under Pyodide: 54 passed, 0 failed. The two prebuilt-grid tests SKIP
  there, because the harness copies only the package and the tests;
- fixtures current in 6 modules;
- `web/physics`: 51 checks (5 + 36 + 10);
- app unit tests: 28;
- e2e: drive 7 of 7, sound 6 of 6;
- audit unchanged: 0 dead, 2 frozen, 0 tiny.

The dyno accuracy table is unchanged: no solver file changed in Phase 4
(the grid rebuild reproduced every committed value).

---

## Addendum (2026-09-28) — FINDING-022 fixed

The owner chose FINDING-022's option A, on its own. FINDING-023 goes in a
later rebuild. It landed in #64, on top of this stack.
- The intake now carries (ṁ/ṁ_ref)^1.5, and the turbo's boost term sits
  after the normalisation: ×2 moves them +182.8% and +190.5%, where both
  were 0.0000%.
- The known defect became an assertion.
- The balance moves most at idle: the intake and turbo parts drop 28–39 dB,
  and the intake-mic total 11–19 dB. At full boost the turbo rises ~4 dB.
  The table is in FINDING-022.

M-1 (the listening sign-off) is unchanged, and FINDING-023 is still open.
The text above is left as it was written.

---

## Addendum (2026-09-29) — m-1, phone cost, measured

`npm run perf` (Chrome CPU throttling; 4× ≈ mid-tier phone, 6× ≈ low-end).
The synth was made allocation-free, bit-identical over 1,154,688 values:

| synth | 4× | 6× |
|---|---|---|
| share of the audio thread, before → after | 19–21% → 8% | 29–32% → 12% |
| worst block, before → after | up to 6.6 ms → 3.2 ms | 61 ms → 4.7 ms |
| over the 2.9 ms budget (of 3,445), before → after | 0–2 → 0–1 | up to 12 → 0–1 |

Live friction (in the loop worker, off the audio path): 11 ms of a 16.7 ms
frame at 4×, a whole frame at 6×. It is left for an owner decision: a
cheaper bearing solve changes Python and TypeScript together.

m-1 is **addressed for mid-tier phones by measurement**. A real phone is
still the final check (Phase 5's exit).
