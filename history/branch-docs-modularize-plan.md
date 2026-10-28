# docs/modularize-plan (#143)

**2026-10-27:** the plan, `reviews/PROPOSAL-modularize.md`. The owner answered all five
questions as recommended (recorded in the plan and in `STATUS.md`).

**2026-10-28:** #143 conflicted with `main` after #140 merged (STATUS.md only). Merged `main`
in, both entries kept. **Added step A0**: a PR branch never edits `STATUS.md` again; it
writes `status/<branch>.md` (this file is the first). CLAUDE.md says so.
- #143 itself follows A0: its STATUS.md entry moved here verbatim (below), and STATUS.md is
  `main`'s byte for byte, so #143 can no longer conflict on it. #141 got the same move.
- ~~**Next:** the owner merges #143. Then #141 (B-08) after the owner listens. #142 (the
  cold-start session's) still conflicts; its next edit should move its STATUS entry into
  `status/docs-cold-start-ecu.md`. Then A1.~~
  **Done the same day:** #142 (idle 6 days, worktree clean) brought up to `main` and its
  entry moved to `status/docs-cold-start-ecu.md`. **Proof:** none of #141, #142, #143
  edits STATUS.md; all six merge orders of the three onto `main` are clean (a scratch
  branch, merged in each order); GitHub reports all three MERGEABLE.
- **Next:** the owner merges #143 (any order with #141, #142). #141 waits for the owner's
  ear, #142 for the owner's answers. Then A1.

## Moved verbatim from STATUS.md (A0, 2026-10-28)

**Session 10, a plan to modularize the context and the code (2026-10-27),
`docs/modularize-plan`** (docs only): the owner asked for a plan first.
`reviews/PROPOSAL-modularize.md`.
- **Measured:** the session-start read is 14,546 lines / 768 KB (about 190k tokens). The
  current part of STATUS.md is 27 of its 3,714 lines.
- **Found:** three readers list `dieselsim/` at the top level only (`grid_hash`, the Pyodide
  copy, `prepare-assets`), so a subfolder would silently leave the grid hash. And the suite
  runs a hand-kept list of tests.
- ~~**Five questions for the owner.**~~ **Answered 2026-10-27: all five as recommended** (A then
  B; STATUS plus indexes at session start; history moved verbatim; nested CLAUDE.md files;
  merge #140–#142 first). Nothing moved yet. #140, #141 and #142 are open, and all
  three conflict with `main` since #139 merged.
- **Handoff:** the plan's last section ("Continue in a new session") holds the PR table, the
  next steps and this Mac's working notes. A new session starts from that file alone.
