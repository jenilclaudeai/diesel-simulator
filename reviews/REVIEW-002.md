# REVIEW-002 — ADR-006 (cold-start combustion via two grids), reassessed

**Date:** 2026-09-25
**Scope:** ADR-006, on hold since REVIEW-001 B-1, against the numbers after
FINDINGs 001–004, 013, 015 and 016
**Lenses run:** PHY1, PHY2, LEAD, SW1, SW2, PM, QA2, USR1/2 (advisory)
**Reproduce:** `python3 tools/diag_cold_sensitivity.py` and `--visc`
(converged solves, real time, 200 cycles; fuel fixed per point so only
temperature changes)

---

## Summary

| Class | Count |
|---|---|
| BLOCK | 1 |
| MAJOR | 2 |
| MINOR | 1 |
| NOTE | 2 |

**ADR-006 should be superseded.** It interpolates on the wrong temperature
(coolant), aims at the smaller effect (combustion), and its interpolation —
linear in temperature — fails badly for the effect that dominates (friction).
Proposal: **ADR-011** (friction computed live from oil viscosity; combustion
from a cold/warm indicated pair on coolant temperature), appended to
DECISIONS.md as *Proposed*.

---

## The measurements

Each point swept 273 → 363 K three ways: coolant alone (oil warm), oil alone
(coolant warm), and both together. Change at 273 K against 363 K:

| point | sweep | torque | FMEP | ignition delay | premix | combustion dp/dθ |
|---|---|---|---|---|---|---|
| `crdi15` 1800/0.6 | coolant | −5.4% | +31% | +6.7% | +6.7% | +1.0% |
| | **oil** | **−23.4%** | **+224%** | 0 | 0 | 0 |
| | both | −27.9% | +246% | +6.7% | +6.7% | +1.0% |
| `crdi15` 2500/0.3 | coolant | −13.3% | +56% | +7.2% | +7.2% | +2.1% |
| | **oil** | **−78.0%** | **+375%** | 0 | 0 | 0 |
| | both | −87.8% | +414% | +7.2% | +7.2% | +2.1% |
| `hd_i6` 1400/0.6 | coolant | −3.9% | +43% | +4.7% | +4.7% | +2.3% |
| | **oil** | **−21.2%** | **+341%** | 0 | 0 | 0 |
| | both | −23.9% | +363% | +4.7% | +4.7% | +2.3% |

**Two-grid linear interpolation error** (endpoints 273 and 363 K, both
temperatures swept), worst over 293–353 K:

| point | torque | FMEP | ign. delay / premix | dp/dθ comb |
|---|---|---|---|---|
| `crdi15` 1800/0.6 | −12.4% | +75% | +0.1% | 0.0% |
| `crdi15` 2500/0.3 | −53.9% | +108% | +0.2% | 0.0% |
| `hd_i6` 1400/0.6 | −10.8% | +102% | +0.1% | 0.0% |

**Which axis for friction** — FMEP interpolation error between the same
endpoints, oil-only sweep, worst over the range:

| point | linear in T | linear in log μ | linear in μ |
|---|---|---|---|
| `crdi15` 1800/0.6 | +72% | +48% | −9.5% |
| `crdi15` 2500/0.3 | +107% | +70% | −12.5% |
| `hd_i6` 1400/0.6 | +102% | +69% | −11.3% |

---

## BLOCK

### B-1 · PHY2 · ADR-006 interpolates on coolant; the cold engine is an oil-temperature effect

Oil temperature alone accounts for 21–78% of the torque loss and 224–375% of
the FMEP rise; coolant alone for 4–13% and 31–56%. ADR-006's axis is coolant
temperature and its object is combustion. During a warm-up the oil lags the
coolant by minutes, so a coolant-keyed scheme would show a nearly-warm engine
while the oil — and the friction — is still cold. This is REVIEW-001's caveat
("a cold engine's mechanical drag is likely a larger real effect than its
combustion change, and it is not captured by this test or addressed by
ADR-006"), now measured.

## MAJOR

### M-1 · PHY2 · Friction is strongly nonlinear in temperature; two endpoints cannot carry it

Linear-in-T interpolation errs by up to +108% in FMEP and −54% in torque.
Viscosity is the natural variable (friction is close to linear in it: −12.5%
worst), but even there two endpoints are not enough for a stated ~1% bar.

### M-2 · PHY1 · The combustion effect ADR-006 exists for is real but small — and linear

After FINDING-016 (ignition resolved within the step) the cold response is
ignition delay +4.7–7.2%, premix the same, combustion dp/dθ +1.0–2.3%, over
90 K. Small, but **linear in coolant temperature: two endpoints interpolate it
within 0.2%.** So the two-grid idea is sound for combustion and wrong for
friction — the split ADR-011 makes.

## MINOR

### m-1 · QA2 · The audible cold effect is not mostly combustion

The warm/cold listening pair (FINDING-017) is +28% brighter cold, but per
source the change comes from exhaust (+12.6%) and turbo (+20.8%), with
combustion +3.2% — and mechanical noise +0.0% because of FINDING-017's
normalisation bug. "Cold rattle" in this model is currently not carried by
the mechanism ADR-006 names; fixing FINDING-017 is a precondition for judging
cold sound at all.

## NOTE

### n-1 · SW1/SW2 · Friction off-grid fits the architecture that is coming

Phase 3 ports the real-time loop to TypeScript, and oil temperature is already
a live state there (the cooling stack). Evaluating friction per frame from
live viscosity costs one FMEP evaluation per frame, and removes a grid axis
instead of adding one. It needs either the friction model ported (ADR-004
fixtures apply) or a fitted FMEP(rpm, load, μ) surface solved offline.

### n-2 · PM · Build cost

ADR-006 doubled every grid build; a third axis on viscosity would multiply it
by 3–4 (converged: ~30–40 min per engine). ADR-011 adds a second *indicated*
grid (the cold one; ~9 min per engine converged) and no friction axis.

## USR (advisory)

A cold engine that is sluggish and rough for the first minutes and then
settles is the experience enthusiasts expect; getting the *duration* right
depends on oil warm-up, which ADR-006 would not have tracked.

## Dismissed

None.

---

## Decision (2026-09-25)

The owner accepted ADR-011; ADR-006 is superseded. Measured afterwards (see
the ADR-011 addendum in DECISIONS.md): a fitted friction surface needs ~6
viscosity nodes × a coolant axis for ~1%, while friction evaluated from each
cell's stored pressure trace is **exact** with respect to oil state (0.000%
in 9 of 9 cases; oil temperature does not touch the trace). The trace-based
route is chosen.
