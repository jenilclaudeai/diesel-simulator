# PROPOSAL — P08: an automatic that shifts on demand ("Practical torque converter")

**Date:** 2026-10-12 (session 9)
**Status:** for the owner's decision. Nothing in the app has changed. The
numbers come from a prototype patched onto `live.py` at run time:
`tools/p08_proto.py <repo> <base|B|C|C2|C3|C4> <preset ...>` (launches,
cruises, tip-in) and `tools/p08_gear_sweep.py <repo> <preset ...>` (today's
schedule, then every gear forced at each speed). About 25 min per vehicle on
an M2.
**Lenses:** PHY1 (driveline), SW1 (Python/TS parity), QA1 (tests), USR1/2
(feel), PM (scope)

The owner's sheet, Feat Prop P08 (priority 1, "Into Consideration"):

> Instead of shifting at fixed RPM, shift based on demanded torque. If it's
> getting enough torque you can upshift to optimize the fuel delivery.
> Except when whole throttle is press, it should focus on power and torque
> instead of fuel optimization (Basically what currently it does).

It is about the automatic's **shift schedule**. That is Enjoy's "Auto"
(the torque-converter box, `'tc'`) and Drive's `tc` and `dct`. The manual
is not touched.

---

## What the automatic does today, measured

`Gearbox.update_schedule` (`dieselsim/live.py`, ported in
`web/physics/src/live/driveline.ts`) upshifts when the turbine passes

    up = 0.86 × rated × (0.80 + 0.28 × throttle)

so 69% of rated rpm at zero throttle and 96% at full. It downshifts below a
similar line. Torque never enters it: the same pedal gives the same shift
rpm in every gear, whatever the engine has to spare.

Launches from rest, warm engine, constant pedal: the engine rpm at each
upshift.

| vehicle (rated rpm) | 20% pedal | 50% | 100% |
|---|---|---|---|
| hatch15 (4000) | 2,945–2,998 | 3,232–3,384 | 3,886–3,962 |
| crdi15 (4000) | 2,966–2,971 | 3,234–3,364 | 3,878–3,960 |
| crdi22 (3800) | 2,797–2,853 | 3,071–3,215 | 3,706–3,910 |
| truck127 (1800) | 1,325–1,463 | 1,455–1,783 | 1,915–1,920 |

The cars' torque is near its peak from about 1,750 rpm (hatch15 238 N·m
at 1,750, 254 at 2,500), so a gentle driver is held 1,000+ rpm above where
the engine needs to be.

### What it costs at a steady speed

Each speed was held for 90 s by a PI "driver", then repeated with every
gear forced. Fuel is the grid's own (steady-state, FINDING-009). "Least
fuel" is the best gear that can hold the speed.

| vehicle | speed | today: gear, rpm | L/100 km | least fuel: gear, rpm | L/100 km | saving |
|---|---|---|---|---|---|---|
| hatch15 | 30 | 2nd, 2,133 | 4.64 | 3rd, 1,395 | 3.29 | −29% |
| | 50 | 3rd, 2,276 | 3.83 | 5th, 1,311 | 2.83 | −26% |
| | 80 | 5th, 2,097 | 3.72 | 6th, 1,738 | 3.55 | −5% |
| | 110 | 6th | 4.29 | the same | | 0 |
| crdi15 | 30 | 2nd, 2,239 | 3.98 | 3rd, 1,506 | 3.16 | −21% |
| | 50 | 3rd, 2,462 | 3.63 | 5th, 1,430 | 2.80 | −23% |
| | 80 | 5th, 2,288 | 3.43 | 6th, 1,941 | 3.24 | −6% |
| | 110 | 6th, 2,669 | 4.70 | 7th, 2,310 | 4.56 | −3% |
| crdi22 | 30 | 2nd, 2,264 | 7.56 | 4th, 1,238 | 4.32 | −43% |
| | 50 | 4th, 1,997 | 5.16 | 6th, 1,196 | 3.99 | −23% |
| | 80 | 5th, 2,468 | 5.78 | 8th, 1,282 | 4.71 | −19% |
| | 110 | 7th | 6.24 | the same | | 0 |
| truck127 | 30 | 2nd, 1,144 | 29.1 | 3rd, 820 | 24.0 | −18% |
| | 50, 70 | 4th, 5th | | the same | | 0 |
| | 90 | **hunts 5th ↔ 6th** (2 shifts in 50 s) | 42.0 | 5th, 1,309 | 36.5 | −13% |

In the least-fuel gear the cars still keep 73–96% of their torque in
reserve, so it isn't lugging. And the least-fuel gear is **not** simply the
highest gear that can hold the speed. One gear higher is worse for the cars
at 30 km/h, and for the truck at 90.

---

## The trap in "demanded torque"

This loop's pedal sets a **fuel fraction**, so the torque reserve in the
*current* gear is about 1 − pedal in **every** gear. A rule of the form
"downshift when the reserve is short" downshifts, finds the same shortfall
in the lower gear, and downshifts again. Demand has to be read from the
pedal as **power**, which carries across gears:

    P_dem = f(pedal) × peak power

A gear qualifies if its full-load power at its rpm covers `P_dem` with a
reserve: 20% to move into it, 5% to stay in it. At full pedal no gear
qualifies, and the box uses today's schedule unchanged. That gives the
owner's "except when the throttle is fully pressed" without a separate
switch. Kickdown stays as it is.

---

## The options, prototyped

All three share the qualifying test above. Same harness, same four
vehicles, same warm engine.

**A. Lower today's rpm lines at light pedal** (not prototyped). The
smallest change. It still ignores torque, it needs a hand-tuned line per
engine, and a custom engine (ADR-014) gets a guess.

**B. Torque reserve only: the highest gear that qualifies.** This is the
literal reading of P08.
- At steady speed it lands near the least fuel: hatch15 50 km/h 2.98
  against 2.82 at best; crdi22 50 km/h 4.07 against 3.98.
- **It hunts and it lugs.** hatch15 at 30 km/h shifted **27 times in
  50 s**. crdi22 at 50 km/h sat in 7th at 1,004 rpm.
- Avoiding that would need a hand-tuned rpm floor per engine, which is
  option A's problem again.

**C. Fuel map: of the gears that qualify, the one the engine's own grid
says burns least** for the power being delivered. A move needs a minimum
saving, so the box doesn't dither between two gears with almost the same
fuel use.
- It needs no tuning per engine: every grid, custom engines included,
  already carries the fuel map.
- On the cars it cruises in the least-fuel gear, or within the minimum
  saving of it, and it never shifted in the last 50 s of any cruise. See
  the table below.
- Its first version (C) borrowed today's rpm line as a ceiling. On the
  truck, rated at 1,800 rpm, that line sits where it cruises, so it
  hunted. C2 replaced it with 95% of rated rpm and fixed the cars, but the
  truck still shifted 3–4 times in 50 s at 70 and 90 km/h.
- The trace showed why: the test driver overshoots, lifts off and the box
  upshifts; the truck sags, the pedal rises, and the momentary power says
  downshift.
- **C3** smoothed the power reading over 2 s, asked a 6% saving for any
  move, and read demand as pedal^1.5. The truck stopped hunting at 70 km/h
  (4 → 0 shifts), but the cars regressed. The 6% bar trapped them a gear
  low: hatch15 at 110 km/h stayed in 5th on 4.38 L/100 km, worse than
  today's 4.29. Half pedal still shifted at 3,600–4,000 rpm, because where
  specific fuel use is flat no upshift clears the bar.
- **C4** makes the bar asymmetric, as production economy schedules do: an
  upshift needs a 1% saving, a downshift for fuel alone 6%. The rest is
  C3's.

| | today | C2 | **C4** |
|---|---|---|---|
| hatch15 cruise 30 / 50 / 80 / 110 (L/100 km) | 4.64 / 3.83 / 3.72 / 4.29 | 3.29 / 2.82 / 3.55 / 4.29 | **3.29 / 2.82 / 3.55 / 4.29** |
| crdi15 | 3.98 / 3.63 / 3.43 / 4.70 | 3.16 / 2.86 / 3.24 / 4.56 | **3.16 / 2.80 / 3.24 / 4.56** |
| crdi22 | 7.56 / 5.16 / 5.78 / 6.24 | 4.31 / 3.98 / 4.79 / 6.28 | **4.31 / 3.98 / 4.71 / 6.24** |
| truck127 cruise 30 / 50 / 70 / 90 | 29.1 / 27.1 / 30.2 / 42.0 | 23.9 / 27.1 / 30.1 / 41.5 | **23.9 / 27.1 / 30.1 / 42.1** |
| shifts in the last 50 s of a cruise (16 cruises) | truck 90: 2 | truck 70: 4, 90: 3 | **truck 90: 2** (as today) |
| full pedal: 0–100 km/h, hatch15 / crdi15 / crdi22 | 10.5 / 12.8 / 11.5 s | the same | **the same, shift rpm identical** |
| 20% pedal, upshift rpm: hatch15 / crdi15 / crdi22 | 2,945–2,998 / 2,966–2,971 / 2,797–2,853 | 2,462–3,013 / 2,305–2,506 / 2,240–2,719 | **2,141–2,303 / 2,192–2,384 / 1,595–1,856** |
| half pedal, upshift rpm: hatch15 / crdi15 / crdi22 | 3,232–3,384 / 3,234–3,364 / 3,071–3,215 | later on all three | **3,651–3,937 / 2,776–3,191 / 2,932–3,786** (mixed) |
| 60% tip-in from 50 km/h, km/h gained in 6 s: hatch15 / crdi15 / crdi22 / truck | 30.9 / 23.4 / 29.5 / 7.9 | 30.3 / 23.8 / 26.5 / 9.6 | **30.3 / 19.4 / 26.5 / 9.6** |

**C4 puts every car cruise in its least-fuel gear.** All 12 match the
gear-by-gear sweep above, with no hunting, and full pedal is unchanged. The
saving below 110 km/h is 3–43%. Three things are still open:
- **Half pedal is mixed:** crdi15 shifts earlier than today, hatch15 and
  crdi22 later.
- **crdi15's tip-in is softer:** +19.4 km/h in 6 s against +23.4.
- **The truck at 90 km/h** still shifts twice in 50 s, exactly as today's
  box does. It is near its power limit there (56% reserve in 6th, 5th and
  6th within 3% on fuel), and the test driver's overshoot drives it.

---

## Recommendation: C4, for the Auto boxes on Enjoy and Drive, built now

The owner asked to continue with P08, so it would be built before Phase 8.
P08 is not in PLAN or ADR-016 today; PLAN would gain it as a Phase 7
follow-up.

**Positives**
- It does what P08 says: light pedal shifts early to save fuel, and full
  pedal is today's power schedule, measured identical.
- It uses the engine's own fuel map, so custom engines (ADR-014) get it with
  no tuning.
- Enjoy's trip computer rewards gentle driving: 3–43% less fuel on the
  cars below 110 km/h.

**Costs and trade-offs**
- **Lower cruise rpm is a different sound:** 1,196–1,941 rpm instead of
  1,997–2,468 on the cars below 110 km/h. That's realistic for a modern diesel
  automatic, but it is a change.
- **The same part pedal gives less push in a higher gear.** A stab of
  throttle still kicks down. crdi15's tip-in is 17% softer and would be
  tuned in the build.
- **The live fixtures change.** The `tc`, `dct`, `dct_hot` and kickdown
  drives must be regenerated and the TS port re-matched to 1e-6 (ADR-004).
  There is **no grid rebuild**: `live.py` is outside the grid hash.
- **Per-frame cost:** a fuel-map lookup for each gear, five times a second,
  not every frame. Measured with `npm run perf` before merging.
- **The prototype's numbers used friction updated once per simulated
  second** (the app: every 6 frames), the same for every variant compared.
  The build's tests use the real cadence.

**What would be built**
1. `live.py`: `Gearbox` gets the economy schedule, fed by the loop's map,
   with today's schedule as its full-pedal and kickdown branch. Then the
   port in `driveline.ts` / `engine.ts`.
2. Fixtures regenerated, and TS parity.
3. Tests, each mutation-tested against a passing baseline:
   - the cruise gear is the least-fuel gear at 30 and 50 km/h on two
     vehicles;
   - no shifts in a held car cruise;
   - full pedal shifts at today's rpm;
   - the coast-down test (bug #11) still passes;
   - the half-pedal rule the owner picks (below).
4. PLAN and DECISIONS: P08's place, and an ADR for the schedule.

## Questions for the owner

1. **The approach:** C4 (recommended), B, or A?
2. **Which boxes:** Enjoy's Auto and Drive's `tc` and `dct` (recommended,
   since they share one schedule), or Enjoy's Auto only?
3. **Half pedal:** never later than today's shift point (recommended: no
   car feels lazier than it does now), pure fuel map (today's mixed
   result), or deliberately sportier?
