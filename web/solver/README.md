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

## Test

```bash
npm install
npm test          # type-checks, then runs the real worker under Node worker_threads
```

16 end-to-end checks through `worker-client.ts` → `worker-main.ts` → Pyodide →
unmodified `dieselsim`. About a minute on a normal machine.

If the Pyodide CDN is unreachable, `loadPackage("numpy")` fails — see
`tools/pyodide/README.md` for fetching the wheel from GitHub instead.

## Layout

| file | runs on | role |
|---|---|---|
| `src/solver-port.ts` | anywhere | the interface and types the UI depends on |
| `src/protocol.ts` | anywhere | messages, and the `Endpoint` transport abstraction |
| `src/worker-client.ts` | main thread | `SolverPort` implementation over an `Endpoint` |
| `src/worker-main.ts` | worker | owns Pyodide, serves requests |
| `test/node-worker.ts` | Node worker | the only Node-specific code: adapts `worker_threads` |

A browser build needs a second small adapter like `test/node-worker.ts`:
wrap `self` as the `Endpoint`, load Pyodide from wherever it is hosted, fetch
the package sources, and **route Python's stdout/stderr to the console
explicitly**.
