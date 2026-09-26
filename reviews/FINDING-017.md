# FINDING-017 — piston slap and valve tick lose their physical scaling in the mix; mechanical-lash engines seat valves off the ramp

**Opened by:** preparing the A/B listening pairs FINDING-004 was never judged
on (`tools/render_ab.py`)
**Lens:** QA2 (lead), PHY2
**Status:** measured, not fixed — fixes are decisions, see Options
*(Updated 2026-09-26: the line above is stale. Item 1 is fixed (PR #34), item 2 is fixed by raising the ramps (PR #37), and seating at ramp speed is PR #43. Item 3 was not applied. By-ear sign-off is a Phase 4 exit criterion.)*
**Reproduce:** `python3 tools/render_ab.py --levels` (needs scipy)

---

## What the listening pairs show

`crdi15` 1800 rpm / 0.6, warm vs fully cold (oil and coolant 273 K), exterior
mic at 7 m:

| | warm | cold | change |
|---|---|---|---|
| loudness (RMS) | 0.0372 | 0.0385 | +3.5% |
| brightness (> 1.5 kHz / < 1.5 kHz) | 0.166 | 0.213 | **+28.3%** |
| FMEP | 1.038 bar | 3.915 bar | +277% |

That is the direction FINDING-004 was meant to produce (before it: +1.0%
brighter, −11.2% quieter). Per source: exhaust +12.6%, combustion +3.2%,
turbo +20.8%, **mechanical +0.0%**, rumble −6.9%.

## 1. The mechanical sub-mix normalises piston slap and valve tick away

`EngineSound.render()` scales valve tick by `(v_seating / 1.2)^1.5` and
piston slap by `(skirt_clr / 30 µm)^0.6`, then mixes them as

```
mech = tick / std(tick) + 0.75 · inj / std(inj) + 0.9 · slap / std(slap)
```

Dividing each component by its own standard deviation discards the scaling
just applied — FINDING-004's pattern, surviving inside one sub-mix. The whole
sub-mix is then scaled by `(v_seating / 0.10)^2`, so mechanical noise depends
on seating velocity alone.

Measured: doubling the slap input changes the mechanical output by
**3.6e-11** (its RMS is 0.43) — nothing. That is why a cold engine's
mechanical noise does not move.

Also: the "slap clearance" fed in is `op.friction["h_skirt"]`, the skirt **oil
film** (13.2 µm here), not the piston-to-bore clearance. A cold piston is
looser (more slap) but its film is thicker — related, not the same quantity.

## 2. Mechanical-lash engines seat their valves off the closing ramp

`Cam.seating_velocity()` is `v_ramp · ω · (1 + 2.2 · lash / h_ramp)`. When the
lash is taller than the ramp, the valve lands on the steep flank and the
factor grows large:

| preset | exhaust lash | ramp height | factor | v_seat at 1500 rpm |
|---|---|---|---|---|
| `crdi15`, `crdi_1p5`, `ld_i4` | 0 (hydraulic) | 67–73 µm | 1.00 | 0.044–0.047 m/s |
| `single` | 250 µm | 69 µm | 8.96 | 0.392 m/s |
| `hd_i6` | 550 µm | 106 µm | **12.39** | **0.806 m/s** |

With the mechanical level going as seating velocity squared (reference
0.10 m/s), `hd_i6`'s mechanical source is ~45× every other source in its mix:
valve clatter drowns it. Production cams put ramp height above the lash so the
valve seats on the ramp; so either these specs' ramps are too low or the
formula should saturate once the lash exceeds the ramp. Which, is a judgement.

## 3. Rumble falls when the engine is cold — defensible, but the comment says otherwise

Rumble tracks boundary friction in rings, skirt and bearings. A cold engine's
thick oil builds thicker films, so boundary contact *falls* (the +277% FMEP is
viscous). Quieter rumble cold (−6.9%) is physically reasonable. The code's
comment ("what makes a cold or worn engine sound busier") claims the
opposite; the claim, not the physics, is wrong for cold.

## Options (not applied)

| item | option | positives | trade-offs |
|---|---|---|---|
| 1 | Keep each component's physical scale: normalise tick, injector and slap to a *fixed* reference (e.g. their std at a reference operating point) instead of their own std | slap and tick finally respond to clearance and seating; small change | every mechanical level moves; needs the reference chosen |
| 1 | Feed slap from a piston-to-bore clearance model (cold contraction, wear) instead of the oil film | the physically right input | a new quantity to model |
| 2 | Raise the mechanical-lash presets' ramp height above their lash | matches how real cams are designed; one spec field per preset | changes those presets' valve events slightly |
| 2 | Saturate the seating factor once lash exceeds the ramp | keeps the specs | a modelling choice about what an off-ramp landing sounds like |
| 3 | Fix the comment | trivial | — |

## Caveats

One operating point per pair; one microphone. Loudness and brightness are
numbers, not listening — the WAVs are in `out/listen/` for that.

---

## Item 1 fixed (session 4, owner's decision: fixed-reference normalisation)

Each mechanical component is normalised for shape only and carries its own
physical level; the sub-mix is not renormalised:

| component | level |
|---|---|
| valve tick | (v_seating / 0.10 m/s)² |
| piston slap | (skirt input / 30 µm)^0.6 — the input is still the oil film (not changed) |
| injector | fixed reference |

**Re-measured:** doubling the slap input now changes the mechanical output by
1.48 on an RMS of 1.01 (was 3.6e-11).

**Consequences, stated plainly:**

- `crdi15`'s mechanical level rises 2.3× (0.43 → 1.01): injector and slap were
  being scaled down by the valve factor (0.43 for a hydraulic-lash engine).
  The warm/cold pair is now +11% brighter cold (was +28%) because the
  brighter baseline dilutes the relative change; loudness +2.8%.
- `hd_i6` becomes far brighter (4.96 → 131): its tick keeps the 45× factor
  from lash above the ramp (item 2, not fixed), while slap and injector no
  longer ride on it. **Item 2 now matters more** — `hd_i6` sounds like
  high-frequency valve clatter.

Test `test_mech_levels_carry_physics` (slap input ×2 and seating ×2 must each
raise the mechanical level by > 5%; measured +17% and +92%; SKIP without
scipy). Mutation: the old renormalised sub-mix, a dropped slap level and a
dropped tick level are each caught.

Items 2 (ramp vs lash) and 3 (the rumble comment) are not applied — the
owner chose item 1 only.

---

## Item 2 fixed (session 4, owner's decision: raise the ramps)

`hd_i6` and `single` now set `ramp_fraction` so both closing ramps are at
least 1.25 × their lash (the dataclass default, shared by every preset and by
`builder.py`, is unchanged):

| preset | ramp_fraction | exhaust ramp vs lash | seating at 1500 rpm | reference-point effect |
|---|---|---|---|---|
| `hd_i6` | 0.06 → 0.155 | 106 → **697 µm** (lash 550) | 0.806 → 0.452 m/s | 1700/1.0: torque −0.09%, p_max −0.37% (inside the 0.5% golden tolerance) |
| `single` | 0.06 → 0.13 | 69 → **321 µm** (lash 250) | 0.392 → 0.254 m/s | 2000/0.8: torque +0.08% |

**`hd_i6`'s valve tick falls from ~41× to 13× its loudest other source** —
3.2× quieter, but still dominant (`crdi15`'s is 0.9×). Two things keep it
high, both judgements best made by ear:

- `Cam.seating_velocity()` keeps its lash penalty `(1 + 2.2 · lash / h_ramp)`
  even when the valve lands on the ramp; on a true constant-velocity ramp the
  seating speed is the ramp speed.
- The absolute tick level is set by `_ref_vseat = 0.10 m/s` — a calibration
  choice, not a measurement.

Test `test_closing_ramps_clear_the_lash` (every preset, both cams). Mutation:
reverting either preset's ramp is caught. (A first run showed a spurious
failure after restoring the file: a same-length edit within one second reused
stale bytecode. Rerun with `PYTHONDONTWRITEBYTECODE=1`, it passed.)

`builder.py` engines with mechanical lash still get the default 6 % ramp and
could land off-ramp too; not changed here.

## Item 2 follow-up (session 5, owner's decision: seat at ramp speed)

`Cam.seating_velocity()` no longer applies the lash penalty
`(1 + 2.2 · lash / h_ramp)` when the lash is inside the closing ramp. There,
the valve seats at the ramp's own constant speed. Lash taller than the ramp
keeps the penalty, by the owner's decision. That leaves a jump of ×3.2 at
lash = h_ramp. The honest off-ramp value would be the flank's slope at the
lash height, which is a separate change.

Built on FINDING-018 (PR #42), which doubled every ramp speed. Mechanical
source levels as the mix weights them (`out/tick_dom.py`, not committed):
tick `(v_seat/0.10)²`, injector 0.75, slap `0.9·(clr/30 µm)^0.6`, each at
unit std.

| point | `main` (old profile) | after #42 | after this change |
|---|---|---|---|
| `hd_i6` 1250/0.5, tick ÷ loudest other | 18.9× | 75.7× | **13.0×** |
| `single` 2000/0.8 | 15.3× | 61.3× | **10.6×** |
| `crdi15` 1800/0.6 (lash 0, no change) | 0.57× | 2.30× | 2.30× |

**Correction:** item 2 above says `hd_i6`'s tick fell "from ~41× to 13×" and
that `crdi15`'s is 0.9×. On the same tree, the measure written out here gives
18.9× and 0.57×. That text used a different measure, which it did not record,
so the two sets of numbers are not comparable. The table here is the one to
use from now on.

`hd_i6` and `single` stay tick-dominant, because their ramps are steep. With
this profile, ramp speed scales with `ramp_fraction × lift`, so raising the
ramp to clear large lash (item 2) also sped it up (0.074 mm per cam degree
on `hd_i6`). A real cam clears lash with a long, gentle ramp: its height and
speed are independent. That needs a ramp-height parameter separate from
`ramp_fraction`, which is a sound-design change for Phase 4, judged by ear.

Test `test_seating_on_ramp_is_ramp_speed`: `hd_i6`'s exhaust seats at its
numerical ramp slope, and a cam with lash twice its ramp keeps the penalty.
Mutations: putting the penalty back on the ramp fails the first check;
removing it everywhere fails the second. The unmutated baseline passes.
Suite 42 passed, 0 failed, 2 known.
