#!/bin/sh
# Drivable-grid benchmark for macOS and Linux: sets up its own Python
# environment (numpy only) and runs tools/bench_grid.py.
#
#   sh bench/run_bench.sh            # quick estimate (~3-6 min)
#   sh bench/run_bench.sh --full     # build a whole grid and time it (~15-25 min)
#   sh bench/run_bench.sh --workers 4
#
# Run it from anywhere inside a clone of the repository. Results are printed
# and saved to out/bench/<host>-<mode>-<date>.json.
set -e
cd "$(dirname "$0")/.."

# a Python 3.10 or newer
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10 or newer is needed: install it from https://www.python.org/downloads/ (or your package manager), then run this again." >&2
  exit 1
fi
echo "using $($PY --version) ($(command -v $PY))"

# its own environment, so nothing on the machine is changed
VENV=bench/.venv
if [ ! -x "$VENV/bin/python" ]; then
  echo "creating $VENV ..."
  "$PY" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet "numpy>=1.24"

"$VENV/bin/python" tools/bench_grid.py "$@"
