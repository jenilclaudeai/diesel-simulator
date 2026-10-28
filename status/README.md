# status/

One file per open PR branch, `status/<branch>.md` (slashes as dashes), written only by that
branch (A0, CLAUDE.md). A PR branch never edits `STATUS.md`, so two open PRs never conflict
on status. Once a PR merges, its file moves unchanged into `history/` (`git mv`, named
`branch-<branch>.md`), and what is still true goes into `STATUS.md`.
