# feat/enjoy-pwa (Enjoy installable and offline, ADR-024)

**2026-11-01.** The owner asked to "plan deployment", chose "Installable/offline web" over
store apps, commercial hosting and only releasing the open PRs, then said "Just deploy the
enjoy mode". This branch is from `main` at `2aa1710`, not stacked. It merges cleanly with
#146, #148 and #149 in every order (`git merge-tree`, 9 of 9 combinations).

## Measured first (on `main`'s build, `2aa1710`)

- Pages: the last 7 deploys succeeded, 1–2 min each; `cache-control: max-age=600` on every
  file; no manifest, no service worker. `build:pages` locally gives `main-I7ULBUMY.js`,
  the bundle Pages serves.
- Enjoy loads the shell (main 491 KB raw / 120 KB gzipped, two worker chunks, the 24 KB
  worklet) and one grid per engine started (5.07 MB raw, 1.06 MB over the wire). It
  never loads Pyodide (16.5 MB) or the solver bundle (452 KB).

## Done

- `@angular/service-worker` 22.1.7 (core's exact version). The lockfile gains only its
  entry: npm 10 and npm 11 here both dropped 111 `libc` lines from `main`'s lockfile, so
  the entry was copied in by script, and every other line is `main`'s.
- `ngsw-config.json`: the shell prefetched (13 files, 696 KB raw); grids lazy (kept once
  started; re-fetched on a deploy only if changed); Pyodide and `physics/` never kept.
- `manifest.webmanifest` (opens /enjoy, landscape, full screen), four icons from
  `scripts/icon.svg` via `scripts/make-icons.mjs`. **`.gitignore` ignores `*.png`**
  repo-wide: an exception now ships `web/app/public/icons/*.png` (without it CI and Pages
  would have built with no icons, and the site would not install).
- The update bar (`app-update.ts`): Reload / Later when a new version is ready; checks on
  every return to view. Offline, a never-started engine says "This engine isn't on this
  device yet …" (`drive/offline.ts`). Measured: that fetch fails with `net::ERR_FAILED`,
  not the 504 first assumed (the e2e's first run said so; fixed in the check).
- CI: `e2e:offline` in the web e2e job. Pages: the build is refused without `ngsw.json`'s
  two groups, the manifest or the icons, or with Pyodide in the offline copy.
- ADR-024 in `decisions/` (pointer at DECISIONS.md's top; #146/#148 append ADR-023 at its
  end). PLAN Phase 8; CLAUDE.md: the command and the stale-version trap.

## Verified (local, this Mac, Node 24.15)

- App units **175 passed, 0 failed** (32 files; `main` 167 in 30): 8 new, run with
  `physics-version.ts` moved aside as CI does.
- `e2e:offline` **13 passed, 0 failed**: the server is shut down, not throttled; Enjoy
  reloads from the cache, the hatchback idles at 764 rpm with sound at −30.9 dBFS, and 0
  requests reach the server. Chrome reports the manifest error-free and the page
  installable.
- **Mutants, e2e: 7 of 7 caught**, baseline passing, every mutant built: no grids group;
  service worker off; the worklet not kept (caught by the wait for all 13 shell files, before
  the explicit `audio/` check); no manifest link (caught by a crash, `Invalid URL`, not a
  FAIL line); `start_url` the Dyno; the old "Failed to fetch" message; Pyodide kept.
- **Mutants, units: 5 of 5 caught** (baseline 175 of 175): the bar on VERSION_DETECTED; no
  check on return to view; no `isEnabled` guard; Later does nothing; a 504 not read as
  offline. *My first runner read the exit code of a pipe into `tail` (always 0) and
  printed four as SURVIVED with "1 failed" beside them, and its fifth mutant (`if (false)`)
  didn't compile. Rerun with the verdict read from the counts and a compiling mutant.*
- **Not run locally:** the other e2e checks (dyno, drive, sound, enjoy, cycle, spec, sweep,
  durability, grid, custom), which now all run under the service worker. CI runs them.

## Waiting on the owner

1. **Merge, then a phone check on the S9+** (Chrome): open the site once, start an engine,
   ⋮ → Install app (or Add to Home screen); then flight mode, open it from the home screen,
   drive. **After any later merge, tap Reload on the bar before judging a change.**
2. Two defaults to confirm or change (ADR-024): grids kept only once started (or a
   "Keep every engine offline" button, ~12 MB); installing opens /enjoy (or the Dyno).
3. Still open from STATUS.md: the earlier phone checks (B-07, B-08, P01, P06), FINDING-033,
   FINDING-027's A, and #146, #148, #149 waiting to merge.
