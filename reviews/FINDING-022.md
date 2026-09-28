# FINDING-022 — the intake's loudness and the turbo's boost term are normalised away, in render() and so in the synth

**Opened by:** Phase 4, mutation-testing the TypeScript synth port. A mutant scaling the intake hiss's constant (4.0 → 4.1) moved nothing. Asking why found this.
**Lens:** PHY2 (lead), QA2, USR1
**Status:** **fixed with option A** (the owner's decision, 2026-09-28), in `acoustics.render`, `dieselsim/livesound.py` and the TypeScript synth; see "Fix" at the end. The known defect became an assertion, `test_intake_and_boost_levels_carry_physics`. *(Was: "open, recorded as a known defect in the suite (`test_intake_and_boost_levels_are_normalised_away`). Left for the owner's listening review (Phase 4 decision: "port faithfully, decide by ear").")*
**Reproduce:** the test; `out/f22.py` (not committed)

---

## What was measured

hd_i6 at 1,400 rpm / 0.6. One physical input doubled at a time, and the RMS of the part it feeds compared:

| input ×2 | part | `acoustics.render` | streaming synth |
|---|---|---|---|
| **exhaust mass flow** | **intake** | **+0.0000%** | **+0.0000%** |
| **boost** | **turbo** | **+0.0000%** | **+0.0000%** |
| exhaust mass flow | exhaust | +182.84% | +182.8% |
| turbo speed | turbo | +300.0% | — |
| peak dp/dθ | combustion | +100.0% | — |
| boundary friction power | rumble | +41.4% | — |
| load | gear | +58.0% | — |

Every other part carries its physical level: FINDING-004's
(ṁ/ṁ_ref)^1.5, dp/dθ, (N/1.2e5)², √P_b, and the load. Two do not.

## Why

`acoustics.py:429–433`:

```python
# filter / throttle hiss: turbulent broadband ~ mdot^3
hiss = _bandpass(noise, 700.0, 6500.0, fs, order=2)
hiss *= (meta["mdot_air"] * spd ** 1.5) ** 1.5 * 4.0
y = y / (np.std(y) + 1e-12) + 0.45 * hiss / (np.std(hiss) + 1e-12)
```

The flow scaling is applied, and the next line divides it out again: at a
steady operating point `spd` is constant, so the whole factor cancels.
Nothing after that line gives the intake a level.

The turbo is the same (`acoustics.py:506–507`): `amp = (boost − 1)·spd²`
multiplies the whine, and `y / np.std(y)` cancels it. Only
`(turbo_rpm / 1.2e5)²` survives. Turbo speed and boost rise together, so
the turbo is not silent or frozen, but boost itself is dead.

It is CLAUDE.md's pattern again: a mechanism built, wired and fed, whose
effect is removed one line later, with no error raised.
`tools/audit_dead_signals.py` looks at scalar outputs, so it cannot see
this. The mutation test found it.

The streaming synth reproduces both faithfully, because it was built to
match `render()`. In the synth, `spd` varies within a block, so the factor
reshapes a transient a little, but in steady state it cancels just the same.

## Options (for the owner, after listening)

| option | what changes | trade-offs | positives |
|---|---|---|---|
| **A. Give the intake the exhaust's law**: multiply the part by (ṁ/ṁ_ref)^1.5 after normalisation; move the boost term after the turbo's normalisation | `render()` and `livesound`, the same edit in both | changes the balance of every mic, so the listening review has to be redone; editing `acoustics.py` changes `grid_hash()`, so all five grids need a rebuild (~70 min) even though no cell's content changes | intake roar with load, and turbo whoosh with boost, both physical; the known defect flips to an unexpected pass, which proves it |
| B. Hiss only: move just the (ṁ·spd^1.5)^1.5 factor after the hiss's normalisation | the same two files | the intake's tonal part stays level-less | the smallest change to the balance |
| C. Leave it | nothing | the intake sounds the same at idle and at full load | no retuning; the owner may prefer it by ear |

Recommendation: **A**, decided together with the Phase 4 listening review,
because both change how every mic balances, and the rebuild should happen
once.

## A side finding, recorded where it was seen

Two constants in `livesound` sit directly ahead of a shape tracker, so a
mutant changing either one is equivalent:
- the rumble's "divide by the firing waveform's maximum", now removed
  (FINDING-021);
- the hiss's `* 4.0`, which stays until option A or B decides the hiss's
  level.

---

## Fix (option A), 2026-09-28

The owner chose **option A**, for this finding alone; FINDING-023 goes in a
later rebuild. The same edit went into all three implementations, in the
same operation order:

- **intake:** the part is multiplied by (ṁ/ṁ_ref)^1.5 *after* its
  normalisation, the exhaust's law (FINDING-004);
- **turbo:** the boost term `max(boost − 1, 0)·spd²` is applied after the
  normalisation and referenced to rated (`pr − 1 = 1.2` at `spd = 1`), so
  that it is 1.0 where the other references are.

The hiss's own `(ṁ·spd^1.5)^1.5 · 4.0` is left in place, and its comment now
says what is true: the next line normalises it, so it survives only as
shape. Its original intent, a hiss that grows faster than the tone, is not
part of option A. It is noted here for the listening review.

**Measured after the fix** (hd_i6, 1,400 rpm / 0.6):
- mass flow ×2 moves the intake **+182.8%**, exactly the exhaust's figure;
- boost ×2 moves the turbo **+190.5%**;
- both were 0.0000%.
- The stream still matches `render()`: sources within 1.2%, third-octaves
  within 1.04 dB.
- PLAN's exit peaks still hold: +30.2/+28.6/+25.5 dB in Python and
  +35.9/+27.9/+25.4 dB in TypeScript.
- TypeScript against Python: 2.79e-13 of peak.

**What it does to the balance** (old against new synth, 1.6 s streams):

| operating point | intake part | turbo part | exterior 7 m total | intake-mic total |
|---|---|---|---|---|
| crdi15 idle (ṁ/ṁ_ref 0.07, boost 1.03) | −33.9 dB | −32.0 dB | −2.8 dB | −18.8 dB |
| crdi15 part (0.54, 2.69) | −8.0 | +3.0 | +0.6 | +0.8 |
| crdi15 rated full (1.15, 2.99) | +1.9 | +4.4 | +0.9 | +3.0 |
| hd_i6 idle (0.12, 1.01) | −27.7 | −39.0 | −0.5 | −10.9 |
| hd_i6 part (0.31, 1.37) | −15.2 | −10.2 | −0.0 | −3.2 |
| hd_i6 rated full (1.08, 2.78) | +1.0 | +3.4 | +0.0 | +0.4 |

At idle the intake and turbo nearly vanish: (0.07)^1.5 is −35 dB, the same
law the exhaust already follows. Above the 2.2 reference boost, the turbo
is ~4 dB louder than before. These are the places to listen.

**Mutation.** 6 of 6 caught:
- Python: the intake level removed; the boost term removed; the boost
  reference set to 1.0; the intake exponent set to 1.0. The last two are
  caught by the comparison against `render()`.
- TypeScript: the intake level dropped; the boost term dropped.

Editing `acoustics.py` changed `grid_hash()`, so all five grids were
rebuilt. No cell's content depends on `render()`, and the rebuild confirms
it value for value (see the PR).

