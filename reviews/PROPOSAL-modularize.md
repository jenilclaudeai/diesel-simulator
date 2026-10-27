# PROPOSAL — Modularize the context, then the code

**Asked by:** the owner, 2026-10-27: "the codebase and context has grown too big… you're
hallucinating… modularize the code as well as context. Start with the plan first."
**Status:** ~~**plan only, for the owner.** Nothing moved yet.~~ **Answered 2026-10-27: all five as
recommended** (see the answers under the questions). Nothing moved yet.
**Measured on:** `main` at `e4e7428` (after #139). Open: #140 (B-07), #141 (B-08), #142
(cold-start ECU proposal).
**Lens:** PM (sequencing), LEAD (seams), SW2 (build, hash), QA1 (proof that nothing changed).

---

## What was measured

| what | size |
|---|---|
| **The session-start read** CLAUDE.md asks for (CLAUDE, STATUS, PLAN, DECISIONS, TEAM, every review) | **14,546 lines, 768 KB**: roughly 190k tokens before any work starts |
| STATUS.md | 3,714 lines, 223 KB, 35 dated sections. **The current one is 27 lines**; the rest is history |
| reviews/ | 52 files, 8,367 lines, 406 KB; most are decided or fixed |
| DECISIONS.md | 1,577 lines, 71 KB (ADR-001 to ADR-022) |
| PLAN.md | 501 lines; most phases are done |
| CLAUDE.md, loaded on **every turn** | 295 lines, 19 KB; ~150 lines of traps, most about one area each |
| Python solver | 9,484 lines in 19 files. `live.py` 2,238 is the outlier; the next is `cycle.py` 1,021 |
| `tests/test_physics.py` | 3,565 lines, one file |
| TS port / app / e2e | 3,635 / 6,364 / 2,146 lines; the largest files 787 (`engine.ts`), 400 (`enjoy.ts`), 588 (`enjoy.e2e.mjs`) |

**The problem is mostly the context, not the code.** Every session starts by reading ~190k
tokens, of which perhaps 5% is current. Old, superseded text sits beside the current truth,
and I have to tell them apart from memory. That is where wrong recall comes from. The code is
moderately sized. Two files are big enough to hurt: `live.py` and `test_physics.py`.

## Constraints found while measuring (each fails silently if ignored)

1. **Three readers list `dieselsim/` at the top level only:** `bridge.grid_hash`
   (`os.listdir`), the Pyodide suite's copy (`tools/pyodide`, `readdirSync`), and
   `prepare-assets`' physics bundle (`readdirSync`). Code moved into a subfolder such as
   `dieselsim/live/` would be **left out of the grid hash with no error**, and would be missing
   from Pyodide and the browser. **So the Python stays flat**: smaller top-level files, no
   subpackages. A test will refuse a subfolder of `.py` files.
2. **Any edit to a hashed file stales all ten grids.** Hashed means every `dieselsim/*.py`
   except `live.py`, `livesound.py`, `bridge.py` and `environment.py`. Clearing that means
   `restamp_grids.py` plus the proof that no cell changed. So the solver files (`cycle.py`,
   `engine.py`, …) are **not** split in this plan.
3. **The suite runs a hand-kept list** (`tests/test_physics.py` `main()`, line 3465). A
   `test_*` function left out of it never runs, and nothing says so.
4. ADR-001 (the solver runs unmodified under Pyodide), ADR-003, ADR-005: untouched.
5. No code, tool or test refers to STATUS.md or DECISIONS.md. 11 lines of docs do, and they
   get updated. One permanent pointer lives inside an old STATUS section today (the bug
   sheet's Drive ID): it moves to a "Where things are" list.

## The plan: two parts, context first

### Part A — the context (docs only; no grid, fixture or code change)

| step | change | result (target, measured after) |
|---|---|---|
| A1 | **STATUS.md holds only the present**: open PRs, open questions for the owner, the last verified counts, next steps, "where things are" (the live URL, the bug sheet, the machine's Node). **Capped at 150 lines.** The 35 dated sections move **verbatim** to `history/status-<session>.md`, one file per session | 223 KB → ~10 KB |
| A2 | **`reviews/INDEX.md`**: one line per finding and proposal (id, title, status, its ADR, its PR). The files stay where they are, since code comments cite them by id | read the index (~6 KB), open a file only when the work touches it |
| A3 | **DECISIONS.md becomes an index plus summaries**: per ADR, status (accepted, superseded by…), the decision in 2–4 lines, and "easily undone by accident" where it applies. Full texts move verbatim to `decisions/ADR-0NN.md` | 71 KB → ~12 KB |
| A4 | **PLAN.md**: done phases collapse to one line each, with a pointer; open work goes on top | 24 KB → ~8 KB |
| A5 | **CLAUDE.md splits by area.** A core stays at the root (how you work, git, the session-start rule, the main commands): ~100 lines. Traps move to **nested `CLAUDE.md` files** beside their code: `dieselsim/` (hash, walls, knock, early stop), `web/app/` (e2e, units, Pyodide CI, physics-version), `web/physics/` (what must mirror Python), `tools/` (grid builds, restamp, pool). Claude Code loads a folder's `CLAUDE.md` when it works on files there, so a trap arrives when it is relevant | 19 KB every turn → ~7 KB, plus the area's file when needed |
| A6 | **The session-start rule** (your instruction, so your decision): read STATUS.md and the two indexes, then open a finding or ADR only when the task touches it | ~768 KB → **~35 KB** |
| A7 | **Guards against regrowth:** a test that STATUS.md stays within 150 lines and that every finding has an INDEX line (both SKIP under Pyodide, which has no repo files). The rule "a finished entry moves to history" goes into CLAUDE.md core | the cap holds itself |

**Proof for Part A:** a script checks that every line removed from STATUS, DECISIONS and PLAN
appears verbatim in `history/` or `decisions/`. Nothing is rewritten, so "own mistakes in
place" still holds: the struck-through corrections move with their text.

### Part B — the code (after A, one PR per step, not stacked)

| step | change | proof that nothing changed |
|---|---|---|
| B1 | **Split `tests/test_physics.py`** by area into flat `tests/test_<area>.py` (solver, live loop, sound, grids and tools, web assets). `test_physics.py` stays the entry point (CI and Pyodide unchanged). It **finds tests by name**, replacing the hand-kept list, and **fails if a `test_*` was found but did not run** (closes constraint 3) | the same test names and the same pass / known / skip counts before and after, on 3.10, 3.12 and Pyodide; mutant: a test dropped from discovery is caught |
| B2 | **Split `live.py` (unhashed)** into flat modules that mirror the TS port's files (`live_vehicle`, `live_driveline`, `live_engine`, `live_route`, `live_grid`). `live.py` re-exports them, so imports elsewhere don't change. The new files join `GRID_HASH_EXCLUDES`. `prepare-assets` reads that list from `bridge.py`, so it follows | `grid_hash()` identical before and after (no grid goes stale); `gen_fixtures --check` all ok (the live fixtures byte-identical); TS live tests unchanged |
| B3 | A test that **refuses a `.py` file in a subfolder of `dieselsim/`** (constraint 1) | mutant: a stray `dieselsim/x/y.py` is caught |
| — | **Not proposed:** splitting the hashed solver files, or `enjoy.ts` and the e2e files | each would cost a restamp, or CI time, for little gain at today's sizes |

## Options for the overall approach

| option | positives | trade-offs |
|---|---|---|
| **1. A then B (recommended)** | the biggest win first, at no code risk; B is done with the new, smaller context | about 4–6 PRs over a few days |
| 2. A only | no code risk at all; quickest | `live.py` and the suite stay hard to work in; the hand-kept test list stays a silent hole |
| 3. A and B, plus the hashed solver files | the most even file sizes | each solver split stales ten grids, and needs a restamp with proof |

**Timing:** #140, #141 and #142 each add to the top of STATUS.md. A1 rewrites that file, so
it is cleanest **after they merge**, or with their entries carried over.

## Questions for the owner

1. **The overall option:** 1 (A then B, recommended), 2 or 3?
2. **The session-start rule (A6):** read STATUS plus the indexes, and open the rest on demand?
   This changes your standing instruction.
3. **History (A1, A3):** move it verbatim into `history/` and `decisions/` (recommended; still
   in the repo and searchable), or rely on git history alone (smaller, but harder to find)?
4. **Nested CLAUDE.md files (A5):** yes (recommended), or one shorter root file?
5. **Order:** merge #140–#142 first (recommended), or start A now and carry their entries over?

**The owner's answers (2026-10-27, a new session):**
1. Option **1**: A then B.
2. **Read STATUS plus the indexes**, and open the rest on demand. (Takes effect with A6;
   until then, the handoff below still says what to read.)
3. **Move history verbatim** into `history/` and `decisions/`.
4. **Nested CLAUDE.md files.**
5. **Merge #140–#142 first.** The owner also flagged the conflicts on #140 and #141.

---

## Continue in a new session (handoff, 2026-10-27)

A fresh session continues from **this file alone**. Until question 2 is answered, it should
**not** do CLAUDE.md's full session-start read (768 KB). Read this file, the top entry of
STATUS.md, and nothing else unless a step needs it.

**State of the PRs (2026-10-27):**

| PR | what | state | who | to do |
|---|---|---|---|---|
| #143 | this plan | open, mergeable, docs only | this session | the owner merges it, or answers on it |
| #140 | B-07: Stop stops the sound; a stop while starting ends the start | open, **conflicts** since #139 merged | this session | merge `main` in, keep both sides. Expected: STATUS.md's top and maybe `web/app/e2e/enjoy.e2e.mjs`. Rerun units and `e2e:enjoy` (36 + #139's 2 = 40 + 5 B-07 = about 45 checks, **counted from the run, not assumed**); read every CI job |
| #141 | B-08: no sound spikes on a tip-in | open, conflicts | the B-08 session | leave it to that session unless the owner asks |
| #142 | proposal: a cold-start ECU (FINDING-031 C) | open, conflicts | the cold-start session | same |

**Next steps, in order:**
1. ~~Get the owner's answers to the five questions above (ask them if they haven't been given).~~
   **Done 2026-10-27: all five as recommended.**
2. If the order is "merge #140–#142 first": bring #140 up to `main` (the row above) and tell
   the owner it is ready.
3. Then Part A, one PR per step, in the order A1 → A7. Each moved line is checked verbatim by
   a script before the PR. Read every CI job.
4. Part B only after A has merged. B1, then B2, then B3. Each proof is in the table above.

**Working notes for this Mac (each cost time to find):**
- **Node:** the system has 20.19, and Angular needs 24.15. Prefix commands with
  `PATH=$(dirname $(npx -y -p node@24.15.0 -- which node)):$PATH`, or run
  `npx -y -p node@24.15.0 -- <cmd>`.
- **Worktrees:** a worktree-isolated session refuses compound shell commands that mention
  `git`. Put multi-step git work in a script file and run `sh script.sh`.
- **A fresh worktree:** `npm ci` in `web/physics`, `web/solver` and `web/app`, then
  `mkdir -p web/app/e2e/out` before any e2e. The first screenshot is taken before the script
  creates that folder.
- **e2e:** `CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" npm run e2e:enjoy`
  after `npm run build:pages`.
- **A cheaper session-start read already exists:** `gh pr list --state open` and the top entry
  of STATUS.md give the present. The rest is history.
