# PROPOSAL — Phase 6 (Expert mode): plan and scope

**Date:** 2026-10-05 (session 6)
**Status:** for the owner's decision. Nothing here is built yet.
**Lenses:** PM, LEAD, PHY1, PHY2, SW1, SW2, QA1, QA2, USR1/2 (advisory)

PLAN.md's Phase 6:
- **Spec editing:** lazy-loads Pyodide; full editing across all nine
  dataclasses, grouped by physical subsystem rather than class name; live 2D
  schematics (ADR-009).
- **Grid invalidation:** a banner, with rebuild progress.
- **Analysis pages:** curve, map, cycle (p–V log-log, p–θ, HRR, valve lift),
  sweep, durability.
- **Labels:** economy and BSFC shown anywhere are labelled steady-state
  (FINDING-009). Durability's `health` is **life consumed** (0 = new), not
  remaining health (FINDING-019).

The owner's direction (2026-10-05): finish this version as planned, with
grid-build speed deferred until after it (`PROPOSAL-grid-build.md`).

---

## Where it stands, measured today

| piece | state | evidence |
|---|---|---|
| Pyodide, lazily | **exists** | Dyno and Grid boot the solver worker on first use; `/enjoy` never fetches it (CI) |
| editing, solver side | **exists** | the bridge takes `"overrides"` on any engine: dotted paths over the 9 dataclasses' **173 fields** plus `EngineSpec`'s own (e.g. `idle_rpm`, `afr_limit`), type-checked, with "did you mean" errors (`overrides.py`) |
| editing, UI | brochure form only | ADR-014's custom-engine form: the headline numbers, not the spec |
| schematics | none | — |
| curve | **exists** | the Dyno page: a full-load pull, achieved against requested for custom engines |
| map | **exists** | the Grid page: 8 × 6 cells, cached by spec hash (ADR-010 addendum) |
| cycle | none | the solver has the traces (`CycleTraces`), but no bridge call returns them. FINDING-008: per-cylinder traces are in that cylinder's own crank angle, manifolds in engine angle |
| sweep | in Python only | `batch.sweep` uses `multiprocessing`, which Pyodide lacks: it needs a sequential bridge call |
| durability | in Python only | `DieselEngine.durability_run`, natively **2.8 min per 1,000 h** (`crdi15`, 200 h in 34 s), so **~7.5 min per 1,000 h in the browser** (×2.65, ADR-014) |
| invalidation banner | none | the cache key already changes with the spec, so a stale result is never *served*; nothing yet *tells* the user |

## The work, in order

1. **Bridge calls** (Python, numpy-only, ADR-001 unchanged):
   - `solve_cycle`: one point's traces. Cylinder 1's p, T, HRR and V,
     valve lifts, and the manifolds, with both angle axes named
     (FINDING-008).
   - `sweep`: one spec field over a range of values, sequential, with
     progress.
   - `durability`: in blocks, with progress, and a stated cost before it
     starts.

   Each gets golden fixtures and the round-trip test.
2. **Cycle page:** p–V (log-log), p–θ, HRR and valve lift, with injection
   timing and the valve events marked. The page an enthusiast learns most
   from.
3. **Spec editor:** every field, grouped by subsystem.
   - The groups: Cylinder and crank; Valvetrain; Injection and fuel; Turbo
     and air path; Lubrication and friction; Thermal and cooling; Ratings
     and limits.
   - Each field shows its unit, the preset's value, and whether it was
     changed. Any field resets.
   - Errors come from the bridge, word for word.
   - Export and import as JSON. This is ADR-007's spec part; the project
     file proper is Phase 7.
4. **Schematics (ADR-009),** SVG, derived from spec fields only:
   - the cylinder cross-section (bore, stroke, conrod, compression ratio,
     pin offset);
   - the valve-timing dial with overlap, and injection on the same circle;
   - the compressor map with the live operating point;
   - ring-pack and bearing-clearance detail.
5. **The invalidation banner:** an edit marks the curve, map and cycle
   results stale and offers a rebuild with progress. A drivable grid for an
   edited engine reuses ADR-014's build (the same 21–28 min on a laptop).
6. **Sweep and durability pages.** Durability shows life consumed (0 =
   new), and its default length is set by cost (e.g. 1,000 h, about 7.5
   min), with longer runs offered with their time stated first.

## Options for scope

| option | contents | costs | gives |
|---|---|---|---|
| **A. PLAN as written** | all six items above | the most work: 4 schematics and 3 new analysis pages | everything PLAN promises; the expert's full toolbox |
| **B. PLAN, staged (recommended)** | the same six items, delivered as two stacks: 1–3 (bridge, cycle page, editor) first, then 4–6 | the same total work | something useful at each stage (editing plus the cycle page first); review points between |
| C. Reduced | 1–3 and the banner; schematics, sweep and durability later | less now | the core expert loop sooner, but PLAN's phase isn't complete |

**Recommendation: B.** It's PLAN's scope, finished as the owner asked, but
staged so each half is reviewable and usable.

## Lens notes

- **PHY1/PHY2:** every plot labels what it shows. Cylinder 1's traces are in
  its own crank angle, and the manifolds in engine angle. Never overlay them
  without saying so (FINDING-008). Read `dpdtheta_comb`, not `dpdtheta_max`,
  if the cycle page shows dp/dθ. Use `n_cycles ≥ 9`. Economy and BSFC are
  steady-state.
- **SW1:** charts follow the Dyno page's hand-drawn SVG and tested axis
  helper (`dyno/axis.ts`); no chart library.
- **SW2:** the new bridge calls stay numpy-only, and no `multiprocessing`;
  they join the round-trip test and the Pyodide suite.
- **QA1/QA2:** each page gets an e2e check against native Python (as the
  Dyno page's has), and each bridge call a golden fixture. Mutation-test
  every guard.
- **USR1/2 (advisory):** 173 fields is a wall. Order each group by influence
  (geometry and injection first, tribology constants last), collapse the
  rarely changed, and show a schematic beside each group.

## Decisions needed

1. **Scope:** A, B (recommended) or C.
2. **Fields:** all 173+ (PLAN), grouped and ordered by influence with the
   rare ones collapsed (recommended), or a curated subset.
3. **Development presets** (`hd_i6`, `ld_i4`, `crdi15`, `single`) in Expert
   mode, as ADR-008 says, alongside the roster engines: yes (recommended)
   or roster only.
4. **Durability's default length:** 1,000 h (~7.5 min in the browser,
   recommended), or another.
