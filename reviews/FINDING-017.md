# FINDING-017 — piston slap and valve tick lose their physical scaling in the mix; mechanical-lash engines seat valves off the ramp

**Opened by:** preparing the A/B listening pairs FINDING-004 was never judged
on (`tools/render_ab.py`)
**Lens:** QA2 (lead), PHY2
**Status:** measured, not fixed — fixes are decisions, see Options
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
