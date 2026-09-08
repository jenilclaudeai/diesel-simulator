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

## Open decisions

These are blocking or near-blocking and are tracked in `STATUS.md`.

### OPEN-A — Cold-start combustion (known bug #7)

The real-time grid is solved warm, so the gauge, fan and radiator respond to
coolant temperature but the engine does not actually run worse cold.

| Approach | Cost | Fidelity |
|---|---|---|
| Third grid axis on coolant T | build time × N | highest |
| **Two grids (cold + warm), interpolate on coolant T** | 2× build | captures the cold rattle |
| Leave as-is | free | a cold diesel that does not rattle |

Recommendation: two-grid. The cold rattle is the part users actually hear, and
it comes from longer ignition delay → bigger premixed spike → sharper `dp/dθ`.

### OPEN-B — Persona team operating model

Proposed: use the twelve roles as **review lenses at decision points** (physics
pair reviews physics ADRs, testers write acceptance criteria, the two
non-technical users are consulted on UX only) rather than as active agents in
every response. Running all twelve every turn costs a great deal of context for
little added rigour.

### OPEN-C — Project JSON contents

Engine spec only, or spec + vehicle + gearbox config + solved grid? Bundling
the grid makes files large but lets a recipient drive a shared engine
immediately instead of waiting on a rebuild.

### OPEN-D — Enjoy mode engine roster

The four existing presets (`hd_i6`, `ld_i4`, `crdi15`, `single`), or a curated
set built with `builder.py`?

### OPEN-E — Scope of "visually configurable"

Assumed: live-updating 2D schematics — cross-section redrawing as bore / stroke
/ CR change, a valve-timing dial, a turbo map with the operating point plotted
on it. Not 3D part models. Needs confirmation.
