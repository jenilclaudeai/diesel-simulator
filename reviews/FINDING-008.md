# FINDING-008 — `CycleTraces.theta` indexes two different crank-angle references

**Opened by:** the "trace shape inconsistency" item in `STATUS.md`, carried
forward from FINDING-002's *Also found*
**Lenses:** PHY2 (lead), SW1, SW2
**Status:** diagnosed, not fixed — the fix is an API contract decision
**Blocks:** the Angular cycle page (PLAN Phase 6); relevant to the Phase 3 port

---

## The reported symptom does not reproduce

`STATUS.md` records `traces.p` and `traces.theta` differing in length,
1430 vs 720, at load 1.0. Measured across `crdi15` at loads 0.2 / 0.6 / 1.0 and
`hd_i6` at load 1.0, every trace is **720 long on the crank axis** and no length
disagrees:

```
theta            ndim=1  shape=(720,)
p                ndim=2  shape=(4, 720)
p_int_manifold   ndim=1  shape=(720,)
valve_lift_int   ndim=1  shape=(720,)
```

`len(traces.p)` returns **4**, the cylinder count, because the array is
`(n_cyl, n)`. That is the trap the note was probably reaching for, but the axis
lengths themselves agree.

The **1440** in the package is `AcousticEngine.grid` — `acoustics.py:162`
builds its own crank grid at `dtheta=0.5` while `DieselEngine` defaults to
`dtheta=1.0`. `_phase_sum` resamples across the two with `np.interp`, correctly.
Two crank grids at different resolutions is worth knowing for the TypeScript
port, but it is not a defect.

**The real inconsistency is semantic, not dimensional, and it is worse.**

---

## Finding — one `theta`, two meanings

`cycle.py:363` stores each cylinder's sample at a phase-shifted index:

```
kk = (k + self.phase_idx[c]) % self.n     # k is the global step
p_tr[c, kk] = p_new
```

while the manifold traces at `cycle.py:648` store at the raw global index:

```
pim_tr[k] = p_int
pem_tr[k] = p_exh
```

So the fields in one dataclass, sharing one `theta` axis, split into two
conventions:

| fields | indexed by |
|---|---|
| `p`, `p_motored`, `T`, `hrr`, `T_burned`, `mdot_int`, `mdot_exh`, `mdot_blowby` | **cylinder-local** crank angle — each cylinder aligned to its own TDC |
| `p_int_manifold`, `p_exh_manifold` | **global** crank angle |
| `V`, `valve_lift_int`, `valve_lift_exh` | cylinder-local (identical geometry, so shared) |

### Measurement

`hd_i6` @ 1400 rpm, load 1.0. Peak-pressure angle read off `traces.theta`:

| cyl | phase_deg | θ of max p, as read from the trace |
|---|---|---|
| 0 | 0 | 10.0° |
| 1 | 480 | 10.0° |
| 2 | 240 | 10.0° |
| 3 | 600 | 10.0° |
| 4 | 120 | 10.0° |
| 5 | 360 | 10.0° |

Six cylinders firing 120° apart all report peak pressure at the same crank
angle. That is only coherent under a local convention.

The exhaust manifold, from the same traces object, pulses at global
**101 / 221 / 341 / 461 / 581 / 701°** — genuinely 120° apart. Cylinder 0's
blowdown reads 207° and the manifold answers at 221°, a 14° lag, which is
correct *for cylinder 0 only*, because its phase offset is zero.

### Why nothing is currently wrong

Every existing consumer either indexes `[0]`, where local and global coincide,
or handles the phase itself. `friction.evaluate` and `acoustics.build_sources`
both take `traces.p[0]`. So this is a **latent contract defect, not a live
numerical error** — no shipped number is wrong because of it.

### Why it will bite

PLAN Phase 6 specifies a cycle page with p–V, p–θ, HRR and valve lift.

- **p–V is correct for every cylinder, for free.** `V` is local too, so
  `p[c]` against `V` pairs correctly for all `c`. This is a real virtue of the
  current layout and any fix must preserve it.
- **p–θ for more than one cylinder is wrong.** Plotting `p[c]` against `theta`
  draws `n_cyl` curves stacked on top of each other instead of spread across
  the firing order. It will look like a bug in the plotting code.
- **Overlaying manifold pressure on cylinder events is wrong for every
  cylinder except #0**, and wrong by the phase offset — up to 600°.

Nothing raises an error in any of these cases.

---

## Second-order: the roll sign in `crank_torque` is backwards

`engine.py:401` converts local back to global:

```
shift = int(round(g.phase_deg(c) / dth))
T += np.roll(t_c, shift)
```

Under the storage convention above, `p_tr[c][j]` holds the value from global
step `j - phase_idx[c]`, so recovering the global trace needs
`np.roll(t_c, -shift)`. The shipped sign is positive.

**It is almost invisible, for a structural reason.** `phase_deg` is always
`pos * (720 / n_cyl)` (`config.py:72`), so the shift set is always
`{0, s, 2s, …}` — closed under negation mod 720. Summing over all cylinders
therefore permutes the same terms either way. If the cylinders were identical
the sum would be exactly invariant.

They are not quite identical, so a residual survives:

| preset | max\|shipped − corrected\| | ripple peak-to-peak | share |
|---|---|---|---|
| `hd_i6` @1400/1.0 | 17.7 N·m | 7608.7 N·m | 0.23% |
| `crdi15` @1800/1.0 | 11.0 N·m | 1378.2 N·m | 0.80% |

So it is a sub-1% error today, masked by even-fire symmetry. It becomes a
first-order error the moment any odd-fire phasing exists, and it is exactly the
kind of thing a TypeScript port reproduces faithfully and no fixture test
catches, because the fixture would be generated from an even-fire engine.

---

## Relation to the standing pattern

Not the same shape as FINDINGs 001/003/005/006 — nothing here is pinned at a
clamp, and `tools/audit_dead_signals.py` would not have caught it, since every
value moves. It is the neighbouring failure: **a quantity that is live and
correct but silently means something other than its label implies.**

Worth noting that the audit tool checks whether signals *move*, not whether
they mean what they say. A second audit dimension — assert that per-cylinder
peak angles are spread by the firing order — would have caught this in one
line.

---

## Caveats

- Two presets, one speed each, load 1.0 for the axis test. The convention is
  read off the source and is not operating-point dependent, so a wider sweep
  would not change it.
- The `crank_torque` residual is measured at one point per preset. The claim
  that the sum is exactly invariant for identical cylinders is analytic, not
  measured; the measured residual is consistent with it.
- Whether the local convention is *intended* cannot be established from the
  code. `crank_torque` clearly knows about it, which argues intent.

---

## Independent verification and one correction

Re-measured from a clean clone before acting on any of the above.

### Confirmed

`crdi15` @ 1800 rpm, load 0.8 — all four cylinders report peak pressure at
θ ≈ 11° despite `phase_deg` of 0 / 540 / 180 / 360, while the exhaust manifold
from the same traces object peaks at 565°. Local and global in one dataclass,
as described.

### Correction: the roll sign was latent, not live

The finding states the sign is backwards, which is correct. It does not
establish whether that is currently harmful. It is not.

For an evenly-fired engine the set of phase offsets is **symmetric under
negation mod 720**, so rolling the wrong way permutes which cylinder lands
where and leaves the sum unchanged:

| preset | phases | negated | summed torque |
|---|---|---|---|
| crdi15 | 0, 540, 180, 360 | 0, 180, 540, 360 | identical |
| hd_i6 | 0, 480, 240, 600, 120, 360 | 0, 240, 480, 120, 600, 360 | identical |
| single | 0 | 0 | identical |

So no shipped number was wrong, and `torque_trace` was correct for every
preset by symmetry rather than by construction.

**It becomes a live error the moment the firing is uneven** — a V-twin, an
odd-fire V6, anything where `vee_angle_deg` breaks the symmetry. `builder.py`
lets a user create exactly that, and the failure would appear as a
plausible-looking but wrong torque trace with no error raised.

Fixed to `np.roll(t_c, -shift)` with the reasoning recorded inline.

### Note on the 1440

The finding correctly identifies `AcousticEngine.grid` at `dtheta=0.5` as the
1440 in the package. Worth carrying into ADR-003's TypeScript port: the
`AudioWorklet` inherits two crank grids at different resolutions bridged by
`np.interp`, and that interpolation has to be reproduced, not assumed away.

### Merged with the parallel branch

`docs/trace-shape-convention` reached the same conclusion about the 1430 being
a measurement error and added a `CycleTraces` docstring. That docstring covered
only the 1D/2D split and **would have been misleading**, because it implied a
single shared `theta`. It has been rewritten here to state both references and
their consequences. FINDING-002's retraction is kept.

---

## Options for the contract (session 4, for decision)

*Added 2026-09-25. Nothing above is changed. The decision is the owner's; this
section lays it out.*

### What constrains it, measured from the code

- **Every consumer today reads cylinder 0 or handles the phase itself.**
  `friction.evaluate`, `acoustics.build_sources`, `demo.py` and the engine's
  own friction call use `p[0]` / `mdot_*[0]` / `T[0]`; only
  `DieselEngine.crank_torque` reads `p[c]` for `c > 0`, and it rolls each
  cylinder to global itself. Cylinder 0's phase is 0, so for it local and
  global coincide. **No option below moves a shipped number.**
- **Traces are not exposed to the browser.** `dieselsim/bridge.py` and
  `web/solver/src` never touch `traces` or `theta`. The contract can still be
  chosen freely — but it has to be chosen before the Phase 6 cycle page, the
  Phase 3 port or any fixture (ADR-004) freezes one.
- **p–V is correct for every cylinder today, for free** (`V` is local too).
  Any option should keep that.

### Options

| option | what changes | positives | trade-offs |
|---|---|---|---|
| **A. Document and add helpers.** Keep storage; add `phase_deg` (per cylinder) to `CycleTraces` and a `to_global(c, arr)` helper. | a field and a helper | smallest change; zero risk to existing consumers; p–V stays free | two conventions remain in one dataclass; correctness depends on every consumer remembering the helper — the failure mode this finding is about |
| **B. Store everything in global angle.** Roll per-cylinder arrays to global at the end of `run()`; `V` becomes per-cylinder `(n_cyl, n)`. | array layout, `crank_torque` (drop its roll) | one convention; p–θ overlays and manifold-vs-cylinder overlays are right by construction | `V` changes shape (1-D → 2-D), a breaking change for any p–V code; per-cylinder event analysis (e.g. "peak pressure at 10° ATDC") needs a shift back; the TS port and fixtures must follow |
| **C. Store everything local.** Add per-cylinder manifold traces `(n_cyl, n)`, each as seen from that cylinder's frame. | two arrays duplicated per cylinder | everything a single cylinder experiences lines up with its own TDC, which is how engine analysts usually read a cycle | manifold data stored `n_cyl` times; a firing-order view (all cylinders on one axis) still needs conversion; bigger payload for the browser |
| **D. Keep storage, add a per-cylinder axis.** Add `theta_global` `(n_cyl, n)` = `(theta + phase_deg[c]) % 720`, and document the pairing: `p[c]` against `theta` (own TDC) or against `theta_global[c]` (engine angle); manifold arrays against `theta` (engine angle). | one array, docs | no data moves; p–V stays free; every array has an axis that is correct for it by name; firing-order and manifold overlays become plain plots; cheapest to carry into the TS port | the consumer still has to pick the right axis (but the names now say which); `theta_global[c]` wraps at 720°, so a plot must split or sort at the wrap |

### Recommendation: D, plus a guard

D fixes the misleading pairing without moving data or breaking p–V, and costs
one array. Whatever is chosen, add the second audit dimension this finding
proposed: **assert that per-cylinder peak-pressure angles, read on the
engine-angle axis, are spread by the firing order** (120° apart on `hd_i6`,
180° on `crdi15`). It is one line and would catch a regression in either
direction — and it is the kind of test to mutation-check against a baseline
that passes, per the working rules.

Decide before the Phase 3 port or the Phase 6 cycle page, whichever comes
first.

---

## Decided and implemented: option D (session 4)

`CycleTraces.theta_global`, shape `(n_cyl, n)`: the engine angle of each
sample of cylinder c's local arrays, `(theta − phase_deg[c]) % 720`, built from
the solver's own rounded `phase_idx` so it matches the storage exactly. No
data moves; p–V stays correct for free; the `CycleTraces` docstring states
which axis pairs with which array.

Guard `test_theta_global_axis`, on `hd_i6` and `crdi15`: peak pressure read on
`theta_global` is spread by the firing order (gaps within 2° of 720/n_cyl),
and `theta_global` agrees with the storage convention sample for sample.
Mutation: a flipped sign is caught — by the storage check only, as expected,
since an even-fire engine's phase set is symmetric under negation and the
peak spread cannot tell the signs apart; reading the local angle (no
conversion) is caught by both checks.
