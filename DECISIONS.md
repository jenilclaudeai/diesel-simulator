# Architecture Decision Record

Append-only. Each decision gets a number, a status, the trade-offs that were
weighed, and what would make us revisit it. Do not edit accepted decisions —
supersede them with a new one.

Status values: `Proposed` · `Accepted` · `Superseded by ADR-NNN` · `Open`

---

## ADR-001 — Run the Python physics under Pyodide, do not rewrite it

**Status:** Accepted (2026-09-08)

### Context

`dieselsim` is ~3,700 lines of coupled float64 numerics. One operating point
takes ~1.5 s on developer hardware. The browser app needs both that solver
(offline, on spec change) and a 60 Hz real-time loop (flywheel, turbo shaft,
driveline, thermal).

Three options were considered.

### Options

| Option | Solve time | Rewrite risk | Download |
|---|---|---|---|
| **A. Pyodide, unmodified Python** | ~5–12 s | none | 15–30 MB (deferred) |
| B. Full port to Rust/WASM | ~50 ms | very high | ~1 MB |
| C. Full port to TypeScript | ~0.5–2 s | very high | small |

### Decision

Option A. The solver runs unmodified in a Web Worker under Pyodide.

### Rationale

The physics *is* the product. A rewrite is the single largest source of
"the simulator quietly lies" risk, and it front-loads that risk before there is
anything playable. Option C pays nearly all of B's rewrite cost for a fraction
of the payoff.

### Consequences

- Enjoy mode ships prebuilt grids and **never loads Pyodide** — instant start.
- Expert mode lazy-loads Pyodide on first spec change.
- Grid rebuild is minutes, not seconds. Needs a real progress UI and IndexedDB
  caching, not a spinner.
- The solver sits behind a single worker interface (`SolverPort`) so that
  swapping in a WASM implementation later touches one file.

### Revisit when

Grid rebuild time makes Expert mode unpleasant in real user testing, or the
Pyodide payload proves unacceptable on mobile. Then port hot modules
(`thermo`, `cycle`) to Rust behind the same port, keeping Python as the
reference.

### Verified 2026-09-08 — the solver needs numpy only

The dependency surface turned out much smaller than assumed. `scipy` is
imported in exactly two places, and **neither is on the solver path**:

| File | Import | Fate |
|---|---|---|
| `dieselsim/acoustics.py` | `scipy.signal` | ported to TypeScript (ADR-003) |
| `play.py` | `scipy.signal` | ported to TypeScript (Phase 3) |

Confirmed empirically by blocking `scipy` in `sys.meta_path` and solving an
operating point: `crdi15 @ 1800 rpm, load 0.8` returned 171.3 N·m with scipy
entirely unavailable.

**Consequences of this:**

- Pyodide needs `numpy` only. scipy is the bulk of the payload, so the download
  estimate drops well below the 15–30 MB assumed above. To be measured.
- The risk that flagged this ADR as provisional is gone. ADR-001 is firm.

### `multiprocessing` will not work in the browser

`dieselsim/batch.py` imports `multiprocessing` — the only module that does.
Pyodide has no process model, so `batch.py`'s parallel grid solving cannot run
as written.

Options for browser-side grid build, to be decided in Phase 2:

| Approach | Trade-off |
|---|---|
| Single-threaded in one Pyodide worker | simplest; grid build is N × solve time |
| Pool of Web Workers, one Pyodide each | near-linear speedup; N × the memory, and each worker pays Pyodide init |

The second is likely worth it — grid build is the one genuinely slow operation
in Expert mode — but it multiplies memory, which matters on mobile. Enjoy mode
is unaffected either way since it never builds a grid.

---

## ADR-002 — v1 includes a vehicle, but no tyre model

**Status:** Accepted (2026-09-08)

### Context

The brief lists three gearboxes (torque converter, DCT, manual) as headline
features, but also says v1 is "engine focused" with the car coming later. A
gearbox needs something to push against.

### Decision

v1 ships the vehicle as a **point mass**: aero drag, rolling resistance, grade,
driveline inertia. No tyre model, so no grip limit — tractive force may exceed
what a real contact patch could transmit.

"Extend to the car later" means tyres, suspension, weight transfer, chassis.

### Rationale

Reuses `play.py`'s already-debugged `Driveline`, `Gearbox`, `TorqueConverter`
and `LaunchClutch` (~2,000 lines) rather than discarding them. The alternative
(dyno rig only) would drop three headline features.

### Consequences

- Project files carry an engine identity **and** a vehicle identity.
- Standing-start acceleration figures will be optimistic. The UI must say so
  rather than presenting them as truth.
- Manual gearbox needs a clutch model that does not exist in `play.py` yet.
  Clutch operation detail is deferred (see Open Questions).

---

## ADR-003 — Audio synthesis in TypeScript AudioWorklet, not WASM

**Status:** Accepted (2026-09-08) — supersedes an earlier verbal recommendation

### Context

Initially assumed the DSP would need Rust/WASM for sample-accurate,
GC-free operation in an `AudioWorklet`.

On inspection the per-sample cost of `acoustics.py`'s signal chain — waveguide
delay lines, a modal resonator bank, biquads, impulse trains — is a few hundred
multiply-adds. TypeScript handles that comfortably at 48 kHz.

### Decision

Port `acoustics.py` to TypeScript running in an `AudioWorkletProcessor`.

### Consequences — this is why it matters

- No Rust toolchain in v1. One language for the entire frontend.
- No `SharedArrayBuffer`, therefore no COOP/COEP headers required, therefore
  **GitHub Pages hosting works with no service-worker workaround**.
- The worklet synthesises from crank-angle source arrays handed to it when the
  operating point changes, rather than streaming PCM across a thread boundary.
  No jitter buffer, no ring buffer underruns.

### Risk and mitigation

If TS proves too slow, that one worklet is ported to WASM behind an unchanged
interface. Contained.

### Do not reintroduce

`acoustics._impulses()` once had a window that was **identically zero** —
`raised_cosine(w)` with `w=2` — which silently deleted valve tick, injector
tick and piston slap with no error raised. The TS port must have a test that
asserts each source is non-silent.

---

## ADR-004 — Differential testing against Python golden fixtures

**Status:** Accepted (2026-09-08)

### Context

ADR-001 keeps the solver in Python, but the 60 Hz loop, the driveline and the
audio are all TypeScript ports. Ports drift. A drifted real-time loop produces
an engine that behaves differently from the solver that supposedly defines it —
the worst possible failure for this product, because it is invisible.

### Decision

Every TypeScript port of a Python module ships with a fixture file of
input/output pairs generated by the Python original. CI fails on divergence
beyond a per-module tolerance.

### Scope

| Module | Tolerance | Note |
|---|---|---|
| `kinematics` | 1e-12 rel | pure geometry, should be near-exact |
| `thermo` | 1e-10 rel | scalar fast paths already validated to 3e-14 |
| driveline / gearbox | 1e-6 rel | integrator, accumulates |
| `acoustics` | spectral | compare band energies, not samples |

### Consequences

Fixture generation needs the Python package runnable in CI. Adds a Python job
to an otherwise pure-Node pipeline.

### Non-negotiable

Without this, the port is unverifiable and every physics claim in the README
becomes a guess.

---

## ADR-005 — Angular standalone components with signals

**Status:** Accepted (2026-09-08)

### Decision

Standalone components, signals for state, `ChangeDetectionStrategy.OnPush`
everywhere. No NgRx.

### Rationale

State is small and mostly streaming telemetry. NgRx would add ceremony without
solving a problem we have.

### Consequences

- Telemetry updates happen inside `NgZone.runOutsideAngular`; OnPush components
  with `computed()` pull only what they need.
- Fastest-moving needles render on canvas in a `requestAnimationFrame` loop
  reading the signal directly, never triggering change detection.
- **Do not run change detection at 60 Hz across the tree.**

Angular version to be pinned at scaffold time against what is current then,
not quoted from memory.

---

## ADR-006 — Cold-start combustion via two grids

**Status:** ON HOLD (2026-09-08) — blocked by REVIEW-001 finding B-1

> **Do not implement.** Measurement shows the cold-start combustion sensitivity
> this decision exists to capture is largely absent from the solver: `dp/dθ`
> moves 1.7% across a 90 K coolant swing, `premix_fraction` is pinned at 0.0200
> at every temperature, and ignition delay is quantised to the crank step.
> Two-grid linear interpolation error on ignition delay reaches −27.5%.
> Diagnose the pinned `premix_fraction` first — it may restore the sensitivity
> and will change the numbers this decision was made on.
> Root cause now diagnosed in `reviews/FINDING-001.md`: the Watson premixed-
> fraction correlation returns a negative value at modern common-rail ignition
> delays and is absorbed by its 0.02 floor, so the premixed spike cannot
> respond to anything. Resolve that before reconsidering this ADR.

### Context

The real-time grid is solved warm. The coolant gauge, fan and radiator respond
to temperature, but the engine does not actually run worse cold. A cold diesel
that does not rattle is a conspicuous falsehood to the target user.

### Decision

Solve **two grids — cold and warm — and interpolate on coolant temperature.**

### Rationale

The physics that produces cold rattle is a chain the solver already models:
lower wall temperature → more heat lost per cycle → longer ignition delay →
larger premixed fraction → sharper `dp/dθ` → the high structural modes light
up. Two endpoints capture that; a full third grid axis captures it more
smoothly at N× the build cost.

| Approach | Build cost | Fidelity |
|---|---|---|
| Third grid axis on coolant T | N × | highest, smooth |
| **Two grids, interpolate** | 2 × | captures the rattle |
| Leave warm-only | 1 × | rejected |

### Consequences

- Grid build time doubles. Already the slowest operation in Expert mode, and it
  compounds with the `multiprocessing` limitation noted in ADR-001.
- Interpolation between two thermal endpoints is linear in coolant T. Real
  behaviour is not linear, so mid-warm-up is approximate. Accepted: the
  endpoints are right and the direction of travel is right.
- The cold grid needs a defined temperature. Proposal: solve cold at ambient /
  `thermal.oil_T_start`, warm at `thermal.coolant_T`.
- Enjoy mode's prebuilt grids ship in pairs.

### Note

Recorded as two-grid on the strength of the recommendation made when the
question was put. If the intent was the full third axis, supersede this.

---

## ADR-007 — Project file contents

**Status:** Accepted (2026-09-08) — resolves OPEN-C

### Decision

A project JSON contains **engine spec + vehicle + gearbox configuration**.
The solved grid is **not** bundled.

### Consequences

- Files stay small and diff-able. A project is text and can live in git.
- **Sharing a custom engine means the recipient rebuilds the grid**, which
  needs Pyodide and takes minutes. The UI must set that expectation at import
  time rather than appearing to hang.
- Enjoy mode is unaffected — its curated engines ship with prebuilt grids
  (ADR-008).
- The grid cache is keyed by spec hash, so re-importing a project already built
  on that machine resolves instantly from IndexedDB.

### Revisit when

Sharing becomes a common flow and the rebuild wait is the main complaint. An
optional "export with grid" toggle would be the fix.

---

## ADR-008 — Enjoy mode ships a curated roster built with `builder.py`

**Status:** Accepted (2026-09-08) — resolves OPEN-D

### Decision

Enjoy mode ships a curated set of engines authored via `builder.py` from
headline numbers, rather than exposing the four development presets
(`hd_i6`, `ld_i4`, `crdi15`, `single`).

### Rationale

The presets are development fixtures, chosen to exercise the solver across its
range. A roster should instead span *characters* an enthusiast recognises —
different displacements, cylinder counts, turbo arrangements and torque shapes
— so that switching engines feels like a meaningfully different vehicle rather
than the same curve rescaled.

### Consequences

- Roster contents become a new open item (OPEN-F), needed before Phase 5.
- Each roster engine needs two prebuilt grids (ADR-006), generated at build
  time by native Python — not in-browser — and shipped as static assets.
- `builder.py` sizes hardware from headline numbers, but **the solver decides
  what the engine actually does**. Every roster entry must be run through
  `verify()` and its achieved-vs-requested figures recorded in the repo.
- Development presets remain available in Expert mode.

---

## ADR-009 — Visual configuration means live 2D schematics

**Status:** Accepted (2026-09-08) — resolves OPEN-E

### Decision

Spec editing is backed by **2D schematics that update live** as values change.
No 3D part models.

### Scope

- Cylinder cross-section redrawing with bore, stroke, conrod, compression ratio
  and pin offset
- Valve-timing dial showing IVO / IVC / EVO / EVC and the overlap region
- Injection timing marked on the same crank-angle circle
- Turbo compressor map with surge and choke lines and the live operating point
- Ring pack and bearing clearance detail in the tribology panel

### Rationale

The schematics are not decoration — they are how a user builds intuition about
what a number means. Watching overlap open up as EVC moves teaches more than
the number does. This is the *Automation* lesson.

### Consequences

- SVG, driven by the same signals as the numeric inputs, so there is exactly
  one source of truth.
- Every schematic must be **derived from spec fields**, never hand-drawn to
  approximate them, or it will drift from the physics it claims to depict.
- Substantially cheaper than 3D, and works on mobile.

---

## Open decisions

### OPEN-B — Persona team operating model

Proposed: use the twelve roles as **review lenses at decision points** — the
physics pair reviews physics ADRs, the testers write acceptance criteria, the
two non-technical users are consulted on UX only — rather than as active agents
in every response. Running all twelve every turn costs a great deal of context
for little added rigour.

### OPEN-F — Enjoy mode roster contents

Which engines, and how many? Opened by ADR-008. Needed before Phase 5, not
before Phase 1.
