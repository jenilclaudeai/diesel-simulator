# PROPOSAL-P10 — a deeper, bassier diesel sound (feasibility)

**The owner's Feat Prop P10** (priority 1, "Into Consideration"): "Current
sound is little high pitch. Actual diesel engines sound is more deeper and
bassy. For example CRDi, DDIS, TDC."
**Status:** **decided 2026-10-14 (ADR-018): B, loudness matched at a cruise;
built on `feat/p10-sound`.** *(Was: "measured, feasible; nothing built.")* ~~Questions for the owner at
the end. (2026-10-13, session 9)~~ **The owner answered (2026-10-14):
phone speaker; cabin and intake mics; yes to A/B files.** The listening
files are made (`tools/p10_ab.py`). **The "muffler" piece below was wrong**:
see "Correction and the listening round" at the end.
**Reproduce:** `python3 tools/p10_sound_split.py . crdi15 800 0.05`,
`python3 tools/p10_rebalance.py . crdi15` (each ~20 s; the second changes
nothing in the repo).

---

## What was measured

The streaming synth (`dieselsim/livesound.py`, which the TypeScript worklet
matches to 2.2e-13), at the app's default mic (`exterior_7m`), on the three
car diesels, from each engine's own solved operating point (`n_cycles=9`).

**The ear is right: there is almost no bass.**

| | crdi15 idle (800) | crdi15 2000 / 0.3 |
|---|---|---|
| spectral centroid | 1,901 Hz | 2,370 Hz |
| power below 250 Hz | 2.1% | 2.4% |
| strongest bin | 907 Hz | 666 Hz |
| firing frequency (4 cyl) | 27 Hz, 37 dB under the strongest bin | 67 Hz, 24 dB under |

**Why: the mix is dominated by the high-frequency sources, and the exhaust,
which carries the low firing pulse, is nearly silent in it.** The
exhaust's, combustion's and mechanical noise's shares of the mix (power, at
the mic's gains, before the mic's filters):

| | exhaust | its power < 250 Hz | combustion (centroid ~700 Hz) | mechanical: valve tick 3.1/5.4 kHz, injector 4.2/6.8 kHz |
|---|---|---|---|---|
| crdi15 idle | **0.2%** | 8% | 12.6% | **81.8%** |
| hatch15 idle | 0.2% | 1% | 15.8% | 78.5% |
| crdi22 idle | 0.2% | 87% | 15.5% | 79.5% |
| crdi15 2000 / 0.3 | 1.0% | 50% | 37.6% | 58.6% |
| hatch15 2000 / 0.3 | 1.3% | 85% | 37.1% | 18.4% |
| crdi22 2000 / 0.3 | 1.6% | 84% | 43.1% | 33.3% |

How the balance is set: each source is normalised to a unit shape, then
scaled by its physical law against a fixed reference (FINDING-004/017/022):
exhaust `(ṁ / ṁ_ref)^1.5` with `ṁ_ref` the *rated, boosted* flow, so at idle
it sits ~30 dB down. Tick is `(v_seat / 0.10 m/s)^2`. Then the mic's
constant gains (`acoustics.MICS`) mix them. **The physics sets each
source's change with the operating point. The balance between sources is a
set of constants, not a measurement.** So P10 changes design constants and
one filter, not the solver.

**What-if, in memory** (`tools/p10_rebalance.py`, crdi15, the exterior mic's
gains only):

| | idle centroid | idle < 250 Hz | 2000 rpm centroid | 2000 rpm < 250 Hz |
|---|---|---|---|---|
| today | 1,901 Hz | 2.1% | 2,370 Hz | 2.4% |
| exhaust ×10 | 1,956 | 3.1% | 1,220 | 31.3% |
| exhaust ×10, mechanical ÷3 | 1,627 | 6.1% | **501** | **39.6%** |
| + combustion ÷2 | 1,841 | 6.5% | 474 | 46.9% |

Rebalancing alone fixes the sound off idle, but not at idle. On crdi15 and
hatch15 **the exhaust itself is bright at idle** (centroid 2.2–2.3 kHz,
1–8% below 250 Hz), while crdi22's is 87% bass. The exhaust path is
`d(flow)/dt` → pipe comb → a 2nd-order low-pass near 900 Hz → two −14 dB
notches at the muffler's resonances → a 35 Hz high-pass. A real muffler cuts
the broadband highs far more than two notches do. That is the second piece.

## The limit no synth change removes

A 4-cylinder's firing frequency is 25–27 Hz at idle and 67 Hz at 2000 rpm. **A
phone's own speaker reproduces little below a few hundred hertz**, so on a
phone speaker the fundamental can't be heard whatever the synth does. What
can be heard there is the firing *harmonics* (100–400 Hz). The ear infers
the low pitch from them (the "missing fundamental"). On headphones, a laptop
or a car's speakers the fundamental itself comes through. A bassier synth
helps on every device, but the most on headphones.

## Options

| | what | positives | costs |
|---|---|---|---|
| **A** rebalance the mix | raise the exhaust's level (its reference flow nearer the idle/cruise flow, or its mic gains); lower the tick and the injector clicks | one change; off idle it already gives the measured 2,370 → ~500 Hz centroid; the physics laws stay | idle stays bright on 2 of 3 cars; it reopens the owner's sign-off by ear (2026-09-30) |
| **B** A + a muffler model | a broadband muffler low-pass (insertion loss rising above ~200 Hz) in the exhaust path, from the spec's muffler length | bass at idle too; physically motivated (a muffler is a low-pass) | one new filter, so the idle sound changes on every engine, the truck included |
| **C** B + a "bass" option for phone speakers | a toggle that adds firing harmonics (100–400 Hz) for small speakers | the phone can sound deep | not physics: a playback effect, labelled as one |

Recommended: **B**, judged by ear with A/B WAV pairs before building, as
FINDING-017's were.

**Cost (B):**
- `livesound.py` (outside the grid hash), the TypeScript synth to match, and
  `acoustics.py`'s `render()` and `MICS` (the offline reference the synth
  is held to).
- `acoustics.py` is in the grid hash, but no cell reads the mix (cells carry
  the *sources*, built by `build_sources`, unchanged). So the ten grids are
  re-stamped with `tools/restamp_grids.py` and that proof (CLAUDE.md), not
  rebuilt.
- Sound fixtures regenerated.
- The I6 firing-peak test should only get easier.
- About one session, plus the listening round.

**Risk:** taste. The current balance is the one the owner signed off by ear
(REVIEW-006). The `hd_i6` tick-dominance question is still open, and this
answers it the same way.

## Questions for the owner

1. **What did you listen on:** the phone's speaker, headphones, or a
   laptop? (It decides how much C matters.)
2. **Which mic:** the default (outside, 7 m) or the cabin?
3. **Go ahead with A/B WAV pairs** (today against B, idle / 2000 rpm /
   full pedal, crdi15, hatch15, crdi22) for you to judge before anything is
   built?

---

## Correction and the listening round (2026-10-14, session 9)

**The owner's answers:**
1. Listened on: **the phone's speaker**.
2. Mics: **cabin and intake**.
3. A/B files: **yes**.

**At those mics, today's sound is measured the same way** (crdi15,
`tools/p10_sound_split.py . crdi15 800 0.05 cabin`). Each source's share of
the mix:

| | exhaust | combustion | mechanical | rumble | turbo | strongest bin |
|---|---|---|---|---|---|---|
| cabin, idle | 0.1% | 14.8% | 65.4% | 17.6% | 0.0% | 907 Hz |
| cabin, 2000 / 0.3 | 0.4% | 44.2% | 46.6% | 7.4% | 0.6% | 666 Hz |
| intake, idle | 0.0% | 11.3% | 80.5% | 4.6% | 0.0% | 907 Hz |
| intake, 2000 / 0.3 | 0.1% | 26.8% | 45.8% | 1.5% | 14.6% | 666 Hz |

- **At the cabin mic**, the mic's own 1.9 kHz low-pass already removes the
  3–7 kHz clicks. What is left is the 650–900 Hz band: the combustion
  knock's lowest mode (680 Hz) and the piston slap (900 Hz). The centroid
  is 700–850 Hz. A phone speaker plays exactly that band well, and not the
  bass under it.
- **At the intake mic under load**, 85–91% of the sound is above 2 kHz,
  and its level is 3–5× the cabin's. That is the turbo's whine plus the
  intake hiss.

**Correction: the muffler.** The table above says the idle exhaust "itself
is bright" on crdi15 and hatch15, and blames the muffler model. Measured
now:
- **99.6% of crdi15's idle d(flow)/dt sits in 2–4 kHz**, at exactly 180
  orders per revolution: the solver's 1° step's Nyquist (FINDING-028).
- **A 2° moving average** of the flow takes the idle exhaust's centroid
  from 2,159 to 208 Hz. At 2000 rpm it changes nothing (271 against 272 Hz).
- **With the zig-zag gone, a 300 Hz muffler low-pass** moves the cabin
  centroid only 492 → 481 Hz at idle, and 461 → 432 Hz at 2000 rpm.

So option B's second piece is **the zig-zag's removal, not a muffler
filter**. "Rebalancing alone fixes the sound off idle, but not at idle"
was true only because the zig-zag was being amplified with the exhaust.

**The listening files** (`python3 tools/p10_ab.py . OUTDIR`):
- One WAV per engine (crdi15, hatch15, crdi22) and mic (cabin, intake),
  34 s each.
- Each file plays idle, 2000 rpm at 30%, and 2500 rpm at full pedal. Each
  of those plays A, B and C for 3 s each, every segment at the same RMS so
  the ear compares tone, not loudness.
- **A:** today.
- **B:** the zig-zag averaged out (FINDING-028 option A); the exhaust ×8;
  the mechanical clicks ÷3; combustion ×0.6; the intake hiss ×0.4; the
  turbo ×0.4.
- **C:** B plus a +9 dB peak at 200 Hz (Q 0.8) on the output. That is a
  small-speaker bass boost, not physics.

The numbers (centroid, and the share below 250 Hz), crdi15:

| | cabin A | cabin B | cabin C | intake A | intake B | intake C |
|---|---|---|---|---|---|---|
| idle | 852 Hz, 11.5% | 474, 34.6% | 340, 48.3% | 1943, 2.2% | 1221, 19.2% | 760, 36.6% |
| 2000 / 0.3 | 707, 7.0% | 424, 35.5% | 301, 57.4% | 2533, 7.2% | 1248, 25.3% | 842, 33.2% |
| 2500 / full | 746, 17.9% | 216, 83.4% | 185, 89.5% | 3370, 10.3% | 1670, 50.1% | 761, 70.6% |

hatch15 and crdi22 move the same way at the cabin mic (B: 339–539 Hz,
183–195 Hz at full pedal). **At the intake mic under load they stay
bright even in B** (2,892–3,829 Hz, 66–79% above 2 kHz): their turbo
whine is that strong. Turning it down further is a taste question,
because a turbo diesel's intake does whistle.

**What B costs in level** (the synth's own RMS, before the files matched
it):
- Idle gets quieter: cabin 0.021 → 0.015, because the clicks went.
- Full pedal gets louder: 0.076 → 0.14–0.16, because the exhaust went up.
- So idle-to-full becomes about 20 dB instead of 11. C at full pedal reaches
  the output's soft clip (0.37 RMS). A build would recalibrate the levels.

**Questions for the owner, after listening:**
1. A, B or C, per mic?
2. At the intake mic, keep the turbo's whistle or turn it down further?
3. FINDING-028: hide the zig-zag in the synth now and fix the solver at
   the next rebuild (C, recommended)?

## The owner's decision (2026-10-14)

"B sounds better, go with C for findings": B, and FINDING-028's option C.
For loudness, which the files had hidden by matching levels, the owner chose
"Match at cruise". It is recorded as ADR-018, with the numbers.
