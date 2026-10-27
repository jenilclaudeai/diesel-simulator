# fix/b08-sound-spikes (#141, draft)

**2026-10-28:** A0 (see CLAUDE.md, landing with #143): this branch's STATUS.md entries moved
here verbatim, and STATUS.md is `main`'s byte for byte, so #141 cannot conflict on it again.
**Next:** the owner listens to B-08, takes it out of draft, and merges.

## Moved verbatim from STATUS.md (A0, 2026-10-28)

**Session 11, #141 (B-08) brought up to `main` (2026-10-27):** the owner flagged the
conflicts on #140 and #141 (#140's merge is its own entry, merged as #140). Merged `main`
(`e4e7428`) in, no rebase, no force-push. **Only STATUS.md conflicted**: both kept, main's
entries above B-08's. `test_physics.py`, `gen_fixtures.py` and the rest merged cleanly; the
checks below look for what a clean merge can still break (main changed `live.py` and the
live fixture, B-08 the sound and its fixture).
- **Verified (local):**
  - `gen_fixtures.py --check`: all 7 ok, worst diff 0 (live and sound included);
  - suite **98 passed, 0 failed, 3 known, 4 skipped** (main's 97 + B-08's 1), and with scipy
    (`.venv`, 3.12) **103 passed, 0 failed, 3 known**: the 4 skips pass, one of them as
    2 checks (diffed by name). B-08's check: worst 0.67 dB;
  - `web/physics` npm test: exit 0, 5 / 68 / 13 / 11 passed, 0 failed;
  - `audit_dead_signals.py` runs; no hashed file changed, so no grid goes stale.
- **Still the owner's:** B-08 is a draft waiting for the owner's ear (its entry below).
- ~~**Next:** read every CI job on #141.~~ **CI on #141 at `7e748b3`: 10 of 10, every job
  read.** Units 164 (29 files); physics **103/0/3** on 3.10 and 3.12 (#140's 102 + B-08's
  test), Pyodide 82/0/2 (21 skipped); TS ports 5/68/13/11; SolverPort 20/15/30; e2e enjoy
  40, dyno 15, drive 11, sound 6, cycle 11, spec 18, sweep 6, durability 5; grid 9, custom 7.
- **Then the owner merged #140 and updated this branch from `main` on GitHub (`1472b6b`).**
  That merge kept `main`'s STATUS.md whole and dropped this branch's two entries (this one
  and B-08's below); restored here verbatim from `7e748b3`. The code came through intact:
  `main`..`1472b6b` is exactly B-08's 11 files.
- **Next:** the owner listens (B-08 stays a draft until then), then merges. #142 still
  conflicts (the cold-start session's). Then the modularize plan's Part A, A1 first.

**Session 10, B-08 fixed and waiting for the owner's ear (2026-10-21), `fix/b08-sound-spikes`, draft PR #141**
(from `main` at `173a65f`; independent of B-07's #140, which another session did):
- **The bug sheet has two new rows (2026-10-21):**
  - **B-08**, /enjoy, Sound: "Sudden noise spikes"; open the throttle, close it, open it again; every time.
  - **B-07**, "Engine doesn't stop even when we stop the engine", sometimes. Not mine; fixed in #140.
- **B-08 verdict: Confirmed.** It has been there since Phase 4 (`1c11c72`); the tree before P09 measures the
  same, so it is not a P09 or P10 regression.
  - Cause: each source's shape tracker (`livesound.Norm`, a one-pole over 0.3 s) lagged a step in the
    source's level, while the level law applied the step again.
  - Measured with `tools/b08_tip_in.py` (new): the live loop at 60 Hz, blends every 17 quanta as in the
    worklet; the synth's output over a zero-lag reference, in 100 ms windows; six cases on crdi15, hatch15
    and the single.
  - `main`: tip-in **+3.2 to +9.0 dB**, lift-off **−3.9 to −10.4 dB**.
- **The fix** (`livesound.py`, unhashed, so no re-stamp; mirrored in `web/physics` dsp.ts and synth.ts):
  - each tracker is divided by the level the synth knows ahead of its filters (`LiveSynth._amps`, gliding
    with the waveforms; the hiss's scale; the knock bands' weights);
  - the crank-locked sources average over the last engine cycle (`CycleNorm`); the noises and tones keep
    the one-pole.
  - After: tip-in **+0.8 to +3.5 dB**, lift-off **−0.2 to −0.7 dB**. The rest is the combustion's first
    ~100 ms: its spectrum changes under load, and a causal tracker needs about a cycle. Removing it would need
    a spectrum per blend on the audio thread; not done.
  - Steady sound, 30 cases: output within 0.12 dB of `main`'s; mech +0.32 dB at the single's idle.
- **Tried and dropped, measured:**
  - feed-forward alone on the 0.3 s one-pole: tip-in still +1.3 to +7.1 dB;
  - each block's levels from the gliding waveforms: ±0.5 dB either way, ~25% more synth work;
  - the rumble's level the same way. *My hypothesis was wrong:* its −1.7 dB in the test was the noise's
    scatter, not the glide. The test now compares with a synth held at the new point, playing the same noise.
- **Verified (local):**
  - Python suite **95 passed, 0 failed, 3 known, 4 skipped** (`main`'s 94 + 1). The scipy-gated sound tests,
    run in a scratch venv, pass: render third-octave 1.22 dB (main 1.24).
  - `test_livesound_level_step_is_clean`: worst 0.67 dB (limit 1.0). **Mutants 7 of 7 caught**; `main`'s
    livesound gives 14.75 dB.
  - TS **5 + 56 + 13 + 11, 0 failed**. The sound fixture gains a 300→200 rpm segment (the window cap, the
    ring's wrap) and the trackers' constants. **TS mutants 7 of 7 caught.**
  - fixtures current; audit 0 DEAD, 2 FROZEN (known); `e2e:sound` 6 passed (on `build:pages` under Node
    24.15 via `npx -p node@24.15.0`).
  - `perf` at 6×, main thread: synth mean 0.54 ms (main 0.47–0.52), p99 1.8–1.9 of 2.90 ms; worker equal.
  - `tools/p10_ab.py`'s hiss wrapper now passes the level on; it was not run.
- **CI on #141 (`544f10c`, run 39630080216): 10 of 10 passed, every job read.** Physics 3.10 41.4 min and
  3.12 33.6; Pyodide 43.3 min, **80 passed, 0 failed, 2 known, 20 skipped**, the B-08 test among the passes;
  golden fixtures + TS ports; SolverPort; web app; the three e2e jobs; claude-review.
- **Waiting on the owner:** listen to `out/b08/` in the main checkout. Three A (`main`) / B (fix) pairs at
  true level: crdi15 exterior driving, hatch15 cabin driving, the single revving in neutral; pedal off at
  3–6, 9–10 and 13–15 s. Then merge or say what is still wrong. The phone check on the live site comes after.
- **When #140 (B-07) meets this:** `reviews/ANDROID-BUGS.csv` and this file conflict. Keep both, CSV rows in
  ID order.
