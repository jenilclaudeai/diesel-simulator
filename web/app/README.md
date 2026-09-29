# Diesel Sim — the browser app

Angular (standalone components, signals, OnPush; ADR-005). Three pages:

- **Dyno pull** (`/`) and **Operating grid** (`/grid`): the Python solver
  (`dieselsim/`, unmodified) runs in your browser under Pyodide, in a worker.
- **Drive** (`/drive`): the real-time engine and drivetrain in TypeScript
  (`web/physics`), on prebuilt converged grids (`public/grids/`), with engine
  sound from an AudioWorklet. No Python in the browser.

## Requirements

- **Node.js ≥ 22.22.3** (Angular 22). If npm 10 fails resolving Angular's peer
  dependencies, use `npx -y npm@11 install`.
- Google Chrome, only for the end-to-end checks.

## Run it

```bash
npm ci
npm start                 # http://localhost:4200
```

`npm start` first runs `scripts/prepare-assets.mjs`. It copies the Pyodide
runtime from `node_modules`, bundles `dieselsim/*.py` and the sound worklet,
and **downloads the numpy wheel for Pyodide once** (checked against its
sha256).

**If that download fails** (a proxy or an offline network), the script says
why and carries on without numpy. The Drive page works; Dyno and Grid say
numpy is missing. To fix it, use one of these:

```bash
# behind a proxy: Node's fetch ignores HTTPS_PROXY unless told to (Node 22.21+)
export HTTPS_PROXY=http://<host>:<port>      # `npm config get https-proxy` shows npm's
export NODE_USE_ENV_PROXY=1

# or: download the file named in the warning elsewhere, then
PYODIDE_WHEEL_DIR=/folder/with/the/wheel npm start

# or: a mirror of the Pyodide CDN
PYODIDE_CDN=https://<mirror>/pyodide npm start
```

## Build

```bash
npm run build:pages       # for GitHub Pages: base href /diesel-simulator/
```

**Never deploy plain `npm run build` / `ng build`**: its base href is `/`, and
on GitHub Pages the page comes up blank. Builds are strict: without the numpy
wheel they stop rather than ship a broken solver.

## Test

```bash
npm test -- --watch=false          # unit tests (vitest)
npm run check:assets               # prepare-assets on a network without the Pyodide CDN
npm run build:pages                # the e2e checks serve dist/, so build first
CHROME_PATH="/path/to/chrome" npm run e2e         # dyno pull vs native Python
CHROME_PATH="/path/to/chrome" npm run e2e:grid    # full 8 x 6 grid vs native (~9 min)
CHROME_PATH="/path/to/chrome" npm run e2e:drive   # /drive: 60 s script frame-exact vs Python
CHROME_PATH="/path/to/chrome" npm run e2e:sound   # /drive with sound: worklet output, pitch, mics
```

On macOS: `CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"`.
The drive and dyno checks call `python3` for their native reference, so run
them with the repository's Python environment active.

## Notes

- Over plain http on a LAN address (not `localhost`), the grid cache turns
  itself off by design: WebCrypto needs a secure context.
- The prebuilt grids are keyed on the solver's hash. After a solver change,
  rebuild them with `python3 tools/build_live_grids.py` (~1 h); until then
  the Drive page labels them as built by an older physics build.
