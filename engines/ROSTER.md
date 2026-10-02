# Enjoy mode roster — achieved against requested

ADR-008 requires every roster engine to be run through `builder.verify()`,
with its achieved-against-requested figures recorded here. ADR-012 set the
roster: **A** first (these three), then B (a 15 L V8 truck and an old
naturally aspirated single). Measured 2026-09-30, fresh engine per point,
9 cycles, as the app solves.

`tests/test_physics.py::test_roster_engines_make_their_numbers` re-checks
each engine's plateau start and rated power, and fails if a physics change
breaks them.

## The engines

| key | brochure (`engines/<key>.json`) | vehicle (`dieselsim/live.py`) |
|---|---|---|
| `hatch15` | 1.5 L four, 260 N·m from 2,000 to 2,750 rpm, 85 kW (115 ps) at 4,000 | 1.3 t hatchback, 6-speed |
| `crdi22` | 2.2 L four, 360 N·m from 1,750 to 2,750 rpm, 110 kW (150 ps) at 3,800 | 1.9 t SUV, 8-speed auto |
| `truck127` | 12.7 L six, 2,400 N·m from 1,000 to 1,400 rpm, 390 kW (530 hp) at 1,800 | 40 t tractor-trailer (the one `hd_i6` drives) |

## Tuning

Straight out of the builder, every engine made its peaks, but not its low
end. At the start of the plateau it had 77% (hatch15), 83% (crdi22) and 86%
(truck127) of the rating cap. The cause, measured:
- the engine was **air-limited at its boost target**: AFR at the smoke
  limit, and boost equal to target;
- not pressure- or temperature-limited: no limit was set, and the peak
  pressures were 130–181 bar.

Two knobs were enough, and each engine uses the least aggressive values that
hold its plateau:

| key | `boost_map_rise` (default 0.45) | `afr_limit` (default 17.5 LD / 19 HD) | why |
|---|---|---|---|
| `hatch15` | 0.12 | 16.0 | the boost target rises earlier; λ ≈ 1.10 at full load |
| `crdi22` | 0.12 | 16.0 | the same |
| `truck127` | 0.12 | 18.0 | λ ≈ 1.24 |

`boost_map_rise` became a `build_engine` parameter for this; its default is
unchanged.

**hatch15's brochure plateau was moved from 1,750 to 2,000 rpm.** No
setting of the two knobs held 1,750: the best was 89.3%, and the builder's
turbo sizing does not deliver the air there. It holds from 2,000 (96.7%).
That is a small turbo engine whose torque arrives a little later, stated
honestly rather than forced by a third knob.

## Correction (2026-09-30): truck127's valves landed on the flank

Roster A shipped (#76) with `truck127` given the builder's default 6% cam
ramp: 113 µm under 550 µm of exhaust lash. Its valves therefore landed on
the steep flank:
- 0.65 m/s seating at idle;
- valve tick 224× its loudest other mechanical source at 1200 rpm, half load.

FINDING-017 had warned that builder engines with lash could land off the
ramp, and I did not check. The lash test only looked at the presets.

REVIEW-003 m-5 fixed it. Every builder engine with lash now gets ramps
1.25× its lash tall, at 0.025 mm per cam degree, in front of the unchanged
main event: 0.045 m/s at idle, tick 0.90×, and 26 dB quieter overall at
idle. The lash test now covers the roster engines.

`verify()` re-run after the change: peak 2,393.6 N·m and 383.3 kW, the
same, and the plateau points the same (99.8 / 97.4 / 99.8 / 99.9%). Only
two points moved: 700 rpm 1,780.6 → 1,781.3 N·m, and 1,100 rpm
2,363.2 → 2,363.4. The table below stands. (The ramps change only the lift
below 1.25× the lash; the valves clear it 9° earlier, at very small lift.)

## verify() after tuning

**hatch15:** achieved 261.9 N·m (100.7%), 83.3 kW (98.0%). Plateau: 96.7%
at 2,000, 98.5% at 2,250, 100.7% at 2,500, 99.9% at 2,750. Max soot
0.088 g/kWh.

| rpm | 900 | 1433 | 1967 | 2500 | 3033 | 3567 | 4100 |
|---|---|---|---|---|---|---|---|
| N·m | 124.4 | 213.2 | 250.2 | 261.9 | 245.9 | 221.6 | 194.1 |
| kW | 11.7 | 32.0 | 51.5 | 68.6 | 78.1 | 82.8 | 83.3 |
| boost | 1.38 | 1.81 | 1.96 | 2.34 | 2.54 | 2.46 | 2.35 |
| BSFC g/kWh | 390 | 296 | 265 | 240 | 227 | 229 | 236 |

**crdi22:** achieved 359.9 N·m (100.0%), 109.6 kW (99.6%). Plateau: 96.6%
at 1,750, 100.0% at 2,083, 99.9% at 2,417, 99.7% at 2,750. Max soot
0.101 g/kWh.

| rpm | 860 | 1367 | 1873 | 2380 | 2887 | 3393 | 3900 |
|---|---|---|---|---|---|---|---|
| N·m | 217.2 | 304.0 | 351.9 | 359.9 | 348.5 | 308.4 | 261.0 |
| kW | 19.6 | 43.5 | 69.0 | 89.7 | 105.3 | 109.6 | 106.6 |
| boost | 1.56 | 1.67 | 1.92 | 2.28 | 2.38 | 2.27 | 2.18 |
| BSFC g/kWh | 349 | 285 | 253 | 231 | 229 | 234 | 239 |

**truck127:** achieved 2,393.6 N·m (99.7%), 383.3 kW (98.3%). Plateau:
99.8% at 1,000, 97.4% at 1,133, 99.8% at 1,267, 99.9% at 1,400. Max soot
0.086 g/kWh.

| rpm | 700 | 900 | 1100 | 1300 | 1500 | 1700 | 1900 |
|---|---|---|---|---|---|---|---|
| N·m | 1780.6 | 2274.2 | 2363.2 | 2393.6 | 2330.1 | 2153.3 | 1839.1 |
| kW | 130.5 | 214.3 | 272.2 | 325.9 | 366.0 | 383.3 | 365.9 |
| boost | 2.26 | 2.13 | 2.20 | 2.37 | 2.52 | 2.52 | 2.38 |
| BSFC g/kWh | 304 | 268 | 249 | 234 | 222 | 216 | 211 |

Above rated speed the governor pulls fuel to 4% at max rpm, so the last
point of each full-load curve is negative torque, as intended (CLAUDE.md).
