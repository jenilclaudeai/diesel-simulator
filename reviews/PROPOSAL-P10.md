# PROPOSAL-P10 — a deeper, bassier diesel sound (feasibility)

**The owner's Feat Prop P10** (priority 1, "Into Consideration"): "Current
sound is little high pitch. Actual diesel engines sound is more deeper and
bassy. For example CRDi, DDIS, TDC."
**Status:** measured, feasible; nothing built. Questions for the owner at
the end. (2026-10-13, session 9)
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
