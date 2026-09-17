# FINDING-002 — `dp/dθ` measures compression, not combustion

**Opened by:** FINDING-001 P-2, which fixed `premix_fraction` but did not
produce cold rattle
**Lenses:** PHY1 (lead), QA2
**Status:** diagnosed, not fixed
**Severity:** this is the root cause FINDING-001 was chasing

---

## Symptom

After FINDING-001 P-2, `premix_fraction` swings +67% between 273 K and 363 K.
`dpdtheta_max` moves +0.4%. A large change in the premixed spike produces
almost no change in the reported pressure-rise rate.

## Root cause

**Peak `dp/dθ` occurs before combustion starts.**

`crdi15` @ 1800 rpm, load 0.6:

| | θ of peak dp/dθ | SOC main | gap |
|---|---|---|---|
| 273 K | 709.0° | 719.0° | peak is **10° before** ignition |
| 363 K | 708.0° | 718.0° | peak is **10° before** ignition |

The maximum is on the compression stroke, driven by piston motion. It cannot
respond to combustion because it happens first.

This is not obviously wrong physics — a well-phased modern diesel with pilot
injection genuinely has a soft combustion pressure rise, which is much of the
point of pilot injection. The error is in **what gets measured and what that
measurement is then used for.**

## Proof

Restricting the same calculation to a 40° window after start of combustion:

| coolant | premix | whole-cycle dp/dθ | after-SOC dp/dθ |
|---|---|---|---|
| 273 K | 0.1709 | 4.611 | **3.726** |
| 313 K | 0.1733 | 4.580 | 3.704 |
| 353 K | 0.1740 | 4.590 | 3.665 |
| 363 K | 0.1023 | 4.594 | **3.342** |

| metric | cold vs warm |
|---|---|
| whole-cycle `dpdtheta_max` | **+0.4%** |
| combustion-window dp/dθ | **+11.5%** |

A factor of 29. The combustion signal is there and it responds correctly to
temperature. It is being averaged away by a compression peak that dominates it.

---

## Why this matters more than FINDING-001

`acoustics.py:195` computes the clatter excitation from the raw cylinder
pressure trace:

```
dpdth = np.gradient(p1, th[1] - th[0])
src["dpdth"] = self._phase_sum(dpdth, th)
```

and line 363 uses it directly to excite the block and head structural modes.

**So diesel clatter is excited by a compression-dominated signal.** The
signature sound of the engine is not being driven by the combustion physics
that supposedly produces it.

`PROJECT_CONTEXT.md` §1.3 says "diesel clatter ← `dp/dθ` exciting block/head
structural modes; sharper rise lights up the high modes". The structure is
right. The signal is wrong.

Downstream consequences:

- Cold rattle cannot emerge — compression is largely insensitive to wall
  temperature
- Injection timing, rail pressure and pilot changes will barely alter the
  clatter character, though they should dominate it
- The three findings chain: P-1 was inert, P-2 was real but invisible, and this
  is why

---

## Fix path

`p_mot` is already computed at `cycle.py:483` for the Woschni correlation and
then discarded. Motored pressure is exactly the reference needed.

1. **Expose `p_mot` in `CycleTraces`.** Cheap — it exists, it is thrown away.
2. **Report `dpdtheta_max` on the combustion-driven rise**, `d(p − p_mot)/dθ`,
   or over a window after SOC. The current field is misleading and any UI
   showing it would be misleading too.
3. **Drive clatter excitation from the combustion-driven rise** in
   `acoustics.py`.

Step 3 changes all rendered audio. It should be done with the worn/new audio
pair from known bug #9 as a check, since that pair is already suspect.

## Also noted — and later retracted

This finding originally claimed the trace arrays were shape-inconsistent, with
`traces.p` 2D, `traces.theta` 1D, and lengths differing at load 1.0 (1430 vs
720).

**That was wrong, and it was my error, not the package's.** Verified across all
four presets and `n_cyl` of 1, 4 and 6: every field has the same crank-angle
length at every load. The 1430 came from ravelling a 4-cylinder `(4, 720)`
array into 2880 points and indexing `theta` with the result.

The 1D/2D split is deliberate and sensible: `(n_cyl, n)` for quantities that
genuinely differ between cylinders, `(n,)` for those identical to every
cylinder and differing only by firing phase. It was undocumented, which is why
I misread it twice. Now documented on the `CycleTraces` docstring.

No code change was needed. Retained here rather than deleted because a
retracted finding is more useful to a future reader than a silently removed
one.

## Caveats

One preset, one speed, one load. The 40° combustion window is a judgement, not
a standard. Whether compression dominates at all operating points is untested —
at high load and advanced timing the combustion rise may well win, which would
mean the clatter signal is *sometimes* right and sometimes not. That would be
worse than consistently wrong, because it would look plausible.
