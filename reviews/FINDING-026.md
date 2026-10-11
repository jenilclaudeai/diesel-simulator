# FINDING-026 — Off the rating's air, the modern ECU's boost target passes the compressor's limit, and the vanes jam shut

**Opened by:** session 8 (2026-10-08), measuring Phase 7 step 4 (the Drive
weather table) on `main` after #107.
**Lens:** PHY1 (lead), PHY2, QA2
**Status:** **closed: A fixed, C declined, D stated.** The owner decided
on 2026-10-08: "C: No don't cut the fuel. then D." A is in #110 (landed on
`main` by #111). D is in `fix/finding-026-state` (below). *(Was: "fix A
built on `fix/finding-026-cap` (stacked on this finding's PR), with its
test and re-stamp proof below. Options C and D are for the owner." And
before that: "open. Fix A is measured below, in a scratch copy, and is not
yet on any branch.")*
**Reproduce:** the session-8 scripts (`diag_vgt.py`, `diag_roster.py`),
described below. They are not kept in the repo; the numbers are.

---

## How it was found

Step 4's first job was to re-measure the proposal's measurement 1 (a table
fitted from a few airs, within 1.15% of converged solves) on today's code,
before building anything. That figure was taken on #101's code, before
#107's modern ECU. On `crdi15`, 312 converged solves (12 coarse cells × 20
airs, plus 6 left-out cells × 12 airs):

| table | worst torque error, held-out airs |
|---|---|
| 4 pressures × 3 temperatures (12 airs) | 20.3% |
| 3 × 3 | 16.5% |
| 2 × 2 | 40.0% |
| no correction (Drive today) | 98.5% |
| density ratio | 50.5% |

Across cells (factors from the coarse cells at the left-out ones), torque
was up to 15.4% off and boost up to 25.1%. Read cell by cell, the worst
errors sat where the solved torque itself looked wrong. At 4057 rpm / 20%
load, Leh's air **halved indicated torque at the same fuel** (31.3 → 16.0
N·m), with boost up and the exhaust 77 K hotter. That is what this finding
is about. **The proposal's 1.15% does not hold on today's code.** It was true
of the code it measured, so its text stands, with a dated note beside
it there, in ADR-016 item 1 and in PLAN.

## What was measured

`crdi15`, converged, on the shipped grid's row fuel (as `bridge.live_cell`
solves), at Leh's air (65.8 kPa, 20 °C):

| 4057 rpm / 20% | brake torque | gross IMEP | PMEP | p_exh / p_int |
|---|---|---|---|---|
| standard air | 20.4 N·m | 4.14 bar | −1.52 bar | 3.65 / 2.48 bar |
| Leh, modern ECU | **5.2 (−75%)** | 4.04 | **−2.70** | **5.07** / 2.32 |
| Leh, mechanical | 29.9 (+47%) | 4.11 | −0.74 | 2.09 / 1.61 |

Combustion work is flat, so the whole loss is pumping. The VGT and its
target:

| crdi15 at Leh, modern | target after cap | after the EGR raise | achieved | VGT (minimum) | shaft krpm (clamp 277) |
|---|---|---|---|---|---|
| 4057/0.2 | 3.14 | **3.77** (cap 3.30) | 3.53 | **0.320 (0.32)** | 264 |
| 4057/0.6 | 3.30 | 3.63 | 3.61 | 0.348 | **276.8** |
| 2971/0.2 | 2.96 | **3.83** | 2.90 | **0.320** | 206 |
| 1886/0.6 | 3.28 | **3.85** | 3.31 | **0.320** | 215 |

## Cause

Two clamps, with no error raised: the pattern CLAUDE.md warns about.

1. **The cap comes before the EGR raise.** `engine.operating_point`
   (`engine.py:463`) caps the modern target at `turbo.pr_max_ref`. Then
   `cycle.run` (`cycle.py:323`) raises the target the VGT chases by
   ×(1 + 0.42 · EGR share), so EGR has exhaust pressure to flow on. At part
   load with EGR on, the target ends above the compressor's limit and is
   unreachable. The VGT's integrator winds onto `vgt_min_frac`, and exhaust
   back-pressure climbs to 4–6 bar.
2. **The shaft rides the solver's numeric clamp** (1.35 × `n_corr_ref`,
   `turbo.py:200`) at high rpm and full load. Every VGT roster engine
   reaches it at Leh, modern or mechanical, most with the vanes already
   wide open. Nothing models a real ECU's turbo-overspeed protection, which
   cuts fuel once the vanes can't open any further.

**Why #107's test passed:** its "boost ratio within the compressor's map
limit (+5%)" part is checked only at 2500 rpm full load, where EGR is zero
and nothing raises the target. At part load the achieved ratio was 3.53,
7% over the 3.30 limit.

## Scope: the roster at Leh

Converged; brake torque against standard air. "PIN" means on the clamp
(vanes within 0.005 of their minimum, or the shaft within 0.5% of its
limit).

| engine, rpm/load | now | VGT / shaft | with fix A | VGT / shaft |
|---|---|---|---|---|
| crdi15 4057/0.2 | −74% | PIN / 96% | −37% | 0.36 / 91% |
| crdi15 4057/0.6 | −30% | 0.35 / PIN | −2% | 0.73 / 97% |
| crdi15 4057/1.0 | −13% | 0.70 / PIN | −13% | 0.70 / PIN |
| crdi22 3854/0.2 | −31% | 0.52 / PIN | +3% | 0.70 / 85% |
| crdi22 3854/1.0 | −15% | 1.00 / PIN | −15% | 1.00 / PIN |
| hatch15 4057/0.2 | −40% | 0.46 / 99% | −2% | 0.63 / 85% |
| hatch15 4057/1.0 | −15% | 1.00 / PIN | −15% | 1.00 / PIN |
| truck127 1860/0.2 | −67% | PIN / PIN | −12% | 0.45 / 89% |
| truck127 1860/0.6 | −16% | 0.50 / PIN | −4% | 0.88 / 94% |
| v8hd 1959/0.2 | −76% | PIN / PIN | −6% | 0.50 / 90% |
| v8hd 1959/0.6 | −24% | 0.43 / PIN | −4% | 0.96 / 95% |
| v8hd 1959/1.0 | −14% | 1.00 / PIN | −14% | 1.00 / PIN |

At the middle of the speed range, 60% load, fix A costs 2–5 points
(crdi22 1791/0.6 −9% → −13%, hatch15 1886/0.6 −9% → −12%, truck127
1020/0.6 −8% → −11%, v8hd 1053/0.6 −9% → −11%). The capped target gives
less boost, so the smoke limiter trims fuel. That is plausible.

At idle speed and full load, the small engines lose 37–41% (crdi15,
crdi22, hatch15; truck127 −7%, v8hd −10%), and fix A doesn't change it.
That is the physical knee, not this defect: at 800 rpm there is no boost
to help, so the smoke-limited fuel follows air density (0.66 of
standard).

**Standard air: identical** in every one of the 25 cells, with and without
fix A (asserted). Both clamps act only off the rating's air.

**Live today:** the solving pages with the "High plateau" preset (#106),
and any edit of `/spec`'s ambient pressure. Drive and Enjoy run at standard
air, so they are untouched.

## Options

| option | what | measured | positives | costs |
|---|---|---|---|---|
| **A. Cap the target the VGT chases** | the modern target's cap divides by the EGR raise, so the raised target stays ≤ `pr_max_ref`; one shared function for the raise, so the two can't drift | yes, roster above | the defect itself; one line plus a refactor; at the rating's air bit-identical by construction, so the grids are re-stamped, not rebuilt | 2–5 points less torque at mid-speed part load; leaves item 2 and the residual below |
| B. A turbo-speed limit on the VGT | open the vanes above a shaft limit | yes: **does nothing useful.** At 4057/1.0 the vanes open fully (1.000) and the shaft stays at 276.4k | — | dismissed: the vanes are already open where it matters |
| **C. Turbo-overspeed fuel derate (modern ECU)** | above a shaft limit, trim fuel, as real ECUs protect the turbo | not yet | replaces a silent numeric clamp with the real protection; full load at altitude then loses power for a stated reason | a new limit per engine (e.g. its highest speed at the rating's air), its test and a re-stamp proof; the mechanical engine keeps riding the clamp (a real uncompensated turbo would overspeed) unless the page warns |
| D. State the light-load residual | crdi15 4057/0.2 stays −37% with A (vanes 0.467 at standard air, 0.361 at Leh): holding the rating's absolute boost at 20% load costs pumping. At 2971/0.2 and 1886/0.6 the sea-level calibration already runs the vanes at 0.325–0.329, just above their 0.32 minimum, so any altitude puts them on it | yes | honest, costs nothing | a known part-load inaccuracy at altitude, labelled where weather is compared |

**Recommendation:** A now. It is the defect, and ADR-016 item 2 already
says "capped at the compressor's map limit", so it makes the code do what
was decided. Then C, measured, before step 4's table, then D stated. Step
4's measurement is redone after the fix. A and C both touch hashed files.
Each must be proven bit-identical at the rating's air and the grids
re-stamped with `tools/restamp_grids.py`, as for FINDING-025 and #107.

## Fix A, built (`fix/finding-026-cap`)

- `cycle.egr_boost_raise(spec, egr_cmd)` is the raise, one function for
  `cycle.run` and the cap. The modern target is now
  `min(target × 101325 / p_amb, pr_max_ref / raise)`, so the target the
  vanes chase stays ≤ `pr_max_ref`.
- **At the rating's air nothing moves.** `tools/ab_rating_air.py` (new,
  kept): `solve_point` at 1200/0.3 and 2400/1.0 on all 10 engines, plus
  crdi15's `solve_cycle`. Old against new: **21 of 21 replies identical**
  by sha256. The tool itself is tested: a mutant raise (0.42 → 0.43, which
  acts at the rating's air) changes 8 of the 21.
- Grids re-stamped `0f1cc94c` → `172454a3` by `tools/restamp_grids.py`.
  The pre-change tree hashes to the grids' stamp, and each of the 10 grids
  and the accuracy table changes only in its 64-byte hash.
- `test_modern_cap_holds_with_egr_on`: crdi15 at Leh, converged, 5 parts.
  Baseline passes (PR 3.29 / 3.30 against 3.30; vanes 0.362; 115.5 vs
  117.4 N·m). Mutants, each tree probed to run its own code first:
  - the original code fails 4 parts;
  - no cap fails 4;
  - the cap divided twice by the raise (an over-cap) fails 1 part.

  3 of 3 caught, by assertion. The over-cap passed the first version of
  the test, so the "reaches the limit" part was added.
- **Corrected in place:** the first mutation run was void. The mutant
  trees linked `tests/` to the clone, so `tests/..` resolved to the clone
  and every mutant ran the fixed code: four identical passes. An
  `abspath` check didn't see it. The trees now copy `tests/`, the runner
  asserts with `realpath`, and the run was redone.

## The owner's decision, and D (`fix/finding-026-state`)

- **C declined:** no turbo-overspeed fuel cut. At high rpm and full load
  in thin air the shaft keeps riding the solver's clamp (1.35 ×
  `n_corr_ref`), on the modern and the mechanical ECU alike. That is now
  said, not hidden.
- **D, stated where the air is chosen:**
  - `web/app/src/app/weather/altitude.ts` holds the statement and its
    threshold, 90 kPa (about 1000 m; of the presets, only Leh).
  - The solving pages' environment picker shows it below the place's
    numbers, at full load too, because the turbo's ceiling is a full-load
    effect.
  - `/spec` says it beside ambient pressure and the ECU switch. The words
    live in `spec-meta.ts`'s `NOTE_EXTRA`, not in `config.py`'s comments:
    `config.py` is hashed, and a comment there would stale every grid.
  - The text: "In thin air, a turbocharged engine with a modern ECU holds
    its sea-level boost up to the compressor's limit. At light load that
    costs pumping work (crdi15 at Leh, 4057 rpm and 20% load: 37% less
    torque, converged), and at high rpm and full load the turbo runs at
    the model's speed ceiling: no turbo-overspeed protection is modelled
    (FINDING-026)."
- **Tests:**
  - Units 112 (+3), run without `physics-version.ts`; 6 of 6 mutants
    caught by assertion (the threshold flipped and lowered to 60 kPa, the
    finding dropped from the text, the ambient note removed, `noteFor`
    dropping the addition, the addition replacing the field's own note).
  - e2e:cycle 10 (+1): Leh shows the note, standard air doesn't. Its
    mutant (the picker without the line) fails exactly that check.
  - e2e:spec 13 (+1): both fields carry the note. Its mutant (`noteFor`
    without the path) fails exactly that check. A first mutant that
    didn't compile was refused as broken, not counted.

## Notes

- **NOTE (QA2):** `tools/audit_dead_signals.py` solves at standard air
  only, so a control pinned off the rating's air is invisible to it. It
  reported 0 dead, 2 frozen (the known ring-film clamp), 0 tiny with fix A,
  as before.

- **NOTE:** the shipped grids' recorded `spec` has no `ecu_modern` key.
  They were re-stamped after #107, not rebuilt, so that record predates the
  field. The live loop doesn't read it.
- **NOTE (cost):** converged solves ran at 49 s each on 7 workers in
  parallel on this Mac, against 20 s for a single solve alone. The
  proposal's browser-time estimate for the table (7–8 min) assumed
  single-solve speed per core, so it will be re-measured with the table.
