# @dieselsim/physics

TypeScript ports of `dieselsim` modules for the real-time loop, each held to
the Python original by golden fixtures (ADR-004). Framework-free.

| module | port | fixture | tolerance |
|---|---|---|---|
| `kinematics.py` | `src/kinematics.ts` | `fixtures/kinematics.json` | 1e-12 rel; finite differences at their stencil's rounding bound |
| `thermo.py` (scalar paths) | `src/thermo.ts` | `fixtures/thermo.json` | 1e-10 rel |
| `friction.py` + `lubrication.py` (via `grid.cell_friction`) | `src/friction.ts`, `src/lubrication.ts` | `fixtures/friction.json` | 1e-6 rel |
| `live.py` (vehicle, launch clutch, converter, gearbox, manual box with dry clutch and auto-clutch, driveline, `LiveEngine`, driver keys) | `src/live/*.ts` | `fixtures/live.json` | per step 1e-12 from Python's state; terminal 1e-6 and every event at the same step |

The live-loop port keeps Python's field names (`T_coolant`, `phase_t`, ...)
so a state snapshot from the reference loads into it field for field: that
is how the per-step test takes one TypeScript step from Python's exact state.

With an `Adr011Grid` (`src/live/adr011.ts`, cells in `fixtures/live_grid.json`)
the loop computes friction live from the cells' pressure traces at the live
oil and coolant temperature (ADR-011), and carries an oil node.

```bash
npm ci && npm test                              # ports against the fixtures
python3 ../../tools/fixtures/gen_fixtures.py    # regenerate after a physics change
python3 ../../tools/fixtures/gen_fixtures.py --check   # CI: are they current?
```

The ports follow the Python operation order line for line, so they agree to
a few ulps, not merely within tolerance. Python's float modulo (the result
takes the divisor's sign) is `pyMod`; JavaScript's `%` is not a substitute.
