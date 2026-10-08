"""
The five places (dieselsim/environment.py) as a static file for Drive and
Enjoy (Phase 7 step 4), which must not fetch Pyodide (Phase 5's exit
criterion) and so can't ask the bridge. Generated, so it can't drift from
the Python; the solving pages keep reading the bridge's runtime_info.

    python3 tools/environments_json.py           # write web/app/src/app/weather/environments.json
    python3 tools/environments_json.py --check   # exit 1 if it is out of date
"""
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)
from dieselsim.environment import describe_environments  # noqa: E402

OUT = os.path.join(REPO, "web", "app", "src", "app", "weather", "environments.json")


def content():
    return json.dumps(describe_environments(), indent=1) + "\n"


def main():
    text = content()
    if "--check" in sys.argv:
        with open(OUT) as fh:
            ok = fh.read() == text
        print(("ok    " if ok else "STALE ") + f"{os.path.relpath(OUT, REPO)}"
              + ("" if ok else ": run python3 tools/environments_json.py"))
        sys.exit(0 if ok else 1)
    with open(OUT, "w") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(OUT, REPO)}: {len(describe_environments())} places")


if __name__ == "__main__":
    main()
