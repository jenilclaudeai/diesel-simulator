# Status

**Updated:** 2026-09-08
**Phase:** 0 — Foundations
**Branch:** `docs/project-plan`

Read this first in a new session, then `PLAN.md`, then `DECISIONS.md`.
Those three files replace pasting a context document.

---

## Where things stand

The Python `dieselsim` package is in the repo and verified working.
Architecture is decided (ADR-001 to ADR-005). No frontend code exists yet.

### Verified in this container

```
crdi15 @ 2000 rpm, full load, n_cycles=9
  torque 232.8 N·m · power 48.8 kW · BSFC 229 · boost 2.15 · p_max 138 bar
```

Sane for a 1.5 L CRDI. Solve took **10.0 s here** against 1.47 s documented on
developer hardware — this container's CPU is much slower. **Do not use this
container to benchmark Pyodide.** That has to happen on real hardware.

Repo `dieselsim/` is byte-identical to the delivered tarball.

---

## Blocking — nothing

All questions that blocked Phase 1 are resolved. Two open items remain, neither
blocking:

| # | Question | Needed by |
|---|---|---|
| OPEN-B | Persona operating model | process, not architecture |
| OPEN-F | Enjoy mode roster contents | Phase 5 |

### Resolved 2026-09-08

| Was | Now |
|---|---|
| OPEN-A cold combustion | ADR-006 — **ON HOLD**, blocked by REVIEW-001 B-1 |
| OPEN-C project file | ADR-007 — spec + vehicle + gearbox, no grid |
| OPEN-D Enjoy roster | ADR-008 — curated set via `builder.py` |
| OPEN-E visual config | ADR-009 — live 2D schematics, no 3D |

Consequences worth carrying forward:

- **Grid build time doubles** (ADR-006) and compounds with the
  `multiprocessing` limitation. The Web Worker pool question in Phase 2 matters
  more than it did.
- **Sharing a custom engine means the recipient rebuilds the grid** (ADR-007).
  The import UI must set that expectation rather than appearing to hang.
- **Every roster engine needs `verify()` run and recorded** (ADR-008).
  `builder.py` sizes hardware; the solver decides what it does.
- **Schematics must be derived from spec fields**, never hand-drawn to
  approximate them (ADR-009), or they drift from the physics they depict.

---

## Resolved this session

**The solver needs numpy only — no scipy.** This was the highest-value unknown
and it came out well. `scipy.signal` is imported only by `acoustics.py` and
`play.py`, both of which are being ported to TypeScript anyway. Verified by
blocking scipy at import and solving successfully (171.3 N·m, crdi15 @ 1800 rpm
load 0.8).

Pyodide payload is therefore numpy-only, well under the 15–30 MB originally
assumed. ADR-001 is now firm rather than provisional.

**New issue found:** `batch.py` imports `multiprocessing`, which does not exist
in Pyodide. Browser grid build is either single-threaded or a pool of Web
Workers each running its own Pyodide. Decision deferred to Phase 2 — see
ADR-001.

---

## Known bugs — status

Source: `PROJECT_CONTEXT.md` § 2.7. Nothing fixed yet.

| # | Issue | Plan |
|---|---|---|
| 1 | `n_cycles=6` not converged | **measured 10.8% drift**, worse than documented; test added |
| 2 | Fuelling open-loop on rpm | Phase 1c — design work |
| 3 | Torque limiter ±3% | symptom of #2 |
| 4 | Light-load fuel understated ~2× | Phase 1b — measure first |
| 5 | `operating_point` path-dependent | deferred, documented |
| 6 | `l` key dead in DCT | Phase 1a |
| 7 | No cold-temperature combustion | root cause found — see FINDING-001 |
| 8 | Unknown-provenance code in `engine.py` | Phase 1a — audit |
| 9 | Worn-vs-new audio pair suspect | Phase 1b |
| 10 | `render_transient` seams | deferred |
| 11 | Coast downshift calibration | deferred |
| 12 | Grade small-angle form | Phase 1a |

### Do not reintroduce

Ring/skirt film dimensional errors (400 µm films) · missing piston pin, timing
gear, crank seal, HP fuel pump friction · unstable oil thermal integrator ·
`_impulses()` zero-width window silently deleting three sound sources · TBN
consumed 10× too fast · converter sized off rated instead of stall speed ·
DCT clamping teleporting road speed · `q_wall_frac` 0/0 at zero fuelling.

---

## Next actions

1. **FINDING-002 is the root cause** — peak `dp/dθ` occurs 10° *before*
   combustion starts, so the reported pressure-rise rate measures compression.
   `acoustics.py:195` drives diesel clatter from that same signal. Combustion-
   window dp/dθ responds +11.5% to temperature; the whole-cycle max responds
   +0.4%. Fix path in `reviews/FINDING-002.md`.
2. **Decide FINDING-001 P-2** — P-1 (the double-counted pilot) is fixed on
   `fix/pilot-double-count`. P-2 remains: the Watson correlation is out of
   domain at modern common-rail delays. Options A/C/D in FINDING-001.
3. ~~Decide FINDING-001 P-1~~ — done — `premix_fraction` is pinned at its 0.02 floor
   because the Watson correlation returns a negative value at modern
   common-rail ignition delays. Four options recorded; PHY1 recommends fixing
   the double-counted pilot effect first, then replacing the correlation.
   ADR-006 stays on hold until this is settled.
2. Begin **Phase 1a** — cheap bug fixes (#1, #6, #12) and the #8 audit of
   unknown-provenance code in `engine.py`
3. Phase 1b — measure #4 before changing anything: trace `fuel_kg_h` at low
   load against the grid's `fuel_mg`

---

## Tests

`python3 tests/test_physics.py` — dependency-free, no pytest needed.

Golden operating points are locked at 0.5% tolerance, including `hd_i6`
@ 1700 rpm reproducing the 2310 N.m peak torque from `PROJECT_CONTEXT.md`
section 1.5.

Three defects are encoded as KNOWN rather than FAIL. When one is fixed the
suite reports UNEXPECTED PASS, which is the signal to promote it to a real
assertion.

## Housekeeping

- The GitHub PAT used this session appears in chat history. **Revoke it when
  the session ends** and issue a fresh fine-grained token next time.
- Working style: ask rather than assume; options come with trade-offs and
  positives; warn before context budget limits.
- GitHub Flow — branch per change, PR, merge to `main`.
