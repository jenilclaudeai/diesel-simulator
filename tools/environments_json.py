"""
The five places (dieselsim/environment.py) as a static file for Drive and
Enjoy (Phase 7 step 4), which must not fetch Pyodide (Phase 5's exit
criterion) and so can't ask the bridge. Generated, so it can't drift from
the Python; the solving pages keep reading the bridge's runtime_info.
Since Phase 7 step 6 it also writes the fuel grades (environment.FUELS)
for the fuel picker.

    python3 tools/environments_json.py           # write web/app/src/app/weather/environments.json, fuels.json
    python3 tools/environments_json.py --check   # exit 1 if either is out of date
"""
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)
from dieselsim.environment import describe_environments, describe_fuels  # noqa: E402

OUT = os.path.join(REPO, "web", "app", "src", "app", "weather", "environments.json")
FUELS_OUT = os.path.join(REPO, "web", "app", "src", "app", "weather", "fuels.json")


def content():
    return json.dumps(describe_environments(), indent=1) + "\n"


def fuels_content():
    return json.dumps(describe_fuels(), indent=1) + "\n"


FILES = ((OUT, content), (FUELS_OUT, fuels_content))


def main():
    if "--check" in sys.argv:
        bad = 0
        for path, make in FILES:
            try:
                with open(path) as fh:
                    ok = fh.read() == make()
            except FileNotFoundError:
                ok = False
            bad += not ok
            print(("ok    " if ok else "STALE ") + os.path.relpath(path, REPO)
                  + ("" if ok else ": run python3 tools/environments_json.py"))
        sys.exit(1 if bad else 0)
    for path, make in FILES:
        with open(path, "w") as fh:
            fh.write(make())
        print(f"wrote {os.path.relpath(path, REPO)}")


if __name__ == "__main__":
    main()
