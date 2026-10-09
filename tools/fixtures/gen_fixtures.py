"""
Golden fixtures for the TypeScript ports (ADR-004): input/output pairs from
the Python original, which every port is tested against.

  kinematics.json  slider-crank (every preset + one with a pin offset) and
                   cam lift (every preset, both cams)   tolerance 1e-12 rel
  thermo.json      gas properties, energy, u -> T inversion, orifice and
                   valve flow                           tolerance 1e-10 rel
  friction.json    grid.cell_friction() from stored pressure traces at warm
                   and cold oil (ADR-011): the reference for the Phase 3
                   port of the friction model            tolerance 1e-6 rel
  live.json        the real-time loop (dieselsim/live.py): scripted 60 s
                   drives on a stored grid. Per-step snapshots (state
                   before and after sampled steps) for the per-step bound,
                   events and final integrated quantities for the terminal
                   bound (ADR-004 addendum)                 --check 1e-6 rel

Each file records the physics source hash (bridge.source_hash) and the
generator's numpy version.

Run:  python3 tools/fixtures/gen_fixtures.py           (write)
      python3 tools/fixtures/gen_fixtures.py --check   (CI: recompute from
            each file's stored inputs and fail if any output has moved
            beyond its module's tolerance -- i.e. the physics changed and
            the fixtures were not regenerated)

The --check comparison is numeric, not textual: Linux and macOS libm may
differ in the last ulp, which is far inside every tolerance here.
"""
import copy
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, ROOT)
from dieselsim import thermo  # noqa: E402
from dieselsim.bridge import source_hash  # noqa: E402
from dieselsim.config import PRESETS  # noqa: E402
from dieselsim.engine import DieselEngine  # noqa: E402
from dieselsim.kinematics import Cam, SliderCrank  # noqa: E402

OUT = os.path.join(ROOT, "web", "physics", "fixtures")
TOL = {"kinematics": 1e-12, "thermo": 1e-10, "friction": 1e-6, "live": 1e-6, "sound": 1e-12, "vehicles": 0.0}
EPS = float(np.finfo(float).eps)
# Finite-difference outputs are compared at the rounding bound propagated
# through their stencil, not at the module tolerance. A lift sample may
# differ by up to 4 ulp of lift_max between two libms (1 ulp in sin, doubled
# by the square, plus two roundings), so the central first difference over
# 2h can differ by 4*eps*Lmax/h and the 1,-2,1 second difference by
# 16*eps*Lmax/h^2. Near an inflection that is ~1e-10 of the series' largest
# value -- between two Python builds on different libms as much as between
# Python and JS (web/physics/test/fixtures.test.ts uses the same bounds).
FD_KEYS = {"dlift_dtheta": (4.0, math.radians(0.05), 1), "d2lift_dtheta2": (16.0, math.radians(0.10), 2)}


def meta(module):
    return {"module": module, "tolerance_rel": TOL[module], "physics_hash": source_hash(),
            "numpy": np.__version__, "generator": "tools/fixtures/gen_fixtures.py"}


def lst(a):
    return [float(x) for x in np.asarray(a, dtype=float).ravel()]


# ---------------------------------------------------------------- kinematics
def kinematics_inputs():
    th = [float(x) for x in np.linspace(0.0, 4.0 * math.pi, 97)]     # radians, two revolutions
    deg = [float(x) for x in np.arange(0.0, 720.0, 0.91)]            # crank degrees
    cranks, cams = [], []
    for key in sorted(PRESETS):
        g = DieselEngine(preset=key).spec.geom
        cranks.append(dict(name=key, a=g.crank_radius, l=g.conrod, e=g.pin_offset,
                           Ap=g.piston_area, Vc=g.clearance_volume))
        cyc = DieselEngine(preset=key).cycle
        for cam, which in ((cyc.cam_int, "intake"), (cyc.cam_exh, "exhaust")):
            cams.append(dict(name=f"{key} {which}", open_deg=cam.open_deg, close_deg=cam.close_deg,
                             lift_max=cam.lift_max, lash=cam.lash, ramp=cam.ramp,
                             ramp_height=cam.ramp_height))
    g = DieselEngine(preset="crdi15").spec.geom
    cranks.append(dict(name="crdi15, 0.6 mm pin offset", a=g.crank_radius, l=g.conrod, e=0.6e-3,
                       Ap=g.piston_area, Vc=g.clearance_volume))
    # a cam whose lash is taller than its ramp, so the off-ramp seating branch is covered
    cams.append(dict(name="lash above ramp", open_deg=700.0, close_deg=230.0, lift_max=0.012,
                     lash=0.4e-3, ramp=0.06))
    return dict(theta_rad=th, theta_deg=deg, omega=[10.0, 150.0, 400.0], cranks=cranks, cams=cams)


class _Geom:
    def __init__(self, c):
        self.crank_radius, self.conrod, self.pin_offset = c["a"], c["l"], c["e"]
        self.piston_area, self.clearance_volume = c["Ap"], c["Vc"]


def kinematics_outputs(inp):
    th = np.asarray(inp["theta_rad"])
    deg = np.asarray(inp["theta_deg"])
    out = {"cranks": [], "cams": []}
    for c in inp["cranks"]:
        sc = SliderCrank(_Geom(c))
        out["cranks"].append(dict(displacement=lst(sc.displacement(th)), dx_dtheta=lst(sc.dx_dtheta(th)),
                                  d2x_dtheta2=lst(sc.d2x_dtheta2(th)), volume=lst(sc.volume(th)),
                                  dV_dtheta=lst(sc.dV_dtheta(th)), beta=lst(sc.beta(th))))
    for c in inp["cams"]:
        cam = Cam(c["open_deg"], c["close_deg"], c["lift_max"], c["lash"], c["ramp"],
                  ramp_height=c.get("ramp_height"))
        out["cams"].append(dict(h_ramp=cam.h_ramp, dur=cam.dur, lift=lst(cam.lift(deg)),
                                cam_lift=lst(cam.cam_lift(deg)), dlift_dtheta=lst(cam.dlift_dtheta(deg)),
                                d2lift_dtheta2=lst(cam.d2lift_dtheta2(deg)),
                                seating_velocity=[cam.seating_velocity(w) for w in inp["omega"]]))
    return out


# -------------------------------------------------------------------- thermo
def thermo_inputs():
    T = [float(x) for x in np.linspace(250.0, 3000.0, 56)]
    yb = [0.0, 0.05, 0.3, 0.7, 1.0]
    orifice = []
    for p_up, T_up, p_dn, A, g, R in ((2.0e5, 300.0, 1.0e5, 1e-4, 1.4, 287.05),     # choked
                                      (1.2e5, 350.0, 1.0e5, 2e-4, 1.38, 287.05),    # subsonic
                                      (1.0e5, 400.0, 1.0e5, 1e-4, 1.35, 286.0),     # no dP
                                      (3.0e5, 50.0, 2.0e5, 5e-5, 1.33, 286.0),      # T floor
                                      (1.0e5, 300.0, 2.0e5, 1e-4, 1.4, 287.05),     # reversed: pr clipped
                                      (1.0e5, 300.0, 0.5e5, 0.0, 1.4, 287.05)):     # zero area
        orifice.append(dict(p_up=p_up, T_up=T_up, p_dn=p_dn, A=A, gamma=g, R=R))
    signed = [dict(p1=1.5e5, T1=320.0, yb1=0.1, p2=1.2e5, T2=900.0, yb2=0.8, A=3e-4),
              dict(p1=1.1e5, T1=320.0, yb1=0.1, p2=2.4e5, T2=900.0, yb2=0.8, A=3e-4),
              dict(p1=1.1e5, T1=320.0, yb1=0.1, p2=2.4e5, T2=900.0, yb2=0.8, A=0.0)]
    valve = [dict(lift=L, dia=0.042, n=2, cd=0.62) for L in (0.0, 1e-4, 1e-3, 4e-3, 12e-3)]
    u_targets = [dict(u=u, yb=y) for u, y in ((2.0e5, 0.0), (9.0e5, 0.4), (1.9e6, 1.0), (-1.0e4, 0.0))]
    return dict(T=T, yb=yb, orifice=orifice, signed=signed, valve=valve, u_targets=u_targets,
                p_T=[dict(p=p, T=t) for p, t in ((1e5, 298.0), (3e5, 330.0))])


def thermo_outputs(inp):
    T, yb = inp["T"], inp["yb"]
    grid = lambda f: [[float(f(t, y)) for t in T] for y in yb]   # noqa: E731
    return dict(cp_air=[thermo.cp_air(t) for t in T], cp_burned=[thermo.cp_burned(t) for t in T],
                gas_R=[thermo.gas_R(y) for y in yb], cp_mix=grid(thermo.cp_mix),
                gamma_mix=grid(thermo.gamma_mix), u_mix=grid(thermo.u_mix), h_mix=grid(thermo.h_mix),
                speed_of_sound=grid(thermo.speed_of_sound),
                air_viscosity=[thermo.air_viscosity(t) for t in T],
                air_density=[thermo.air_density(d["p"], d["T"]) for d in inp["p_T"]],
                T_from_u=[thermo.T_from_u(d["u"], d["yb"]) for d in inp["u_targets"]],
                orifice_mdot=[thermo.orifice_mdot(d["p_up"], d["T_up"], d["p_dn"], d["A"], d["gamma"], d["R"])
                              for d in inp["orifice"]],
                signed_orifice=[list(thermo.signed_orifice(d["p1"], d["T1"], d["yb1"], d["p2"], d["T2"],
                                                           d["yb2"], d["A"])) for d in inp["signed"]],
                valve_effective_area=[thermo.valve_effective_area(d["lift"], d["dia"], d["n"], d["cd"])
                                      for d in inp["valve"]])


# ------------------------------------------------------------------ friction
FRICTION_KEYS = ("fmep", "P_friction", "P_mech", "P_rings", "P_skirt", "P_mains", "P_rods", "P_pin",
                 "P_valvetrain", "P_windage", "P_accessories", "P_oilpump", "P_fuelpump",
                 "Pb_rings", "Pb_skirt", "Pb_rods", "Pb_mains", "Pb_pin", "Pb_valvetrain",
                 "h_ring", "h_rod", "h_main", "h_skirt", "h_ring_mid", "lambda_ring",
                 "gallery_pressure", "v_seating")


# moved to the package (ADR-014 step 3: the browser builds grids too)
from dieselsim.bridge import friction_engine_view  # noqa: E402


FRICTION_CASES = (("crdi15", 1800.0, 0.6, 373.0, None), ("crdi15", 1800.0, 0.6, 273.0, None),
                  ("hd_i6", 1300.0, 1.0, 373.0, None), ("hd_i6", 1300.0, 1.0, 273.0, None),
                  ("crdi15", 1800.0, 0.6, 300.0, 300.0),           # cold coolant moves the walls
                  ("single", 2000.0, 0.8, 373.0, None))            # flat tappet


def _friction_engine(preset, T_oil, T_coolant):
    eng = DieselEngine(preset=preset)
    eng.oil.cond.T_oil = T_oil
    if T_coolant is not None:
        eng.T_coolant = T_coolant
        eng._apply_thermal_state()
    return eng


def friction_inputs():
    from dieselsim.acoustics import EngineSound
    from dieselsim.grid import solve_cell
    cases, solved = [], {}
    for preset, rpm, load, T_oil, T_cool in FRICTION_CASES:
        spec = DieselEngine(preset=preset).spec
        if (preset, rpm, load) not in solved:
            src, perf = solve_cell(spec, rpm, load)
            solved[(preset, rpm, load)] = (src, perf, EngineSound(spec).grid)
        src, perf, grid = solved[(preset, rpm, load)]
        eng = _friction_engine(preset, T_oil, T_cool)
        cases.append(dict(preset=preset, rpm=rpm, T_oil=T_oil, T_coolant=T_cool, fuel_mg=float(perf["fuel_mg"]),
                          p_rail=float(perf["p_rail"]), grid_deg=lst(grid), p_cyl=lst(src["p_cyl"]),
                          engine=friction_engine_view(eng)))
    return dict(cases=cases)


def friction_outputs(inp):
    from dieselsim.grid import cell_friction
    out = []
    for c in inp["cases"]:
        eng = _friction_engine(c["preset"], c["T_oil"], c.get("T_coolant"))
        r = cell_friction(eng, c["rpm"], c["p_cyl"], c["grid_deg"], c["fuel_mg"], c["p_rail"])
        out.append({k: float(r[k]) for k in FRICTION_KEYS if k in r})
    return out


# ---------------------------------------------------------------------- live
LIVE_DT, LIVE_N = 1.0 / 60.0, 3600
LIVE_SKIP = {"g", "spec", "veh", "lock", "dl", "tc", "gb"}     # structure, not state


def _grid_cell(task):
    from dieselsim.grid import solve_cell
    key, rpm, load = task
    spec = DieselEngine(preset=key).spec
    return solve_cell(spec, rpm, load)[1]


def _row_limit(task):
    key, rpm = task
    return DieselEngine(preset=key).fuel_limit(rpm)


def _adr011_cell(task):
    """One ADR-011 cell: perf and the cylinder-1 trace, at a coolant
    temperature, on the row's shared full-load fuel."""
    from dieselsim.grid import solve_cell
    key, rpm, load, flim, T_cool = task
    spec = DieselEngine(preset=key).spec
    src, perf = solve_cell(spec, rpm, load, fuel_limit=flim, T_coolant=T_cool)
    return {k: float(v) for k, v in perf.items()}, np.asarray(src["p_cyl"], dtype="<f4").tobytes()


LIVE_GRID = os.path.join(OUT, "live_grid.json")
ADR011_T_COLD = 273.0


def live_grid_adr011(key="crdi15"):
    """The ADR-011 grid for the live fixture: warm and cold cells with their
    pressure traces (base64 float32, as grids store them). Built once into
    fixtures/live_grid.json and reused; --regrid rebuilds it."""
    import base64
    from multiprocessing import get_context
    from dieselsim.acoustics import EngineSound
    if os.path.exists(LIVE_GRID) and "--regrid" not in sys.argv:
        with open(LIVE_GRID) as fh:
            return json.load(fh)
    spec = DieselEngine(preset=key).spec
    rpms = [float(x) for x in np.linspace(spec.idle_rpm, spec.max_rpm, 8)]
    loads = [float(x) for x in np.linspace(0.0, 1.0, 6)]
    with get_context("spawn").Pool(min(6, os.cpu_count() or 1)) as pool:
        flims = pool.map(_row_limit, [(key, r) for r in rpms])
        out = {}
        for tag, T in (("warm", None), ("cold", ADR011_T_COLD)):
            cells = pool.map(_adr011_cell, [(key, r, l, f, T) for r, f in zip(rpms, flims) for l in loads])
            out[tag] = cells
    shape = lambda cells, k: [[cells[i * len(loads) + j][k] for j in range(len(loads))]  # noqa: E731
                              for i in range(len(rpms))]
    b64 = lambda cells: [[base64.b64encode(c).decode() for c in row] for row in shape(cells, 1)]  # noqa: E731
    grid = {"preset": key, "rpms": rpms, "loads": loads, "fuel_limits": flims,
            "T_warm": spec.thermal.coolant_T, "T_cold": ADR011_T_COLD,
            "grid_deg": lst(EngineSound(spec).grid),
            "perf": shape(out["warm"], 0), "perf_cold": shape(out["cold"], 0),
            "p_cyl_f32": b64(out["warm"]), "p_cyl_cold_f32": b64(out["cold"]),
            "physics_hash": source_hash()}
    with open(LIVE_GRID, "w") as fh:
        json.dump(grid, fh, separators=(",", ":"))
        fh.write("\n")
    return grid


def live_weather_table(gj, key="crdi15"):
    """Phase 7 step 4: a weather table for the live fixture's grid, assembled by
    bridge.live_weather_assemble (the real format) from deterministic synthetic
    pieces -- non-linear in the air and different per cell, so both loops'
    blending is exercised. No solves: the fixture tests the port, not physics."""
    from dieselsim import bridge
    plan = json.loads(bridge.live_weather_plan(json.dumps({"rpms": gj["rpms"], "loads": gj["loads"]})))
    k_t = DieselEngine(preset=key).spec.geom.displacement / (4.0 * math.pi)
    pieces = []
    for q in plan["pieces"]:
        c = gj["perf"][q["i"]][q["j"]]
        x, y = (q["p"] - 101325.0) / 43325.0, (q["T"] - 298.0) / 45.0      # about -1..0 and -1..0.45
        s = 1.0 + 0.1 * q["i"] + 0.05 * q["j"]
        std = [c["torque"] + c["fmep"] * k_t, c["fuel_kg_h"], c["boost"], c["turbo_rpm"], c["afr"], c["T_exh"]]
        off = [s * (40.0 * x + 6.0 * x * x - 9.0 * y), -0.4 * s * x * x, s * (-0.9 * x + 0.1 * y),
               s * (-6.0e4 * x + 4.0e3 * y), s * (12.0 * x - 3.0 * y * x), s * (-60.0 * x + 25.0 * y)]
        pieces.append({"values": [a + b for a, b in zip(std, off)], "settled": 1.0})
    return json.loads(bridge.live_weather_assemble(json.dumps({
        "engine": {"preset": key}, "grid": {k: gj[k] for k in ("rpms", "loads", "perf")}, "pieces": pieces})))


def adr011_grid_object(gj):
    from dieselsim.live import Adr011Grid
    return Adr011Grid.from_json(gj)


def live_state(live):
    """Every scalar the loop carries, nested as the Python objects are."""
    def pick(o):
        out = {}
        for k, v in vars(o).items():
            if k in LIVE_SKIP:
                continue
            if isinstance(v, (bool, np.bool_, str)) or v is None:
                # numpy.bool_ too: `tank_L <= 0.0` on a numpy float yields one
                out[k] = bool(v) if isinstance(v, np.bool_) else v
            elif isinstance(v, (int, float, np.integer, np.floating)):
                out[k] = float(v) if isinstance(v, (float, np.floating)) else int(v)
            elif isinstance(v, dict):
                out[k] = {kk: float(vv) for kk, vv in v.items()}
        return out
    return {"live": pick(live), "dl": pick(live.dl), "gb": pick(live.dl.gb), "tc": pick(live.dl.tc)}


def live_script_hot():
    """A second drive, for what the first never reaches: a warm engine
    (coolant starts at 368 K, just above the fan-on point of 367 K, so the fan engages and later drops out as the radiator pulls the coolant under 362 K), a light-throttle cruise that
    upshifts early into a high gear, a full-throttle stab there (a kickdown
    that may skip two gears), then a long full-throttle 10 % climb that heats
    the coolant through the fan's switching band."""
    def thr(t):
        return 0.0 if t < 1 else 0.35 if t < 25 else 1.0
    return {"dt": LIVE_DT, "n": LIVE_N, "throttle": [thr(n * LIVE_DT) for n in range(LIVE_N)],
            "brake": [], "grade": [[int(round(26.0 / LIVE_DT)), 0.10]], "keys": [[int(round(40.0 / LIVE_DT)), "l"]]}


def live_script_kickdown():
    """A 10 s case for the kickdown's skip order: a converter car in 6th at
    72 km/h (turbine ~1750 rpm, inside both shift thresholds at zero
    throttle), throttle off for 1 s, then a full stab. Two gears down (4th,
    ~2610 rpm) is under the 0.95 x rated guard, so it must skip two."""
    n = 600
    return {"dt": LIVE_DT, "n": n, "throttle": [0.0 if k * LIVE_DT < 1.0 else 1.0 for k in range(n)],
            "brake": [], "grade": [], "keys": []}


def live_script_manual():
    """The manual box, 60 s: clutch held while 1st is selected, a slipping
    launch, shifts with the clutch, a shift refused without it, braking to a
    stop in 3rd (a stall), a refused and a proper restart, two downshifts,
    a second launch, then the auto-clutch: a launch, two assisted shifts
    and braking to a stop without stalling."""
    def thr(t):
        return (0.0 if t < 1.8 else 0.35 if t < 8 else 0.5 if t < 20 else 0.0 if t < 36 else
                0.4 if t < 41 else 0.0 if t < 42.5 else 0.6 if t < 52 else 0.0)
    taps = ((1.0, "."), (8.2, "."), (14.0, "."), (14.7, "."), (33.0, "i"), (34.5, "i"), (35.0, ","),
            (35.3, ","), (40.3, "i"), (41.0, "x"), (42.0, "a"), (44.0, "."), (48.0, "."), (59.0, "n"))
    return {"dt": LIVE_DT, "n": LIVE_N, "throttle": [thr(n * LIVE_DT) for n in range(LIVE_N)],
            "brake": [[24.0, 32.0, 0.8], [41.0, 42.5, 0.8], [52.0, 58.0, 0.5]], "grade": [],
            "keys": [[int(round(t / LIVE_DT)), k] for t, k in taps],
            "holds": [[0.0, 2.0, "z"], [8.0, 8.4, "z"], [14.5, 14.9, "z"], [34.0, 36.0, "z"], [40.0, 40.6, "z"]]}


def live_script():
    """The scripted drive: throttle per step (applied only while cruise is
    off), a brake window, a grade step and key presses -- the drive P3-1
    proved bit-identical across the move out of play.py."""
    def thr(t):
        return 0.0 if t < 1 else 1.0 if t < 12 else 0.3 if t < 20 else 1.0 if t < 26 else 0.0 if t < 34 else 0.7
    keys = [[int(round(t / LIVE_DT)), k] for t, k in ((27.0, "e"), (33.0, "e"), (40.0, "l"), (45.0, "c"),
                                                   (48.0, "+"), (52.0, "."), (55.0, ","), (57.0, "n"),
                                                   (58.5, "n"), (59.0, "m"))]
    return {"dt": LIVE_DT, "n": LIVE_N, "throttle": [thr(n * LIVE_DT) for n in range(LIVE_N)],
            "brake": [[30.0, 34.0, 0.6]], "grade": [[int(round(34.0 / LIVE_DT)), 0.06]], "keys": keys}


def live_inputs():
    import dataclasses
    from multiprocessing import get_context
    key = "crdi15"
    spec = DieselEngine(preset=key).spec
    rpms = [float(x) for x in np.linspace(spec.idle_rpm, spec.max_rpm, 8)]
    loads = [float(x) for x in np.linspace(0.0, 1.0, 6)]
    tasks = [(key, r, l) for r in rpms for l in loads]
    with get_context("spawn").Pool(min(6, os.cpu_count() or 1)) as pool:
        cells = pool.map(_grid_cell, tasks)
    perf = [[{k: float(v) for k, v in cells[i * len(loads) + j].items()} for j in range(len(loads))]
            for i in range(len(rpms))]
    spec_json = json.loads(json.dumps(dataclasses.asdict(spec), default=float))
    # properties, not fields, so asdict() leaves them out; the loop reads them
    spec_json["geom"]["displacement"] = spec.geom.displacement
    return {"preset": key, "spec": spec_json, "engine_view": friction_engine_view(DieselEngine(preset=key)),
            "grid": {"rpms": rpms, "loads": loads, "perf": perf},
            "drives": [{"name": "tc", "trans": "tc", "script": live_script(), "init": {}},
                       {"name": "dct", "trans": "dct", "script": live_script(), "init": {}},
                       {"name": "dct_hot", "trans": "dct", "script": live_script_hot(),
                        "init": {"T_coolant": 368.0}},
                       {"name": "manual", "trans": "manual", "script": live_script_manual(), "init": {}},
                       {"name": "adr011_cold", "trans": "tc", "grid": "adr011", "script": live_script(), "init": {}},
                       {"name": "adr011_warm", "trans": "dct", "grid": "adr011", "script": live_script(),
                        "init": {"T_coolant": 361.0, "T_oil": 373.0}},
                       # Phase 7 step 4: Leh's air, through the weather table
                       {"name": "adr011_weather", "trans": "dct", "grid": "adr011", "air": [65764.1, 293.15],
                        "script": live_script(), "init": {"T_coolant": 361.0, "T_oil": 373.0}},
                       {"name": "tc_kickdown", "trans": "tc", "script": live_script_kickdown(),
                        "init": {"dl.v": 20.0, "dl.gb.gear": 5, "dl.gb.gear_from": 5,
                                 "dl.w_in": 20.0 / 0.315 * 0.67 * 4.30, "rpm": 20.0 / 0.315 * 0.67 * 4.30 * 60.0 / (2.0 * math.pi)}}],
            "weather_table": live_weather_table(live_grid_adr011(key)),
            "sample_every": 45}


def live_run(inp, drv):
    from dieselsim.live import LiveEngine, PerfGrid, handle_key, pedal_return
    spec = DieselEngine(preset=inp["preset"]).spec
    g = inp["grid"]
    grid = (adr011_grid_object(live_grid_adr011(inp["preset"])) if drv.get("grid") == "adr011"
            else PerfGrid(spec, g["rpms"], g["loads"], g["perf"]))
    if drv.get("air"):                    # Phase 7 step 4: the weather table, at this air
        from dieselsim.live import WeatherTable
        grid.weather = WeatherTable(grid.rpms, grid.loads, inp["weather_table"])
        grid.spec = copy.deepcopy(grid.spec)
        grid.spec.thermal.ambient_p, grid.spec.thermal.ambient_T = drv["air"]
    live = LiveEngine(grid, inp["preset"], trans=drv["trans"])
    for k, v in drv["init"].items():      # dotted paths: "dl.gb.gear"
        *path, last = k.split(".")
        obj = live
        for p in path:
            obj = getattr(obj, p)
        setattr(obj, last, v)
    if live.adr011 and drv["init"]:
        live._update_friction()           # at the initial state just set
    sc = drv["script"]
    keys = {k: c for k, c in sc["keys"]}
    grade = {k: v for k, v in sc["grade"]}
    dt = sc["dt"]
    snaps, events, trace, hints = [], [], [], []
    prev, prev_hint = None, ""
    for n in range(sc["n"]):
        t = n * dt
        if not live.cruise_on:
            live.throttle = sc["throttle"][n]
        for t0, t1, b in sc["brake"]:
            if t0 <= t < t1:
                live.dl.brake = b
        if n in grade:
            live.dl.grade = grade[n]
        for t0, t1, k in sc.get("holds", []):      # a held key repeats every frame
            if t0 <= t < t1:
                handle_key(live, k)
        if n in keys:
            handle_key(live, keys[n])
        pedal_return(live, dt)
        before = live_state(live) if n % inp["sample_every"] == 0 else None
        live.step(dt)
        ev = (live.dl.gb.gear, live.dl.gb.phase, bool(live.dl.lockup), bool(live.dl.rigid), bool(live.dl.gb.neutral),
              bool(live.dl.lock_allowed), bool(live.fan_on), bool(live.stalled), bool(live.dl.assist))
        if live.hint != prev_hint:
            hints.append([n, live.hint])
            prev_hint = live.hint
        if ev != prev:
            events.append([n] + [int(x) for x in ev])
            prev = ev
        if before is not None:
            snaps.append({"step": n, "before": before, "after": live_state(live)})
        if n % 6 == 0:
            trace.append([n, float(live.rpm), float(live.dl.v), float(live.T_coolant), float(live.trip_L)])
    final = {k: float(getattr(live, k)) for k in ("rpm", "odo_m", "trip_m", "fuel_L", "trip_L", "T_coolant",
                                                  "boost", "turbo_rpm", "tank_L", "inst_kmpl", "fan_frac",
                                                  "fan_power", "derate", "T_oil", "fmep_live")}
    final["v"] = float(live.dl.v)
    veh = {k: v for k, v in vars(live.dl.veh).items()}
    return {"veh": veh, "snapshots": snaps, "events": events, "hints": hints, "trace": trace, "final": final}


def live_outputs(inp):
    return {d["name"]: live_run(inp, d) for d in inp["drives"]}


# --------------------------------------------------------------------- sound
def _sound_cell(task):
    """One fast cell for the sound fixture: perf, trace and acoustic sources."""
    import base64
    from dieselsim.grid import solve_cell
    from dieselsim.livesound import SOURCE_KEYS
    key, rpm, load, T_cool = task
    spec = DieselEngine(preset=key).spec
    src, perf = solve_cell(spec, rpm, load, T_coolant=T_cool)
    b64 = lambda a: base64.b64encode(np.asarray(a, dtype="<f4").tobytes()).decode()  # noqa: E731
    return ({k: float(v) for k, v in perf.items()}, b64(src["p_cyl"]),
            {k: b64(src[k]) for k in SOURCE_KEYS}, {k: float(v) for k, v in src["_meta"].items()})


def sound_inputs():
    """Phase 4: a 2 x 2 hd_i6 grid, warm and cold, in the prebuilt grids'
    form (Adr011GridData with its acoustic sources), and the points to blend
    it at: inside the cell part-cold, on a node warm, and clamped outside
    (above max rpm, below the cold coolant)."""
    from multiprocessing import get_context
    from dieselsim.acoustics import EngineSound
    key = "hd_i6"
    spec = DieselEngine(preset=key).spec
    rpms, loads = [900.0, 1600.0], [0.2, 0.9]
    grid = {"preset": key, "rpms": rpms, "loads": loads, "T_warm": spec.thermal.coolant_T,
            "T_cold": ADR011_T_COLD, "grid_deg": lst(EngineSound(spec).grid)}
    with get_context("spawn").Pool(min(8, os.cpu_count() or 1)) as pool:
        for tag, T in (("", None), ("_cold", ADR011_T_COLD)):
            cells = pool.map(_sound_cell, [(key, r, ld, T) for r in rpms for ld in loads])
            shape = lambda n: [[cells[i * 2 + j][n] for j in range(2)] for i in range(2)]  # noqa: E731
            grid["perf" + tag], grid["p_cyl" + tag + "_f32"] = shape(0), shape(1)
            grid["src" + tag + "_f32"], grid["src_meta" + tag] = shape(2), shape(3)
    import dataclasses
    live_spec = json.loads(json.dumps(dataclasses.asdict(spec), default=float))
    live_spec["geom"]["displacement"] = spec.geom.displacement
    from dieselsim.acoustics import MICS, SPL_CAL
    mics = {k: {"gains": dict(m.gains), "lp_hz": m.lp_hz, "hp_hz": m.hp_hz, "distance_m": m.distance_m,
                "reverb": m.reverb} for k, m in MICS.items()}
    live = {"boost": 1.3, "turbo_rpm": 6.0e4, "load": 0.3, "Pb": 400.0, "skirt_clr": 2.0e-5, "v_seating": 0.05}
    # the streaming synth, driven block by block: a run-up, a glide to a
    # new point with a microphone change (reverb), a stall, and a restart
    # below the turbo's threshold on a third microphone
    segments = [
        {"blocks": 60, "rpm": [750.0, 1300.0], "blend": [900.0, 0.3, 300.0], "live": live, "running": True},
        {"blocks": 40, "rpm": [1300.0, 1600.0], "blend": [1500.0, 0.85, 350.0], "mic": "cabin",
         "live": dict(live, boost=2.1, turbo_rpm=1.1e5, load=0.85, Pb=900.0), "running": True},
        {"blocks": 16, "rpm": [1600.0, 600.0], "running": False},
        {"blocks": 50, "rpm": [600.0, 900.0], "blend": [800.0, 0.1, 280.0], "mic": "engine_bay",
         "live": dict(live, turbo_rpm=500.0, boost=1.0, load=0.1), "running": True},
    ]
    return {"spec": live_spec, "grid": grid,
            "blend": [[1234.0, 0.55, 320.0], [900.0, 0.9, 361.0], [2500.0, 0.1, 250.0]],
            "mics": mics, "spl_cal": SPL_CAL,
            "butter": [[1, 0.06, "low"], [3, 0.3, "low"], [2, 0.0027, "high"], [1, 0.0016, "high"],
                       [2, [0.0317, 0.295], "band"], [2, [0.0018, 0.0218], "band"]],
            # the synth's outputs are held at their own bound: libm differs by
            # an ulp between platforms and from V8 (17,458 of the noise table's
            # 262,144 entries do), and the rumble's 40 Hz band-pass amplifies
            # that to ~4e-12 of its peak -- 1.6e-10 in this floored-relative
            # measure. The arithmetic parts above stay at the module's 1e-12.
            "synth": {"mic": "exterior_7m", "segments": segments, "tolerance_rel": 1e-8}}


def sound_outputs(inp):
    from dieselsim import livesound as LS
    from dieselsim.live import Adr011Grid
    g = Adr011Grid.from_json(inp["grid"])
    out = []
    for rpm, load, T in inp["blend"]:
        b = g.blend_sources(rpm, load, T)
        out.append({k: (dict(v) if k == "_meta" else lst(v)) for k, v in b.items()})
    butter = [[{"b": list(map(float, b)), "a": list(map(float, a))} for b, a in LS.butter_sos(o, wn, kind)]
              for o, wn, kind in inp["butter"]]
    table = LS.noise_table()
    pure, LS.PURE = LS.PURE, True        # the reference the TypeScript port matches
    try:
        syn = LS.LiveSynth(g.spec, inp["synth"]["mic"])
        y, live = [], {}
        for seg in inp["synth"]["segments"]:
            if "blend" in seg:
                syn.set_sources(g.blend_sources(*seg["blend"]))
            if "mic" in seg:
                syn.set_mic(seg["mic"])
            live = seg.get("live", live)
            r0, r1 = seg["rpm"]
            for b in range(seg["blocks"]):
                y.append(syn.block(r0 + (r1 - r0) * (b + 1) / seg["blocks"], live, seg["running"]))
        parts = {k: lst(v) for k, v in syn.last_parts.items()}
    finally:
        LS.PURE = pure
    return {"blend": out, "butter": butter,
            "noise": {"head": lst(table[:64]), "sum": float(np.sum(table)), "sumsq": float(np.dot(table, table))},
            "synth": {"y": lst(np.concatenate(y)), "last_parts": parts}}


# ------------------------------------------------------------------ vehicles
def vehicles_inputs():
    """Every vehicle the live loop knows, under every gearbox (Phase 5: the
    Enjoy roster added three). Plain data, duplicated in TypeScript, so the
    two copies are held together here."""
    from dieselsim.live import VEHICLE_KEYS
    return {"keys": ["hd_i6", "ld_i4", "crdi15", "crdi_1p5", "single", "hatch15", "crdi22", "truck127",
                     "v8hd", "single10"],
            "trans": ["tc", "dct", "manual"],
            # the vehicles a custom engine may name (ADR-014), held in both languages
            "vehicle_keys": list(VEHICLE_KEYS)}


def vehicles_outputs(inp):
    from dieselsim.live import Vehicle, _finish_vehicle
    return {k: {t: {kk: (list(vv) if isinstance(vv, (list, tuple)) else vv)
                    for kk, vv in vars(_finish_vehicle(Vehicle(k, t))).items()}
                for t in inp["trans"]} for k in inp["keys"]}


MODULES = {"kinematics": (kinematics_inputs, kinematics_outputs),
           "thermo": (thermo_inputs, thermo_outputs),
           "friction": (friction_inputs, friction_outputs),
           "live": (live_inputs, live_outputs),
           "sound": (sound_inputs, sound_outputs),
           "vehicles": (vehicles_inputs, vehicles_outputs)}


def compare(a, b, tol, path=""):
    """Largest relative difference between two nested structures, with the
    denominator floored at 1e-3 of the largest |value| in the same array, so
    zero crossings (TDC displacement, closed valves) do not divide by zero.
    Returns (worst, where)."""
    if isinstance(b, dict):
        worst = (0.0, "")
        for k in b:
            if k in FD_KEYS:
                continue          # checked by compare_fd
            worst = max(worst, compare(a[k], b[k], tol, f"{path}.{k}"), key=lambda x: x[0])
        return worst
    if isinstance(b, list) and b and isinstance(b[0], (list, dict)):
        worst = (0.0, "")
        for i, (x, y) in enumerate(zip(a, b)):
            worst = max(worst, compare(x, y, tol, f"{path}[{i}]"), key=lambda x: x[0])
        return worst
    x, y = np.atleast_1d(np.asarray(a, float)), np.atleast_1d(np.asarray(b, float))
    if x.shape != y.shape:
        return (math.inf, f"{path} shape {x.shape} vs {y.shape}")
    floor = max(1e-3 * float(np.max(np.abs(y))) if y.size else 0.0, 1e-300)
    rel = np.abs(x - y) / np.maximum(np.abs(y), floor)
    i = int(np.argmax(rel))
    return (float(rel[i]), f"{path}[{i}]")


def compare_fd(got, want, cams):
    """Worst finite-difference error as a fraction of its propagated rounding
    bound (1.0 = at the bound). Returns (worst, where)."""
    worst = (0.0, "")
    for i, (g, w, c) in enumerate(zip(got["cams"], want["cams"], cams)):
        for key, (k, h, n) in FD_KEYS.items():
            bound = k * EPS * c["lift_max"] / h ** n
            d = np.abs(np.asarray(g[key]) - np.asarray(w[key])) / bound
            j = int(np.argmax(d))
            worst = max(worst, (float(d[j]), f"cams[{i}].{key}[{j}]"), key=lambda x: x[0])
    return worst


def compare_live(got, want, tol):
    """Events and strings exactly; every number at `tol` relative (floored at
    1e-9 absolute). Returns (worst, where); worst = inf on an exact mismatch."""
    worst = [0.0, ""]

    def walk(a, b, path):
        if isinstance(b, dict):
            if set(a) != set(b):
                worst[:] = [math.inf, f"{path} keys"]
                return
            for k in b:
                walk(a[k], b[k], f"{path}.{k}")
        elif isinstance(b, list):
            if len(a) != len(b):
                worst[:] = [math.inf, f"{path} length {len(a)} vs {len(b)}"]
                return
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, f"{path}[{i}]")
        elif isinstance(b, (bool, str)) or b is None or isinstance(b, int) and not isinstance(b, bool):
            if a != b and not (isinstance(b, int) and isinstance(a, float) and a == b):
                worst[:] = [math.inf, f"{path}: {a!r} vs {b!r}"]
        else:
            # relative, floored at 1e-6: a quantity that is zero on one platform (a locked
            # converter's slip, 0.0 on the Mac) is ~1e-14 on another (Linux CI: 5.7e-14,
            # adr011_weather, Phase 7 step 4), which a 1e-9 floor read as 5.7e-5 "stale".
            # Anything above 1e-6 is judged as before; a real change to a small value still shows.
            r = abs(a - b) / max(abs(b), 1e-6)
            if r > worst[0]:
                worst[:] = [r, path]
    for tr in want:
        walk(got[tr]["events"], want[tr]["events"], f"{tr}.events")
        walk(got[tr]["hints"], want[tr]["hints"], f"{tr}.hints")
        for key in ("veh", "final", "snapshots", "trace"):
            walk(got[tr][key], want[tr][key], f"{tr}.{key}")
    return worst[0], worst[1]


def main():
    os.makedirs(OUT, exist_ok=True)
    check = "--check" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    bad = 0
    for name, (gen_in, gen_out) in MODULES.items():
        if only and name != only:
            continue
        path = os.path.join(OUT, f"{name}.json")
        if check:
            with open(path) as fh:
                fx = json.load(fh)
            now = gen_out(fx["inputs"])
            if name == "live":
                worst, where = compare_live(now, fx["outputs"], TOL[name])
            elif name == "vehicles":
                # plain data with strings (names, gearbox): exact equality
                diff = [f"{k}/{t}/{f}" for k in fx["outputs"] for t in fx["outputs"][k]
                        for f in fx["outputs"][k][t] if now.get(k, {}).get(t, {}).get(f) != fx["outputs"][k][t][f]]
                worst, where = (0.0, "") if not diff and now == fx["outputs"] else (math.inf, diff[0] if diff else "keys")
            elif name == "sound":
                # the synth at its own bound (see sound_inputs), reported on the module's scale
                ts = fx["inputs"]["synth"]["tolerance_rel"]
                syn_now, syn_want = now.pop("synth"), dict(fx["outputs"]).pop("synth")
                rest = {k: v for k, v in fx["outputs"].items() if k != "synth"}
                w1 = compare(now, rest, TOL[name])
                w2 = compare(syn_now, syn_want, ts)
                worst, where = max(w1, (w2[0] * TOL[name] / ts, "synth" + w2[1]), key=lambda x: x[0])
            else:
                worst, where = compare(now, fx["outputs"], TOL[name])
            ok = worst <= TOL[name]
            bad += not ok
            print(f"{'ok   ' if ok else 'STALE'} {name:10} worst rel diff {worst:.2e} at {where} "
                  f"(tolerance {TOL[name]:.0e})")
            if name == "kinematics":
                f, where = compare_fd(now, fx["outputs"], fx["inputs"]["cams"])
                bad += f > 1.0
                print(f"{'ok   ' if f <= 1.0 else 'STALE'} {'  (FD)':10} worst {f:.3f} of the "
                      f"stencil's rounding bound at {where or '-'}")
        else:
            inp = gen_in()
            fx = {"meta": meta(name), "inputs": inp, "outputs": gen_out(inp)}
            with open(path, "w") as fh:
                json.dump(fx, fh, separators=(",", ":"))
                fh.write("\n")
            print(f"wrote {os.path.relpath(path, ROOT)} ({os.path.getsize(path) / 1024:.0f} KiB)")
    if check and bad:
        print("\nFixtures are stale: the physics changed. Regenerate with\n"
              "  python3 tools/fixtures/gen_fixtures.py\nand re-run every port's tests.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
