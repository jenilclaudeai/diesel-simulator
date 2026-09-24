# FINDING-014 — `render_transient` seams: every chunk restarts at crank angle 0, and each cross-fade deletes 20 ms

**Opened by:** known bug #10, "`render_transient` cross-fade seams are audible
where the source operating point switches" — unmeasured until now (FINDING-012
unblocked it)
**Lens:** QA2 (lead), PHY2
**Status:** measured, not fixed — fix options below, for decision
**Reproduce:** `python3 tools/diag_render_seams.py` (needs scipy)

---

## Two mechanisms, both independent of the operating point

`EngineSound.render_transient()` renders a transient in chunks of `blend`
seconds, each an independent `render()` call, and joins them with a 20 ms
equal-power cross-fade.

1. **Crank phase resets at every chunk.** `render()` integrates crank angle
   from zero on every call (`theta = np.cumsum(6 * rpm / fs) % 720`), so each
   chunk starts at 0° whatever angle the previous chunk ended at. (Noise and
   filter state restart too.) A 20 ms cross-fade cannot hide a phase jump in a
   signal whose firing period is ~21 ms at 1400 rpm on an I4.
2. **Each cross-fade overlaps 20 ms and removes it from the output.** The join
   is `out[:-xf] + fade + c[xf:]`, so every boundary shortens the result by
   `xf`, and every later chunk sits 20 ms × (boundary index) earlier than the
   rpm trajectory it was rendered for.

FINDING-012 described mechanism 1 from reading the code and said explicitly it
was not a measurement. Mechanism 2 is new.

## Measurement — the same operating point in every chunk

`crdi15`, 1400 rpm, load 0.6, `blend = 0.25` s, a 2.0 s log whose every entry is
the same point, noise seed fixed. Because the point never changes, anything
found is caused by the chunking.

**Duration**

| | length |
|---|---|
| log | 2.000 s |
| single `render()` | 2.000 s |
| `render_transient()` | **1.860 s** — 140 ms short over 7 boundaries |

**Firing regularity** — firing events are envelope peaks; nominal interval
21.43 ms. The control is the single uninterrupted render, judged at the *same*
boundary times, to show the metric measures seams rather than where it looks.

| | firings | away from seams: median / max deviation | across seams: median / max deviation |
|---|---|---|---|
| single render (control) | 94 | 0.2% / 7.1% | 0.1% / 2.1% |
| `render_transient` | 89 | 0.1% / 6.0% | **13.4% / 29.0%** (14 intervals) |

Firing intervals that span a chunk boundary are off by a median 13.4% and up to
29% — in the control, at the same instants, 0.1% and 2.1%. Five firings are
missing, consistent with 140 ms at 21.4 ms per firing.

So bug #10 is real, and it is **not** "where the source operating point
switches": the seams exist with no switch at all. A switch adds a change of
character on top.

## Why it matters

- Every transient render (`demo.py`'s tip-in WAV, anything built on
  `DieselEngine.transient()`) carries a rhythmic glitch every `blend` seconds
  and runs ~7% short at `blend = 0.25`.
- **ADR-003's TypeScript AudioWorklet must not copy the pattern.** It is meant
  to swap crank-angle source arrays when the operating point changes; the
  crank phase and filter state must carry across the swap. A port that
  re-creates a renderer per operating point would reproduce this exactly — and
  a fixture comparing band energies (ADR-004's audio tolerance) would not catch
  it, because seams barely move band energy. The measurement here (firing
  intervals across boundaries) is the kind of check that would.

## Fix options (not applied)

| option | positives | trade-offs |
|---|---|---|
| A. Carry crank phase (and noise / filter state) into each chunk: `render(..., theta0=...)` returning its end state | removes mechanism 1 at the source; small change; also what the AudioWorklet should do | touches `render()`'s signature; filter-state carry needs care in the biquad chain |
| B. Render each chunk `xf` longer so the cross-fade overlaps extra audio instead of deleting it | fixes duration and time alignment (mechanism 2) in a few lines | does nothing for the phase jump |
| C. One continuous render with sources interpolated between operating points along the log | no chunks, no seams at all; closest to the worklet design | bigger change; interpolating crank-angle sources between points needs a defined rule |

Recommended: **A + B** now (both small, each removes one measured mechanism);
C when the TS worklet is built, since that is its natural shape anyway.

## Caveats

One preset, one speed, one `blend`. Mechanism 2 is exact by construction
(20 ms per boundary). The firing-interval metric depends on envelope peak
picking; the control at the same instants shows it discriminates (2.1% max
there against 29% across seams).
