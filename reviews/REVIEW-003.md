# REVIEW-003 — Phase 1 exit (physics truth pass)

**Date:** 2026-09-26 (session 5)
**Scope:** PLAN.md Phase 1's exit criteria, on the stack #40 → #46
**Lenses run:** PM, LEAD, PHY1, PHY2, QA1, QA2, SW1, USR1/2 (advisory)
**Reproduce:**
- `python3 tests/test_physics.py`
- `python3 tools/validate_table.py [--aged]`
- `python3 tools/audit_dead_signals.py`

---

## Summary

| Class | Count |
|---|---|
| BLOCK | 0 |
| MAJOR | 2, both carried by the owner's decision (M-1, M-2) |
| MINOR | 5 |
| NOTE | 3 |

**Phase 1 can exit** once the stack is merged and the owner confirms
FINDING-018's option C′ (M-2). All three exit criteria are met, and the
evidence follows.

---

## Exit criterion 1 — every fixed bug has a regression test

Known bugs:

| bug | outcome | guarded by |
|---|---|---|
| #1 `n_cycles=6` | measured; call sites ≥ 9 | `test_n_cycles_convergence` (KNOWN, records the drift), `test_durability_solves_are_converged_enough` |
| #2 open-loop fuelling | no instability (FINDING-010); limits added | `test_pressure_and_temperature_limits` |
| #3 limiter ±3% | FINDING-013 items 1–2 | `test_limiter_calibrates_under_evaluation_schedules`, golden EGR-delivery check |
| #4 economy 2× | the claim was wrong (FINDING-009); no code change | — (a labelling requirement in Phases 5/6) |
| #5 path dependence | fixed (PR #41) | `test_cold_solve_is_path_independent` |
| #6 `l` key in DCT | fixed in `play.py` | **none**: interactive terminal loop (MINOR m-4) |
| #7 cold combustion | FINDINGs 001–004; ADR-011 | `test_premix_responds_to_temperature`, `test_combustion_dpdtheta_responds`, `test_sharp_not_clamped`, `test_no_pilot_double_count`, `test_cell_friction_from_trace` |
| #8 unknown code | FINDING-007; cache bug fixed | `test_calibration_cache_is_consistent` (**new**) |
| #9 worn-vs-new audio | FINDINGs 004, 005, 015, 017 | `test_source_levels_carry_physics` (**new**), `test_cam_film_and_time_base`, `test_flat_tappet_wears_more_than_roller`, `test_cam_wear_calibration`, `test_mech_levels_carry_physics` |
| #10 render seams | FINDING-014 | `test_render_transient_has_no_seams` |
| #11 coast downshift | deferred to Phase 3 | — |
| #12 grade | already correct | — |

Findings with code fixes:

| finding | guarded by |
|---|---|
| 001 | premix and pilot tests |
| 002 | `test_cold_start_sharpens_dpdtheta` (KNOWN), `test_combustion_dpdtheta_responds` |
| 003 | `test_sharp_not_clamped` |
| 004 | `test_source_levels_carry_physics` (**new**) |
| 005 | `test_cam_film_and_time_base` (boundary share) |
| 006 | `test_ring_film_field_responds` (**new**) |
| 007 | `test_calibration_cache_is_consistent` (**new**) |
| 008 | `test_theta_global_axis` |
| 010 | `test_pressure_and_temperature_limits` |
| 011 | grid cell equals a fresh-engine solve, in `test_cell_friction_from_trace` (**new check**) |
| 012 | `test_transient_stalls_cleanly` |
| 013 | limiter, converged flag, unsettled averaging, seeded limit, EGR delivery |
| 014 | seams |
| 015 | cam film, flat tappet, wear calibration |
| 016 | two ignition tests |
| 017 | mech levels, ramps clear the lash, `test_seating_on_ramp_is_ramp_speed` |
| 018 | `test_cam_lift_is_continuous` |
| 019 | `test_durability_solves_are_converged_enough` |

**The new tests were mutation-tested against a passing baseline** (`out/mut_p1.py`):

| mutant | result |
|---|---|
| BUG-8 cache clips to the raw limit | caught |
| `h_ring_mid` reads the clamp | caught |
| exhaust level factor dropped | caught |
| combustion level factor dropped | caught |
| grid solved at 6 cycles | caught |
| revert PR #37 (`hd_i6` ramp 0.06), against the tightened goldens | caught |

Every test added earlier in this session was mutation-tested in its own PR.

Suite: **51 passed, 0 failed, 2 known** with scipy; 47 passed, 0 failed,
2 known, 3 skipped without it (as under Pyodide).

## Exit criterion 2 — the validation table still holds

`tools/validate_table.py` (new), `hd_i6`, fresh engine per point, n_cycles 9.
**12 of 12 rows are in band:**
- peak torque 2313 N·m at 1700 rpm (documented 2310);
- rated power 432 kW;
- peak BMEP 22.8 bar;
- best BSFC 200 g/kWh (documented 213; inside 190–215);
- peak p_max 179 bar (documented 176);
- FMEP at rated 1.10 bar;
- mechanical efficiency 95%;
- volumetric efficiency 1.18;
- NOx 4.4 rated and 15.6 lugging (documented 20);
- soot 0.047 g/kWh;
- blow-by 11.7 L/min;
- wall heat 18%.

My first run printed a volumetric efficiency of 2.74. That run referenced it
to ambient density; the documented value uses intake-manifold density, and
the tool now does too.

**The 12,000 h paragraph under the table did not hold** and is corrected in
place in PROJECT_CONTEXT.md. Measured now:

| over 12,000 h | now | documented |
|---|---|---|
| power | −3.6% | −5% |
| BSFC | +3.7% | +6% |
| blow-by | 11.5 → 18.3 L/min | 11.8 → 18 L/min |
| oil soot peak | 1.8% | 2.8% |
| life consumed | 6% | ~20% |

How the documented figures were measured was not recorded.

## Exit criterion 3 — no number moved without an explanation

Every re-baseline in this phase is written up beside the golden it moved in
`tests/test_physics.py`, with converged references where the move was a
correction. One move was **not** explained: PR #37 moved `hd_i6`'s golden
−0.09%, inside the old 0.5% tolerance, and it went unrecorded. It is recorded
now (PR #40), and the tolerance is tightened (m-1).

---

## Findings of this review

**M-1 (MAJOR, carried by the owner to Phase 3) — the fast path does not converge at part load.**
FINDING-013 item 3. After the EGR start fix (PR #40), part-load torque is
13.5% RMS off converged, and 38.8% at worst (`crdi15` 4000/0.25). The cause is
the VGT loop on its clamp. The dyno page states its accuracy only for full
load, where it is 3–8.5%. Phase 3's real-time loop reads part-load cells, so
before Phase 3 exits, either fix item 3 or have the UI state part-load accuracy.
*(LEAD, PHY1, USR)*

**M-2 (MAJOR, owner's decision needed) — FINDING-018's fix option.**
C′ is applied in PR #42. It keeps breathing (≤ 0.1% torque) and the ramp
heights, and doubles the ramp speed (tick +6 dB). A, B and C are measured in
the finding. Confirm C′, or choose another option, before merging #42. #43
builds on C′'s ramp speed.
*(PHY2, PM)*

**m-1 (MINOR, fixed here) — golden tolerance.** It goes from 0.5% to 1e-5,
the SolverPort's measured cross-platform bound (the calibration chain
amplifies 1e-10 to ~1e-6), with values stored to 9 significant figures.
Mutation: reverting PR #37 now fails the `hd_i6` golden (+0.007%).
*(QA1, QA2)*

**m-2 (MINOR) — the p_max limit acts on fuel only.** Cutting `hd_i6`'s
peak pressure by 11% costs 57% of its torque. A real ECU retards timing
first. The limits don't bind today. If one ever does, model timing.
*(PHY1)*

**m-3 (MINOR) — cost of the limit check.** It adds one solve per speed:
+14–18% per capped cell and +89% per uncapped cell. Fast grids pay this per
cell. Row-sharing would move grid numbers. *(SW1)*

**m-4 (MINOR) — bug #6 has no test.** The fix sits in `play.py`'s terminal
key loop. It is carried to Phase 3, whose port needs a test for it. *(QA2)*

**m-5 (MINOR) — `hd_i6` and `single` stay tick-dominant (13×, 10.6×).**
Their ramps are steep, because ramp speed scales with `ramp_fraction`. The
fix needs a ramp-height parameter separate from `ramp_fraction`; judge it by
ear in Phase 4. *(PHY2, USR)*
*(2026-09-30: the owner chose to build it, in the same grid rebuild as
FINDING-023 option A, judged by ear on a before/after pair.)*
*(**Built 2026-09-30, `feat/slap-and-ramp`:**
- `ValveTrain.ramp_height_intake/_exhaust`: the ramps run to their own
  height (1.25× the lash) at 0.025 mm per cam degree, in front of the
  unchanged main event, so breathing is kept (lift-area within 0.1%).
- Tick ÷ loudest other: `hd_i6` 13.0× → 1.00×, `single` 10.6× → 2.98×;
  `crdi15` unchanged at 2.30× (`tools/tick_dominance.py`, now committed).
- Found on the way: the roster's `truck127` was at 224×, its valves on the
  flank (`engines/ROSTER.md`), now 0.90×.
- Awaiting the owner's ear.)*

**N-1 — the owner has not listened** to any audio change since FINDING-004.
That is now a Phase 4 exit criterion, not a Phase 1 one, by decision.

**N-2 — "two fitted scalars" was untrue**, and is corrected in place. Two
constants are fitted to data (`NOX_CAL`, `SOOT_CAL`). Several more are chosen
and are listed in PROJECT_CONTEXT.md §1.3.

**N-3 — a measurement slip this session, caught before use.** The EGR
comparison's "old" variant set module constants inside reused pool workers,
which contaminated 8 of 12 rows. It was rerun with explicit constants and one
task per worker. The correction is recorded in FINDING-013.

---

## Lens notes (advisory)

- **PM:** the exit is real, not declared. Two carried items have owners and
  phases. The FINDING-018 decision is the only thing between this stack and
  merge.
- **USR1/2:** nothing an enthusiast sees changed except the dyno page's
  accuracy note, which reads "not measured" until the table is regenerated
  on the merged tree (Phase 2, task #33). Part-load accuracy is the thing
  they would catch first (M-1).
- **SW1:** the solver gained two cached, state-restoring paths, the limit
  check and the cold calibration. Both are tested for bit-identity, because
  golden tolerances can't see a restore bug (−0.07%).
