# FINDING-006 — `h_min_ring` is pinned at its floor and exposed as a headline field

**Found by:** `tools/audit_dead_signals.py`, written after four consecutive
findings shared the same shape
**Status:** fixed — PR #5; `h_ring_tdc` renamed honestly, read `h_ring_mid`. *(Updated 2026-09-23: this line was not updated when the fix landed, and read "diagnosed, not fixed" until then.)*

## The audit

102 scalar outputs across 8 operating points spanning two presets pairs, cold
and warm, light and heavy load, 1200–3000 rpm.

| class | count | result |
|---|---|---|
| DEAD (exactly zero everywhere) | 0 | none |
| FROZEN (identical everywhere) | 2 | `fric.h_ring`, `op.h_min_ring` |
| TINY (boundary power negligible) | 1 | `Pb_valvetrain` |

The zero DEAD count is worth stating: after the roller-follower fix, no output
is structurally dead. The package is in better shape than the run of findings
might suggest.

## The finding

`h_ring` and `h_min_ring` return **exactly 1.2e-8 m in all eight cases** —
identical to floating-point equality across a 90 K coolant swing, a 5× load
range and four different engines.

That is `h_floor = 12e-9`, the clamp in `lubrication.ring_film_thickness()`.
The reported minimum ring film is the clamp, always.

## Why it matters

`PROJECT_CONTEXT.md` §2.3 already warns:

> `h_ring` is the instantaneous minimum, which always occurs at TDC/BDC where
> piston speed is zero and tells you nothing. Read `h_ring_mid`.

That is correct, and the audit confirms it quantitatively. But two things
follow that the note does not cover.

**1. `h_min_ring` is a top-level field on `OperatingPoint`.** It sits in the
headline list alongside `h_min_rod` and `h_min_main`, both of which *do* vary.
Any dashboard built from that structure will show a ring-film gauge that never
moves, next to two bearing gauges that do. The Angular build guide (§3.5)
specifically calls for film gauges on the vitals panel.

A number that is always the clamp is worse than a missing number, because it
looks like a measurement.

**2. It cannot be distinguished from a real reading.** 12 nm is a physically
plausible boundary-regime film. Nothing in the value announces that it is a
floor.

## Options

1. **Expose `h_ring_mid` on `OperatingPoint`** and either drop `h_min_ring` or
   rename it to something that cannot be mistaken for a measurement. Cheapest,
   and it matches the guidance already in the docs.
2. **Report the minimum over the mid-stroke window only**, so the field means
   what a reader assumes it means.
3. **Return NaN when the clamp binds.** Honest, and it forces every consumer to
   handle it, but it will break naive plotting.

Recommendation: 1. `h_ring_mid` already exists in `FrictionResult` and is the
quantity the documentation tells you to read. Promote it and remove the trap.

## On the pattern

This is the fifth instance, and the audit now exists to catch the sixth. Worth
running after any change to the physics, and worth porting alongside the
solver — the same failure in TypeScript would be considerably harder to find.

## Caveat

Eight operating points, four presets, no EGR, no wear accumulation, one
`n_cycles`. FROZEN means "did not move under these conditions", not "cannot
move". A wider matrix might unfreeze something, and `EXPECTED_CONSTANT` in the
script currently excludes the EGR fields by hand, which is a judgement that
should be revisited if EGR is ever exercised.
