# FINDING-012 — `transient()` has no stall floor and crashes on NaN

**Found while:** trying to measure known bug #10 (`render_transient`
cross-fade seams), which needs a transient log as input
**Lens:** QA1, SR1
**Status:** diagnosed, not fixed
**Severity:** a crash on an ordinary input, with a misleading error

---

## Reproduction

`crdi15`, `idle_rpm` 800, lugged with a load it cannot pull:

```python
eng = DieselEngine(preset="crdi15")
eng.transient(0.38,
              lambda t: 0.2,            # light throttle
              lambda t, rpm: 60.0,      # 60 N.m load
              dt=0.02, n_cycles=3)
```

The engine decelerates as it should — 756, 732, 708, 682, 655, 626, 594, 559,
523, 483, 440, 393, 342, 284, 217 rpm — and then keeps going:

| duration | result |
|---|---|
| 0.30 s | runs, ends at 217 rpm |
| 0.34 s | runs, **last rpm = `nan`** |
| 0.38 s | **`ValueError: cannot convert float NaN to integer`** |

The failure is at `engine.py:168`, `key = int(round(rpm / 25.0))` inside
`fuel_for_torque` — three frames away from the actual problem and saying
nothing about what went wrong.

## Root cause

The flywheel integration has **no floor at zero speed**. When load torque
exceeds what the engine can produce, rpm integrates straight through zero into
negative, then thermodynamic terms go non-finite, and the NaN propagates until
something tries to use it as an index.

This is a physically ordinary scenario: lug a diesel below its stall speed and
it stops. The model has no concept of stopping.

`play.py` does — `LiveEngine` carries a `stalled` flag and an
`engine_stopped` state. **`DieselEngine.transient()` does not**, so the library
API crashes where the application layer copes.

## Why it matters beyond the crash

- It is reachable from a plausible call. Nothing in the signature warns that
  some `load_torque_fn` values are unsurvivable.
- The 0.34 s case is worse than the crash: it **returns successfully with
  `nan` in the log**. A caller that does not check would carry NaN forward
  into a plot, a WAV, or a stored result.
- `demo.py` stage `s5` and any Phase 2 transient endpoint sit on this path.

## Also found: `load_torque_fn` takes two arguments

`PROJECT_CONTEXT.md` §2.2 documents:

```
eng.transient(duration, throttle_fn, load_torque_fn, dt=0.02, ...)
```

The actual call is `load_torque_fn(t, rpm)` (`engine.py:672`). A one-argument
lambda — the obvious reading of the docs — fails with
`TypeError: <lambda>() takes 1 positional argument but 2 were given`.
Documentation fix, not a code fix.

## Known bug #10 remains unmeasured

The seam measurement needs a clean transient log, and building one ran into
the above. What can be said from reading `render_transient`:

Each chunk is produced by an independent `self.render(op, ...)` call, so **both
filter state and crank phase reset at every chunk boundary**. The 20 ms
equal-power cross-fade cannot conceal a phase discontinuity in a periodic
signal — at 1400 rpm an I4 fires every ~21 ms, so the fade is about one firing
period long. That is consistent with the reported seams, but it is a reading of
the code, **not a measurement**, and should not be treated as one.

## Suggested fixes

1. **Floor the flywheel integration at zero** and set a `stalled` flag, as
   `LiveEngine` already does. Return the log with the stall recorded rather
   than crashing or emitting NaN.
2. **Guard `fuel_for_torque`** against non-finite rpm with a clear error, so
   the failure names itself even if something upstream slips.
3. **Fix the `load_torque_fn` signature in the docs.**

(1) is the real fix. (2) is cheap insurance of the kind FINDING-001 through
006 kept showing was missing.

## Caveat

One preset, one load profile. The stall threshold was not mapped, and whether
other entry points (`durability_run`, `warmup`) share the missing floor is
untested.
