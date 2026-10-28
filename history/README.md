# history/

Old status, moved here **verbatim** so that `STATUS.md` holds only the present (step A1 of
`reviews/PROPOSAL-modularize.md`, 2026-10-28). Nothing here is current. Read a file when a
task needs to know what happened, not at the start of a session.

A finding, proposal or code comment that cites "STATUS.md" or "STATUS, session N" means
the file as it was then; that text is now in the session's file below.

## STATUS.md's sections, as of `a57a6fd`

Each file is a short header plus one range of STATUS.md's lines, copied byte for byte.
`python3 tools/check_verbatim_move.py history/` proves it: every line of the old file is
in exactly one range, or still in `STATUS.md`.

| file | what | STATUS.md lines |
|---|---|---|
| `status-session-11.md` | session 11 (2026-10-27): #140 brought up to `main` | 3-23 |
| `status-session-10.md` | session 10 (2026-10-19 to 10-22): P06, P01 driving, B-07, FINDING-032, units | 24-377 |
| `status-session-09.md` | session 9 (2026-10-11 to 10-19): P08, P09, P10, P13, accessibility, units | 378-1494 |
| `status-session-08.md` | session 8 (2026-10-07 to 10-11): Phase 7 | 1495-1855 |
| `status-start-here.md` | "Start here", the standing summary of sessions 6 to 8 | 1856-2005 |
| `status-session-07.md` | session 7 (2026-10-06): FINDING-025 | 2006-2292 |
| `status-session-06.md` | session 6 (2026-10-05/06): Phase 6, the Android bugs, the bug sheet | 2293-2516 |
| `status-session-05.md` | session 5 (2026-09-26 to 10-05): Phases 1 to 5 | 2517-3276 |
| `status-session-04.md` | session 4 (2026-09-25/26) | 3277-3458 |
| `status-standing-to-session-6.md` | the standing sections kept up to session 6: Phase 2's state, findings, bugs, tests, branches, next actions | 3459-3772 |

## Merged branches' status files (A0)

A PR branch writes `status/<branch>.md`. Once it merges, the file moves here unchanged
(`git mv`), named `branch-<branch>.md`.

| file | PR |
|---|---|
| `branch-docs-cold-start-ecu.md` | #142, the cold-start ECU proposal (session 11, 2026-10-22 to 10-28) |
| `branch-docs-modularize-plan.md` | #143, the modularize plan and A0 (2026-10-27/28) |
| `branch-fix-b08-sound-spikes.md` | #141, B-08 (sessions 10 and 11, 2026-10-21 to 10-28) |
