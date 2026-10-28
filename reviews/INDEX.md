# reviews/ — index

One line per file (step A2 of `reviews/PROPOSAL-modularize.md`, 2026-10-28). Read this, then
open a file only when the work touches it. The files stay where they are, because code
comments cite them by id.

**Status** is what is true on `main` at `a57a6fd`, with its source: a PR, an ADR, or the
PLAN or REVIEW line that records it. **line stale** marks a file whose own status line, near
its top, still says something older. The file's body or a later document has the truth.
Those lines are left as written. A finding's or proposal's status changes here first.

## Findings

| id | what | status | ADR | PR / commit |
|---|---|---|---|---|
| 001 | `premix_fraction` pinned at its floor | fixed (P-1, P-2) | | #5 |
| 002 | `dp/dθ` measures compression, not combustion | fixed; read `dpdtheta_comb` | | #5 |
| 003 | clatter's high-mode weight pinned at its ceiling | fixed (`b16c267`, on `main`). **line stale**: names only a branch | | `b16c267` |
| 004 | the sound engine discards every physical amplitude | fixed; signed off by ear in Phase 4, 2026-09-30 (REVIEW-006, PLAN Phase 4). **line stale**: "not yet listened to" | | #6 |
| 005 | lash growth zero, so the tick never ages | fixed: roller `Pb_vt` (#5); the cam film's part through FINDING-015 (PLAN Phase 1 outcome, bug #9 done). **line stale**: "still open" | | #5 |
| 006 | `h_min_ring` pinned at its floor | fixed; read `h_ring_mid` | | #5 |
| 007 | audit of bug #8, unknown-provenance code | closed: one bug fixed, two items cleared | | `64b47b0` |
| 008 | `CycleTraces.theta`: two crank-angle references | fixed with option D, `theta_global` (#30, 2026-09-25). Every plot names its axis (ADR-015). **line stale**: "diagnosed, not fixed" | 015 | #30 |
| 009 | bug #4 is ~29%, not 2× | stated, not recalibrated: every fuel figure labelled steady-state (`npm run check:labels`); recalibration needs part-load data | | |
| 010 | bug #2's instability does not reproduce | closed; the real gap (no p_max / T_exh limit) fixed (PLAN Phase 1 outcome) | | #44 |
| 011 | the real-time grid is the least accurate part | fixed: per-cell fresh engines at `n_cycles=9` | | #8 |
| 012 | `transient()` has no stall floor, crashes on NaN | fixed (`e4af517`); the first root cause recorded was wrong, corrected in the file | | `e4af517` |
| 013 | the limiter fitted with EGR on; `crdi15` never converges near 1650 rpm | items 1, 2 fixed; item 3 answered by prebuilt converged grids (#56) and the dyno's stated accuracy | 010 | #21, #40, #56 |
| 014 | `render_transient` seams | fixed (carry phase, keep length) | | #29 |
| 015 | cam film ~780× too thick | items 1, 2 fixed; wear rate calibrated to 2000 h / 150 µm | | #28, #35, #38 |
| 016 | the 001/002 guards rode a 1° ignition-delay step | fixed: ignition resolved within the crank step | | #27 |
| 017 | slap and tick lose their scaling; valves seat off the ramp | items 1, 2 fixed, seating at ramp speed; item 3 not applied; signed off by ear (Phase 4) | | #34, #37, #43 |
| 018 | valve lift steps 4× where ramps meet the flank | fixed with C′; signed off by ear in Phase 4 (PLAN Phase 4). **line stale**: "the owner should confirm C′" | | #42 |
| 019 | the aged `crdi15`'s torque gain is a fast-path artifact | closed; `durability_run`'s cycle count fixed | | #45 |
| 020 | the converter's lock-up clutch numerically unstable (bug #11) | fixed, Python and TS | | #54 |
| 021 | `play.py`'s sound a stale copy of acoustics | fixed: `livesound.py` | | #59 |
| 022 | intake loudness and boost term normalised away | fixed, option A (the owner, 2026-09-28) | | #61, #64 |
| 023 | the slap input on the skirt film's clamp, cold cells | fixed, option A | | #78 |
| 024 | MFB50 late by up to 7° | fixed; a reported figure only | | #91 |
| 025 | the spec's ambient reached no solve | fixed | 016 | #101 |
| 026 | off the rating's air the boost target passes the compressor limit | closed: A fixed (#110, landed by #111), C declined, D stated (#112) | 016 | #109-#112 |
| 027 | cold, thin air: the NA single's ignition all or nothing | **open, for the owner.** P09 shipped "with single10's 36% Leh check stated" (the owner, 2026-10-16), which looks like option A: confirm | | |
| 028 | port mass flows zig-zag at idle | fixed: hidden in the synth (option A, #128), then the solver fix (option B) in P09 (#131): idle ripple 0.80 → 0.022 (CLAUDE.md). **line stale**: "option B still open" | 018, 019 | #128, #131 |
| 029 | altitude lengthens the delay, but the knock falls | decided and built as P09 option C: the knock at altitude and on a cold start, heard in Enjoy. **line stale**: "open, for the owner" | 019 | #131 |
| 030 | P09's cold cells carry 6-140× a cold start's friction | fixed, option A (cold-cell friction at the running walls) | | #131 |
| 031 | light pedal from cold: creeps, at 0 °C does not move | A (stated) shipped with P09; C, a cold-start ECU: proposal answered 2026-10-28, build not started | | #131, #142 |
| 032 | the live loop's radiator, fan and drag breathe sea-level air | fixed, drag included | | #137 |
| 033 | an automatic dragged to its 60 rpm floor stays "running" | **open, for the owner**; latent (no shipped grid reaches it). Recommended A: stall it | | |

## Proposals

| file | what | status | ADR | PR |
|---|---|---|---|---|
| `PROPOSAL-phase5.md` | Phase 5 (Enjoy) plan and roster | decided and built; exit review REVIEW-007, one item left (the owner's phone re-check, M-1). **line stale**: "for the owner's decision" | 012 | |
| `PROPOSAL-phase6.md` | Phase 6 (Expert) plan | decided (option B) and built; exit review REVIEW-008. **line stale** | 015 | #89-#99 |
| `PROPOSAL-phase7.md` | Phase 7 (environment, projects) | decided (six recommendations) and built (PLAN Phase 7). **line stale** | 016 | |
| `PROPOSAL-weather-table.md` | Phase 7 step 4, the table's shape | decided A3 and built: every shipped grid carries a table. **line stale**: "being built" | 016 | |
| `PROPOSAL-grid-build.md` | custom-engine grids people will wait for | deferred until after v1 (the owner, 2026-10-05); option A, the ETA, shipped. P13 builds on it | | #88 |
| `PROPOSAL-P06.md` | P06 tier 1, random roads in /enjoy | decided and built. **line stale**: "tier 2 is next" (built since) | 021 | #138 |
| `PROPOSAL-P06-goals.md` | P06 tier 2, goals against a par | decided and built | 022 | #138 |
| `PROPOSAL-P08.md` | an automatic that shifts on demand | decided C4 and built | 017 | #122, #123 |
| `PROPOSAL-P09.md` | more knocking at high altitude | decided option C and built. **line stale**: "being built" | 019 | #131 |
| `PROPOSAL-P10.md` | a deeper, bassier sound | decided B; merged; the owner's listen accepted it (2026-10-14) | 018 | #128 |
| `PROPOSAL-P13.md` | a drivable grid built faster | decided ("both, N first") and built: N (#132), B + C (#133). **line stale**: "being revised" | 020 | #132, #133 |
| `PROPOSAL-cold-start-ECU.md` | a cold-start ECU in the live loop (FINDING-031 C) | answered 2026-10-28 (C1; no fast idle; extra fuel and glow plugs when cold, glow plugs measured first; keep P08); **build not started**. **line stale**: "questions for the owner" | | #142 |
| `PROPOSAL-P14.md` | at least ten popular diesel engines in the roster | decided 2026-10-28, every recommendation; batch 1 being built | 023 | #146 |
| `PROPOSAL-modularize.md` | modularize the context, then the code | answered 2026-10-27 (A then B); A0 done (#143), A1 #144, A2 this index | | #143 |

## Reviews

| file | what | status |
|---|---|---|
| `REVIEW-001.md` | ADR-001 to ADR-009 | done |
| `REVIEW-002.md` | ADR-006 (cold start via two grids) reassessed | done; ADR-006 since superseded by ADR-011 |
| `REVIEW-003.md` | Phase 1 exit (physics truth) | passed |
| `REVIEW-004.md` | Phase 2 exit (solver port, fixtures) | passed |
| `REVIEW-005.md` | Phase 3 exit (real-time loop in TS) | passed |
| `REVIEW-006.md` | Phase 4 exit (audio) | passed; signed off by ear 2026-09-30 |
| `REVIEW-007.md` | Phase 5 exit (Enjoy) | exit-ready; M-1, the owner's phone re-check, still open |
| `REVIEW-008.md` | Phase 6 exit (Expert) | passed |

## Sheets

| file | what |
|---|---|
| `ANDROID-BUGS.csv` | the bug sheet's Tracker tab reads it from `main` (B-01 to B-08). Update the CSV, never the sheet |
| `FEATURES.csv` | the Features tab's status columns; a header only as of 2026-10-28 |
