# FINDING-001 — `premix_fraction` is pinned at its floor in all conditions

**Opened by:** REVIEW-001 B-1
**Lenses:** PHY1 (lead), PHY2, SW2
**Status:** P-1 and P-2 fixed — PR #5 (`physics/verified-fixes`). *(Updated 2026-09-23: this line was not updated when the fix landed, and read "diagnosed, not fixed — the fix is a physics decision, see below" until then.)*
**Blocks:** ADR-006, and reframes known bug #7

---

## Symptom

`premix_fraction` returns exactly 0.0200 at every coolant temperature from
273 K to 363 K, while ignition delay changes 41% across the same range.

## Root cause

`cycle.py:430–435` applies a Watson-type correlation:

```
b = 1.0 - 0.926 * max(phi, 0.05)**0.37 / max(tau_ms, 0.12)**0.26
premix = min(0.72, max(0.02, b)) * (pilot multiplier)
premix = min(0.72, max(0.02, premix))
```

Measured at `crdi15`, 1800 rpm, load 0.6:

| coolant | τ (deg) | τ (ms) | φ | Watson `b` | after clamp | final |
|---|---|---|---|---|---|---|
| 273 K | 2.425 | 0.2245 | 0.670 | **−0.178** | 0.0200 | 0.0200 |
| 363 K | 1.425 | 0.1319 | 0.663 | **−0.347** | 0.0200 | 0.0200 |

`b` is negative in both cases. The `max(0.02, ...)` floor absorbs it, so the
output is the floor, and *no input can change the output*. The clamp is not the
bug — it is correctly preventing a negative premixed fraction. The bug is that
`b` is negative at all.

`b` goes negative because **τ is too short for the correlation's domain**. The
`τ^0.26` denominator means the subtracted term grows without bound as τ → 0.
For `b` to be meaningfully positive at φ ≈ 0.67, τ needs to be around 1 ms.
Measured τ is 0.13–0.22 ms.

---

## Two contributing problems

### P-1 · The pilot's suppression of premixed burn is counted twice

`cycle.py:421` accelerates the main-injection delay counter when the pilot has
already ignited:

```
boost = 1.0 if soc_p[c] < 0.0 else 2.1
```

and then `cycle.py:432` *separately* multiplies the resulting premixed fraction
by a pilot factor (0.45 at `pilot_fraction = 0.05`).

Both model the same physical effect — a pilot leaves hot radicals and raised
charge temperature, so the main charge ignites sooner and burns less
premixed. Applying it once through τ and again as a multiplier double-counts.

**Confirmed by test.** Disabling the pilot lengthens τ from 2.425° to 4.425°
(0.22 → 0.41 ms), close to what Hardenberg-Hase alone predicts for these
conditions. The 2.1× boost was responsible for roughly half the deficit.

### P-2 · The Watson correlation is outside its calibrated domain

With the pilot disabled and τ = 0.41 ms, `b` is **still** marginally negative
(≈ −0.007). So P-1 is not the whole story.

Watson's premixed-fraction correlation was developed for older direct-injection
diesels with ignition delays around 1–2 ms. A modern common-rail engine at high
compression and 1800 bar rail genuinely has a much shorter delay, and 0.4 ms is
not obviously wrong physics. The correlation simply is not valid there — it
saturates against the floor and stops responding to anything.

**This is the finding that matters.** It is a model-validity problem, not a
coding error, and it cannot be fixed by adjusting a constant.

---

## Consequences

1. **The premixed spike is always at 2%.** Diesel clatter in `acoustics.py` is
   driven by `dp/dθ`, which is therefore dominated by the diffusion burn.
2. **Cold rattle does not emerge.** `dp/dθ` moves 1.7% across 90 K with the
   pilot enabled, 4.3% with it disabled — right direction, wrong magnitude,
   inaudible either way.
3. **`PROJECT_CONTEXT.md` §1.4 is not supported by the code.** It states that a
   cold engine has "a bigger premixed spike and a sharper `dp/dθ` — which is
   exactly why a cold diesel rattles". The mechanism is present in the source
   but inert, because the middle link is clamped.
4. **ADR-006 cannot be assessed** until this is resolved. Two grids built on a
   pinned premixed fraction would differ by a fraction of a percent.

---

## Options — this is a physics decision, not an implementation one

### A. Replace the premixed-fraction correlation
Use a formulation valid at short delays. The premixed mass is physically the
fuel injected during the delay period, which the solver already knows from
nozzle flow and τ — so it can be computed directly rather than correlated.

- **Positive:** removes an empirical correlation in favour of something the
  solver can derive, consistent with the package's stated philosophy of physics
  over fits. Restores temperature sensitivity by construction.
- **Trade-off:** changes every combustion result. The §1.5 validation table
  must be re-run and re-verified. This is the largest change on the list.

### B. Fix P-1 only, accept P-2
Remove the double-count — keep either the 2.1× delay boost or the 0.45
multiplier, not both.

- **Positive:** small, well-understood, defensible on its own merits regardless
  of what is decided about P-2.
- **Trade-off:** `b` stays marginally negative, so `premix_fraction` remains
  pinned and nothing observable changes. Correct but not sufficient.

### C. Recalibrate the correlation constants for modern delays
Refit 0.926 / 0.37 / 0.26 against short-delay data.

- **Positive:** contained; keeps the existing structure.
- **Trade-off:** adds fitted scalars. The package currently has exactly two
  (`NOX_CAL`, `SOOT_CAL`) and says so prominently. This erodes that claim.

### D. Do nothing, and stop claiming cold rattle
Document that premixed fraction is pinned, delete the §1.4 claim, drop ADR-006.

- **Positive:** free, and honest.
- **Trade-off:** loses a signature behaviour for the target audience. A cold
  diesel that does not rattle is something an enthusiast will notice.

**PHY1 recommendation:** B first, since it is right regardless, then A. A is
the fidelity upgrade the project's own philosophy points to, and
`PROJECT_CONTEXT.md` §1.6 already names combustion parameterisation as the
biggest available improvement.

---

## Caveats on this diagnosis

- One preset, one operating point, one load. Not swept across rpm or load.
- Oil temperature was held warm throughout. Cold *friction* is a separate
  state and likely a larger real effect than cold combustion; it is untested
  here and unaddressed by ADR-006.
- Whether 0.4 ms is the correct ignition delay for this engine has not been
  independently validated. If the delay is itself too short for another reason,
  P-2's framing changes.

---

# P-2 attempt — Option A implemented, partial result

**Branch:** `fix/premix-from-delay-injection` · **Status:** not merged, needs a decision

## What was done

Replaced the Watson correlation with a derived quantity. The premixed burn is
physically the fuel that entered the chamber before ignition. Injection rate is
constant over the main event, so that fraction is simply:

```
premix = tau / dur_main
```

Both terms were already computed by the solver from nozzle flow. This removes an
empirical correlation rather than recalibrating one, which is what the package's
stated philosophy points to.

## What it fixed

`premix_fraction` is no longer pinned. It now reads 0.10–0.17 — physically
sensible for a modern common-rail engine with a pilot — and responds strongly
to temperature: **+67% cold** (0.1023 warm → 0.1709 at 273 K).

The regression suite reports UNEXPECTED PASS on the premix test, which is the
intended signal.

## What it did NOT fix

**`dp/dθ` still moves only +0.4% cold.** The cold rattle does not emerge.

A 67% swing in premixed fraction should sharpen the pressure rise noticeably.
It does not, which means **a further link is broken downstream** — most likely
the premixed Wiebe shape parameters (`r_pre` vs `r_dif` at `cycle.py:455`) are
too similar for the blend to matter, or the heat release is dominated by
something else entirely.

Ignition delay also remains quantised to the crank step (flat at 2.425° from
273–353 K, then 1.425°), so the premix response is a step, not a curve.

## Effect on validation

| Point | torque | BSFC | p_max |
|---|---|---|---|
| crdi15 @1800/0.6 | −0.40% | +0.72% | **+3.31%** |
| crdi15 @3000/1.0 | −0.15% | −0.18% | **+3.11%** |
| hd_i6 @1700/1.0 | +0.22% | −0.22% | **+2.79%** |

Torque is preserved — `hd_i6` still gives 2313 N·m against the documented
2310. BSFC moves under 1%. **p_max rises ~3% everywhere**, which is the
physically expected direction: more premixed burn means a sharper, higher peak.

`hd_i6` p_max goes 173.7 → 178.5 bar, still inside the 160–200 bar band in
`PROJECT_CONTEXT.md` §1.5.

Four golden assertions now fail. They are not wrong — the baseline moved for a
defensible reason.

## The decision

1. **Accept and re-baseline.** The change is more physical than what it
   replaced and validation still holds. Update the goldens with this finding as
   the justification, promote the premix test to a real assertion.
2. **Accept, then chase the Wiebe shape.** As above, but treat the flat `dp/dθ`
   as the next finding, since the cold rattle is still missing.
3. **Revert.** The premix fix alone does not deliver the user-visible behaviour
   it was meant to, and a 3% p_max shift is not free.

Recommendation: **2**. The premix fix is correct on its own merits and should
not be held hostage to the downstream problem, but the cold rattle is the thing
the work was for and it is still absent. Do not close FINDING-001.
