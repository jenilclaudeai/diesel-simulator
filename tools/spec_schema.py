"""
The spec editor's schema (Phase 6, ADR-015): every EngineSpec leaf's dotted
path (what `overrides` takes), the dataclass it lives in, its type, and the
comment config.py gives it (usually its unit first). The editor's groups,
order and labels are curated in TypeScript on top of this; this file is
generated, so it can't drift from config.py.

    python3 tools/spec_schema.py           # write web/app/src/app/spec/spec-schema.json
    python3 tools/spec_schema.py --check   # exit 1 if it is out of date
"""
import ast
import json
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)
from dieselsim import config  # noqa: E402
from dieselsim.bridge import spec_leaves  # noqa: E402

OUT = os.path.join(REPO, "web", "app", "src", "app", "spec", "spec-schema.json")


def comments():
    """{(class name, field name): inline comment} from config.py's source."""
    path = os.path.join(REPO, "dieselsim", "config.py")
    with open(path) as fh:
        src = fh.read()
    lines = src.splitlines()
    out = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.ClassDef):
            for st in node.body:
                if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                    m = re.search(r"#\s*(.*?)\s*$", lines[st.lineno - 1])
                    out[(node.name, st.target.id)] = m.group(1) if m else ""
    return out


def schema():
    spec = config.get_preset("crdi15")   # the field tree is the same for every engine
    notes = comments()
    rows = []
    for path, value in spec_leaves(spec):
        obj, parts = spec, path.split(".")
        for p in parts[:-1]:
            obj = getattr(obj, p)
        cls = type(obj).__name__
        kind = ("bool" if isinstance(value, bool) else "int" if isinstance(value, int)
                else "number" if isinstance(value, float) else "list" if isinstance(value, list) else "string")
        rows.append({"path": path, "cls": cls, "type": kind, "note": notes.get((cls, parts[-1]), "")})
    return rows


def main(argv):
    text = json.dumps(schema(), indent=1) + "\n"
    if "--check" in argv:
        with open(OUT) as fh:
            current = fh.read()
        if current != text:
            print(f"{os.path.relpath(OUT, REPO)} is out of date: run python3 tools/spec_schema.py")
            return 1
        print(f"ok    spec schema current ({len(json.loads(text))} fields)")
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(OUT, REPO)}: {len(json.loads(text))} fields")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
