"""
Prove that text moved out of a context file (STATUS.md, DECISIONS.md, PLAN.md)
was moved verbatim -- the proof Part A of reviews/PROPOSAL-modularize.md asks for.

A file that receives moved text marks each copied range with a line

    <!-- verbatim: STATUS.md@a57a6fd 378-1494 -->

followed by exactly those lines of STATUS.md as it was at commit a57a6fd.
Anything before a file's first marker is its own header and is not checked.
For every source@ref named by a marker this asserts:

1. each range's lines equal the old file's, byte for byte;
2. no two ranges overlap;
3. every old line outside the ranges is still in the source file today
   (counted with multiplicity), so nothing was dropped on the way.

Usage, from the repo root:
    python3 tools/check_verbatim_move.py history/ [decisions/ ...]

Exit status 1 on any failure. Written for step A1 (2026-10-28).
"""
import collections
import os
import re
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MARKER = re.compile(r"^<!-- verbatim: (\S+)@([0-9a-f]{7,40}) (\d+)-(\d+) -->$")


def old_lines(path, ref):
    text = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=REPO, check=True,
                          capture_output=True, text=True).stdout
    return text.split("\n")


def md_files(paths):
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.endswith(".md"):
                    yield os.path.join(p, name)
        else:
            yield p


def parse(fname):
    """[(source, ref, start, end, lines, marker line no.)] for one file."""
    with open(fname, encoding="utf-8") as f:
        lines = f.read().split("\n")
    ranges, i = [], 0
    while i < len(lines) and not MARKER.match(lines[i]):
        i += 1
    while i < len(lines):
        m = MARKER.match(lines[i])
        if not m:
            raise SystemExit(f"{fname}:{i + 1}: text after a range that is not in it")
        src, ref, a, b = m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
        if b < a:
            raise SystemExit(f"{fname}:{i + 1}: empty range {a}-{b}")
        body = lines[i + 1:i + 1 + (b - a + 1)]
        ranges.append((src, ref, a, b, body, i + 1))
        i += 1 + (b - a + 1)
        # one optional trailing empty string from the file's final newline
        if i == len(lines) - 1 and lines[i] == "":
            break
    return ranges


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    groups = collections.defaultdict(list)
    for fname in md_files(argv):
        for src, ref, a, b, body, at in parse(fname):
            groups[(src, ref)].append((a, b, body, fname, at))
    if not groups:
        print("no verbatim markers found")
        return 1
    bad = 0
    for (src, ref), ranges in sorted(groups.items()):
        old = old_lines(src, ref)
        n = len(old) - (1 if old and old[-1] == "" else 0)
        owner = [None] * (n + 1)
        differ = overlap = 0
        for a, b, body, fname, at in sorted(ranges):
            if b > n:
                print(f"FAIL {fname}:{at}: {src}@{ref} has {n} lines, range ends at {b}")
                bad += 1
                continue
            want = old[a - 1:b]
            if body != want:
                k = next((j for j, (x, y) in enumerate(zip(body, want)) if x != y),
                         min(len(body), len(want)))
                print(f"FAIL {fname}:{at}: {src}@{ref} {a}-{b} differs at old line {a + k}")
                differ += 1
            for ln in range(a, b + 1):
                if owner[ln] is not None:
                    overlap += 1
                owner[ln] = fname
        if overlap:
            print(f"FAIL {src}@{ref}: {overlap} lines are in more than one range")
        with open(os.path.join(REPO, src), encoding="utf-8") as f:
            now = collections.Counter(f.read().split("\n"))
        missing = []
        for ln in range(1, n + 1):
            if owner[ln] is None:
                if now[old[ln - 1]] > 0:
                    now[old[ln - 1]] -= 1
                else:
                    missing.append(ln)
        moved = sum(o is not None for o in owner[1:])
        print(f"{src}@{ref}: {n} lines; {moved} moved in {len(ranges)} ranges "
              f"({differ} differ, {overlap} overlap); {n - moved - len(missing)} still in "
              f"{src}; {len(missing)} missing")
        if missing:
            print(f"FAIL missing old lines: {missing[:20]}{' ...' if len(missing) > 20 else ''}")
        bad += differ + (overlap > 0) + (len(missing) > 0)
    print("OK" if not bad else f"FAILED ({bad})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
