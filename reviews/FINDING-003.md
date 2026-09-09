# FINDING-003 — clatter high-mode weight was pinned at its ceiling

**Opened by:** FINDING-002, which fixed the clatter excitation signal but
produced only a +2.9% cold/warm change in the rendered spectrum
**Lens:** PHY1
**Status:** fixed on `fix/combustion-dpdtheta`

## Symptom

After FINDING-002 corrected the clatter excitation to the combustion-driven
pressure rise, cold and warm renders still differed by only 2.9%.

## Root cause

`acoustics.py` weights the block/head structural modes by

```
sharp = min(3.0, meta["dpdt_max"] / 6.0e6)
w     = gn * (1.0 + sharp * (f0 / 2000.0) ** 1.1)
```

Measured `dpdt_max` across the shipped presets:

| preset | point | dpdt_max (Pa/s) | dpdt_max / 6.0e6 | sharp |
|---|---|---|---|---|
| crdi15 | 1800 / 0.6 | 4.95e9 | 825 | **3.000** |
| crdi15 | 3000 / 1.0 | 7.95e9 | 1324 | **3.000** |
| hd_i6 | 1700 / 1.0 | 5.59e9 | 932 | **3.000** |
| single | 2000 / 0.8 | 1.26e10 | 2107 | **3.000** |

The divisor is roughly three orders of magnitude too small. `sharp` sat pinned
at its 3.0 ceiling for **every engine at every operating point tested**. The
parameter did nothing. A 13% cold/warm difference in `dpdt_max` was absorbed
entirely by the clamp.

This is the third instance of the same failure mode in one chain: a clamp
silently absorbing the signal it was meant to bound. See also FINDING-001
(`premix_fraction` at its 0.02 floor).

## Fix

Divisor changed to `5.0e9`, putting the presets in a 1.0–2.5 band with
headroom above.

**This makes most engines duller than before**, because previously they were
all pinned at maximum high-mode excitation. That is a real, audible change to
every rendered sound and should be listened to before merging.

## Result — and honest limits

End to end, cold vs warm at `crdi15` 1800 rpm load 0.6:

| stage | cold/warm change |
|---|---|
| `premix_fraction` | +67% |
| `dpdtheta_comb` | +13.6% |
| combustion high-mode weight | +10% |
| **rendered high/low band ratio** | **+2.9%** |

The chain now works and moves in the right direction at every stage, but the
final acoustic difference is modest — around the edge of audibility, not the
dramatic rattle of a real cold diesel.

**Why, probably: real cold rattle is substantially mechanical, not
combustion.** Cold-shrunk pistons slap harder, thick oil changes valvetrain
seating, clearances are at their largest. Those are separate sources in
`acoustics.py` driven by `v_seating` and skirt clearance, and by oil viscosity
through the friction model. Oil temperature is a **separate state** from
coolant temperature (`oil.cond.T_oil`) and was held warm throughout all of this
work.

So the combustion path is now correct, and it is probably not the dominant
term. **Testing a genuinely cold engine — cold oil and cold coolant together —
is the obvious next step** and has not been done.

## Caveat

The 5.0e9 divisor is chosen to put four preset operating points in a sensible
band. That is a calibration, not a measurement, and it adds a fitted scalar to
a package that advertises having exactly two. It should be justified against
real cylinder-pressure data or derived, not left as a chosen constant.
