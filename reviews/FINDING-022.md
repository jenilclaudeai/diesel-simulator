# FINDING-022 — the intake's loudness and the turbo's boost term are normalised away, in render() and so in the synth

**Opened by:** Phase 4, mutation-testing the TypeScript synth port. A mutant scaling the intake hiss's constant (4.0 → 4.1) moved nothing. Asking why found this.
**Lens:** PHY2 (lead), QA2, USR1
**Status:** open, recorded as a known defect in the suite (`test_intake_and_boost_levels_are_normalised_away`). Left for the owner's listening review (Phase 4 decision: "port faithfully, decide by ear").
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
