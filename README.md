# dieselsim

A physics-based diesel engine simulator. Not a lookup table, not a curve fit,
not a sample library — the torque, the fuel consumption, the emissions, the
wear and the *sound* are all consequences of solving the same set of physical
equations that govern a real engine.

The scope is deliberately broad, in the spirit of *Automation*: geometry,
valve timing, injection strategy, turbo matching, oil grade, surface finish
and clearances are all inputs, and everything downstream reacts to them.

---

## Getting started

Python 3.10+ for the solver; Node.js ≥ 22.22.3 for the browser app.

```bash
git clone https://github.com/jenilclaudeai/diesel-simulator.git
cd diesel-simulator
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python tests/test_physics.py          # the regression suite (counts in STATUS.md)

cd web/app && npm ci && npm start     # the browser app on http://localhost:4200
```

`python3 play.py --preset crdi15` drives an engine from the terminal (with
sound, if `sounddevice` is installed). The browser app's own setup notes are
in [web/app/README.md](web/app/README.md), including what to do behind a
proxy or offline. The project's working state is in `STATUS.md`.

---

## What actually gets solved

### 1. In-cylinder process — `cycle.py`

A crank-angle-resolved first-law energy balance on every cylinder, integrated
over the full 720° with a 0.5–1° step:

```
du/dθ = (−p dV/dθ + dQ_comb/dθ − dQ_wall/dθ + Σ ṁ_i h_i /ω) / m
```

- **Gas properties** are a two-component (unburned/burned) mixture with
  temperature-dependent `cp` fitted to JANAF data and a dissociation term
  above 2200 K. `γ` is *never* assumed constant.
- **Ignition delay** uses Hardenberg–Hase, but **integrated along the real
  p–T history** (`∫ dt/τ = 1`), not evaluated once at injection.
- **Heat release** is three superposed Wiebe functions — pilot, premixed
  main, diffusion main. The premixed fraction comes from a Watson correlation
  driven by the computed delay; the **diffusion burn duration is set by the
  actual nozzle flow rate**, so rail pressure, hole count, hole diameter and
  injector coking all change the burn shape.
- **Heat transfer** is Woschni, with the motored-pressure reference tracked
  in parallel through the cycle.
- **Gas exchange** is bidirectional compressible orifice flow through
  lift-dependent valve areas (curtain vs. throat, `L/D`-dependent `Cd`) into
  finite-volume manifolds — so back-flow, valve overlap scavenging and
  residual gas all emerge on their own. **PMEP is a result, not an input.**
- **Blow-by** flows both ways through the ring-gap labyrinth, using the gap
  the wear model currently reports.
- **EGR** is a real high-pressure loop: flow needs exhaust-to-intake ΔP, so
  the VGT has to be closed to drive it, and that costs pumping work.
- **Emissions**: extended Zeldovich NO in a two-zone burned region with
  excess-air entrainment, and Hiroyasu formation/oxidation for soot.

### 2. Kinematics — `kinematics.py`

Exact offset slider–crank (no `sin`/`cos` small-angle shortcuts), plus cam
profiles built from a raised-cosine main event with **explicit
constant-velocity opening and closing ramps**. The ramps matter: the finite
seating velocity they produce is the physical source of valvetrain tick, and
it grows as lash opens up with wear.

### 3. Lubrication — `lubrication.py`

- Viscosity: Vogel base curve → Barus piezo-viscosity → Cross shear thinning
  → condition multipliers. So a bearing at 2 GPa sees a very different oil
  than the sump does.
- Journal bearings: Ocvirk short-bearing solution, solved by bisection on
  eccentricity for `h_min`, attitude, friction torque and side leakage, with
  a squeeze-film credit under the firing impulse.
- Ring and skirt films from 1-D Reynolds, **supply-limited**: a ring can only
  entrain the film the previous stroke left behind.
- Cam/follower via Hamrock–Dowson EHL line contact.
- Mixed lubrication everywhere through a Greenwood–Tripp-style λ ratio.
- Oil circuit: positive-displacement pump against a clearance-cubed leakage
  network, so a worn engine genuinely loses oil pressure.
- Oil ageing: Arrhenius oxidation, soot loading, TBN depletion, fuel
  dilution, additive consumption.

### 4. Friction — `friction.py`

Component-by-component and crank-angle-resolved. There is **no
`FMEP = A + B·N + C·p_max` fit anywhere in this package**:

| source | model |
|---|---|
| compression rings | gas-loaded, inter-ring pressure decay, mixed lubrication |
| oil control ring | tension-loaded, boundary-dominated |
| piston skirt | side thrust from rod angle, partial journal bearing |
| piston pin | oscillating — never builds a full film, so boundary/mixed |
| rod & main bearings | Ocvirk + squeeze credit + asperity share |
| valvetrain | spring + inertia + gas load, roller or flat-tappet branch |
| windage / churning | oil density and speed dependent |
| timing gears, seals | tooth mesh + lip drag |
| accessories | oil pump, water pump, fan, alternator, air compressor |
| HP fuel pump | `p_rail · Q / η` — on a 1800 bar common rail this is one of the largest single parasitic loads |

The boundary-friction power from each contact is passed straight into the
wear model.

### 5. Wear — `wear.py`

Archard rewritten in energy form, `V = k·E_boundary/(μ_b·H)`, so wear is
driven by the friction the tribology model actually computed — including a
cold-start multiplier that reaches ~23× below 40 °C.

The feedback loop is closed. Wear changes: ring gap → blow-by → trapped mass
→ IMEP; bearing clearance → leakage → gallery pressure → thinner film → more
wear; cam wear → lost lift → breathing; injector coking → longer burn →
soot; turbo fouling → boost.

### 6. Turbocharger — `turbo.py`

Similitude compressor map (PR ∝ u², elliptical speed lines between surge and
choke), variable-nozzle turbine with efficiency peaking at a blade-speed
ratio of ~0.68, and the shaft integrated **in real time**:

```
J dN/dt = (P_turbine − P_compressor − P_friction) / (N ...)
```

which is where turbo lag comes from. Nothing is quasi-steady.

### 7. Engine layer — `engine.py`

Couples all of the above and adds the governor, the smoke limiter, the EGR
and boost schedules, the injection-timing map, and a flywheel:

```
J dω/dt = T_indicated(ω, fuel) − T_friction(ω, oil, wear) − T_load(ω)
```

Provides steady-state points, full-load curves, performance maps, cold-start
warm-up, multi-thousand-hour durability runs, and free-acceleration
transients.

### 8. Sound — `acoustics.py`

Every source is driven by a quantity the solver already computed:

| you hear | it comes from |
|---|---|
| exhaust note | ṁ through the exhaust valve → 1-D waveguide (delay + open-end reflection + wall loss) → reactive muffler |
| intake roar | ṁ through the intake valve → runner quarter-wave → airbox Helmholtz resonance → turbulent filter hiss ∝ ṁ³ |
| diesel clatter | `dp/dθ` exciting block/head structural modes — the sharper the pressure rise, the more the high modes light up |
| injector tick | the commanded injection events |
| valvetrain tick | cam seating velocity, growing as lash wears open |
| piston slap | thrust reversal of the rod side force, scaled by skirt clearance |
| turbo whine | shaft order of the live turbo speed (blade-pass is usually ultrasonic and is only included when it lands below Nyquist) |
| gear whine | tooth-mesh frequency of the timing gear train |
| rumble | boundary-friction power, firing-modulated |

Synthesis happens in the **crank-angle domain** and is then resampled through
the instantaneous engine speed by integrating the crank phase. Pitch
therefore tracks rpm exactly — a rev sweep or a tip-in sounds right without
any pitch shifting, and the engine orders fan out correctly on a
spectrogram.

Five microphone positions are provided: `exhaust_tip`, `intake`,
`engine_bay`, `cabin`, `exterior_7m`.

---

## Usage

```python
from dieselsim.engine import DieselEngine
from dieselsim.acoustics import EngineSound

eng = DieselEngine(preset="hd_i6")      # or "crdi15", "crdi_1p5", "ld_i4", "single"

op = eng.operating_point(1500, load=1.0)
print(op)
# 1500 rpm | 2241.0 N.m | 352.0 kW | BMEP 22.10 bar | BSFC 214.3 g/kWh ...

snd = EngineSound(eng.spec)
y, sources = snd.render(op, duration=4.0, mic="exterior_7m")
snd.write_wav("full_load.wav", y)
```

Sweeping something physical:

```python
for egr in (0.0, 0.5, 1.0):
    o = eng.operating_point(1400, load=0.65, egr=egr)
    print(o.egr_pct, o.nox_g_kwh, o.soot_g_kwh, o.bsfc)
```

Ageing it:

```python
log = eng.durability_run(8000.0)        # hours, with oil changes
```

Free acceleration:

```python
tl = eng.transient(3.0,
                   throttle_fn=lambda t: 0.08 if t < 0.5 else 1.0,
                   load_torque_fn=lambda t, rpm: 380 + 0.28*rpm + 2.6e-4*rpm**2)
wav = snd.render_transient(eng, tl)
```

Run `python3 demo.py <outdir>` to generate every figure and audio file.

### Your own engine, from brochure numbers (ADR-014)

Write the numbers as JSON, in the same format as the Enjoy roster
(`engines/*.json`), plus the vehicle it should drive in:

```json
{"key": "my20", "name": "2.0 L four, 140 ps", "displacement": 2.0, "n_cyl": 4,
 "rated_rpm": 4000, "peak_torque": 320, "peak_power": 103, "plateau": [1750, 2500],
 "vehicle": "crdi15"}
```

- `vehicle` is one of `hatch15` (1.3 t hatchback), `crdi15` (1.5 t compact),
  `ld_i4` (1.75 t car), `crdi22` (1.9 t SUV), `hd_i6` (40 t truck) or
  `tractor` (3 t utility tractor).
- The other keys are `builder.build_engine`'s parameters. The roster files
  show the optional tuning, such as `afr_limit` and `boost_map_rise`.

Check what the engine actually makes. The builder sizes the hardware, but
the solver decides what it delivers:

```python
from dieselsim.builder import from_dict, verify
import json
verify(from_dict(json.load(open("my20.json"))))
```

Then build the grid the real-time drive needs, and drive it:

```bash
python3 tools/build_live_grids.py --engine my20.json    # ~15 min on 6 cores -> out/grids/my20.json
```

On `/drive` or `/enjoy`, choose the grid file under "Custom engine" (or
"Your own engine"). The app refuses a file that is not a converged grid, or
that names no known vehicle, and says why.

---

## Does it produce sensible numbers?

12.74 L heavy-duty inline-6, VGT, cooled EGR. Measured on 2026-09-29 with
`tools/validate_table.py` (fresh engine per point, 9 cycles, the way the app
solves), which re-runs this table on any tree:

| quantity | simulated | typical real HD diesel |
|---|---|---|
| peak torque | 2313 N·m @ 1700 rpm | 2000–2500 N·m |
| rated power | 432 kW @ 1800 rpm | 350–450 kW |
| peak BMEP | 22.8 bar | 20–24 bar |
| best BSFC | 200 g/kWh @ 1800 rpm, half load | 190–215 g/kWh |
| peak cylinder pressure | 179 bar | 160–200 bar |
| FMEP at rated | 1.10 bar | 0.9–1.5 bar |
| mechanical efficiency | 95 % @ rated, 91 % @ 700 rpm | 88–95 % |
| volumetric efficiency | 1.18 (boosted) | 1.1–1.3 |
| engine-out NOx | 4.4 g/kWh @ rated, 15.6 g/kWh lugging (1000 rpm) | 4–20 g/kWh |
| engine-out soot | 0.047 g/kWh | 0.02–0.08 g/kWh |
| blow-by, new engine | 11.7 L/min | 8–20 L/min |
| wall heat loss | 18 % of fuel energy | 15–25 % |

The trends behave too, which matters more than any single number:

- **EGR trade-off.** Adding ~18 % EGR cuts NOx by ~70 % (7.1 → 2.2 g/kWh at
  1400 rpm, 65 % load), raises soot (+5 %) and costs fuel (+2 % BSFC). This is not scripted anywhere — it falls out of the dilution
  lowering the flame temperature (more inert mass to heat per kg of fuel)
  while simultaneously displacing oxygen in the Zeldovich and Hiroyasu terms.
- **Cold start.** Thick oil raises FMEP sharply and boundary-friction wear
  rises by more than an order of magnitude below 40 °C.
- **Turbo lag.** A tip-in from idle shows boost building over ~0.7 s, AFR
  diving toward the smoke limit, and a soot spike — the black puff.
- **Ageing.** Over 8000 h, ring gap opens, blow-by rises, oil pressure falls,
  oil consumption climbs and rated power decays.

---

## Honest limitations

- The burned zone is "two-zone-lite": one lumped burned region with air
  entrainment, not a multi-zone spray model. NOx is therefore calibrated
  through one constant, and soot through another.
- The manifolds are finite-volume (filling-and-emptying), not 1-D gas
  dynamics. Ram tuning and pulse converter effects are approximated, and the
  acoustic waveguide is a separate downstream model rather than being solved
  with the flow.
- Compressor and turbine maps are similitude-generated, not measured.
- The structural response in the sound engine is a bank of modal resonators
  with assumed frequencies — a real one would come from an FE model of the
  block.
- Wear coefficients are literature values, not measurements from your engine.
- Combustion is a Wiebe parameterisation informed by physics, not a CFD spray
  and chemistry solve. Getting rid of that assumption is the single biggest
  fidelity upgrade available.

---

## Files

```
dieselsim/          the solver: numpy only, runs unmodified under Pyodide
  config.py         specification dataclasses + presets
  builder.py        a new engine from the numbers on the brochure
  overrides.py      validated spec overrides
  thermo.py         gas properties, fuel, compressible flow
  kinematics.py     slider-crank and cam profiles
  lubrication.py    viscosity, films, bearings, oil ageing
  wear.py           Archard wear and its feedback into everything else
  friction.py       crank-resolved component friction
  turbo.py          compressor, turbine, shaft dynamics
  cycle.py          the crank-angle first-law solver
  engine.py         governor, flywheel, maps, durability, transients
  acoustics.py      physics-driven sound synthesis (offline render)
  grid.py           one cell of the real-time (rpm x load) grid
  live.py           the real-time loop: vehicle, gearboxes, driveline, LiveEngine
  livesound.py      the engine sound, streamed block by block
  bridge.py         the Python side of the browser's SolverPort contract
  batch.py          many independent operating points at once (native only)
web/
  app/              the Angular app: dyno, grid, drive (see web/app/README.md)
  physics/          TypeScript ports (live loop, friction, synth), held to Python by fixtures
  solver/           the SolverPort: Pyodide worker, grid cache
tools/              fixtures, grid builder, audits, diagnostics
tests/              the regression suite (test_physics.py)
reviews/            findings and phase reviews
play.py             drive an engine in the terminal, with sound
demo.py             generates every figure and wav file
```
