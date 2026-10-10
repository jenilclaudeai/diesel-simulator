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

**Quick or full?** Validated on an Apple M2 laptop (8 cores, 6 workers):
- `--full` measured 22.1 min. The benchmark's schedule, fed that run's own
  piece times, gave 23.4 min (+6%), so the schedule is sound.
- The quick mode said 16.8 min (−24%). Over 22 minutes of full load every
  piece ran slower (a row 270 s against 182, a cell 57 s against 40), and
  a 5-minute run doesn't reach that.

So the quick figure fits a machine that holds its speed: desktops, or
laptops with good cooling. To compare thin or quiet laptops, which slow
under sustained load, use `--full`.

The browser figure is an estimate and a range. It scales the native
estimate by this project's two measured whole browser builds on one 8-core
Mac (21.5 and 27.5 min in Chrome against 14.8 min natively, 6 workers
each: ×1.45–1.86), on the app's pool (cores − 1, at most 6). The browser
itself is not run.

**Compare like with like.** The software changes the figure as well as the
hardware. On the same M2, the quick mode said 16.8 min under Python 3.12
with numpy 2.1, and 13.0 min under Python 3.13 with numpy 2.5.3, the run
`run_bench.sh` set up. Background load between the two runs wasn't
controlled, so the split between causes isn't known. Each result records
its Python and numpy versions. To compare hardware, install the same
Python version on each machine. The scripts take the newest 3.10+ they
find.
