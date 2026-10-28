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

### Addendum (2026-09-26, Phase 2): the harness, and REVIEW-001 M-1

**Built.**
- `tools/fixtures/gen_fixtures.py` writes `web/physics/fixtures/*.json`
  (inputs, outputs, physics hash, numpy version).
- `web/physics` holds the TypeScript ports and their differential test.
- CI job `fixtures` runs two checks:
  1. `gen_fixtures.py --check` recomputes every fixture from its stored inputs
     and fails, naming the module, when the physics has changed and the
     fixtures were not regenerated;
  2. every port is run against the fixtures.

**Ported so far:** `kinematics` (slider-crank and cam lift) and `thermo`'s
scalar paths. The `friction` fixture (`grid.cell_friction` from stored
pressure traces, warm and cold oil) is generated now for the Phase 3 port
that ADR-011 needs.

**Measured:** kinematics agrees to 3.6e-14 and thermo to 4.0e-16. Mutations:
- five port mutants are caught (the pre-FINDING-018 ramp, JS `%` for Python's
  modulo, the on-ramp lash penalty, a sign in d²x/dθ², a missing
  dissociation term);
- three physics changes are caught by `--check` (a cam profile, `_K_DISS`,
  windage).

**One rule the table above did not have:** outputs computed by finite
differences cannot meet a module's relative tolerance on a different libm.
One ulp in `sin` becomes ~1e-10 of `d²L/dθ²` near an inflection, and that holds
between two Python builds as much as between Python and JavaScript. They are
compared at the rounding bound propagated through the original's stencil:
- 4·ε·L_max/h for the central first difference;
- 16·ε·L_max/h² for the second difference, at 4 ulp per sample: sin's ulp
  doubled by the square, plus two roundings.

A first bound of 1 ulp per sample was measured at 1.002 of itself, which was
too tight. Everything else is compared at the module tolerance, with the
denominator floored at 1e-3 of the series' largest value so that zero
crossings don't divide by zero.

**REVIEW-001 M-1 (per-step vs terminal).** Resolved as follows, for every
integrator port (driveline, gearbox, the real-time loop):
- **Reference trajectory:** Python's recorded state at every step of a fixed
  scripted drive (inputs recorded per step), written by the generator.
- **Per-step bound:** starting from Python's state *k* with Python's inputs,
  one TypeScript step must reproduce state *k+1* to **1e-12 rel** for
  arithmetic-only steps, and to the module tolerance where a step calls an
  iterative solver. This isolates the step function; nothing accumulates.
- **Terminal bound:** the free-running TypeScript trajectory against
  Python's after the whole drive, on integrated quantities (distance, fuel
  used, final speed and temperature), to **1e-6 rel**. The trajectory
  comparison is aligned on discrete events (gear changes, lock-up, stall),
  and an event firing at a different step is reported as a failure in its
  own right, not as a numeric drift. A drive chaotic enough to break 1e-6
  without an event mismatch has to be shortened, and the reason recorded.
  The tolerance is not to be loosened to fit it.

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

**Resolved by ADR-013 (2026-09-30).** *Was:* Proposed: use the twelve roles as **review lenses at decision points** — the
physics pair reviews physics ADRs, the testers write acceptance criteria, the
two non-technical users are consulted on UX only — rather than as active agents
in every response. Running all twelve every turn costs a great deal of context
for little added rigour.

### OPEN-F — Enjoy mode roster contents

**Resolved by ADR-012 (2026-09-30).** *Was:* Which engines, and how many?
Opened by ADR-008. Needed before Phase 5, not before Phase 1.

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

### Addendum (2026-09-26, Phase 3): step 2 done -- friction live in the real-time loop

- `web/physics/src/friction.ts` and `lubrication.ts` port `FrictionModel.evaluate`.
  Against `fixtures/friction.json` they agree to **3.5e-13** (6 cases × 27
  quantities: warm and cold oil, a cold-coolant case, and the flat-tappet
  `single`), at **8.2 ms** per 1,440-sample evaluation in Node.
- `dieselsim/live.py` `Adr011Grid` holds warm (spec coolant, 361 K) and cold
  (273 K) cells on a shared per-row fuel limit, each with its cylinder-1
  trace. `grid.solve_cell` takes `T_coolant` for the cold cells. Indicated
  torque is each cell's brake torque plus the friction torque it was solved
  with, and it is interpolated linearly on coolant temperature.
- `LiveEngine` evaluates friction every 6th frame (10 Hz) from the blended
  trace at the live oil temperature, with walls set by the live coolant (the
  same path as `grid.cell_friction`). It adds engine.py's oil node to its
  cooling stack. Grids without traces keep the old behaviour; play.py still
  uses them.
- Measured:
  - At the warm state on a cell, live friction from the float32 trace is the
    cell's own to within 0.02–0.09% (the traces are stored float32), and
    brake torque matches to 0.01 N·m.
  - A 298 K engine has ×1.74 the friction at 1800 rpm / 0.6.
  - Over a 60 s drive from cold, the oil warms 298 → 328 K. The cold drive ends
    slower (63.2 vs 64.8 km/h on the old warm-baked grid), which is bug #7
    closed in real time.
- The TypeScript loop matches Python on the two ADR-011 fixture drives:
  per step 1.0e-14, every event on the same step, final values within 2e-15.

---

## ADR-012 — Enjoy mode: the roster, touch pedals, `/enjoy`, judged on a mid-range Android

**Status:** Accepted (2026-09-30), resolving OPEN-F. The owner chose each
recommendation in `reviews/PROPOSAL-phase5.md`.

### Decision

1. **Roster B, delivered as A first.**
   - A: a 1.5 L I4 hatchback; a 2.2 L I4 SUV (`engines/crdi22.json`); a
     12.7 L I6 truck.
   - B adds: a 15 L V8 truck (`engines/v8hd.json`), and an old naturally
     aspirated single-cylinder.
   - Each is built with `builder.py` from brochure numbers (ADR-008), gets
     its own vehicle, is tuned until `verify()` holds its plateau, and ships
     a converged warm/cold grid.
2. **Touch controls: pedals, plus paddles along the top.**
   - Throttle on the right edge and brake on the left, each pressed harder
     by sliding up.
   - Shift-up and shift-down paddles in the top corners.
   - A clutch beside the brake for the manual.
   - The throttle follows the finger and returns to zero when released.
     Brake and clutch spring back as the keyboard's do (`pedal_return`).
   - The keys keep working.
3. **A new `/enjoy` page:** the dashboard and the touch controls, nothing to
   configure. `/drive` stays as the engineering page.
4. **The exit is judged on a real mid-range Android phone in Chrome.**

### Rationale

The roster spans characters that *sound* different: 1, 4, 6 and 8
cylinders, and one engine with no turbo. It starts with the three engines
whose vehicles mostly exist. Touch is what makes the app drivable on a phone
at all: measured on 2026-09-29, `/drive` had no touch controls. Chrome on
Android is the engine every test here already runs.

### Consequences

- Touch input is UI and worker plumbing only. It sets the same loop fields
  the keys do, so the Python reference and the fixtures are unaffected.
- Every roster engine costs a vehicle (Python + TypeScript + fixture), a
  tuning pass, and a converged grid (3.5–15 min, ~1 MB gzip).
- FINDING-023 (cold slap) is best settled before the roster is tuned by ear.

---

## ADR-013 — The twelve personas are review lenses, not agents

**Status:** Accepted (2026-09-30), resolving OPEN-B. The owner accepted the
proposal as written.

### Decision

The twelve roles in `TEAM.md` are **review lenses applied at decision
points**:
- the physics pair reviews physics ADRs and findings;
- the testers write acceptance criteria and review test design;
- the two non-technical users are consulted on UX only.

They are not active agents in every reply.

### Rationale

Running all twelve every turn costs a great deal of context for little added
rigour. The project had already worked this way since session 1 (CLAUDE.md
says so), and every finding names its lenses. The ADR records the practice.

### Consequences

- No change in how work is done; `DECISIONS.md` now agrees with CLAUDE.md,
  and no open decision remains in it.
- Revisit if a review misses something a lens would have caught at the time.

---

## ADR-014 — Custom engines: from brochure numbers or JSON, drivable

**Status:** Accepted (2026-10-01). The owner chose each option below.

### Decision

1. **A custom engine is the roster's JSON format** (`engines/*.json`:
   brochure numbers for `builder.build_engine`, plus its optional tuning),
   with one addition: `vehicle`, the key of an existing vehicle
   (`live.Vehicle`). The app builds the engine from a form or an imported
   file, and exports the same JSON. The browser's solver already takes it,
   as `{"headline": ...}` (ADR-010).
2. **Dyno and Grid run it in the browser**, showing achieved against
   requested, as `builder.verify()` does.
3. **It can be driven.** Driving needs the same converged warm+cold
   **8×6** grid as the roster (the owner's choice over a coarser 6×5), by
   either of two paths:
   - **built in the browser** by a pool of solver workers, with progress,
     resumable, and cached per engine (by spec hash, as ADR-007 expected);
   - **built natively** from the JSON with one command, and imported into
     the app as a file. This is the path for phones.

### Rationale

Measured 2026-10-01 on `hatch15`, single-threaded. Native: a row's fuel
calibration takes 75 s and a converged cell about 18 s. Under Pyodide those
are 199 s and about 50 s, 2.65× slower. A full grid (8 rows, 96 cells) is
therefore:

| where | time |
|---|---|
| one browser worker | ~105 min |
| 4 workers | ~26 min |
| 8 workers | ~13 min |
| native, 6 cores | ~15 min |
| a phone | hours (not measured) |

No single path serves every device, so the app offers both. A coarser grid
would have cut the wait by about 40%, at the price of a second grid shape
to support and a coarser map; the owner kept one shape.

### Consequences

- The worker and `LiveEngine` take the vehicle from the grid file (a
  roster key still maps to its own vehicle). A custom grid must name one of
  the known vehicles (`live.VEHICLE_KEYS`, held to TypeScript by the
  vehicles fixture). The build tool and the app refuse one that doesn't,
  rather than letting it fall through to the default vehicle.
- A custom grid records its engine JSON and its SHA-256, as roster grids
  do, so a grid is never paired with the wrong engine.
- A custom engine is `verify()`-checked the same way as roster ones, but it
  is the user's engine: the app shows its achieved figures and does not
  refuse an engine that misses its brochure.
- ADR-007's project file can later carry the same engine JSON.

### Revisit when

The browser build proves too slow in practice on the machines people use
(measure on a real laptop first), or phones become the main way people
build engines.

---

## ADR-015 — Phase 6 (Expert mode): PLAN's full scope, in two stages

**Status:** Accepted (2026-10-05). The owner chose option B in
`reviews/PROPOSAL-phase6.md` ("let's go with option B").

### Decision

1. **Stage 1:** bridge calls for a cycle's traces, a parameter sweep and a
   durability run; the cycle page (p–V log-log, p–θ, heat release, valve
   lift); and the spec editor.
2. **Stage 2:** the four ADR-009 schematics, the grid-invalidation banner,
   and the sweep and durability pages.
3. The proposal's other three recommendations, taken as accepted. The owner
   answered only the scope question; these were offered as the defaults
   ("if you just say 'go' I'll start with my recommendations"):
   - **every field** is editable (173 in the nine dataclasses, plus
     `EngineSpec`'s own), grouped by subsystem, ordered by influence, with
     the rarely changed collapsed;
   - the **development presets** appear in Expert mode beside the roster
     engines (as ADR-008 says);
   - **durability defaults to 1,000 h** (~7.5 min in the browser), and
     longer runs state their time first.

   Any of the three can be changed by the owner without reopening the
   rest.

### Rationale

PLAN.md's scope, which the owner asked to finish before any additions
("First I would like to go as per plan and complete this version"), staged
so each half is usable and reviewable.

### Consequences

- The new bridge calls are numpy-only and use no `multiprocessing`
  (ADR-001). They live in `bridge.py`, which the grid hash excludes, so no
  prebuilt grid goes stale.
- Every plot names its angle axis: cylinder 1's own crank angle for its
  traces, engine angle for the manifolds (FINDING-008).
- The grid-build speed work (`PROPOSAL-grid-build.md`) waits until after
  v1, by the owner's decision of the same day.

---

## ADR-016 — Phase 7 (Environment and projects): the proposal's six recommendations; v2 is a separate list

**Status:** Accepted (2026-10-07). The owner answered four direct questions
(session 7): "Accept all" for `reviews/PROPOSAL-phase7.md`, "On /spec" for
the project file, "v2, after v1" for Feat Prop P02–P05, and "1 is highest"
for the Feat Prop priority scale.

### Decision

1. **Weather in Drive and Enjoy: option A.** A per-engine table of torque
   factors at a few airs, fitted from converged solves and interpolated at
   run time. Measured: within 1.15% of converged solves on held-out air,
   where a density ratio is off by 28.7%. Sound and friction stay the
   grid's (standard air). *(2026-10-08: the 1.15% was measured before
   item 2's ECU (#107). On today's code it is 20.3%, mostly FINDING-026;
   re-measured after the fix. The decision stands.)*
2. **The ECU at altitude: option 2 for the common-rail engines, 1 for the
   mechanical single.**
   - Option 2 is an ECU that knows absolute pressure: an absolute (MAP)
     boost target, and a smoke map on absolute manifold pressure.
   - Option 1 is uncompensated: what FINDING-025's fix ships.
   - Chosen per engine ("ECU: modern / mechanical").
3. **Humidity: ISO 8178's K_H factor on reported NOx.** No water vapour in
   the cycle; the page says it is a correction.
4. **Cold-flow: yes.** Below the fuel's CFPP the filter waxes and fuel flow
   is capped, in the live loop (Python and the TS port, with a fixture).
5. **Presets: five real places and seasons**, each shown with its numbers
   and editable. The proposal's list: sea level temperate (the standard
   air), hot desert summer, cold continental winter, high plateau
   (≈ 3500 m), humid tropics.
6. **Projects (ADR-007's file), saved and opened on `/spec`.** "Save
   project" and "Open project" replace Export/Import spec, and old spec
   files still open. `/drive` and `/enjoy` can open a project. The file
   carries a format version; the environment joins it.

And, for the owner's "Feat Prop" list (the bug sheet, read 2026-10-06):

7. **P01 (vibrations on a phone) is v1**, in `/enjoy`. Android Chrome only:
   iOS Safari has no Vibration API. *(Amended 2026-10-21, the owner's choice
   after feeling the build: the shake runs whenever the engine does and
   follows the pedal, not only at idle and lugging; a Test button on the start
   screen. Was (2026-10-19): events plus a shake while idling or lugging.)*
8. **P02–P05 are v2, after v1.** That's Google sign-in, free/paid roles,
   grid builds on a backend and on AWS Lambda. v1 stays a static site
   (ADR-003), and PLAN's out-of-scope list stands. **Priority 1 is
   highest**, so the owner's order for v2 is P04 (grid on a backend), then
   P02 (sign-in), then P03 and P05.

### Rationale

Each recommendation came with measurements (the proposal's "Three
measurements") and was offered with its alternatives. The owner took all
six. P02–P05 each need a server, which PLAN and ADR-003 rule out for v1,
and the grid-build plan was already deferred until after v1 (2026-10-05).

### Consequences

- Build order, from the proposal: presets; environment on the solving
  pages; the ECU change; the Drive correction table; humidity; cold-flow;
  projects. REVIEW-008 m-3, the persistence the projects need, shipped
  ahead in #103.
- The ECU change touches `turbo.py` and `cycle.py`, both hashed. If the
  absolute target equals ratio × 101325 Pa, no cell moves at standard air,
  and the grids can be re-stamped rather than rebuilt. That must be proven,
  as for FINDING-025, not assumed.
- On the fast solving pages a part-load weather delta can be FINDING-013's
  convergence gap. Weather comparisons are labelled with the measured gap,
  or kept to full load.
- v2's first item is P04: the grid-build plan (`PROPOSAL-grid-build.md`)
  already weighs a build server.

### Addendum (2026-10-08): custom engines get the weather table too

Item 1 left one choice open: build the correction table for custom engines
in the browser (~7–8 min more on 8 cores, the proposal's estimate, not yet
measured), or keep them at standard air and say so. **The owner chose:
the browser builds it** ("Yes, browser should be able to build the weather
table"), noting that all heavy processing is meant to move to a server
later (v2's P04/P05). So the table is built from the same kind of
independent, resumable pieces as ADR-014's grid, through bridge functions:
the browser's worker pool runs them now, and a server or one Lambda
invocation per piece can run the same pieces later without rework.

### Addendum (2026-10-08): P06, randomness in the drive

A sixth "Feat Prop" row, "Randomness in drive mode" (priority 2), arrived
after this ADR, under a duplicate ID P05. The owner's aim: "keep the user
engaged and make it interesting". **Decided by the owner ("Agreed, tiers
1–2 in v1, rename it P06"):**
- **P06 tier 1, v1:** a seeded random route the engine feels: hills,
  surfaces (rolling resistance), headwind, altitude along the route
  through item 1's table, a 2D "road ahead" strip, and speed breakers as a
  slow zone plus a jolt (no suspension; the page says so).
- **P06 tier 2, v1:** goals on a route (reach a pass without overheating,
  an economy run, a time to beat).
- **P06 tier 3, v2:** drawn traffic and scenery.

Constraints carried: one PRNG in Python and TypeScript so the live fixture
holds (ADR-004); sand is rolling resistance only, with no grip (ADR-002).
Its own proposal, with measurements, comes after item 1's table (Phase 7
step 4). Where the build goes in the order is decided in that proposal.

### Addendum (2026-10-08): item 2's ECU in thin air (FINDING-026)

Measuring item 1's table found that the modern ECU's boost cap came before
`cycle.run`'s EGR raise. Off the rating's air the VGT then jammed on its
minimum at part load: up to −76% torque at Leh. It is fixed (#110, fix A),
so the target the vanes chase is capped at the compressor's limit, as item
2 says. Nothing changed at the rating's air (21 of 21 replies identical).

**The owner then decided** ("C: No don't cut the fuel. then D."):
- **No turbo-overspeed fuel cut.** In thin air at high rpm and full load
  the turbo runs at the solver's speed ceiling on both ECUs, with no
  protection modelled.
- **Stated instead:** the solving pages' environment picker (below 90 kPa)
  and `/spec`'s ambient-pressure and ECU fields say so. So does the
  remaining light-load pumping cost: crdi15 at Leh, 4057 rpm / 20%, −37%.

### Addendum (2026-10-08): item 3 built (humidity on NOx), and which form

Item 3 said "ISO 8178's K_H factor (also in 40 CFR 1065)". The two are not
the same equation. The built form is **40 CFR 1065.670-1** for
compression-ignition engines, `× (9.953 x_H2O + 0.832)`, normalised to
exactly 1 at ISO 8178's reference 10.71 g/kg. The equation's own unit
point, 0.01688 mol/mol, is 0.05% off it.

- **Why this form:** it is humidity-only, and it could be read in full (ISO
  8178 is paywalled). The older diesel forms carry a temperature term too
  (e.g. EPA's 1 + 0.00446 (T − 25) − 0.018708 (H − 10.71)), which would
  count intake temperature twice: the cycle already solves it.
- **Direction:** the model's NOx is the reference humidity's. Humid air
  reports less (Mumbai, 21.63 g/kg: ×0.858), dry air more (Leh 7.82 g/kg:
  ×1.047; Rovaniemi 0.67 g/kg: ×1.187, an extrapolation of a linear
  correction).
- `thermal.ambient_humidity` (g/kg, default 10.71) is the spec's field; the
  presets set it. Nothing but the reported NOx moves.
- If the owner prefers an ISO-style form, only `engine.nox_humidity_factor`
  changes.

### Addendum (2026-10-09): item 1's shape is A3

`reviews/PROPOSAL-weather-table.md` measured four shapes for item 1's
table on today's code (624 converged solves). **The owner chose A3**
("A3, go ahead"): every grid cell, warm, at 8 airs. The airs are 3
pressures (58, 72 and 101.3 kPa) × 3 temperatures (−20, 25 and 45 °C),
less the standard air, which is the grid's own cell.

Measured: 2.4–3.6% of full-load torque at the presets, and 5.2–5.5% down
to 52 kPa. About 390 converged solves per engine (with 6 held-out checks at
Leh, whose worst error the file records), and about 1.3 h extra per custom
engine in a browser. The proposal's 1.15% (measured before #107's ECU) is
superseded by these numbers.

*Outcome (2026-10-09):* all ten grids carry a table, and each records its
own Leh check: 0.3–2.8%, except single10 at 7.2% (a misfire in cold, thin
air, FINDING-027) and hd_i6 at 4.7% (a smoke-limit knee between pressure
nodes). The pages show each engine's own figure.

### Addendum (2026-10-10): item 4, cold-flow, and how a driver gets waxed fuel

Every place sells the right fuel (Rovaniemi arctic diesel at −20 °C, Leh
winter diesel at 20 °C), so a wax cap fed only by the place would never
act: an input nothing feeds, FINDING-025's pattern. **The owner chose a
fuel picker** ("A fuel picker"), over extra "wrong fuel" places or an
editable temperature.
- `/drive`, and `/enjoy`'s start screen, show Fuel beside Place: sold here
  (the default), summer (CFPP 18 °C), winter (6 °C) or arctic (−32 °C).
  The grades are `environment.FUELS`, from the same sources as the places.
- The live loop (Python and TypeScript, fixture-matched):
  - The fuel starts at the ambient. Running, it warms toward the ambient
    plus 60% of the coolant's rise over about 7 minutes; stopped, it
    drifts back over about 30.
  - The filter passes all the fuel down to CFPP + 2 K and none at
    CFPP − 6 K. That share caps the governor's demand.
  - Below 12% the engine is waxed out: no fuel, the reason given, and a
    restart refused.
  - A part-waxed engine that can't start says why after 3 s with the car
    standing.
  - These are approximations, stated as such.
- With the five places, each grade either flows or gels: no place's
  temperature falls inside a grade's waxing band. The limp, part-waxed
  path is exercised by the loop's tests and fixture, and is there for
  P06's roads.

### Addendum (2026-10-10): item 6, projects, and where the drive settings come from

ADR-007's project is "engine spec + vehicle + gearbox configuration", and
item 6 adds the environment. But `/spec`, where projects are saved, had no
gearbox, place or fuel. **The owner chose a "Drive with" box on `/spec`**
("A 'Drive with' box on /spec"), over saving the engine and the
environment only, or capturing Drive's last settings unseen.
- **The file** (`web/app/src/app/spec/project.ts`), version 1:
  `{"format": "dieselsim-project", "version": 1, "engine": {"preset",
  "overrides"}, "drive": {"gearbox", "place", "fuel"}}`. The vehicle is
  the base engine's own. No grid is bundled (ADR-007).
  - A newer version is refused, saying so.
  - An old spec file (`{preset, overrides}`) opens as the engine only,
    and the page says the drive settings stayed as they were.
  - Every field is checked, and refused in words.
- **`/spec`:** "Save project" and "Open project" replace Export/Import
  spec. The "Drive with" box holds the gearbox select and the same Place
  and Fuel picker as Drive and Enjoy.
- **One shared choice.** The gearbox joins the place and the fuel in
  `DriveEnv`, kept per browser. So what `/spec` shows is what Drive starts
  with, and opening a project anywhere sets all three. It also becomes
  `/spec`'s edits: a project is the app's one current project.
- **`/drive` and `/enjoy` open a project** and select its engine:
  - an unedited engine selects the preset, if that page offers it;
  - an edited one selects its grid in "Your engines", found by the edits
    (`editedEngine`'s key), or says to build it on `/spec` first, as
    ADR-007 foresaw;
  - Enjoy has no dual clutch, so a DCT project drives as Auto there, and
    the page says so.

## ADR-017 — P08: the automatic shifts on demand, by the engine's fuel map

**Status:** Accepted (2026-10-12). The owner answered three direct
questions (session 9) on `reviews/PROPOSAL-P08.md`: "C4: fuel map" for the
approach, "All automatics" for the boxes, and "Never later than today" for
half pedal.

### Decision

1. **The schedule (option C4).**
   - The pedal's demand is read as power: `P_dem = pedal^1.5 × peak power`.
   - A gear qualifies if its full-load power at its rpm covers `P_dem` with
     a reserve: 20% to move into it, 5% to stay in it. Its rpm must also be
     between 1.25 × idle and a ceiling.
   - Of the qualifying gears, the box takes the one the engine's own grid
     says burns least for the power being delivered (smoothed over 2 s). An
     upshift needs a 1% saving, a downshift for fuel alone 6%.
   - **Full pedal** (no gear qualifies) and **kickdown** use today's
     schedule unchanged.
2. **All automatic boxes:** Enjoy's Auto and Drive's `tc` and `dct`, which
   share `Gearbox`. The manual is untouched.
3. **Half pedal: never later than today.** From 30% pedal up, today's
   upshift line is the ceiling; below 15% the ceiling is 95% of rated rpm;
   in between it blends.

### Why

Measured on four vehicles: at a held cruise, today's gear burns 3–43%
more than the least-fuel gear below 110 km/h on the cars. Of the six
variants prototyped:
- the reserve-only rule (B) hunts;
- a symmetric 6% bar (C3) traps the cars a gear low;
- C4 put all 12 car cruises in the least-fuel gear with no hunting, and
  matched today exactly at full pedal.

The fuel map needs no tuning per engine, so custom engines (ADR-014) get it
too.

### Consequences

- The live fixtures' automatic drives are regenerated and the TS port
  re-matched (ADR-004). There is no grid rebuild: `live.py` is outside the
  grid hash.
- Cruise rpm drops to about 1,200–1,950 on the cars below 110 km/h, so the
  sound changes too.
- The truck at 90 km/h still shifts 5th ↔ 6th as today's box does. That is
  recorded, not fixed.

## ADR-018 — P10: a deeper sound (the balance between sources), and FINDING-028's zig-zag hidden in the synth

**Status:** Accepted (2026-10-14). The owner listened to the A/B/C files
(`tools/p10_ab.py`) on a phone speaker, at the cabin and intake mics, and
answered: "B sounds better, go with C for findings". Asked about loudness,
they chose "Match at cruise".

### Decision

1. **The balance (option B).** `acoustics.SOURCE_BALANCE` weighs the
   sources against each other at every mic:
   - exhaust ×8;
   - mechanical clicks (valve tick, injector, slap) ÷3;
   - combustion ×0.6;
   - turbo ×0.4;
   - and `HISS_WEIGHT` sets the intake hiss against its pulse at 0.18 (was
     0.45).

   Each source's own level law (FINDINGs 004, 017, 022) is unchanged.
2. **The loudness: matched at a cruise.** `acoustics.MIC_TRIM` trims each
   mic so that at half rated rpm and 30% load it is as loud as before. The
   trim is the median over the Enjoy roster (`tools/p10_trim.py`):
   exhaust tip 0.24, intake 1.73, engine bay 1.83, cabin 0.89, outside 0.79.
3. **FINDING-028, option C.**
   - Now: the sound averages the port flows over 2° (`smooth_port_flow`,
     in `render` and `LiveSynth.set_sources`) before differentiating them.
   - Later: the solver's chatter is fixed at the next rebuild. The cells
     keep the raw flow until then.
4. **No C (the phone bass peak).** The owner preferred B.

### Why

Measured (`reviews/PROPOSAL-P10.md`): at idle the exhaust was 0.1–0.2% of
the mix and the clicks 65–82%.
- At the cabin mic, crdi15's centroid goes 852 → 483 Hz at idle, 707 →
  426 Hz at 2000 rpm / 0.3, and 746 → 216 Hz at full pedal.
- The share of the sound below 250 Hz goes from 7–18% to 32–83%.
- Without the zig-zag's removal, the louder exhaust would have made idle
  whine at 2.4 kHz (the idle exhaust's centroid is 2,159 Hz with it, 208 Hz
  without).

### Consequences

- **Loudness:** idle is about 4 dB quieter than before (cabin), a cruise is
  the same, and full pedal at rated rpm is about 10 dB louder, as in a car.
  The exhaust-tip mic no longer saturates. At full pedal the engine bay is
  no louder than before.
- **single10's** exhaust outweighs everything on it: at a cruise its cabin
  is about 11 dB louder than before.
- **No grid rebuild.** `acoustics.py` is hashed, but no cell reads
  `render` or the mix, so the ten grids and the accuracy table were
  re-stamped (`tools/restamp_grids.py`). `livesound.py` is outside the
  hash.
- **Tests and fixtures.** The sound fixture is regenerated and the TS
  synth re-matched (ADR-004). The parity test now compares the mix in
  steady state, over bands within 50 dB of its strongest.
- **Superseded measurements.** It answers REVIEW-006's `hd_i6`
  tick-dominance question the same way (the clicks are ÷3). The owner's
  2026-09-30 sign-off by ear on the old balance is superseded by this one.
- **The owner's listen on the live site** (2026-10-14, after #128): full
  pedal "is little louder. But fine I guess", so the +10 dB stays; the
  exhaust tip, cabin and outside mics sounding alike when revved is not a
  problem ("Nope"). A full-pedal trim is the lever if that changes.

**Revisit if** the owner hears full pedal as too loud, or idle as too
quiet, on the phone; or once FINDING-028's solver fix lands (then drop the
smoothing, with a measurement showing it changes nothing).

## ADR-019 — P09: the port flow and the knock fixed, then the knock at altitude and on a cold start, heard in Enjoy

**Status:** Accepted (2026-10-15). The owner chose C ("Hear in enjoy
also"), for "modern CRDi at Leh and a cold start" (2026-10-14). In round 2
they chose "Staged (Recommended)" and "Add a cold-start model". After the
listening round (`tools/p09_listen.py`: k = 0, 3, 5, 8) they chose k = 4
(2026-10-15). Details: `reviews/PROPOSAL-P09.md`, FINDING-028 and
FINDING-029.

### Decision

1. **Stage 1, the numerics.** Each was checked against 0.5° and 0.25°
   solves.
   - **The port flow is semi-implicit wherever an explicit step would
     overshoot** (FINDING-028 option B, `cycle.implicit_flow`): at the
     valves, and at an NA engine's plenum and manifold orifices.
   - **The burn is integrated over each step** (`cycle.wiebe_step`).
   - **The knock comes from the burn law**, not from the 1° trace's central
     difference (`CycleResult.dpdtheta_knock`, FINDING-029). The sound
     reads it, and `acoustics.KNOCK_REF` becomes 7.5e9 (×1.5) so that the
     sea level's sound stays near P10's.
2. **Stage 2, the burn law.** The premixed burn has no φ term, and it is
   faster by (delay / injection)^0.5 once the delay outlasts the injection,
   with a floor of 2° (`PREMIX_DELAY_EXP`, `D_PRE_FLOOR`). The exponent is
   chosen, not calibrated.
3. **The cold-start model.** It is narrower than the round-2 question
   offered, and the chat said so at the time:
   - the grid's cold cells are a true cold start: every wall, and the
     coolant, at 273 K (`engine.cold_start_walls`);
   - the live loop has a chamber-wall temperature, `T_chamber`, which warms
     with a 60 s time constant and cools with a 600 s one, toward the warm
     walls' `WALL_FOLLOW` value; every warm/cold blend uses it.
   - **Cranking speed is not modelled.**
   - **Cold intake air is already in the model:** the charge picks up heat
     from manifold walls at the coolant's temperature, and the place's air
     temperature reaches the live loop through the weather table.
4. **Enjoy hears it.**
   - The weather table carries the knock (`dpdt_max` in
     `bridge.WEATHER_KEYS`).
   - The live loop sends the knock at `T_chamber` with the weather's
     change, and the warm standard air's knock at the same point.
   - The synth multiplies the combustion part by their ratio to the power
     **`KNOCK_GAIN_EXP` = 4**: a playback gain, chosen by ear, not physics.

### Why

- **Stage 1 (measured):**
  - crdi15's idle port-flow ripple fell 0.80 → 0.022, with its VE within
    0.09% of a 0.5° solve;
  - the NA single's error against a fine step fell from 10.3% to 0.21%
    (VE) and from 10.8% to 0.82% (torque);
  - the knock moves 0.9% over small shifts in injection timing (the
    trace's measure moved 15.9%);
  - the cost is about the same (29.0 s against 28.7 s);
  - the roster's full-load torque moves 0.27% or less.
- **Stage 2 (crdi15 at idle, the physics alone):** knock +17% at Leh, +17%
  on a cold start, +40% for both. At sea level the roster's full-load torque
  moves 0.53% or less and its BSFC 1.2% or less.
- **The gain:** without it +40% is under 1 dB in the P10 mix, which is not
  audible. At k = 4 (`tools/p09_listen.py`, idle):

  | engine, mic | a cold start | Leh | both |
  |---|---|---|---|
  | crdi15, cabin | +2.4 dB | +2.4 dB | +8.7 dB |
  | crdi15, intake | +3.6 dB | +3.2 dB | +9.9 dB |
  | hatch15, cabin | +3.8 dB | +3.2 dB | +9.3 dB |
  | hatch15, intake | +4.4 dB | +3.8 dB | +10.2 dB |

### Consequences

- `cycle.py`, `engine.py` and `acoustics.py` are hashed, so all ten grids
  were rebuilt with their weather tables, and the golden points were
  re-baselined (`tests/test_physics.py`'s `GOLDEN`).
- **single10's torque at 600 rpm, 40% load moves about 18%** to its correct
  value (FINDING-028).
- **A warm engine at sea level gets no gain** (its ratio is 1). Its knock
  still changes, with the new knock measure and burn law, offset by
  `KNOCK_REF` ×1.5. Whether it sounds like P10's was asked on 2026-10-14
  and is not yet answered.
- **A cold Enjoy start knocks for about a minute** before the chamber warms.
  A warm restart within a few minutes does not, because the chamber cools
  over 600 s.
- The traps are in CLAUDE.md: `T_chamber`, the true cold cells,
  `dpdtheta_knock`, and the `dpdt_max` weather key.
- **Left open:**
  - PMEP converges only to first order in the step;
  - the −20 °C cold-oil idle torque reads −1561 N·m, not yet investigated.

**Revisit if** the owner hears the knock as too much or too little on the
phone at a real place; or if a cranking-speed start is wanted (a new live
state, and cells at cranking rpm).

## ADR-020 — P13: a drivable grid built faster (N, then B + C)

**Status:** Accepted (2026-10-16). The owner: "Both, go ahead with N first"
(N, then B + C). The stopping rule wasn't named in the answer: R2, the
recommended one, was used and said so. **Revised the same day to R5**: R2's
rebuild showed it stopping on slow creeps (below). Details:
`reviews/PROPOSAL-P13.md`.

### Decision

1. **N: a native build in one command** (`buildgrid/build.sh`,
   `build.bat`, `tools/build_my_grid.py`; PR #132). The same file as the
   browser, imported with Import grid. The front end is unchanged.
2. **B: a converged solve stops once settled**, rule **R5**: work, boost,
   the intake's burned fraction, the turbo speed and the net IMEP each vary
   by under `EARLY_STOP_TOL` = 2e-4 over `TAIL_CYCLES`, for `EARLY_STOP_HOLD`
   = 10 cycles running (`cycle.EARLY_STOP_KEYS`). *(Was R2: the first four
   keys at `TAIL_TOL` = 1e-3.)* `CONVERGED_CYCLES` (200) becomes a
   ceiling. The cycle that may end the stop is run as the last one, because
   the traces and the knock are recorded only then; if the test fails after
   it, the next last cycle records them afresh (and the knock's running
   peak restarts). `DieselEngine.EARLY_STOP` turns it off.
3. **C: the reference integrals once** (`thermo._INT_CP_*_REF`),
   bit-identical.

### Why

- A drivable grid was ~73% weather table, and all of it the pure-Python
  crank loop: crdi15 58 min natively, ~1.4–1.8 h in a browser.
- ~~R2 against the 200-cycle answer, over 108 solves (three engines; warm,
  cold, 58 kPa / −20 °C): ×1.91; torque within 0.019% of full load; EGR
  within 0.04 points; T_exh 0.1 K; NOx 0.52%.~~ True on that sample, which had
  cold thin air only. **R2's rebuild** (6 h 38 min against 9 h 39 min) left
  the cells within 0.025% of peak torque, but **the weather tables up to 0.49%
  of peak** (truck127) and 0.38% (v8hd). Against 400 cycles the worst pieces
  (hot, thin air, high load) were 0.50% / 0.41% off, where 200 cycles is
  0.01% / 0.03%: R2 stopped on a slow creep, under 0.1% within any 10 cycles
  and ~0.8% over 100.
- **R5** was screened on 180 solves of 400 cycles (the 108 configurations,
  plus hot thin air at 58 and 72 kPa on the four heavy engines) and checked on
  108 held out (crdi15, crdi22, hatch15, hd_i6; 72 kPa / 45 °C, desert,
  plateau). In neither is any stop worse than the 200-cycle answer by more
  than its own error and 0.05% of peak; the largest excess is 0.017% (the
  case R2 missed by 0.50%). ×1.65 / ×1.71 fewer cycles. 200 cycles itself sits
  up to 1.34% from 400 in a limit cycle (FINDING-013), which every rule
  inherits.
- R1 (work and boost) stopped before the EGR loop had settled (NOx 9.9%).
  Stopping at the first pass flipped settled flags: one cell was 10.8% of
  full-load torque off.

### Consequences

- Every converged solve changes slightly (the Dyno's accuracy table, the
  converged golden points, every grid): one rebuild after P09's grids (R2's
  rebuild was discarded).
- Wall time gains less than cycles: R2's rebuild was ×1.46 for ×1.86 fewer
  cycles, because each grid's pool waits for its never-settling pieces.
- **R5's rebuild** (2026-10-16/19): cells 5,452 s against P09's 9,653 (×1.77),
  weather 20,410 s against 26,102 (×1.28), about **×1.34 overall** (7.2 h against
  9.7 h). Against the P09 grids, every cell of all ten: torque within 0.003% of
  peak, EGR 0.007 pts, T_exh 0.04 K, NOx 0.30%; 0 settled-flag flips; unsettled
  counts, slap pulses and Leh checks identical; weather tables within 0.042%
  of peak torque (R2: 0.49%). The Dyno's accuracy table: rows unchanged, only
  its hash.
- `n_cycles_used` varies on the converged path; the cells that never settle
  still run all 200.
- Slap events snap to the grid's sample where the side force changes sign:
  in 1 of 90 stopped cells one moved by a 1° step (discreteness, not
  convergence).
- Measured not worth it: chaining weather solves (×1.26, path dependence),
  rewriting the loop (ADR-001).


---

## ADR-021 — P06 tier 1: random roads in /enjoy (a route the live loop drives)

**Status:** Accepted (2026-10-19, built 2026-10-20). The owner's answers:
Enjoy only; tier 1 first, then goals; everything in PLAN; named and random
routes, the random ones shared by their seed. Details:
`reviews/PROPOSAL-P06.md`.

### Decision

1. **The route lives in the live loop** (`dieselsim/live.py`: `Route`,
   `random_route`, `ROUTES`, `route_from`; `LiveEngine.set_route` and
   `_road`), mirrored line for line in `web/physics/src/live/route.ts`. It
   is **not** in the solver: no grid goes stale. `live.py` is outside the
   grid hash.
2. **One generator, mulberry32, on both sides**, and arithmetic that IEEE
   makes bit-identical. Where libm differs (CPython's `**` against V8's,
   1,958 of 20,000 altitudes in the last bit), the code uses series (`_ln`,
   `_exp`). A route is computed from its key (`'city'`, `'random:1234'`),
   never sent as data.
3. **What the engine feels:**
   - the grade, through the driveline's existing input;
   - the surface, as rolling resistance × `SURFACES`;
   - the wind, as aero on the air speed;
   - a speed breaker, as a 0.15 s resistive pulse worth `BREAKER_LOSS`
     (6 %) of speed × j, where j rises from 0 at 15 km/h to 1 at 50 km/h,
     plus a hint;
   - the altitude, as ISA air relative to the start's place, which the
     grid's weather table turns into the cells' correction.

   The breaker's 6 % is a tuning constant, not a measurement.
4. **No suspension** (ADR-002's out-of-scope list stands). A breaker is a
   speed loss and a buzz.
5. **The share is the address:** `/enjoy?route=random:4242`. There is no
   server and no storage, so ADR-003 is untouched.
6. **The live fixture holds the port** (ADR-004). It has two route drives:
   the city on the plain grid, and random:1234 on the weather grid, which
   drives on the **converter box**, because there the dual clutch's sync
   threshold turns a 1e-9 nudge into a 12-frame event shift in Python
   alone.

### Why

- Only the live loop's code changes, so the cells, the grids and their
  stamps stay as they are.
- A seed is a few bytes, and both sides build the identical road from it.
  The fixture proves that frame by frame: worst 2.9e-14 per step.

### Consequences

- Changing a route constant (`SURFACES`, `BREAKER_*`, `ROUTES`, the
  generator's draws) changes the live fixture: regenerate it with
  `--only live` and re-match `route.ts`.
- Anything new that sets the air from a height uses `LiveEngine._isa`
  (series), not `**`.
- `set_route` copies the spec and its thermal block: the grid's spec is
  shared between drives (a mutant found a climb leaking into the next
  drive).
- Tier 2 (goals on a route) builds on `route_s`, `route_alt` and
  `breaker_hits`, which `LiveView` already carries.


---

## ADR-022 — P06 tier 2: goals on a route, against a par

**Status:** Accepted (the owner, 2026-10-20: every recommendation in
`reviews/PROPOSAL-P06-goals.md`). Built 2026-10-21 on `feat/p06-roads`.

### Decision

1. **Two goals, each one score with one limit:**
   - **time trial:** the fastest lap on at most the par's fuel;
   - **economy run:** the least fuel within the par's time.

   Personal bests are kept per browser (`dieselsim-goal-bests`), keyed by
   engine, route, goal, place and gearbox.
2. **The par** is a ghost lap of the same route at a steady 70 %
   (`live.PAR_THROTTLE`) with the automatic, from the start the driver gets:
   the same grid, place air and fuel (`make-engine.ts`, shared with the
   drive worker). It runs in a worker of its own (`par.worker.ts`), so the
   60 Hz loop never waits. `live.par_run` is the reference; the live
   fixture holds `parRun` to it with ~~three~~ two pars:
   - the city, with breakers, finishing;
   - ~~the pass, with hills, finishing;~~ *(dropped 2026-10-21: Python
     runs a par at about real time, so this one cost 243 s, and with a
     600 s Leh cap it pushed CI's fixtures job past its 15-minute limit on
     #138. The route drives check the hills frame by frame.)*
   - a cold start at Leh on the fixture grid that never finishes
     (FINDING-033), capped at 90 s *(was 600 s; it is at 60 rpm by 30 s)*.
3. **A breaker taken too fast adds 5 s** (`BREAKER_PENALTY_S`) to a lap's
   time, the par's included.
4. **Overheating is not a goal.** A stop on overheat, or running dry,
   fails any run. Measured: four of five roster engines can't overheat
   even on a 1,050 m climb at 42 °C.
5. **A par that never finishes sets no limit**, and the dash says so.
6. **The clock starts** at the first throttle above 5 %, or at the car's
   first metre; the lap ends at the route's length. The fuel burnt idling
   before the start isn't counted.

### One change from the proposal, and why

The proposal said named routes would ship precomputed pars. They don't:
**every par is computed in the browser**, at the driver's own place and
fuel. A shipped par would be right only at standard air, and at Leh it
would set the wrong fuel limit. Measured cost: 6.2 s for the city on this
Mac (Chrome). On a phone it is several times longer, and it runs while
the driver drives.

### Consequences

- Changing `PAR_THROTTLE`, `BREAKER_PENALTY_S` or the start rule changes
  the goals' meaning: regenerate the live fixture (`--only live`), and
  personal bests made under the old rule stay in browsers.
- A goal can be shared: `/enjoy?route=city&goal=time`.

---

## ADR-023 — P14: ten popular diesel engines join the roster

**Status:** Accepted (the owner, 2026-10-28: "Go with all your recommendations" in
`reviews/PROPOSAL-P14.md`; and, question by question, "Most popular onces / N2 / F2 / V2").
Batch 1 merged (#147, 2026-10-28); batch 2 being built.

### Decision

1. **The ten:** `vw19tdi` (VW 1.9 TDI), `mhawk75` (Mahindra mHawk75, the first three),
   `mhawk22` (Mahindra mHawk 2.2), `gd28` (Toyota 1GD-FTV), `duratorq32` (Ford 3.2, the
   first five), `b57` (BMW B57 3.0), `cummins59` (Cummins 5.9 12-valve), `cummins67`
   (Cummins 6.7), `duramax66` (Duramax 6.6 L5P), `powerstroke73` (Power Stroke 7.3).
2. **Names, N2:** a descriptive label in `/enjoy`'s list ("SUV · 2.8 L four, 204 ps"), with
   "modelled on the published figures of …" for the real engine beside it. The maker is
   named by reference, never as the product's name.
3. **Fidelity, F2:** the brochure numbers plus published hardware (bore × stroke, CR, VGT
   or wastegate, pump or common rail, pilot), each sourced and cited in
   `engines/ROSTER.md`. These are all `build_engine` parameters already.
4. **Vehicles, V2:** one new vehicle, a full-size pickup, for the four pickup engines. The
   other six reuse today's vehicles (`hatch15`, `ld_i4`, `crdi22`). This is a smaller step
   than ADR-012's one vehicle per engine.
5. **Delivery:** two PRs, not stacked. Batch 1 is the six on today's vehicles; batch 2, the
   pickup vehicle and its four, follows once batch 1 has merged.

### Why

13 of 14 candidates hold the roster test's bar with the roster's knobs, measured against
the five shipped engines as controls. Approximate real geometry moves them by 0.9 points at
most. No solver change is needed, so no grid goes stale. Details and the costs:
`reviews/PROPOSAL-P14.md`.

### Consequences

- **Twenty grids from now on:** a full rebuild after a solver change takes ~16 h on the
  owner's M2 (7.2 h today). Prefer `rebuild_cold_cells.py` / `restamp_grids.py` where a
  change allows it.
- **Every roster key needs its vehicle `case`** in `live.Vehicle` and `vehicle.ts`. An
  unknown key silently drives the 3 t tractor, so a test holds each key to the vehicle
  its JSON names (`"vehicle"`, which `from_dict` ignores).
- The 1.3 DDiS is not in: the builder's turbo gives it too little boost at 2,000 rpm. That
  is a hashed `builder.py` change, and its own decision.
- Naming makers by reference in a paid app wants legal advice before an app-store release.

---
