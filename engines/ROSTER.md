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

---

## Roster B (2026-10-03)

ADR-012's second half. Measured as above: fresh engine per point, 9 cycles.

| key | brochure (`engines/<key>.json`) | vehicle |
|---|---|---|
| `v8hd` | 15 L V8, 2,600 N·m from 1,000 to 1,450 rpm, 440 kW (600 ps) at 1,900 | 40 t tractor-trailer (the trucks' vehicle) |
| `single10` | 1.0 L single, naturally aspirated, 58 N·m from 1,300 to 1,600 rpm, 11 kW (15 hp) at 2,200 | 3 t utility tractor |

The file `engines/v8_hd.json` was renamed `v8hd.json`. Everything that
reads a roster file looks for `<key>.json`; under the old name, the grid
would have recorded no engine-file fingerprint and the tests would not have
found the file.

**`v8hd`, tuned.** Untuned it had the roster's low-end shortfall: 80.5% of
the cap at 1,000 rpm, 81.2% at 1,150. Air-limited, as roster A was.

| `boost_map_rise` | `afr_limit` | 1,000 | 1,150 | 1,300 | 1,450 | rated |
|---|---|---|---|---|---|---|
| (default) | (default) | 80.5% | 81.2% | 90.4% | 95.8% | 99.9% |
| 0.12 | 18.0 (truck127's) | 96.9% | 91.5% | 99.9% | 100.0% | 99.9% |
| 0.12 | 17.0 | 98.9% | 95.5% | 99.6% | 100.0% | 99.9% |
| **0.08** | **17.0** | **99.6%** | **96.5%** | **99.5%** | **100.0%** | **99.9%** |

Chosen: 0.08 / 17.0 (λ ≈ 1.17, peak 175 bar), the only setting tried that
holds every plateau point above 96%.

`verify()`: achieved 2,592.6 N·m (99.7%), 430.4 kW at 1,783 rpm (97.8%; at
exactly 1,900 rpm, 439.6 kW, 99.9%).

| rpm | 700 | 917 | 1133 | 1350 | 1567 | 1783 | 2000 |
|---|---|---|---|---|---|---|---|
| N·m | 2056.9 | 2491.9 | 2526.5 | 2592.6 | 2491.8 | 2304.6 | 1966.9 |
| kW | 150.8 | 239.2 | 299.8 | 366.5 | 408.8 | 430.4 | 411.9 |
| boost | 2.16 | 1.95 | 2.00 | 2.22 | 2.33 | 2.32 | 2.21 |
| BSFC g/kWh | 307 | 278 | 255 | 237 | 227 | 222 | 217 |

**`single10`, untuned**, with the builder's two new switches set for an old
engine:
- `mechanical_lash` (from 4 L up by default): the single clatters on
  proper ramps.
- `pilot` off: no pilot injection, as on a pump engine.
- `rail_bar` 400: low injection pressure.

It makes its numbers as built: plateau 99.6 / 99.7 / 100.9 / 100.7%; at
rated speed 11.0 kW (100.1%). `verify()`: 58.5 N·m (100.9%), 10.8 kW at
2,033 rpm (98.0%).

| rpm | 700 | 967 | 1233 | 1500 | 1767 | 2033 | 2300 |
|---|---|---|---|---|---|---|---|
| N·m | 46.7 | 50.4 | 56.3 | 58.5 | 55.4 | 50.6 | 43.6 |
| kW | 3.4 | 5.1 | 7.3 | 9.2 | 10.2 | 10.8 | 10.5 |
| BSFC g/kWh | 403 | 303 | 267 | 255 | 249 | 247 | 249 |

Its full-load AFR of 26–38 is lean for an NA diesel (real ones run ~20–25).
The rating caps its fuel well below the smoke limit, because a 1.0 L single
at 11 kW is a low-BMEP engine (~6 bar), as old ones were.

**Not modelled:** the V8 fires evenly every 90°, but the model has no
separate cylinder banks, so a cross-plane V8's per-bank exhaust "burble" is
absent.

---

## P14 batch 1 (2026-10-28, ADR-023)

Six popular engines, each **modelled on the published figures** of a real one. The maker
is named here and in `/enjoy`'s "modelled on" line only, never as the engine's name
(ADR-023, N2). Measured as above: fresh engine per point, 9 cycles. The screen behind the
choice is `reviews/PROPOSAL-P14.md`.

| key | label in /enjoy | modelled on | vehicle (`live.ROSTER_VEHICLES`) |
|---|---|---|---|
| `vw19tdi` | Hatchback · 1.9 L four, 90 ps | Volkswagen 1.9 TDI (ALH) | `hatch15`, 1.3 t hatchback |
| `mhawk75` | Car · 1.5 L three, 75 bhp | Mahindra mHawk75 (Bolero) | `ld_i4`, 1.75 t passenger car |
| `mhawk22` | SUV · 2.2 L four, 175 ps | Mahindra mHawk 2.2 (Scorpio-N) | `crdi22`, 1.9 t SUV |
| `gd28` | SUV · 2.8 L four, 204 ps | Toyota 1GD-FTV (Fortuner, Hilux) | `crdi22` |
| `duratorq32` | SUV · 3.2 L five, 200 ps | Ford 3.2 Duratorq (Endeavour, Ranger) | `crdi22` |
| `b57` | Car · 3.0 L six, 265 ps | BMW B57D30O0 (330d, 530d) | `ld_i4` |

The first three-cylinder and the first five-cylinder on the roster. These six name their
vehicle in their file (`"vehicle"`, which `builder.from_dict` drops). A roster grid records
none, so `live.ROSTER_VEHICLES` maps each key, and
`test_roster_engines_drive_their_vehicles` holds the two together. Without the map, a new
key silently drives the 3 t tractor.

### Sources (F2: brochure plus published hardware)

Where nothing published was found, the builder's default stands and is marked *default*.

- **`vw19tdi`:** 1,896 cc, 79.5 × 95.5 mm; 66 kW (90 PS) at 3,750 rpm, 210 N·m at
  1,900 rpm (a single speed, so `plateau` [1900, 1900]); CR 19.5 (sources say 19.0–19.5);
  a distributor pump, so `pilot: false`. Turbo type *default* (VGT; the ALH's VNT-15 wasn't
  confirmed by any source found).
  [kfz-tech.de](https://kfz-tech.de/Engl/Herstellerdaten/VW/VW_1997_Vento_1.9_TDI_.htm),
  [encycarpedia](https://www.encycarpedia.com/us/volkswagen/98-golf-1-9-tdi-4motion-hatch),
  [luna.ac](https://luna.ac/ficha-tecnica/carros/Volkswagen/Golf%204%20TDI%2090/1997).
- **`mhawk75`:** 1,493 cc, three cylinders inline; 74.96 bhp (56 kW) at 3,600 rpm, 210 N·m
  at 1,600–2,200 rpm. Bore/stroke, CR and turbo type *default*. (Two listings say four
  cylinders; the cylinder-level listings and the 2020 BS6 coverage say three.)
  [cardekho](https://www.cardekho.com/mahindra/bolero/specs),
  [carwale](https://www.carwale.com/news/2020-mahindra-bolero-top-5-features/).
- **`mhawk22`:** 2,198 cc; 128.6 kW (175 PS) at 3,500 rpm, 400 N·m at 1,750–2,750 rpm (the
  automatic; the manual is 370 N·m); a VGT. Bore/stroke and CR *default* (the older
  2,179 cc mHawk's 85 × 96 mm doesn't give 2,198 cc).
  [cardekho](https://www.cardekho.com/mahindra/scorpio-n/specs),
  [Mahindra SA](https://cmhmahindra.co.za/?p=20790),
  [Autocar India](https://www.autocarindia.com/cars/mahindra/scorpio-n/specifications).
- **`gd28`:** 2,755 cc, 92.0 × 103.6 mm, CR 15.6; 150 kW (204 PS) at 3,400 rpm, 500 N·m at
  1,600–2,800 rpm (the high-output version); a VGT.
  [Toyota-Club GD FAQ](https://toyota-club.net/files/faq/15-10-20_faq_gd-engine_eng.htm),
  [Wikipedia](https://en.wikipedia.org/wiki/Toyota_GD_engine),
  [Toyota UK](https://mag.toyota.co.uk/toyota-turbodiesel-engines-cleaner-and-more-efficient/).
- **`duratorq32`:** 3,198 cc inline five, 89.9 × 100.8 mm (the pair that gives 3,198 cc;
  another listing's 89.0 × 100.7 gives 3,132), CR 15.8 (listings say 15.8–16.0); 147 kW at
  3,000 rpm, 470 N·m at 1,750–2,500 rpm.
  [Wikipedia](https://en.wikipedia.org/wiki/Ford_Duratorq_engine),
  [mymotorlist](https://mymotorlist.com/engines/ford/duratorq-3-2/),
  [Everest spec](https://itunesystem.file-service.com/tuning-specs/ford/everest/2015-2018/32-tdci-195hp).
- **`b57`:** 2,993 cc inline six, 84 × 90 mm, CR 16.5; 195 kW (265 PS) at 4,000 rpm, 620 N·m
  at 2,000–2,500 rpm (B57D30O0, single turbo).
  [Wikipedia](https://en.wikipedia.org/wiki/BMW_B57),
  [mymotorlist](https://mymotorlist.com/engines/bmw/b57d30/).

### Tuning

The rule: **the least tuning that holds the plateau start at 96% or more**, one point over
`test_roster_engines_make_their_numbers`' 95%.

| key | `boost_map_rise` | `afr_limit` | plateau start, untuned → chosen | why |
|---|---|---|---|---|
| `vw19tdi` | (default) | (default) | 99.8% | holds untuned |
| `duratorq32` | (default) | (default) | 99.9% | holds untuned |
| `mhawk75` | 0.12 | 16.0 | 95.4 → 100.6% | untuned is 0.4 points from the test's bar |
| `mhawk22` | 0.12 | 16.0 | 89.6 → 100.4% | air-limited low down, as roster A was |
| `gd28` | 0.12 | 16.0 | 85.7 → 100.1% | the same |
| `b57` | **0.08** | **15.5** | 81.7 → 98.5% | at 0.12 / 16: 94.7%; at 0.08 / 16: 95.7% |

### verify() after tuning

At exactly rated speed: vw19tdi 99.7%, mhawk75 99.8%, mhawk22 100.1%, gd28 100.8%,
duratorq32 99.4% and b57 100.2% of the brochure power. verify()'s speeds miss rated by up
to 100 rpm, so their peaks below read a little lower.

**vw19tdi:** achieved 207.1 N·m (98.6%; its single-speed peak falls between verify()'s
speeds), 64.0 kW (96.9%). Max soot 0.178 g/kWh, peak pressure 138 bar.

| rpm | 850 | 1350 | 1850 | 2350 | 2850 | 3350 | 3850 |
|---|---|---|---|---|---|---|---|
| N·m | 145.2 | 180.3 | 207.1 | 198.3 | 190.3 | 175.9 | 158.6 |
| kW | 12.9 | 25.5 | 40.1 | 48.8 | 56.8 | 61.7 | 64.0 |
| boost | 1.27 | 1.36 | 1.64 | 1.91 | 1.87 | 1.78 | 1.70 |
| BSFC g/kWh | 370 | 274 | 234 | 222 | 235 | 256 | 285 |

**mhawk75:** achieved 210.0 N·m (100.0%), 55.6 kW (99.4%). Max soot 0.184 g/kWh, peak
pressure 134 bar.

| rpm | 820 | 1300 | 1780 | 2260 | 2740 | 3220 | 3700 |
|---|---|---|---|---|---|---|---|
| N·m | 135.9 | 190.1 | 210.0 | 207.3 | 186.2 | 165.0 | 140.0 |
| kW | 11.7 | 25.9 | 39.1 | 49.1 | 53.4 | 55.6 | 54.3 |
| boost | 1.37 | 1.54 | 1.74 | 1.80 | 1.76 | 1.71 | 1.67 |
| BSFC g/kWh | 376 | 281 | 257 | 260 | 264 | 272 | 279 |

**mhawk22:** achieved 399.7 N·m (99.9%), 125.6 kW (97.7%). Max soot 0.271 g/kWh, peak
pressure 169 bar.

| rpm | 800 | 1267 | 1733 | 2200 | 2667 | 3133 | 3600 |
|---|---|---|---|---|---|---|---|
| N·m | 195.2 | 322.0 | 399.5 | 399.7 | 398.6 | 375.8 | 333.2 |
| kW | 16.4 | 42.7 | 72.5 | 92.1 | 111.3 | 123.3 | 125.6 |
| boost | 1.32 | 1.99 | 2.13 | 2.29 | 2.67 | 2.84 | 2.77 |
| BSFC g/kWh | 394 | 285 | 258 | 238 | 219 | 217 | 219 |

**gd28:** achieved 498.8 N·m (99.8%), 148.6 kW (99.1%). Max soot 0.239 g/kWh, peak
pressure 164 bar.

| rpm | 780 | 1233 | 1687 | 2140 | 2593 | 3047 | 3500 |
|---|---|---|---|---|---|---|---|
| N·m | 257.0 | 445.0 | 495.6 | 496.2 | 498.8 | 465.8 | 394.8 |
| kW | 21.0 | 57.5 | 87.5 | 111.2 | 135.5 | 148.6 | 144.7 |
| boost | 1.37 | 1.98 | 2.05 | 2.32 | 2.72 | 2.79 | 2.66 |
| BSFC g/kWh | 362 | 274 | 254 | 232 | 219 | 220 | 222 |

**duratorq32:** achieved 469.3 N·m (99.9%), 142.5 kW (97.0%). Max soot 0.183 g/kWh, peak
pressure 155 bar.

| rpm | 700 | 1100 | 1500 | 1900 | 2300 | 2700 | 3100 |
|---|---|---|---|---|---|---|---|
| N·m | 238.1 | 382.1 | 437.4 | 469.0 | 469.3 | 465.4 | 439.1 |
| kW | 17.5 | 44.0 | 68.7 | 93.3 | 113.0 | 131.6 | 142.5 |
| boost | 1.30 | 1.65 | 1.78 | 1.96 | 2.33 | 2.56 | 2.48 |
| BSFC g/kWh | 377 | 282 | 247 | 226 | 210 | 211 | 219 |

**b57:** achieved 617.5 N·m (99.6%), 190.6 kW (97.7%). Max soot 0.242 g/kWh, peak pressure
183 bar.

| rpm | 900 | 1433 | 1967 | 2500 | 3033 | 3567 | 4100 |
|---|---|---|---|---|---|---|---|
| N·m | 297.2 | 525.7 | 603.7 | 617.5 | 560.3 | 510.3 | 438.0 |
| kW | 28.0 | 78.9 | 124.3 | 161.7 | 178.0 | 190.6 | 188.1 |
| boost | 1.38 | 2.09 | 2.16 | 2.59 | 2.77 | 2.78 | 2.65 |
| BSFC g/kWh | 370 | 278 | 256 | 230 | 215 | 217 | 222 |

**Rich when lugged.** At verify()'s lowest speed, full load, mhawk22 (800 rpm) and b57
(900 rpm) run AFR 14.4 and 14.5, under their 16.0 / 15.5 limits, with the most soot of the
six (0.271, 0.242 g/kWh). hatch15 and crdi22 stay at AFR 16.1–17.1 there (soot
0.17–0.19), and both new engines are back over their limits by 1,267 / 1,433 rpm. The cause
is the calibration: `fuel_for_torque` scales the measured air headroom up, never down
(clipped at 1), so where the turbo gives less boost than the open-loop schedule assumes,
the fuel isn't pulled back. Changing that is hashed `engine.py` and every grid, so it is
stated, not fixed. A diesel lugged at 800 rpm smoking a little is not unrealistic.

**The old engine runs lean.** vw19tdi sits at AFR 24.7 at its peak (real ones ~18–22),
because its brochure caps the fuel well under the smoke limit, as with single10.

### The grids

Built 2026-10-28 on the owner's M2 (6 workers): `build_live_grids.py` with the six keys,
then `--weather`. Cells 3,044 s plus weather 11,315 s, **4.0 h** in all (the proposal
estimated 4.4).

| key | cells | unsettled cells | weather | unsettled weather pieces | Leh check, worst | cold / warm FMEP, worst |
|---|---|---|---|---|---|---|
| `vw19tdi` | 261 s | 0 | 1,292 s | 0 | 3.42% | 3.00× |
| `mhawk75` | 233 s | 0 | 952 s | 0 | 2.27% | |
| `mhawk22` | 555 s | 1 | 1,969 s | 28 | 0.41% | |
| `gd28` | 627 s | 1 | 2,014 s | 29 | 1.37% | |
| `duratorq32` | 570 s | 4 | 2,161 s | 34 | 2.33% | |
| `b57` | 798 s | 10 | 2,927 s | 65 | 1.47% | |

All are within the shipped grids' ranges: unsettled cells 0–22, weather pieces 0–68, and
Leh checks 0.28–4.72% (single10's misfire cliff aside, 36%, FINDING-027). No new cliff.
`test_shipped_grids_cold_friction` reports only the worst grid: vw19tdi at 3.00×, under
its 4× bar but above the ten shipped grids' 1.78–2.84×. Why is not investigated. The
engine's CR (19.5, the roster's highest) is the obvious difference, but that is unmeasured.

---

## P14 batch 2 (2026-10-28, ADR-023): the pickups

Four pickup engines and **one new vehicle** for them, `pickup` (V2). Each is **modelled on
the published figures** of a real engine, as in batch 1. The owner answered "Most popular
onces / N2 / F2 / V2".

| key | label in /enjoy | modelled on | vehicle |
|---|---|---|---|
| `cummins59` | Pickup · 5.9 L six, 215 hp | Cummins 5.9 12-valve (Ram 2500, 1996–98, manual) | `pickup` |
| `cummins67` | Pickup · 6.7 L six, 370 hp | Cummins 6.7 (Ram 2500, standard output) | `pickup` |
| `duramax66` | Pickup · 6.6 L V8, 445 hp | GM Duramax L5P (Silverado / Sierra HD, 2017–23) | `pickup` |
| `powerstroke73` | Pickup · 7.3 L V8, 275 hp | Ford 7.3 Power Stroke (Super Duty, 1999–2003, manual) | `pickup` |

### The vehicle: `pickup`, "3.2 t pickup, 6-speed auto"

Sourced from a 2023 Ram 2500 6.7 Cummins (4×4 crew cab): the 6-speed's ratios 3.23 / 1.84 /
1.41 / 1.00 / 0.82 / 0.62; a 3.73 axle; LT275/70 R18 tyres (0.405 m loaded); 7,045 lb
(3,196 kg) curb, so 3,200 kg.
[auto123 Limited](https://www.auto123.com/en/specs/ram/2500/ram-2500-2023-limited-4x4-crew-cab-64%22-box-433610/),
[auto123 Big Horn](https://www.auto123.com/en/specs/ram/2500/ram-2500-2023-big-horn-4x4-crew-cab-64%22-box-433607/).
**Estimates**, scaled from the SUV: the drag area 1.75 m² (Cd ~0.48 × ~3.6 m²), the rolling
resistance 0.0100, the efficiency 0.92, the inertias (gearbox 0.16, wheels 14 kg·m²), the
converter's stall 1,900 rpm, and the 117 L tank (no source found). It is in
`live.VEHICLE_KEYS`, so a custom engine can name it too. One vehicle for four eras of truck
is ADR-023's V2: the 12-valve and the 7.3 had 4- and 5-speed boxes in their day.

### Sources (F2)

The peak torque of all four is published at one speed, so each `plateau` is a single point
(as vw19tdi's is).
- **`cummins59`:** 5,883 cc (359 cu in) inline six, 102 × 120 mm, CR 17.5 (one source says
  17.0); 215 hp (160 kW) at 2,600 rpm and 440 lb-ft (597 N·m) at 1,500 rpm, the manual's
  rating (the automatic's is 180 hp / 420 lb-ft). A mechanical Bosch P7100 pump, so
  `pilot: false`; a wastegated turbo, so `vgt: false`.
  [DieselHub](https://dieselhub.com/cummins/cummins-timeline.html),
  [Wikipedia](https://en.wikipedia.org/wiki/Cummins_B_Series_engine),
  [Maxiforce](https://maxiforce.com/engine-kit/cummins-6bt-5-9-piston-m-7163).
- **`cummins67`:** 6,690 cc, 107 × 124 mm; 370 hp (276 kW) at 2,800 rpm, 850 lb-ft
  (1,152 N·m) at 1,700 rpm (the standard output; the high output is 400+ hp). **CR 17.3**,
  Wikipedia's B6.7 figure, with listings that also say 19, 16.2 and 16.0 by year and
  output. A VGT (the default).
  [auto-data](https://www.auto-data.net/en/ram-2500-3500-regular-cab-ii-dt-2500-6.7-cummins-td-370hp-4x4-automatic-35533),
  [Wikipedia](https://en.wikipedia.org/wiki/Cummins_B_Series_engine),
  [Cummins spec sheet](https://mart.cummins.com/imagelibrary/data/assetfiles/0070408.pdf).
- **`duramax66`:** 6,604 cc (403 cu in) V8, 103 × 99 mm, CR 16.0; 445 hp (332 kW) at
  2,800 rpm, 910 lb-ft (1,234 N·m) at 1,600 rpm (2017–23; 2024 on is 470 hp / 975 lb-ft).
  GM's own figures. A VGT.
  [GM Powered Solutions](https://poweredsolutions.gm.com/products/l5p-engine/),
  [DieselHub](https://www.dieselhub.com/duramax/6.6-duramax-l5p.html).
- **`powerstroke73`:** 7,275 cc (444 cu in) V8, 4.11 × 4.18 in (104.4 × 106.2 mm), CR 17.5;
  275 hp (205 kW) at 2,800 rpm and 525 lb-ft (712 N·m) at 1,600 rpm, the manual's rating
  (the automatic's 250 hp / 505 lb-ft). HEUI injection, modelled as a pump without pilot
  (`pilot: false`); a wastegated turbo (`vgt: false`).
  [Wikipedia](https://en.wikipedia.org/wiki/Ford_Power_Stroke_engine),
  [BD Diesel](https://ca.bddiesel.com/blogs/r-d-blog/ford-7-3l-power-stroke-diesel-engine),
  [TractorByNet](https://tractorbynet.com/forums/threads/whats-the-difference.208063/).
- **Not set:** the firing orders (the builder's even 90° V8 order is used; the model has
  no banks, as with v8hd).

### Tuning (the same rule: the least that holds the plateau start at 96% or more)

| key | `boost_map_rise` | `afr_limit` | plateau start, untuned → chosen |
|---|---|---|---|
| `cummins59` | (default) | (default) | 99.8% |
| `powerstroke73` | (default) | (default) | 99.6% |
| `cummins67` | 0.12 | 16.0 | 89.6 → 99.1% |
| `duramax66` | 0.12 | 16.0 | 85.8 → 102.0% |

At exactly rated speed: 99.6, 99.8, 99.6 and 99.7% of the brochure power.

### verify() after tuning

verify()'s last speed is past rated, in the governor's droop, and its speeds skip the
single-speed torque peaks, so the peaks below read a little low.

**cummins59:** 596.7 N·m (100.0%), 152.3 kW (95.2%). Max soot 0.189 g/kWh, peak pressure
120 bar.

| rpm | 700 | 1033 | 1367 | 1700 | 2033 | 2367 | 2700 |
|---|---|---|---|---|---|---|---|
| N·m | 451.9 | 507.4 | 568.3 | 596.7 | 595.1 | 586.4 | 538.7 |
| kW | 33.1 | 54.9 | 81.3 | 106.2 | 126.7 | 145.3 | 152.3 |
| boost | 1.16 | 1.27 | 1.48 | 1.63 | 1.74 | 1.79 | 1.73 |
| BSFC g/kWh | 328 | 253 | 222 | 214 | 215 | 224 | 239 |

**cummins67:** 1,132.5 N·m (98.3%), 267.6 kW (96.9%). Max soot 0.193 g/kWh, peak pressure
169 bar.

| rpm | 700 | 1067 | 1433 | 1800 | 2167 | 2533 | 2900 |
|---|---|---|---|---|---|---|---|
| N·m | 699.3 | 946.7 | 1066.4 | 1132.5 | 1054.6 | 988.3 | 881.1 |
| kW | 51.3 | 105.7 | 160.1 | 213.5 | 239.3 | 262.2 | 267.6 |
| boost | 1.63 | 1.88 | 1.92 | 2.24 | 2.43 | 2.45 | 2.35 |
| BSFC g/kWh | 342 | 269 | 248 | 228 | 215 | 219 | 225 |

**duramax66:** 1,198.6 N·m (97.1%; at its 1,600 rpm peak, 102.0% of the cap), 319.6 kW
(96.3%). Max soot 0.329 g/kWh, peak pressure 172 bar.

| rpm | 700 | 1067 | 1433 | 1800 | 2167 | 2533 | 2900 |
|---|---|---|---|---|---|---|---|
| N·m | 617.3 | 1069.5 | 1129.7 | 1198.6 | 1180.5 | 1162.1 | 1052.4 |
| kW | 45.3 | 119.5 | 169.6 | 225.9 | 267.8 | 308.3 | 319.6 |
| boost | 1.34 | 1.89 | 2.18 | 2.27 | 2.51 | 2.75 | 2.75 |
| BSFC g/kWh | 402 | 293 | 255 | 241 | 224 | 218 | 217 |

**powerstroke73:** 707.7 N·m (99.4%), 196.2 kW (95.7%). Max soot 0.180 g/kWh, peak pressure
115 bar.

| rpm | 700 | 1067 | 1433 | 1800 | 2167 | 2533 | 2900 |
|---|---|---|---|---|---|---|---|
| N·m | 438.5 | 596.4 | 671.6 | 707.7 | 700.5 | 695.1 | 646.0 |
| kW | 32.1 | 66.6 | 100.8 | 133.4 | 158.9 | 184.4 | 196.2 |
| boost | 1.08 | 1.21 | 1.46 | 1.64 | 1.76 | 1.76 | 1.69 |
| BSFC g/kWh | 371 | 277 | 231 | 220 | 221 | 233 | 253 |

**Rich when lugged**, as mhawk22 and b57 are: duramax66 at 700 rpm, full load, runs AFR 13.8
with the roster's most soot (0.329 g/kWh), for the same reason (batch 1, above).
**The two old engines run lean** (cummins59 and powerstroke73, AFR 26.8 and 27.2 at their
torque peaks),
as vw19tdi and single10 do: their brochures cap the fuel well under the smoke limit.

### The grids

*(filled in when the build finishes)*
