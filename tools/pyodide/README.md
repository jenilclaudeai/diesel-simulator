# Pyodide harness

Runs the **unmodified** `dieselsim` package and its full regression suite
under Pyodide in Node — the same Python runtime the browser app will use.
This is the executable form of ADR-001.

```bash
cd tools/pyodide
npm install
npm run suite
```

Exit code mirrors `tests/test_physics.py`, so CI can gate on it.

## What it proves

- The solver needs **numpy only**. The harness prints whether `scipy` was
  imported; it should always say `False`.
- The solver produces **the same numbers** under Pyodide as under native
  CPython — not "within tolerance", the same to about ten significant figures
  (see ADR-001, *Measured*).
- Anything that breaks under Pyodide breaks here first, not in a browser.

## Pinned version

`pyodide` is pinned to **314.0.7** (Python 3.14.2, numpy 2.4.6). Bump it
deliberately, and rerun this harness when you do.

## If the Pyodide CDN is unreachable

`loadPackage("numpy")` downloads the numpy wheel from `cdn.jsdelivr.net` at
runtime. Some sandboxes and corporate networks block that. Pyodide also
publishes its full distribution on GitHub, so the wheel can be fetched from
there instead and placed where `loadPackage` looks for it:

```bash
cd tools/pyodide
curl -sL https://github.com/pyodide/pyodide/releases/download/314.0.7/pyodide-314.0.7.tar.bz2 \
  | tar -xjf - --wildcards '*numpy-2.4.6-cp314*'
mv pyodide/numpy-2.4.6-*.whl node_modules/pyodide/
```

The archive is ~340 MB, but only the one wheel (~3 MB) is written to disk.
Verify it against `node_modules/pyodide/pyodide-lock.json` → `packages.numpy.sha256`
before trusting it.

## Timing is not representative in a fresh process

WebAssembly is compiled by a fast baseline tier first and optimised later.
The first solve in a new process runs roughly 3.4× slower than native; by the
third it is roughly 1.7×. Compare warm numbers, and remember that a browser's
engine (especially Safari's) may differ from Node's V8.
