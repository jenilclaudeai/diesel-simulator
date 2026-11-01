# deploy/enjoy-only (a deployment branch: Enjoy alone, no custom engines)

**2026-11-02.** The owner asked: "Create a branch for deployment with just enjoy page and
without custom engine option". From `main` at `67c5ca6` (#151 merged; #150's offline app
included). **Not for merging into `main`**, and no PR: it would remove every other page.
Nothing is deployed: the owner picks where it goes live (below).

## Done

- **Routes:** Enjoy only. `/` and any old link (`/spec`, `/drive`, `/grid`, ...) redirect to
  `/enjoy`, keeping `?route=` and `?goal=`. The other pages' code stays in the tree (so
  `main` merges in cleanly) but has no route, so the build leaves it out.
- **No custom engine option on Enjoy:** removed the grid file import ("Your own engine"),
  "Your engines" (custom engines built in this browser, and `?engine=my:...`), and
  project files. *Assumption:* projects went too. They carry /spec's edits, which this
  build has no page for, and can name a custom engine. Restoring them is a small revert in
  `enjoy.ts`/`enjoy.html`. The "Diesel Sim" home link is now plain text.
- **`releaseFocus` copied into `enjoy.ts`:** importing it from `drive/drive.ts` pulled in
  /drive's custom-engine build. Main bundle, measured: **`main` at `67c5ca6` 500.24 kB raw
  (122.57 kB over the wire) → this branch 280.81 kB (78.38 kB)**; 298.20 kB with the routes
  cut but before the copy.
- **`npm run build:enjoy`** = `build:pages`, then `scripts/enjoy-only.mjs`. It removes
  `pyodide/` and `physics/` from `dist/` (Enjoy never boots Python). It also removes the
  solver's worker chunk: Angular emits a bundle for every `new Worker(new URL(...))` in
  the TS program, reachable or not, and this one is named by no shipped file (0 hits
  in `main-*.js`, the other workers and `index.html`). The chunk is dropped from
  `ngsw.json` too, which would otherwise prefetch it, or fail to install on its 404. The
  script refuses the build if a referenced chunk names Pyodide, or if `ngsw.json` lists a
  missing file. `dist` **123.86 → 106.91 MB** (the 20 grids are the rest); the service
  worker's app group 13 → 12 files.
- **`pages.yml` here:** `workflow_dispatch` only (a push never deploys), builds with
  `build:enjoy`, and checks `pyodide/` and `physics/` are absent.
- **e2e:** enjoy's custom-import section is replaced by two checks: no custom option (no
  file input, no "Your engines", the 15 roster keys, no links out), and `/?route=city`
  and `/spec` land on Enjoy. offline reads the app group's size from `ngsw.json`,
  not a fixed 13.

## Verified (local, this Mac, Node 24.15, Chrome)

- App units **178 passed, 0 failed** (33 files), run before `physics-version.ts` existed,
  as CI does.
- `build:enjoy` clean; `check:labels` passes.
- e2e **enjoy 59 passed, 0 failed** (incl. "no Pyodide or solver files are fetched", 49
  requests); **offline 13 passed, 0 failed** (the pruned build installs, and drives offline).
- **Mutants, each against a passing baseline:**
  - e2e, **2 of 2 caught**, each by its own assertion, in one build: a file input put back
    (`files: 1`), and the `**` route removed (`/spec` stayed on `/`);
  - prune script, **3 of 3 caught**, baseline passing before and after: `main` naming
    the orphan chunk ("is loaded by main-…"), `ngsw.json` not stripped ("lists files not
    in dist"), orphan removal off ("still names Pyodide").
- Not run: the other e2e suites (dyno, drive, sound, cycle, spec, sweep, durability, grid,
  custom). They test pages this branch removes. Sound is covered by enjoy's "one tap
  starts the engine and the sound". No CI: CI runs on PRs and `main` only.

## Waiting on the owner

1. **Where it goes live.** Pages has one site per repo, and `main`'s `pages.yml`
   redeploys the full app on every merge, replacing anything run from here. Options:
   - **A: a second repo's Pages** (e.g. `diesel-sim-enjoy`): push this branch there as
     its `main`; `build:pages`'s base href becomes `/<repo>/`. The full app stays where it
     is.
   - **B: this repo's Pages becomes Enjoy-only:** run
     `gh workflow run pages.yml --ref deploy/enjoy-only` and stop `main` deploying (or
     merge this into `main`). The github-pages environment may only allow `main` (repo
     settings → Environments). Installed apps keep working: `start_url` is `/enjoy`.
   - **C: another host** (Netlify, Cloudflare Pages): `npm run build:enjoy`, publish
     `web/app/dist/app/browser` with the base href changed to `/`.
2. **Projects:** removed as part of "custom engine option" (assumption above). Keep them
   out?

## Keeping it current

`git merge origin/main` into this branch picks up `main`'s fixes. Conflicts are likely only
where `main` changes Enjoy's import/project code or the e2e's custom-import section. After
a merge: units, `build:enjoy`, `e2e:enjoy`, `e2e:offline`.
