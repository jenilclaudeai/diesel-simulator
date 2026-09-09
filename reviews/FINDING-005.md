# FINDING-005 — lash growth is identically zero, so valvetrain tick never ages

**Opened by:** FINDING-004's fix, which made source levels physical and then
showed a worn engine rendering *quieter* than a new one
**Status:** diagnosed, not fixed
**Confirms:** the second half of known bug #9

## Measurement

`crdi15`, 8000 hours via `durability_run(8000.0, step_h=400.0)`:

| | v_seating | lash_growth_int | h_skirt |
|---|---|---|---|
| new | 0.06564 | **0.00 µm** | 12.817 µm |
| worn 8000 h | 0.06564 | **0.00 µm** | 13.434 µm |

Seating velocity is **identical to five significant figures**. Lash growth is
exactly zero after 8000 hours.

Known bug #9 recorded that the worn engine showed "zero lash growth". That is
confirmed, and it is not a reporting artifact — the state itself never moves.

## Why it matters

`PROJECT_CONTEXT.md` §1.3 lists valvetrain tick as driven by "cam seating
velocity, growing with lash wear", and `kinematics.py`'s constant-velocity cam
ramps exist specifically so that finite seating velocity is physical. The
mechanism is built. The input never changes.

With FINDING-004's fix in place, the `mech` source level now scales with
`v_seating²`. Since `v_seating` is constant, a worn engine gets no extra
valvetrain noise, and the durability story is inaudible.

## The worn engine is now quieter, and that is currently correct

After FINDING-004:

| | RMS | brightness |
|---|---|---|
| new | 0.1825 | 6.795 |
| worn 8000 h | 0.1600 | 6.345 |
| | **−12.3%** | **−6.6%** |

This is a faithful consequence of the wear model, not a new bug in the mix.
At 8000 h the engine reports only **5.6% life consumed**, blow-by moves 7.0 →
7.4 L/min, and skirt clearance grows 0.6 µm. The one thing that should get
louder — valvetrain tick — is pinned. What remains is slightly reduced airflow,
so the engine is slightly quieter.

**A worn diesel should sound busier, not quieter.** Getting there needs the
lash path fixed first; the mix is now capable of carrying it.

## Where to look

`wear.py` tracks `lash_growth_int` / `lash_growth_exh` in `WearState`, and
`K_ARCHARD["cam"] = 3.2e-9`. Either the cam wear is not being converted into
lash, or the conversion is scaled to nothing. Not yet traced.

## Caveat

One preset, one duration, default duty cycle. 8000 h at 5.6% life consumed
suggests the duty cycle used here is gentle; a harsher one may move lash. That
has not been tested, and it would change the conclusion from "the path is dead"
to "the path is very insensitive".

---

## Root cause found — and it goes deeper than the lash state

`durability_run` (`engine.py:566`) correctly feeds **boundary** powers to the
wear model, remapping them onto the `P_*` key names:

```
"P_valvetrain": op.friction["Pb_valvetrain"]
```

So the zero came from upstream: `Pb_valvetrain` was itself exactly zero.

### The bug: the roller branch never accumulated

In `friction.py`, the cam/follower calculation splits on follower type. The
flat-tappet branch ends with

```
Pb_vt += float(np.mean(mu_b * fb_c * F_cam * u_sl))
```

**The roller branch had no such line.** Any engine with `follower_radius > 0`
reported exactly zero valvetrain boundary friction, so cam wear and lash growth
were structurally impossible. Three of the four shipped presets are roller.

Fixed by resolving the boundary share in the roller branch the same way,
using an equivalent radius that includes the roller and the ~6% sliding
velocity the branch already computes.

### But the deeper problem: cam boundary friction is ~0 for every preset

| preset | follower | nominal lash | Pb_valvetrain |
|---|---|---|---|
| crdi15 | roller | 0 µm | 9.3e-4 W |
| hd_i6 | roller | 300 µm | 4.3e-3 W |
| ld_i4 | roller | 0 µm | 1.1e-3 W |
| **single** | **flat tappet** | 200 µm | **3.9e-7 W** |

Against `P_valvetrain` of order 120 W, these are boundary shares of 1e-5 to
1e-8. The flat tappet — the case that should wear *most*, and whose real-world
cam failures are well known — comes out lowest of all.

The Hamrock-Dowson film is returning a λ high enough that the boundary share
collapses to nothing everywhere. Real cams wear, particularly flat tappets and
particularly at the nose where entrainment velocity passes through zero.

Likely suspects, untested: `sigma_cam` composite roughness too small, or the
entrainment velocity never approaching zero at nose reversal.

**So the fix here is necessary but not sufficient.** The missing `Pb_vt` line
was a genuine bug and had to go. Cam wear remains negligible for every engine,
and lash still does not grow at 8000 h.

### Fourth instance of the same pattern

FINDING-001 (`premix_fraction` at its floor), FINDING-003 (`sharp` at its
ceiling), FINDING-004 (amplitudes normalised away) and now this: a mechanism
that is fully built, correctly wired, and fed a quantity that is effectively
zero. It is worth asking what else in the package has this shape.

### Note on `crdi15` specifically

`crdi15` has `lash_intake = 0`, meaning hydraulic lash adjusters. For that
engine, lash-driven tick growth is **physically inapplicable** regardless of
cam wear — an adjuster takes up the clearance. The documented "valvetrain tick
grows with lash" story applies to mechanical-lash engines: `hd_i6` (300 µm) and
`single` (200 µm). Any test of this behaviour should use those.
