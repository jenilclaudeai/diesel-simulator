# @dieselsim/solver

The one seam between the UI and the physics — see ADR-001 and ADR-010.

```ts
const solver: SolverPort = new WorkerSolver(endpoint);
await solver.ready();
const pt = await solver.solvePoint({ engine: { preset: "crdi15" }, rpm: 1800, load: 0.6 });
const grid = await solver.buildGrid(
  { engine: { preset: "crdi15", overrides: { "turbo.turbine_area_eff": 5e-4 } },
    rpms: [800, 1800, 2800], loads: [0, 0.5, 1] },
  { onProgress: p => console.log(`${p.done}/${p.total}`), signal: abortController.signal });
```

No Angular dependency. The Angular app will wrap this in a service.

## Caching grids

```ts
const solver = new CachedSolver(new WorkerSolver(endpoint),
                                new IndexedDbGridCache(), PHYSICS_VERSION);
```

`PHYSICS_VERSION` is `sourceHash()` of the bundled `dieselsim/*.py`, computed
at build time. A cache **hit never boots Pyodide** — that is why the version is
supplied rather than asked of the worker. On a miss it is checked against what
the worker actually loaded, and a mismatch (a stale bundle) fails loudly rather
than caching old physics under a new key.

Keys: SHA-256 of canonical JSON (sorted keys, spec-defined number formatting),
so `{a, b}` and `{b, a}`, or `5e-4` and `0.0005`, give the same key. Storage:
50 MB budget by default (~30 grids at 1.66 MB), least-recently-used eviction,
and a failure to *store* never fails the *build*.

## Test

```bash
npm install
npm run test:fast   # 20 cache tests, seconds, no Pyodide
npm test            # + 18 end-to-end checks through the real worker, ~1.5 min
```

If the Pyodide CDN is unreachable, `loadPackage("numpy")` fails — see
`tools/pyodide/README.md` for fetching the wheel from GitHub instead.

## Layout

| file | runs on | role |
|---|---|---|
| `src/solver-port.ts` | anywhere | the interface and types the UI depends on |
| `src/protocol.ts` | anywhere | messages, and the `Endpoint` transport abstraction |
| `src/worker-client.ts` | main thread | `SolverPort` implementation over an `Endpoint` |
| `src/worker-main.ts` | worker | owns Pyodide, serves requests |
| `src/cache-key.ts` | anywhere | canonical keys; `sourceHash()`, matching Python's |
| `src/grid-cache.ts` | main thread | memory and IndexedDB storage, budget, LRU |
| `src/cached-solver.ts` | main thread | `SolverPort` decorator: cache in front of any solver |
| `test/node-worker.ts` | Node worker | the only Node-specific code: adapts `worker_threads` |

A browser build needs a second small adapter like `test/node-worker.ts`:
wrap `self` as the `Endpoint`, load Pyodide from wherever it is hosted, fetch
the package sources, and **route Python's stdout/stderr to the console
explicitly**.
