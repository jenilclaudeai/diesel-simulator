# FINDING-021 — play.py's real-time sound was a stale copy of the acoustics model, and ignored the physics its sources carry

**Opened by:** Phase 4, step 1: measuring `play.py`'s `LiveSound` before porting it to an AudioWorklet
**Lens:** PHY2 (lead), SR1, QA2, USR1
**Status:** fixed: `dieselsim/livesound.py` replaces it, and `play.py` now wraps that
**Reproduce:** `out/livesound_stale.py` (not committed; it needs the pre-fix `play.py`); the tests `test_livesound_carries_physics` and `test_livesound_matches_render`

---

## What was measured first

`LiveSound` is the streaming synth behind `play.py` and the obvious thing to
port. It had been copied from `acoustics.EngineSound.render` before FINDINGs
003, 004 and 017, and never updated. On the `crdi15` grid at 1,800 rpm / 0.6,
each of three physical inputs was doubled in the source set it plays:

| input ×2 | output RMS | max \|diff\| |
|---|---|---|
| piston-skirt clearance (slap) | **−0.0000%** | 6.0e-8 |
| exhaust mass flow | **+0.0000%** | 0 |
| valve seating speed | **+0.0000%** | 1.3e-7 |

Why each is dead:

- **Every source was normalised to unit RMS, the mix too**, and then the
  output was set to `0.22 · level`, where `level` is a function of load and
  speed only. So a level carried by a source's physics could not reach the
  output. The slap and seating scalings were applied upstream of a
  `/ np.std(...)`, which divides them out again.
- **The combustion sharpness was pinned against its clamp.**
  `sharp = min(3, dpdt_max / 6e6)`, with `dpdt_max` across the `crdi15` grid
  from 6.3e8 to 9.3e9 Pa/s, is 3.0 in every cell. The 6e6 is from before
  FINDING-003 changed the units of `dpdt_max`.
- **The exhaust mass flow was never read.** The turbo level was
  `max(0, boost − 1)`, normalised away again.
- The load changed the output by exactly what the `level` formula said:
  2.25× from load 0.2 to 0.9, whatever the engine.

This is CLAUDE.md's pattern again: built, wired, fed, and producing no effect,
with no error raised.

## Fix

A new streaming synth, `dieselsim/livesound.py`, is a **faithful streaming
form of `render()`**, the model the offline WAVs and the tests already hold
to physics:

- **Physical levels**, as in `render()` (FINDING-004):
  - exhaust ∝ (ṁ/ṁ_ref)^1.5;
  - combustion ∝ dp/dθ, with the sharpness at `dpdt / 5e9`;
  - tick ∝ (v_seat/0.1)²;
  - slap ∝ (clearance/30 µm)^0.6;
  - turbo ∝ (N/1.2e5)²;
  - rumble ∝ (P_b/P_ref)^0.5.
- **Shape normalisation made causal:** a one-pole mean-square tracker per
  source (0.3 s) in place of `render()`'s whole-signal std. That is the one
  approximation, and it is measured below.
- **Built for the port:**
  - 128-sample blocks (the AudioWorklet quantum);
  - numpy-only Butterworth design;
  - biquads in DF2T with a pure-Python path that the TypeScript port will
    match sample for sample (scipy is a fast path only);
  - a seeded mulberry32 noise table in place of numpy's generator.
- **Live overrides:** boost, turbo speed, load, P_b and skirt clearance from
  the real-time loop replace the grid cell's values, so a cold engine
  (ADR-011) will sound cold.

`play.py`'s `LiveSound` is now a thin wrapper, with the same interface, that
feeds sounddevice's 1024-frame callback from 128-sample blocks. Its streaming
DSP helpers (`Comb`, `Biquad`, `SosStream`, `butter_sos_filter`,
`resonator_coeffs`) had no other caller and are removed.

## Verification

Against `render()` on `hd_i6` at 1,400 rpm / 0.6 (`test_livesound_matches_render`):

| check | result | bar |
|---|---|---|
| Butterworth response vs scipy | 1.4e-12 | 1e-9 |
| pure path vs scipy path | 9.7e-14 | 1e-9 |
| every source's level vs render | worst 1.2% | 3% |
| mix, third-octave | worst 1.02 dB over 27 bands | 1.5 dB |
| each source's shape, bands within 30 dB of its peak | worst 1.23 dB (rumble, noise) | 1.5 dB |

Physics now moves it (`test_livesound_carries_physics`, each judged on the
source it feeds):
- exhaust mass flow ×2: exhaust **+182.8%**;
- seating speed ×2: mech **+298%**;
- skirt clearance ×2: mech **+23.9%**, with the tick turned down so the slap
  is audible in the sum.

Through `play.py`'s own `LiveSound` on `crdi15` at 1,800 rpm / 0.6, the
**whole output** moves:

| input ×2 | output RMS |
|---|---|
| seating speed | **+112.7%** |
| dp/dθ | **+57.8%** |
| exhaust mass flow | **+4.9%** |
| slap | **+0.7%** |

All four were exactly 0 before.

The exit criterion's firing peaks (`test_livesound_firing_peaks_and_sources`):
the I6 at 1,400 rpm shows 70, 140 and 210 Hz standing +31.7, +29.5 and
+25.6 dB over their neighbourhoods, and none of the seven sources is silent.

**Mutation test.** Ten mutants were each run against a passing baseline. Eight
were caught at first:
- the exhaust, slap, tick, combustion, turbo and rumble levels each removed;
- a biquad sign flipped in the pure path;
- the tracker's time constant ×10.

Two survived:
- **Stale sharpness (`dpdt / 6e6`) survived.** That was a real gap: the mix
  spectrum hid combustion's tilt. The per-source shape check above was added,
  and it catches the mutant (2.88 dB) and `sharp = 0` (6.96 dB).
- **Removing the rumble's "divide by the firing waveform's max" survived.**
  That mutant is **equivalent**: a constant scale ahead of a scale-invariant
  tracker (in `render()`, a std) changes nothing. The division is removed from
  the streaming synth, with a comment, and the output moved by at most 2.9e-12.

Suite with scipy: 59 passed, 0 failed, 2 known defects. Without scipy: 54
passed, 4 skipped. The audit is unchanged: 0 dead, 2 frozen, 0 tiny.

## What is left open

- **How it sounds is the owner's call.** The port is faithful by decision
  (Phase 4: "port faithfully, decide by ear"). On `hd_i6` the valve tick is
  13× the slap. That may be right for a diesel with mechanical lash, or a
  level to tune. A listening page and WAVs come with the worklet.
- Its sources are still from the grid cell. Live P_b and skirt film from the
  ADR-011 friction come in the next step, with the grids' acoustic sources.
- `Norm`'s block-step gain changes leave sidebands about 80 dB down in the
  exhaust's upper bands (render: none). They are inaudible. They are recorded
  here so nobody reads them as a filter bug.
