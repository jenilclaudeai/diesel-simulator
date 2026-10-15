#!/bin/sh
# Build a custom engine's drivable grid on this computer (P13), for macOS and
# Linux: sets up its own Python environment (numpy, certifi) and runs
# tools/build_my_grid.py. Then load the file in the app: /drive or /enjoy ->
# Import grid.
#
#   sh buildgrid/build.sh my-engine.json              # the full grid (~1 h on a laptop)
#   sh buildgrid/build.sh my-engine.json --no-weather # cells only (~1/4 of the time)
#   sh buildgrid/build.sh my-engine.json --workers 10
#
# my-engine.json is what the app exports: Dyno -> Custom -> Export.
# Run it from anywhere inside a clone of the repository.
set -e
ENGINE="$1"
if [ -z "$ENGINE" ]; then
  echo "usage: sh buildgrid/build.sh my-engine.json [--no-weather] [--workers N] [--out PATH]" >&2
  echo "(export the engine from the app first: Dyno -> Custom -> Export)" >&2
  exit 1
fi
shift
# the engine path as given, before changing directory
case "$ENGINE" in
  /*) ;;
  *) ENGINE="$(pwd)/$ENGINE" ;;
esac
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
VENV=buildgrid/.venv
if [ ! -x "$VENV/bin/python" ]; then
  echo "creating $VENV ..."
  "$PY" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet "numpy>=1.24" certifi

"$VENV/bin/python" tools/build_my_grid.py "$ENGINE" "$@"
