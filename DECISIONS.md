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

**Status:** Superseded by ADR-011 (2026-09-25). *Was: ON HOLD (2026-09-08) —
blocked by REVIEW-001 finding B-1; REVIEW-002 then recommended superseding it.*

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

---

## ADR-001 — Measured (2026-09-22)

Addendum, not an amendment. The decision stands; these are the numbers it was
waiting on.

**The solver runs unmodified under Pyodide.** Pyodide 314.0.7 (Python 3.14.2,
numpy 2.4.6) in Node, the `dieselsim/` directory copied in byte-for-byte.
`scipy` is never imported.

**It produces the same numbers.** `crdi15`, 1800 rpm, load 0.6, `n_cycles=9`:

| | native CPython 3.12 / numpy 2.4.4 | Pyodide 3.14 / numpy 2.4.6 | relative diff |
|---|---|---|---|
| torque | 124.39075523765574 | 124.39075521835555 | 1.6e-10 |
| BSFC | 265.4029925226589 | 265.40299251761337 | 1.9e-11 |
| p_max | 110.78218326804465 | 110.78218325918708 | 8.0e-11 |

Different interpreter, different numpy, different maths library — agreement to
about ten significant figures.

**It is about 2× slower, not 3–8×.** Same container, run sequentially:

| solve | native | Pyodide | ratio |
|---|---|---|---|
| 1st | 6.61 s | 22.47 s | 3.4× |
| 2nd | 6.66 s | 17.16 s | 2.6× |
| 3rd | 6.53 s | 11.40 s | 1.7× |

Native is flat; Pyodide speeds up as V8 tiers the WebAssembly up from its
baseline compiler to its optimising one. A fresh worker pays ~3.4× on its first
solve; warm, ~1.7×. A grid build is dozens of solves in one worker, so nearly
all of it runs warm.

Load cost: 2.9–5.1 s for the runtime plus numpy in this container.

**Consequences**

- The "revisit when grid rebuild time makes Expert mode unpleasant" trigger is
  much further away than feared. The Rust/WASM port is not needed on current
  evidence.
- Keep the first-solve penalty in mind for UX: a single ad-hoc solve in a
  freshly-spawned worker is the slow case. A long-lived worker amortises it.

**Caveats**

- Node's V8, not a browser. Chrome shares V8; Firefox and especially Safari
  use different engines and may differ.
- One operating point, three runs, one single-core container. The ratio is
  robust in direction and rough in magnitude.

Reproduce with `tools/pyodide/` — see its README.

### ADR-001 — Measured, part 2: the grid builds in the browser too

The first measurement covered single operating points. The real-time grid is
the thing Expert mode actually rebuilds, and it additionally calls
`EngineSound.build_sources()` — in `acoustics.py`, which imported `scipy` at
**module level**. So the grid path was unimportable under a numpy-only Pyodide
even though `build_sources()` never runs any scipy code.

Fixed by deferring the import (`_LazySignal`); call sites and native behaviour
unchanged. The grid cell moved from `play.py` (which imports `termios` and can
never run in a browser) into `dieselsim/grid.py`, so native and browser share
one implementation. Refactor verified **bit-identical** natively: 0 of 64
performance values and 0 of 24 source arrays differ.

Same cell, `crdi15` 1800 rpm load 0.6, built under Pyodide against native:

| | result |
|---|---|
| 16 performance values (float64) | worst relative diff 4.8e-10 |
| 8,640 source samples (float32) | 8,624 bit-identical (99.81%); the rest differ by one float32 rounding step, ≤5.5e-8 of scale |
| scipy imported | no |

**PLAN Phase 2's exit criterion — "a grid built in-browser matches one built by
native Python within tolerance" — is met at cell level**, in Node's Pyodide. Not
yet at full-grid level, and not yet in a browser.

`tests/test_physics.py` now fails if any `dieselsim/` module imports scipy at
module level. Mutation-tested: reintroducing the import is caught and the file
and line are named. Static, because the suite also runs under Pyodide.

---

## ADR-010 — The SolverPort contract

**Status:** Accepted (2026-09-22)

### Context

ADR-001 calls for "one seam, Pyodide behind it". This defines that seam.

### Decisions

1. **Framework-free TypeScript** (`web/solver/`). No Angular dependency, so
   the seam is testable in plain Node now and Angular consumes it later.
2. **Transport-neutral worker.** The worker loop talks through a three-method
   `Endpoint` (`post`, `listen`, `close`), not the browser `Worker` API. The
   same `serveSolver()` runs in a browser Worker and under Node's
   `worker_threads` — so the tests exercise the real worker code, not a mock.
3. **JSON across the Python boundary**, plus raw little-endian float32 bytes
   for crank-angle sources. The TypeScript side never walks Python objects
   element by element; `dieselsim/bridge.py` is testable natively.
4. **Engines are `{preset}` or `{headline}`, plus dotted-path `overrides`** —
   the convention `batch.py` already used, now validated
   (`dieselsim/overrides.py`). An unknown path, wrong type or non-finite value
   is `invalid-request`, with a "did you mean" suggestion.
5. **Typed errors.** `SolverError.kind` is one of `invalid-request`,
   `non-finite`, `python`, `load`, `cancelled`, `protocol`. Python exceptions
   are mapped at the boundary with the traceback attached. Non-finite solver
   output is caught in Python and reported, never returned as a number.
   Addresses REVIEW-001 m-1.
6. **Cancellation granularity is one grid cell.** Python runs synchronously in
   the worker; the loop yields between cells so a cancel can land. Interrupting
   mid-cell would need `SharedArrayBuffer`, which needs COOP/COEP headers,
   which ADR-003 deliberately avoids so GitHub Pages hosting works.

### Verified

16/16 end-to-end tests through the real worker under Node: native agreement
to 1.55e-10 on points and grid cells; malformed requests rejected with useful
messages; a 6-cell build cancelled after 1 cell; the solver usable after
cancellation; concurrent requests correctly matched; `dispose()` rejects
in-flight and later calls.

### Found and fixed on the way

- **Overrides with a typo were silently ignored** (`batch._apply`'s bare
  `setattr` created a new attribute). A parameter sweep would have reported
  "no effect".
- **Registered presets were aliased** — `builder.register` returned the same
  object on every lookup, so a mutation leaked into the next one. Harmless in
  a one-shot CLI; in a long-lived worker, every request would inherit the
  previous request's edits. Built-in presets were never affected.
- **Python's output was silently lost** inside Node worker threads, because
  Pyodide's default writer needs a real file descriptor. The Node adapter now
  routes stdout/stderr explicitly. The browser adapter must do the same.

All three have regression tests; the aliasing one is mutation-tested.

### Decided 2026-09-22

- **Pyodide is self-hosted**, same origin as the app — not a CDN. Measured
  payload 9.3 MB compressed (16.7 MB raw), downloaded only by Expert mode.
  Chosen for: works on networks that block third-party CDNs (the dev
  container is one), no runtime dependency on a third party, version locked to
  the app, offline possible later. Cost: ~17 MB of deploy and hosting
  bandwidth — about 10,000 first-time Expert loads a month within GitHub
  Pages' 100 GB soft limit. The shared-cache argument for CDNs no longer holds:
  browsers partition their HTTP cache per site.
- **The dieselsim sources are bundled at build time** into one content-hashed
  asset, and the physics fingerprint (`sourceHash`) is computed in the same
  step. Runtime fetching of individual files was rejected: it needs a
  generated file list anyway, the cache needs the fingerprint before Pyodide
  boots anyway, and a deploy could leave a browser holding a mix of old and new
  files — silently wrong physics.
- **Hosting will likely change when paid Expert mode arrives**: GitHub Pages'
  terms prohibit commercial SaaS. Both choices produce plain static files, so
  nothing here may depend on GitHub-Pages-specific behaviour.
- ~~Grid cache keying~~ — **built**; see *ADR-010 addendum: grid cache* below.

### ADR-010 addendum: grid cache (2026-09-22)

Resolves REVIEW-001 **M-2** (cache key undefined; Python float formatting
unstable across versions) and **M-3** (no quota or eviction policy).

- **Key** = SHA-256 of canonical JSON of {grid format, physics version, engine,
  rpms, loads, n_cycles}. Computed in TypeScript, where number formatting is
  fixed by ECMA-262 and identical in every engine, with object keys sorted.
  Override order and number spelling (`5e-4` / `0.0005`) do not change it.
- **Physics version** = SHA-256 of the `dieselsim/*.py` sources. Any change to
  the solver invalidates every cached grid. Computed identically by Python
  (`bridge.source_hash()`) and TypeScript (`sourceHash()`) — **verified equal
  against the real worker**.
- **A cache hit never boots Pyodide.** The app supplies the physics version
  from its build; it is checked against the worker only on a miss, where a
  mismatch fails loudly as a stale bundle.
- **Budget** 50 MB (~30 default grids at 1.66 MB), LRU by last *use*. A grid
  larger than the budget is refused; a browser `QuotaExceededError` evicts one
  more entry and retries once. **A failure to store never fails the build.**
- The memory cache clones on the way in and out, so callers never share an
  object with it — the same aliasing bug `builder.register` had.

Verified: 20 fast tests (fake solver, fake IndexedDB) and 2 more through the
real worker — a real miss took 8.8 s and the hit 0.4 ms.

### ADR-001 — Measured, part 3: agreement loosens where the fast path is unconverged (2026-09-25)

Addendum, not an amendment. With FINDING-013 item 1 (the torque limiter
calibrated under the full-load schedules), native CPython and Pyodide agree at
`crdi15` 1800 rpm / 0.6 to **1.2e-6** relative, not the ~1e-10 measured in
part 1. Same numpy (2.4.6) on both sides, so not a numpy difference.

Measured step by step: the limiter's calibration is a chain of six
warm-started 9-cycle solves with the same iteration count on both platforms,
and the difference grows along it — 1.3e-10, 7.6e-11, 1.8e-8, 7.5e-8, 3.7e-7,
1.1e-6. Without EGR in the calibration the VGT limit cycle (FINDING-013 item
3) is active there, and a limit cycle amplifies a 1e-10 platform difference.

**Consequences**

- The decision stands: 1e-6 is physically negligible, and converged solves
  (offline) do not carry the limit cycle.
- `web/solver/test/roundtrip.test.ts` tolerance 1e-8 → 1e-5, justified inline
  and shown to still fail on a 0.1% error.
- "Agrees to ~1e-10" is a property of converged or non-oscillating points,
  not of the fast path in general.

---

## ADR-011 — The cold engine: friction live on oil viscosity, combustion on a cold/warm pair

**Status:** Accepted (2026-09-25) — supersedes ADR-006. See REVIEW-002.
*Was: Proposed (2026-09-25).*

### Context

REVIEW-002 measured the cold engine with converged solves: oil temperature
drives 21–78% of the torque loss and 224–375% of the FMEP rise; coolant drives
the combustion change (ignition delay +5–7%, combustion dp/dθ +1–2%) and a
smaller friction share. Friction is strongly nonlinear in temperature
(two-endpoint error up to +108%) and close to linear in oil viscosity
(−12.5% worst); combustion is linear in coolant temperature (≤ 0.2%).

### Proposal

1. **Friction is not gridded.** The real-time loop evaluates FMEP each frame
   from the live oil viscosity (and rpm, load). Either the friction model is
   ported to TypeScript with ADR-004 fixtures, or an FMEP(rpm, load, μ)
   surface is solved offline with enough viscosity points to meet the
   tolerance (to be measured; two are not enough).
2. **Indicated performance and sources come from two grids**, cold and warm
   *coolant*, oil held warm, interpolated linearly on coolant temperature —
   measured to within 0.2% for the combustion quantities.

### Trade-offs

| | positives | costs |
|---|---|---|
| This proposal | follows the physics; tracks oil warm-up lag; no friction axis | friction evaluated per frame (port or fitted surface); the brake/indicated split must be honoured everywhere |
| ADR-006 as written | one mechanism, simple | wrong axis for the dominant effect; up to +108% FMEP error |
| Third grid axis on viscosity | everything precomputed | 3–4× grid build; still an interpolation |
| Warm only, stated in the UI | nothing to build | the cold engine is a headline behaviour |

### Revisit when

A fitted FMEP surface cannot meet the tolerance with a handful of viscosity
points, or per-frame friction proves too costly on a phone.

### ADR-011 — Accepted: how friction reaches the real-time loop (measured)

Two ways to give the loop friction at the live oil and coolant state were
measured (`tools/diag_friction_adr011.py`):

**A fitted surface FMEP(rpm, load, viscosity)** — piecewise linear in oil
viscosity (nodes even in log viscosity), 273–363 K:

| viscosity nodes | 2 | 3 | 4 | 5 |
|---|---|---|---|---|
| worst FMEP error | 12.6% | 4.3% | 2.5% | 1.6% |

and coolant does not separate additively (up to 4.6%), so a surface needs a
coolant axis as well — roughly 6 × 3 friction solves per cell for ~1%.

**Friction evaluated from the cell's pressure trace** with the live oil state:
oil temperature never touches the pressure trace (IMEP identical to 0.000%
across 273–363 K oil), and friction evaluated on a trace solved at a different
oil temperature matches a full solve to **0.000%** in all 9 cases tried (three
points, three oil-temperature pairs).

**Chosen: trace-based.** Grid cells store the cylinder-pressure trace
(`p[0]`, 720 float32 ≈ 2.9 KB per cell); the real-time loop interpolates the
trace and evaluates the friction model with the live oil and coolant state.
Exact with respect to oil, no friction axis, no build multiplier. It needs the
friction model ported to TypeScript (ADR-004 fixtures).

**Cost, to confirm in the port:** 44 ms per evaluation in native Python, 94%
of it the journal-bearing eccentricity solve (~61 scalar iterations × 1440
points, ~88k calls). As compiled JavaScript that is on the order of a
millisecond — an estimate, not a measurement. Oil and coolant change on
second timescales, so friction need not refresh every frame.

### ADR-011 — step 1 implemented (2026-09-26)

- Grid cells carry `p_cyl` (cylinder 1's pressure, on the 0.5° source grid,
  float32 — +5.8 KB per cell) and `perf.p_rail`. `GRID_FORMAT` 1 → 2 and
  `play.py`'s `CACHE_VERSION` 6 → 7, so grids built without them rebuild.
- `dieselsim.grid.cell_friction(eng, rpm, p_cyl, grid_deg, fuel_mg, p_rail)`
  evaluates friction from a cell's stored trace at the engine's live oil and
  coolant state — the native reference for the TypeScript friction port.
- Measured: friction from the stored trace matches the cell's own to
  −0.008% (`crdi15` 1800/0.6) and −0.016% (`hd_i6` 1400/0.8); with cold oil it
  matches a full cold solve to +0.070% and −0.004%.

Next (Phase 3): port `FrictionModel.evaluate` to TypeScript with ADR-004
fixtures generated from `cell_friction`, and wire it to the loop's live oil
and coolant temperatures.
