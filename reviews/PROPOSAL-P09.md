# PROPOSAL-P09 — more knocking at high altitude (feasibility)

**The owner's Feat Prop P09** (priority 2, "Proposed"): "Knocking:
Increased knocking on high altitude".
**Status:** **decided 2026-10-14: option C.** The owner's answers: "1. C",
"2. Hear in enjoy also", "3. modern CRDi at Leh and a cold start". The
solver fix goes into the same rebuild as FINDING-028's option B (ADR-018).
Being built; the plan is at the end. *(Was: "measured; nothing built;
questions for the owner at the end. (2026-10-14, session 9)".)*
**Reproduce:** `python3 tools/p09_altitude_knock.py .` for the solver's
numbers; the prototype and listening numbers come from scratch scripts
described below.
**Found on the way:** FINDING-029 (the solver's knock mostly falls with
altitude, and the live loop can't hear altitude).

---

## What is real

Measured on real engines:
- **Wang, Ge and Yu, SAE 2013-01-1516**, "Combustion and Emission
  Characteristics of a Heavy-Duty Diesel Engine at Idle at Various
  Altitudes" (550–4500 m). At idle: the ignition delay lengthens; the
  combustion duration gets **shorter**; peak heat release rises with
  altitude up to 3300 m and drops at 4500 m. The pressure-rise curve
  follows the heat release. Peak cylinder pressure falls. (Read from the
  abstract page.)
- A search summary of two MDPI *Energies* papers (13/12/3080 and
  15/9/3083) says that a longer delay makes the premixed burn more abrupt.
  It also reports peak pressure rise rates above 50 bar/°CA at low speed at
  4500 m on a heavy-duty V6. **I could not open either paper (HTTP 403)**,
  so treat these as unverified.

So "more knock at altitude" is real, mostly through a longer delay and a
faster premixed burn. A modern turbo engine's ECU restores much of the
charge under load, so the effect is strongest at idle, at low load, and on
engines without a turbo.

## What the simulator does today (FINDING-029)

- **The delay is right.** At Leh, crdi15's idle delay is +41%; single10's
  is +46–49%.
- **The knock is wrong.** It falls at 6 of 9 points at Leh (by 4–14%), and
  rises by only 3–7% at the other three. There are two causes in
  `cycle.py`:
  - the premixed fraction is pinned at its 0.72 cap at every idle point;
  - the premixed burn gets **slower** as the mixture gets richer (its
    duration carries `30 × φ`), so thinner air softens the spike. The SAE
    data above says the burn gets shorter.
- **Where you'd see it:** `/cycle` shows "Combustion pressure rise",
  "Ignition delay" and "Premixed fraction" at the chosen place. Today, at
  Leh, the delay rises and the pressure rise falls.
- **Where you can't hear it:** Drive and Enjoy play the grid's sea-level
  sound at every place. The weather table corrects torque, fuel, boost,
  turbo, AFR and exhaust temperature, not the sound.

## What a fix would do (prototype, scratch only)

**V1** gives the premixed burn a duration without the φ term: it burns the
mixture the delay prepared, at a rate that doesn't depend on the overall
air. The patch to `cycle.py`, line 594:

```python
d_pre = max(4.0, 0.30 * (bd - 30.0 * min(phi_main, 1.3)))   # was 0.30 * bd
```

`phi_main` is the φ already computed at the main start of combustion.

A switches-off pass matched today's solver at 27 of 27 points, exactly.

| | today, Leh vs sea | V1, Leh vs sea |
|---|---|---|
| crdi15 idle | −13% | **+21%** |
| crdi15 2000 / 30% | −7% | 0% |
| crdi15 2400 / 100% | −12% | −7% |
| single10 idle / cruise / full | +3% / +7% / −14% | +5% / **+18%** / +1% |
| truck127 idle / cruise / full | −4% / −8% / +6% | −8% / −2% / **+14%** |

- **Sea level, across all six roster engines:**
  - full-load torque moves 0.6% or less, and fuel consumption 0.5% or
    less. The brochure test allows 3% on rated power;
  - peak pressure rises up to 5.1%;
  - the sea-level knock moves −11% to +31%. That would change the sound
    signed off in ADR-018, unless the synth's knock reference is
    re-scaled to cancel it.
- **V2** (V1, plus the cap raised 0.72 → 0.95) mostly made idle louder at
  sea level, with no gain at altitude. Not recommended.
- **V1 doesn't make every point rise.** The turbo engines under load stay
  flat or fall slightly. That is plausible, because their ECU restores the
  boost, but it is not proof.

## Can you hear it? Barely

I played the P10 synth with the knock multiplied, at the cabin, intake and
engine-bay mics:

| point | V1's knock change | at the mics | knock ×2 |
|---|---|---|---|
| crdi15 idle | ×1.21 | +0.27 to +0.36 dB | +1.5 to +1.9 dB |
| single10 1100 / 30% | ×1.18 | +0.02 to +0.12 dB | +0.1 to +0.8 dB |
| truck127 1080 / 100% | ×1.14 | +0.04 to +0.29 dB | +0.4 to +2.0 dB |

The smallest loudness change most people can hear is about 1 dB. After
P10, the exhaust carries the sound, and the combustion part scales only
linearly with the knock. **So a correct solver alone would show P09 on
`/cycle`, but you would not hear it in Enjoy**, even with the live loop
wired to it.

## Options

| | what | positives | costs |
|---|---|---|---|
| **A** record only | FINDING-029 stays open; nothing changes | no work, and no risk to the sound you just approved | `/cycle` keeps showing the pressure rise falling at altitude, which is wrong |
| **B** fix the physics at the next rebuild | V1 (re-derived, not just the prototype), done in the same rebuild as FINDING-028's solver fix. Re-scale the synth's knock reference so the sea-level sound stays as approved | `/cycle` and Dyno get altitude knock right (crdi15 idle +21% at Leh); one ~8 h rebuild covers both findings; torque and fuel barely move | `cycle.py` is hashed: all ten grids rebuilt with weather tables (about 8 h), golden fixtures regenerated, tests re-baselined. **Not audible** in Enjoy |
| **C** B, and make Enjoy hear it | B, plus the knock added to the weather table (live loop and TS port), plus a steeper knock law in the synth so a ×1.2 knock is about +2–3 dB | P09 as you wrote it: Enjoy at Leh knocks harder | everything in B, plus a new weather key (Python, TS, fixtures). The steeper law changes the P10 balance, so another listening round |
| **D** fake it in the synth | the synth's knock rises with the place's altitude by a chosen amount | quick; no rebuild; audible | the amount is invented, and Enjoy would disagree with `/cycle`. Against the project's premise that the sound comes from the physics |

**Recommended: A now, and B at the next rebuild.** C only if you want to
*hear* altitude knock, knowing that it means another listening round on
the P10 balance.

## Questions for the owner

1. **A, B, C or D?** (Recommended: A now, B with the next rebuild.)
2. **Do you want to *hear* it in Enjoy, or is it enough that the physics
   and `/cycle` show it?** That is the difference between B and C.
3. **Which case did you have in mind?** For example a modern CRDi at Leh,
   an old mechanical-pump engine, or a cold start. A modern turbo engine
   under load compensates (realistically), so the effect is mostly at idle
   and on single10.

---

## Building C: what the first day found (2026-10-14, later)

Measured on a scratch copy (`tools/p09_prototype.diff`). The numbers are
in FINDING-029 and FINDING-028.

1. **The sound's knock value was a measuring artefact for sharp burns.**
   It took a central difference of the 1° trace. **Fixed in the
   prototype:** the knock now comes from the burn law (the peak of
   `(γ − 1)/V × dQ/dθ` inside each step), which is the same at 1°, 0.5°
   and 0.25° (3.64 / 3.63 / 3.61).
2. **The burn itself was stepped coarsely.** It added the rate sampled at
   the step's end. **Fixed in the prototype:** it is integrated exactly
   over each step.
3. **The burn law needs both V1 and a delay term.** The best variant, V4
   with b = 0.5, speeds up the premixed burn by the delay that outlasts
   the injection. On crdi15 at idle it gives: **Leh +12%, a cold start
   +6%, Leh cold +11%** (today −18%, +1% and −17%). Other strengths were
   worse: V3 broke single10's sea-level calibration, and V4 with b = 1 is
   flat at Leh.
4. **The 1° step is not trustworthy at idle** (FINDING-028). The "Leh
   cold" point is an outlier at 1° in every variant. On single10 the 1°
   grid is about ~~22%~~ 18% low on torque at 600 rpm and 40% load, against a
   0.25° solve. *(Corrected later the same day: about 18%; the 0.25° solve it was measured against still zig-zags. See FINDING-028.)* The first fix tried for FINDING-028 (a linear orifice law)
   does nothing. The real fix is to sub-step the gas exchange.
5. **A cold start barely knocks more in this model.** Walls at 273 K
   lengthen the delay by only 9%. A real cold start combines cranking
   speed, cold intake air and cold walls.

**About hearing it:** +12% is under 0.3 dB in the P10 mix (a ×1.21 knock
measured 0.27–0.36 dB, above). Enjoy will
hear it only through the playback gain in the synth (`(dpdt_max /
dpdt_ref)^k`). The physics sets the direction and the relative sizes (Leh
more than a cold start); `k`, chosen by ear, sets how loud.

### Questions for the owner (round 2)

1. **In what order?**
   - **a. Staged (recommended).**
     - First the numerics, as their own PR, measured against 0.25° solves:
       sub-step the gas exchange (FINDING-028 B), integrate the burn
       exactly, and compute the knock from the burn law. This also fixes
       single10's ~~22%~~ 18%.
     - Then P09: the burn law, the knock in the weather table, and the
       synth's gain, with a listening round.
     - **One rebuild at the end.**
     - Positives: every number the rebuild bakes in has been checked
       against a fine step; one rebuild covers everything.
     - Cost: the longest route before you hear anything. Sub-stepping may
       also slow each solve, so the rebuild could take longer than 8 h.
       I'll measure that first.
   - **b. P09 now, on today's numerics,** with FINDING-028 later.
     - Positives: you hear P09 soonest.
     - Costs: the Leh-cold point is unreliable at 1°; two rebuilds (about
       8 h each); single10 stays ~~22%~~ 18% off until the second one.
   - **c. Build the grids at 0.5° instead of sub-stepping.**
     - Positives: the simplest code change; the cars' zig-zag is gone at
       0.5°.
     - Costs: grid builds take about twice as long, including custom
       engines in the browser; single10's VE is still 9% off at 0.5°.
2. **The cold start:**
   - **a. Take what the model gives** (+6%, made audible by the gain).
   - **b. Add a cold-start model** (cranking speed, cold intake air): more
     work, with a size I can only reason about, not calibrate.

   Recommended: **a** first; listen; then decide on b.

**The owner's answers (round 2, 2026-10-14):** "Staged (Recommended)" and
"Add a cold-start model". So, in order:
1. **Stage 1, the numerics** (their own PR): sub-step the gas exchange
   (FINDING-028 option B); integrate the burn exactly over each step; take
   the knock from the burn law. Each is checked against 0.25° solves.
2. **Stage 2, P09:** the burn law (V1 plus a delay term); **a cold-start
   model** (cranking speed and cold intake air, so a cold start's delay is
   long, as on a real engine); the knock in the weather table; the synth's
   gain `k`, chosen by ear.
3. **One rebuild** of all ten grids, with their weather tables.

**The listening round (2026-10-15).** The owner chose **k = 4**. That is
between the files' 3 and 5. Measured at idle (crdi15 and hatch15, cabin and
intake): a cold start or Leh +2.4 to +4.4 dB, both +8.7 to +10.2 dB. The
decision is ADR-019.

*Recorded late:* the cold-start model that was built is cold walls plus a
chamber warm-up in the live loop. It has **no cranking speed**, which the
chat said when building it ("Cranking speed won't be modelled"), but which
this file didn't record. Cold intake air comes in through the manifold
walls and the place's air. See ADR-019, item 3.
