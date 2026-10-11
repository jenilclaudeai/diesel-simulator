# Drivable-grid benchmark

How long a standard drivable grid (8 × 6, warm and cold: 104 converged
pieces, what `tools/build_live_grids.py` builds) takes on a machine, for
comparing hardware.

1. Get the repository: `git clone https://github.com/jenilclaudeai/diesel-simulator.git`
   (or download it as a zip from GitHub and unpack it).
2. Run the script for the system. It needs Python 3.10 or newer, and
   installs numpy into its own `bench/.venv`, so nothing else on the
   machine changes:
   - macOS / Linux: `sh bench/run_bench.sh`
   - Windows: `bench\run_bench.bat`
3. Read the result. It is printed, and saved to
   `out/bench/<host>-<mode>-<date>.json` to compare machines.

| mode | what | time on a 6–8 core laptop |
|---|---|---|
| default (quick) | one wave of row limits and of cells on the machine's own workers, under full load, then the full build's schedule estimated from them | ~3–6 min |
| `--full` | builds the whole grid and times it: the exact number | ~15–25 min |

Options: `--workers N` (default: the native tool's pool, min(6, cores));
`--engine KEY` (default `crdi15`).

The browser figure is an estimate and a range. It scales the native
estimate by this project's two measured whole browser builds on one 8-core
Mac (21.5 and 27.5 min in Chrome against 14.8 min natively, 6 workers
each: ×1.45–1.86), on the app's pool (cores − 1, at most 6). The browser
itself is not run.
