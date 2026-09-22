# CI — staged, not yet active

`ci.yml` is a complete GitHub Actions workflow, parked here because GitHub
only runs workflows from `.github/workflows/`, and a personal access token
needs the **Workflows** permission to push there.

## To activate

Either:

- add **Workflows: Read and write** to the fine-grained token, and the file is
  moved into place with `git mv tools/ci/ci.yml .github/workflows/ci.yml`; or
- in the GitHub web UI, create `.github/workflows/ci.yml` and paste this file.

Nothing else is needed. Lockfiles are committed, so `npm ci` is reproducible.

## What it runs

| job | what | why separate |
|---|---|---|
| `physics` (3.10, 3.12) | byte-compile every file, then `tests/test_physics.py` | the reference implementation, on the oldest and current supported Python |
| `physics-pyodide` | the same suite under Pyodide (`tools/pyodide`) | ADR-001's guarantee: the browser runs the same physics |
| `solver` | `web/solver` — cache tests, then 18 checks through a real worker | the TypeScript seam, end to end |

Runs on every pull request — including stacked PRs that target another branch
rather than `main` — and on pushes to `main`.

## Verified before staging

- Action versions checked against their latest releases (all v7, Node 24),
  and every input used confirmed present in each v7 `action.yml`.
- `npm ci` from the committed lockfiles, in a clean copy, then the fast tests.
- **Python 3.10**: every file byte-compiles, and the full suite passes with the
  dependency versions `requirements.txt` actually resolves to there.

Not verifiable outside GitHub: the runners themselves. First real run is the
test of that.
