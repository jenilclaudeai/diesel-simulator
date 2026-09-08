# REVIEW-001 — ADR-001 through ADR-009

**Date:** 2026-09-08
**Scope:** all accepted decisions, Phase 0 exit
**Lenses run:** PM, LEAD, SR1, SR2, PHY1, PHY2, SW1, SW2, QA1, QA2, USR1, USR2

---

## Summary

| Class | Count |
|---|---|
| BLOCK | 1 |
| MAJOR | 4 |
| MINOR | 5 |
| NOTE | 3 |

The BLOCK is against ADR-006 and rests on measurement, not opinion. It also
reveals that known bug #7 is materially worse than `PROJECT_CONTEXT.md`
describes.

---

## BLOCK

### B-1 · PHY1 · ADR-006 rests on a sensitivity that is largely absent

ADR-006 builds two grids — cold and warm — to capture cold-start combustion,
on the stated mechanism: colder walls → longer ignition delay → larger premixed
fraction → sharper `dp/dθ` → cold rattle. `PROJECT_CONTEXT.md` §1.4 asserts
this chain, and §2.7 bug #7 says the *grid* is the problem because it is solved
warm.

**Measured, `crdi15` @ 1800 rpm, load 0.6, `n_cycles=9`**, sweeping
`T_coolant` through `_apply_thermal_state()`:

| coolant K | ign delay ° | premix frac | dp/dθ bar/° | p_max bar | torque N·m |
|---|---|---|---|---|---|
| 273 | 2.425 | 0.0200 | 4.687 | 103.9 | 123.8 |
| 293 | 2.425 | 0.0200 | 4.646 | 103.6 | 124.7 |
| 313 | 2.425 | 0.0200 | 4.637 | 103.7 | 125.3 |
| 333 | 2.425 | 0.0200 | 4.612 | 103.7 | 125.0 |
| 353 | 1.425 | 0.0200 | 4.611 | 107.4 | 124.9 |
| 363 | 1.425 | 0.0200 | 4.608 | 107.2 | 124.9 |

Three problems, in ascending order of seriousness.

**1. `dp/dθ` moves 1.7% across a 90 K coolant swing.** Cold is very slightly
sharper — the right direction — but 4.687 vs 4.608 bar/° is inaudible. The
acoustic mechanism that ADR-006 exists to capture is, at this operating point,
not meaningfully present. Two grids that differ by 1.7% do not justify doubling
grid build time.

**2. `premix_fraction` is pinned at exactly 0.0200 at every temperature.**
Ignition delay changes by 41% between the extremes and premixed fraction does
not move at all. The documented model derives it from a Watson correlation
driven by the computed delay, so it should move. 0.0200 looks like a clamp
floor being hit at every point tested. **This is a bug candidate independent of
#7** and it severs the middle link of the cold-rattle chain.

**3. Ignition delay is quantised to the solver crank step.** It holds at 2.425°
across 273–333 K, then steps to exactly 1.425° — a change of precisely 1.000°.
That is a step function on the integration grid, not a physical response. Any
interpolation across it is interpolating an artifact.

**Consequence for ADR-006.** Linear two-grid interpolation error on ignition
delay, cold and warm endpoints only:

| coolant K | actual ° | linear ° | error |
|---|---|---|---|
| 293 | 2.425 | 2.203 | −9.2% |
| 313 | 2.425 | 1.981 | −18.3% |
| 333 | 2.425 | 1.758 | −27.5% |
| 353 | 1.425 | 1.536 | +7.8% |

**Recommendation.** Do not implement ADR-006 yet. Diagnose finding 2 first —
if `premix_fraction` is clamped, fixing it may restore the sensitivity that
makes a two-grid scheme worth building, and it changes the numbers this
decision was made on. Supersede ADR-006 once the physics is understood.

**Caveat on scope.** One preset, one operating point, warm oil throughout. Oil
temperature is a separate state (`oil.cond.T_oil`) and was not swept, so cold
*friction* is untested here. A cold engine's mechanical drag is likely a larger
real effect than its combustion change, and it is not captured by this test or
addressed by ADR-006.

---

## MAJOR

### M-1 · QA2 · ADR-004 tolerances do not say per-step or terminal

Driveline tolerance is given as `1e-6 rel`. A 60-second drive at 60 Hz is 3,600
integration steps. A per-step relative tolerance of 1e-6 permits unbounded
terminal divergence; a terminal tolerance of 1e-6 is probably unachievable.
The table is untestable as written.

**Fix:** state both a per-step and a terminal bound for every integrator, and
define the reference trajectory.

### M-2 · SW2 · Grid cache key is undefined

ADR-001 and ADR-007 both rely on a cache "keyed by spec hash". Nothing defines
what the hash covers or how floats are serialised. Naive `repr()` of a float is
not stable across Python or numpy versions, so a routine dependency bump would
silently invalidate every cached grid — or worse, collide.

**Fix:** define a canonical serialisation (sorted keys, fixed-precision decimal)
and version the hash itself.

### M-3 · SR2 · No IndexedDB quota or eviction policy

ADR-006 doubles grid count. ADR-008 ships a roster, each entry needing a pair.
Mobile IndexedDB quota is finite and eviction is at the browser's discretion.
No budget is stated and no behaviour is defined for quota exhaustion mid-build.

**Fix:** measure one grid's serialised size, set a budget, define LRU eviction,
handle `QuotaExceededError` on a user-visible operation.

### M-4 · PM · Phases 1–3 are serial with nothing demonstrable

Phase 1 (bug fixes, including open-ended design work on #2), Phase 2 (solver
port), Phase 3 (real-time loop) all complete before Phase 5 produces anything a
person can look at. Bug #2 in particular — a rate-limited boost follower with a
stability argument — has no timebox and no fallback.

**Fix:** timebox #2 with an explicit fallback (keep open-loop, document it in
the UI). Add a thin vertical slice after Phase 2 — one engine, one gear, a
rev counter — to prove the whole stack end to end before building it out.

---

## MINOR

### m-1 · SR1 · No error path across the worker boundary
ADR-001 defines `SolverPort` but not how a Python exception inside Pyodide
surfaces to Angular. `PROJECT_CONTEXT.md` §3.8 is explicit that silent zero
substitution is how the `_impulses` bug survived. The seam needs a typed error
channel, not a rejected promise with a stringified traceback.

### m-2 · QA1 · "Loads on a mid-range phone" is not a criterion
Phase 5's exit criterion names no device, no network condition and no time
budget. Not objectively evaluable.

### m-3 · LEAD · ADR-002 and manual gearbox interact unreviewed
A manual gearbox with a clutch, on a point mass with no grip limit, means
side-stepping the clutch produces unbounded tractive force. Needs a defined
behaviour before Phase 3.

### m-4 · PHY2 · `builder.py` verification bound undefined
ADR-008 requires `verify()` on every roster entry but sets no acceptance
threshold for achieved vs requested. Without one, "verified" means "we ran it".

### m-5 · SW1 · Angular version pinning deferred indefinitely
ADR-005 says pin at scaffold time. Record the pinned version in the ADR when it
happens, or the decision is unreproducible.

---

## NOTE

### n-1 · Reviewer error worth recording
An initial version of the B-1 test mutated `spec.thermal.coolant_T` directly
and found *zero* combustion sensitivity. That was wrong: `engine.py` caches
baseline wall temperatures in `self._th0` at construction and drives them from
`self.T_coolant` via `_apply_thermal_state()`. Mutating the spec after
construction does nothing. Recorded because the same mistake will be made again
by anyone wiring the grid builder.

A second error: `dpdtheta_max` is **already in bar/°** — `cycle.py:640` divides
by 1e5 at assignment. Dividing again reads 0.00 and looks like a dead field.

### n-2 · USR1 · "Shit Got Real" as a mode name
Advisory only. It is memorable and fits the audience, but it is unsearchable,
hard to localise, and awkward in a screenshot shared at work. No
recommendation — the lens has no standing to judge audience fit.

### n-3 · USR2 · Grid rebuild wait needs an explanation, not a spinner
ADR-007 means importing a shared engine triggers a multi-minute rebuild.
A progress bar alone reads as a hang. It should say what is being computed and
why it only happens once.

---

## Dismissed

None. All findings stand as recorded.
