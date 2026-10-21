# FINDING-033 — An automatic can be dragged to its 60 rpm floor and left there, "running"

**Opened by:** session 10 (2026-10-21), building P06 tier 2's par runs.
**Lens:** PHY1, SR1, USR1
**Status:** **open, for the owner.** Nothing changed yet. **Latent:** no shipped grid
reaches it in the 40 runs below. Only the test fixture's small crdi15 grid does.
**Reproduce:** scratch scripts `par_trace.py`, `bog_matrix.py` and `bog_all.py` in the
session's job directory; the live fixture's `par_random_leh`.

---

## What happens

Take the live fixture's ADR-011 crdi15 grid (`web/physics/fixtures/live_grid.json`, a
coarse 8 × 6 test grid). Do a cold start at Leh's air (65.8 kPa, 20 °C) with the automatic,
70 % throttle from rest, on random route 1234 (2.5 % gravel, 7.5 m/s headwind). Then:
- by 30 s the engine is at **60 rpm** and the car doesn't move;
- it stays there for the whole hour (3,600 s), with `stalled` false;
- the coolant warms from 20 °C to 93 °C;
- it burns 2.43 L, as if it idled.

Python and the TypeScript port agree to the frame, so it is the model, not the port.

## Why

`LiveEngine._sub` floors an automatic's speed at 60 rpm and clears `stalled` every
substep: "a converter slips, so a torque-converter automatic does not stall"
(`live.py`, after `rpm_new`).
- If the engine's net torque at that floor is ≤ 0, nothing lifts it off.
- The fuel and the heat come from the grid's lowest cells (rpm is clamped to the grid), so
  it looks like a running engine.
- The page shows no Restart button: Enjoy shows Restart only when `stalled` is true.

It is CLAUDE.md's pattern: **pinned against a clamp, raising no error**.

## How exposed (measured)

All ten shipped grids: a cold start at Leh with the automatic, 60 s from rest, at 70 % and
100 %, on a flat road and on random:1234 (40 runs).
- **None fell below 561 rpm** (hd_i6), and every engine recovered.
- The dev single's 743–777 rpm crawl is its known defect (the suite's KNOWN "dev single
  sags on the tractor's converter"), not this.
- With hatch15, standard air and warm starts didn't reach it either (16 more runs).

So today it takes a weak grid: a custom engine (ADR-014) could, a roster engine doesn't.

## Options

- **A, stall an automatic that can't hold its speed.** Below `STALL_FRAC` × idle, with the
  box in gear, an automatic stalls as a manual does. Enjoy then offers Restart, and the
  hint says why.
  - *Positives:* no "running at 60 rpm" state; it's honest, since a converter only keeps an
    engine alive while the engine's torque can carry it.
  - *Trade-offs:* the live fixtures that reach the floor move (here only the stuck par);
    a test needs a weak grid to reach it; the restart key works on the automatic too.
- **B, state it.** Note it in ADR-014's custom-engine notes and leave the model.
  - *Positives:* nothing moves.
  - *Trade-offs:* a weak custom engine can still sit at 60 rpm with no way out but Stop.

**Recommendation: A**, but after P06. It doesn't block anything: P06's par treats a par
that never finishes as "no limit", and that path is tested on this very case.
