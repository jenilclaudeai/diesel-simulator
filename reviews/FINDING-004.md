# FINDING-004 — the sound engine discards every physical amplitude

**Opened by:** FINDING-003, where a fully cold engine with 255% more friction
rendered 11% *quieter*
**Lens:** PHY1, QA2
**Status:** diagnosed, not fixed — this is architectural
**Severity:** highest of the four findings

## Symptom

Cold oil plus cold coolant at `crdi15` 1800 rpm, load 0.6:

| | FMEP | friction power | torque |
|---|---|---|---|
| fully warm | 1.104 bar | 2.48 kW | 124.3 N·m |
| cold coolant only | 1.470 bar | 3.31 kW | 121.6 N·m |
| **fully cold** | **3.922 bar** | **8.82 kW** | 98.3 N·m |

A genuinely cold engine has **+255% friction**. Rendered:

| | change |
|---|---|
| brightness (hi/lo band ratio) | +1.0% |
| loudness (RMS) | **−11.2%** |

More than triple the mechanical losses, and the engine gets quieter.

## Root cause

There are two normalisation stages, and between them they remove every
amplitude the solver computed.

**Stage 1 — each source is normalised to unit standard deviation:**

```
out["exhaust"]    = y / (np.std(y) + 1e-12)          # line 356
out["combustion"] = knock / (np.std(knock) + 1e-12)  # line 398
out["mech"]       = mech / (np.std(mech) + 1e-12)    # line 413
out["turbo"]      = y / (np.std(y) + 1e-12)          # line 434
out["rumble"]     = rum / (np.std(rum) + 1e-12)      # line 455
```

**Stage 2 — mixed with fixed per-mic constants, then normalised again:**

```
for k, gn in m.gains.items():
    y += gn * out[k]
...
lvl = (0.25 + 0.75 * min(1.6, meta["load"])) * (0.45 + 0.55 * spd)
y = _softclip(y / (np.std(y) + 1e-12) * 0.22 * lvl, 1.1)
```

**Final loudness is a function of load and speed only.** Nothing else reaches
it — not friction, not blow-by, not wear, not oil condition, not boost, not
peak cylinder pressure.

**Relative balance between sources is a fixed constant per mic.** A worn engine
cannot have proportionally more piston slap. A cold engine cannot have
proportionally more rumble. The `rumble` source is driven by boundary-friction
power, which just tripled, and it arrives at the mix at exactly the same level
as before.

## What survives

The physics is not entirely absent. What reaches the listener:

- **Waveform shape** of each source, which is real and correctly derived
- **Pitch and timing** — crank-angle synthesis resampled through instantaneous
  rpm. This is genuinely excellent and should not be touched.
- A handful of post-normalisation scalars: `sharp` on the combustion high modes
  (FINDING-003), the load term on `gear`, the firing modulation on `rumble`

So `PROJECT_CONTEXT.md` §1.3's claim that "every source is driven by something
the solver already computed" is **true for shape and timing, false for level
and balance**.

## This explains known bug #9

Bug #9 records that the worn-vs-new audio pair is "suspect". It would be. Wear
changes ring gap, blow-by, lash and clearances — all of which alter source
*amplitudes*, and all of which are normalised away. The pair should sound
nearly identical, and reportedly does.

The bug is not in the wear model. It is here.

## Fix path — substantial

1. **Give each source a physical amplitude reference.** Sound power from mass
   flow, from `dp/dt`, from impulse energy, from boundary-friction power. These
   are all computed already.
2. **Calibrate once to an absolute scale**, e.g. SPL at 1 m for a known engine
   at a known operating point.
3. **Mix without renormalising.** Mic gains become distance and directivity,
   not level correction.
4. **Keep a final limiter** for clipping only, not for level setting.

This is a redesign of the mix stage, not a patch. It should be done before the
TypeScript `AudioWorklet` port (ADR-003), because porting the current design
would carry the defect into the browser and make it much harder to fix later.

## Recommendation

Do this **before** Phase 4. It is the difference between a simulator whose
sound is a consequence of its physics and one where the physics selects a
timbre and the volume knob is turned by load and rpm alone.

## Caveat

One preset, one operating point. The normalisation is unambiguous from the
source, but the claim that "final loudness depends only on load and speed" is
read off the code rather than measured across a sweep. Worth confirming with a
sweep before acting.
