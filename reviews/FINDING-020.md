# FINDING-020 — the converter's lock-up clutch was numerically unstable, pinned at its clamp; bug #11's coast jolts were its symptom

**Opened by:** measuring known bug #11 ("coast downshifts use power-on calibration; lock-up is binary") before changing anything
**Lens:** PHY2 (lead), SR1, QA2
**Status:** fixed in `dieselsim/live.py` and its TypeScript port
**Reproduce:** `out/coast.py`, `out/coast_sweep.py` (not committed); the test `test_lockup_and_coast_downshifts`

---

## What was measured first

A torque-converter `crdi15` coasting from 100 km/h in top gear, throttle off,
light brake (0.08), on the fixture's 8 × 6 grid. The steady coast is
−0.65 m/s². Each coast downshift peaked at:

| shift | 7→6 | 6→5 | 5→4 | 4→3 | 3→2 | 2→1 |
|---|---|---|---|---|---|---|
| deceleration peak | +4.83 | −7.98 | −9.67 | **−13.01** m/s² | −1.83 | −2.24 |

That is over 1 g, where a real coast downshift is barely felt. The engine
jumped from idle to 2,300 rpm in 0.1 s. Bug #11's "a real TCU is gentler"
understates it by an order of magnitude.

## Why

Frame by frame, around the 5→4 shift: once lock-up engaged, the torque into
the gearbox flipped between **+4,500 and −4,500 N·m every sub-step**, and the
engine bounced between 1,050 and 2,130 rpm.

The lock-up was a spring: `T = C_LOCK · slip`, with `C_LOCK = 900 N·m per rad/s`,
integrated explicitly against the flywheel (0.22 kg·m²) at 240 Hz.
**h·C/J = 17**, and explicit Euler is only stable below 2. The ±4,500 N·m clamp
kept it bounded.

It was not only coasting. In the powered 60 s converter drive, **2,409 of
2,409 locked frames** had the lock-up torque at its clamp (median 4,829 N·m
into the box). It is CLAUDE.md's pattern exactly: a mechanism fed a quantity
pinned against a clamp, with no error raised. It had been in `play.py` all
along, and the Phase 3 port reproduced it faithfully, bit for bit.

## Fix

The lock-up is now a clutch, like the dual clutch and the manual box:

- **Engaging:** it slips at the capacity that pulls the engine onto input
  speed in `LOCK_ENGAGE_S = 0.5` s: `|T_eng| + J_flywheel · |slip₀| / 0.5`.
  The slip `slip₀` is latched when engagement starts; recomputing it from the
  live slip is the shift trap in PLAN.md.
- **Clamped:** once the slip closes (under 3 rad/s) or crosses zero, the
  driveline is rigid from crank to wheels. It is solved exactly as the DCT's
  clamped state, with the car's inertia reflected onto the crank, which is
  unconditionally stable.
- `C_LOCK` is kept, marked retired, for the record.

Options considered:
- an implicit (backward-Euler) spring, which is stable but keeps a stiff-spring
  model a real TCU doesn't have;
- a soft spring below 105 N·m per rad/s, which is stable but slips permanently
  by `T/C`.

Both were rejected, because the clutch model matches the other two boxes and
the real controller.

**Coast downshifts (the second half of bug #11).** They now stretch both shift
phases off-throttle: torque phase ×2 and inertia phase ×4, set by a gear
request with throttle below 0.05. Swept on the same coast-down:

| coast factors | worst overshoot, converter | worst overshoot, DCT |
|---|---|---|
| ×1 / ×1 (power-on) | 1.57 m/s² | **6.49** m/s² |
| ×1.5 / ×2 | 1.55 | 3.31 |
| ×2 / ×3 | 1.51 | 2.26 |
| **×2 / ×4 (applied)** | **1.51** | **1.74** |

Overshoot here means the excursion beyond both the steady deceleration before
the shift and the steady deceleration after it. Neither steady value changes
across a shift.

## After the fix

| | before | after |
|---|---|---|
| coast-down, converter, worst per shift | −13.01 m/s² | overshoot 1.51 m/s² |
| coast-down, DCT, worst | 6.49 m/s² | 1.74 m/s² |
| powered drive, locked frames at the clamp | 2,409 of 2,409 | **0** (2,394 rigid) |
| powered 60 s drive, final speed | 61.1 km/h | 63.2 km/h: slightly quicker, because the limit cycle's losses are gone |

**Not fixed, recorded.** The converter's remaining 0.2–1.5 m/s² (worst on
2→1 at 17 km/h) comes *after* the shift completes. It is the converter pulling
the engine up to the new input speed through its steep coupling curve. That is
real converter physics. A real TCU would also raise engine speed during the
shift, and that is not modelled.

Lock-up is still commanded on/off by the existing hysteresis rule. Only its
engagement is now slip-controlled, which answers bug #11's "lock-up is
binary" as far as the feel is concerned.

## Tests

- `test_lockup_and_coast_downshifts` (toy grid with engine braking at zero
  load): on a coast-down from 100 km/h, no locked frame reaches the clamp, and
  no downshift overshoots by more than 2 m/s² (converter or DCT).
- Mutations:
  - the old lock-up spring: 1,436 frames at the clamp, 9.30 m/s²;
  - power-on calibration for coast shifts: DCT 6.50 m/s².

  Both are caught; the unmutated baseline passes.
- The TypeScript port matches the new Python per step (worst 8.8e-16), with
  every event at the same step in all five fixture drives.
