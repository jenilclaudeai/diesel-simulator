# Status

**Updated:** 2026-09-09 (session 2)
**Phase:** 1 — Physics truth pass, substantially complete
**Branch:** `fix/physical-source-levels` (stacked, see Branches below)

Read this first in a new session, then `PLAN.md`, then `DECISIONS.md`, then
`reviews/`. Those replace pasting a context document.

---

## Where things stand

Architecture is decided (ADR-001 to ADR-009, with ADR-006 on hold). No frontend
code exists yet. The Python physics has been through a review pass that
produced six findings, five fixes, a regression suite and a standing audit tool.

### The pattern that came out of it

Five of the six findings share one shape: **a mechanism fully built, correctly
wired, and fed a quantity that is effectively zero or pinned against a clamp.
None raised an error.**

- `premix_fraction` sat on its 0.02 floor (FINDING-001)
- `sharp` sat on its 3.0 ceiling (FINDING-003)
- every acoustic amplitude was normalised away (FINDING-004)
- the roller-follower branch never accumulated boundary friction (FINDING-005)
- `h_min_ring` was always its 12 nm clamp (FINDING-006)

`tools/audit_dead_signals.py` exists to catch the sixth. **Run it after any
physics change, and port it alongside the solver** — the same failure in
TypeScript would be far harder to find, and Phase 3 ports the whole real-time
loop.

Latest audit: 102 scalars over 8 operating points — **0 dead, 1 frozen (the
now-honestly-named `h_ring_tdc`), 1 tiny (`Pb_valvetrain`)**.

---

## Findings

| # | Issue | Status |
|---|---|---|
| 001 | `premix_fraction` pinned; Watson correlation out of domain at modern common-rail delays | P-1 and P-2 fixed |
| 002 | `dp/dθ` peaks 10° *before* ignition, so it measures compression; clatter was driven by it | fixed |
| 003 | clatter high-mode weight pinned at its ceiling; divisor 3 orders of magnitude out | fixed |
| 004 | every physical amplitude discarded by two normalisation stages | fixed |
| 005 | roller-follower branch never accumulated `Pb_vt`; cam wear structurally impossible | fixed, **but insufficient** |
| 006 | `h_min_ring` always its clamp, and exposed as a headline field | fixed |
| 007 | bug #8 audit; `fuel_for_torque` returned 8.7% different fuel depending on cache warmth | fixed |

### Still open inside those

- **FINDING-005 is not closed.** `Pb_valvetrain` is now nonzero but runs 1e-5
  to 1e-8 of total. The flat-tappet case is *lowest* at 3.9e-7 W — the case
  that should wear most. Cam wear is still negligible and lash still does not
  grow at 8000 h. Suspects: `sigma_cam`, or entrainment velocity at nose
  reversal. Untested.
- **FINDING-004 has not been listened to.** Every judgement was band ratios and
  RMS. It changes the character of every rendered sound. Four WAVs were
  produced for A/B; the warm-vs-cold pair at load 0.6 is the one that matters.

---

## Known bugs — status

| # | Issue | Status |
|---|---|---|
| 1 | `n_cycles=6` not converged | **measured 10.8% drift**, worse than documented; test added |
| 2 | Fuelling open-loop on rpm | not started — Phase 1c |
| 3 | Torque limiter ±3% | symptom of #2 |
| 4 | Light-load fuel understated ~2× | not started — measure first |
| 5 | `operating_point` path-dependent | **measured 3.92%**, not "mild"; compounds in the grid build — FINDING-011 |
| 6 | `l` key dead in DCT | not started |
| 7 | No cold-temperature combustion | root-caused through FINDINGs 001–004 |
| 8 | Unknown-provenance code in `engine.py` | **closed** — FINDING-007; found a real cache bug |
| 9 | Worn-vs-new audio pair suspect | root-caused — FINDING-004 and 005 |
| 10 | `render_transient` seams | deferred |
| 11 | Coast downshift calibration | deferred |
| 12 | Grade small-angle form | not started |

---

## Also found, not yet actioned

- **Trace arrays are shape-inconsistent.** `traces.p` is per-cylinder 2D while
  `traces.theta` is 1D, and at load 1.0 their lengths differ (1430 vs 720).
  Hit twice while writing diagnostics. **Resolve before the Angular cycle page
  consumes traces.**
- **ADR-006 is on hold** and should be reassessed now that FINDINGs 001–004
  have changed the numbers it was decided on.
- **`SPL_CAL` and the 5.0e9 clatter divisor are chosen constants.** The package
  advertises exactly two fitted scalars (`NOX_CAL`, `SOOT_CAL`). That claim is
  no longer accurate; either derive the constants or update the claim.

---

## Tests

```
python3 tests/test_physics.py        # 13 passed, 0 failed, 2 known defects
python3 tools/audit_dead_signals.py  # diagnostic, reports only
```

Golden points are locked at 0.5%. They were re-baselined after FINDING-001 P-2
with the justification recorded inline — torque and BSFC moved under 1%, p_max
rose ~3%, and `hd_i6` still reproduces the documented 2310 N·m and stays inside
the 160–200 bar band.

Known defects report as KNOWN, not FAIL. When one is fixed the suite reports
UNEXPECTED PASS, which is the signal to promote it to a real assertion.

---

## Branches

Split by whether the change can be validated numerically.

| branch | contents | validated by |
|---|---|---|
| `physics/verified-fixes` | P-2 premix, motored pressure, `dpdtheta_comb`, roller `Pb_vt`, `h_ring_mid`, audit tool, tests | regression suite, 12 passed 0 failed |
| `audio/physical-levels` | all `acoustics.py` changes — clatter source, `sharp` divisor, physical source levels | **ear only** |

The audio branch depends on `physics/verified-fixes` for `p_motored` and
`dpdtheta_comb`, so merge that first.

The four earlier stacked branches (`fix/premix-from-delay-injection`,
`fix/combustion-dpdtheta`, `test/cold-oil-and-coolant`,
`fix/physical-source-levels`) are superseded by this split and can be deleted
once it lands.

---

## Next actions

1. **Listen to the audio pair** before merging branch 4. It is the one change
   here that cannot be validated numerically.
2. Decide whether FINDING-005's remaining cam-wear insensitivity is worth
   chasing, or whether roller cams genuinely barely wear and the durability
   story should say so.
3. Fix the trace shape inconsistency before any UI work.
4. Reassess ADR-006 against the new combustion numbers.
5. Then Phase 2 — `SolverPort` and the Pyodide worker.

---

## Housekeeping

- The GitHub PAT used in these sessions appears in chat history. **Revoke it**
  and issue a fresh fine-grained token.
- Solve time in the dev container is ~10 s against 1.47 s on developer
  hardware. **Do not benchmark Pyodide here.**
- The solver needs **numpy only**; `scipy.signal` is confined to `acoustics.py`
  and `play.py`, both being ported to TypeScript.
- `batch.py` imports `multiprocessing`, which does not exist in Pyodide.
- Working style: ask rather than assume; options come with trade-offs; warn
  before context budget limits.
