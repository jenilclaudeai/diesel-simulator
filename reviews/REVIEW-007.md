# REVIEW-007 — Phase 5 exit (Enjoy mode)

**Date:** 2026-10-05 (session 6)
**Scope:** PLAN.md Phase 5, on `main` after #72–#88
**Lenses run:** PM, LEAD, SR1, SW1, QA1, QA2, PHY2, USR1/2 (advisory)
**Reproduce:**
- `cd web/app && npm run build:pages && CHROME_PATH=… npm run e2e:enjoy`
- The owner's bug sheet and its tracker, `reviews/ANDROID-BUGS.csv`

---

## Summary

| Class | Count |
|---|---|
| BLOCK | 0 |
| MAJOR | 1 (M-1: the owner's re-check on the phone, which closes the exit) |
| MINOR | 6 |
| NOTE | 4 |

**Phase 5 is exit-ready except for one thing only the owner can do:**
re-check B-01 and B-02 on the Galaxy S9+, and confirm that the sound plays
and the drive is smooth. Every bug the Android check found is fixed on the
live site, and CI checks each fix.

---

## Exit criterion

PLAN.md: *loads and drives on a mid-range phone in landscape with audio,
without ever fetching Pyodide. Judged on a real mid-range Android phone in
Chrome (ADR-012).*

| part | state | evidence |
|---|---|---|
| without fetching Pyodide | **met, checked by CI** | e2e:enjoy, "no Pyodide or solver files are fetched": 16 requests, none from Pyodide or the solver (CI on #88) |
| loads and drives, landscape, on a real Android | **met, with the fixes** | The owner's check on 2026-10-05, Samsung Galaxy S9+ (a 2018 flagship, mid-range by today's standard), found 4 bugs (below). The two on the phone, B-01 and B-02, are fixed on the live site. |
| with audio | **not yet confirmed in words** | The owner's report lists no sound problem, but doesn't say it played. Headless Chrome: −33.3 dBFS at idle (e2e:enjoy, CI on #88). M-1 asks. |

## The Android check's bugs

From the owner's sheet; the full records are in `reviews/ANDROID-BUGS.csv`.

| bug | verdict | fix | proof |
|---|---|---|---|
| B-01: Restart after a stall does nothing | confirmed: a tap made while the clutch finger is down fired no click (0 click events), and the hint named keyboard keys | #88: Restart acts on press; touch wording (`enjoy/hints.ts`) | restarts with the clutch held, 564–594 rpm on the live site; e2e check plus mutant |
| B-02: text over text on a clutchless shift | confirmed at 846×300: the column ran 41 px into the strip | #88: the hint is an overlay toast; the dials' row can't shrink below its content; the strip scrolls | layout rules hold at 846×300 with 125% text, with the Mac font, Verdana and CI's Linux font; e2e plus 2 mutants |
| B-03: a console error | not reproduced: local dev server only, with a Chrome extension (`chext`) in the log | none | no errors on the dev server without extensions, or on Pages |
| B-04: a custom build at 0 for an hour; Stop dead | partly: Stop and a misleading ETA reproduced; stuck-at-0 not | #88: Stop at once, an ETA from timed pieces and workers | Stop 40–72 ms (CI, e2e); ETA 0.84–0.98× of the real time left from the 5th piece on |

---

## Findings

**M-1 (MAJOR): the owner's re-check closes the exit.** On the S9+, on the
live site: after a stall, hold the clutch and tap Restart (B-01); shift
without the clutch at the phone's real height (B-02); and confirm that the
sound plays without crackle and the drive is smooth. *QA1:* every other
part of the criterion is measured; this one is the owner's by ADR-012.

**m-1 (MINOR): the first ETA readings are optimistic, up to 1.6×,** until a
cell has been timed (a cell counts as a quarter of a row). It was measured
over one full build, and left untuned on a single run.

**m-2 (MINOR): B-04's "stuck at 0 for an hour" is not explained.** It
didn't reproduce here, where the first piece came at 156 s. Possible
causes: a dev-server live reload, a backgrounded or sleeping tab, a slow
browser. It needs the owner's circumstances if it comes back.

**m-3 (MINOR): custom-grid build times are long:** 21.5–27.5 min on a
laptop, and hours on a phone. Measured, with options, in
`PROPOSAL-grid-build.md`. **Deferred by the owner on 2026-10-05:** "First I
would like to go as per plan and complete this version … For now it should
be fine with grid build time."

**m-4 (MINOR), carried from REVIEW-005 m-5 and REVIEW-006 m-1: live
friction's and the synth's cost on a low-end phone.** The owner's check on
the S9+ reported no stutter. Close it if M-1 confirms the drive is smooth.

**m-5 (MINOR), known: the dev preset `single` sags on its converter in
Auto** (KNOWN in the suite). The roster's `single10` idles at 553 rpm and
isn't affected (e2e:enjoy, CI on #88).

**m-6 (MINOR): the stalled-state layout at very short heights.** It holds
at 300 px by rule, and the strip scrolls. Below 300 px (no current phone
in landscape with Chrome's toolbar) the dash relies on that scrolling.

**N-1 (NOTE), PHY2: the V8 fires evenly every 90°,** with no per-bank
"burble". Recorded in ROSTER.md; a model change for later.

**N-2 (NOTE): `truck127` has 13 unsettled cells and `v8hd` 8,**
period-averaged (FINDING-013). Nothing showed on the dials in the owner's
check.

**N-3 (NOTE), SW1: B-02's first fix leaned on the Mac's font, and CI's
Linux font caught it.** The lesson is now in the test: B-02's e2e asserts
layout rules at 125% text, not pixel margins.

**N-4 (NOTE), USR1/2 (advisory): keyboard words had leaked into a touch
UI** ("clutch down (z)"). Hints shown on `/enjoy` are now worded for touch.
`/drive`, with a keyboard, keeps the key names.

---

## Lens notes

- **PM:** the phase ends on M-1 alone. Phase 6 can be planned in the
  meantime; its proposal is `reviews/PROPOSAL-phase6.md`.
- **LEAD:** no ADR was contradicted. ADR-003 (no `SharedArrayBuffer`) is why
  Stop must terminate the workers rather than interrupt Python. That's
  recorded in the code and in B-04's tracker row.
- **SR1:** the worker pool now ends on Stop, and the pieces in flight are
  lost, by design: they're redone on resume. Finished pieces are kept.
- **QA2:** every new check was mutation-tested against a passing baseline
  (10 of 10 caught, all compiled), and every count here is read from
  finished runs (CI on #88).
