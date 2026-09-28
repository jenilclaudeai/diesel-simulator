# @dieselsim/physics

TypeScript ports of `dieselsim` modules for the real-time loop, each held to
the Python original by golden fixtures (ADR-004). Framework-free.

| module | port | fixture | tolerance |
|---|---|---|---|
| `kinematics.py` | `src/kinematics.ts` | `fixtures/kinematics.json` | 1e-12 rel; finite differences at their stencil's rounding bound |
| `thermo.py` (scalar paths) | `src/thermo.ts` | `fixtures/thermo.json` | 1e-10 rel |
| `friction.py` via `grid.cell_friction` | — (Phase 3, ADR-011) | `fixtures/friction.json` | 1e-6 rel |

```bash
npm ci && npm test                              # ports against the fixtures
python3 ../../tools/fixtures/gen_fixtures.py    # regenerate after a physics change
python3 ../../tools/fixtures/gen_fixtures.py --check   # CI: are they current?
```

The ports follow the Python operation order line for line, so they agree to
a few ulps, not merely within tolerance. Python's float modulo (the result
takes the divisor's sign) is `pyMod`; JavaScript's `%` is not a substitute.
