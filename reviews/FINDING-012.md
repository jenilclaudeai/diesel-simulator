# FINDING-012 — `transient()` has no stall floor and crashes on NaN

**Found while:** trying to measure known bug #10 (`render_transient`
cross-fade seams), which needs a transient log as input
**Lens:** QA1, SR1
**Status:** fixed — **root cause as first recorded was wrong**, corrected below
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


---

## Correction — the root cause above is wrong

The section "Root cause" states the flywheel integration has **no floor at
zero speed** and that rpm "integrates straight through zero into negative".
That is incorrect. Reading `transient()` rather than inferring from a traceback:

```python
om = max(om, 2.0 * math.pi * 150.0 / 60.0)
```

**There is a floor, at 150 rpm.** rpm never goes negative. The earlier
measurement recording `min=150.0` was the floor showing itself, and I
misread it.

### What actually happens

Solving `crdi15` at 20% of the fuel limit, stepping down:

| rpm | torque |
|---|---|
| 500 | −6.27 |
| 400 | −14.48 |
| 300 | −26.72 |
| 250 | −35.64 |
| **200** | **NaN** |
| **150** | **NaN** |

The solver is valid down to about 250 rpm — negative torque, friction exceeding
indicated work, which is correct for a dying engine — and returns NaN from
about 200 rpm down.

So the real defect is two things together:

1. **The floor is set inside the solver's failure region.** 150 rpm is below
   where the solver stops working.
2. **The floor cannot catch NaN.** `max(nan, x)` returns `nan` in Python, so
   once the solver emits NaN torque, `om` becomes NaN and passes straight
   through the clamp meant to bound it.

The engine is held at 150 rpm, the solver is asked about a speed it cannot
model, it answers NaN, and the NaN walks through the floor.

### Fix

- **Stall detection** at `max(300, 0.4 × idle_rpm)` — above the solver's
  measured limit with margin, scaling with the engine. Below it the engine is
  declared stalled, its logged rpm is 0, `stalled=True` is recorded, and
  integration stops: a stalled diesel does not restart itself.
- **Explicit non-finite guard** on the solver's torque, raising a
  `RuntimeError` that names the rpm and time. It should never fire — the stall
  check sits above the failure region — but if it does, it fails loudly at the
  source rather than three frames downstream.
- Every log entry now carries `stalled`.

Verified: the lugging case now runs 756 → … → 342 → stalled, 14 entries, no
NaN. The benign case (1500 rpm start, 20 N·m) is unchanged.

### Why this correction is worth keeping visible

This is the second root cause recorded this session that did not survive
reading the code — after the trace-shape claim in FINDING-002. Both were
inferred from a stack trace or a symptom rather than confirmed at the source.
The measurements in every finding held; the *explanations* built on top of two
of them did not. Worth treating inferred root causes as hypotheses until the
code has been read.
