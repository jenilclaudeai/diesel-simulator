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
TOL = {"kinematics": 1e-12, "thermo": 1e-10, "friction": 1e-6}
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
                             lift_max=cam.lift_max, lash=cam.lash, ramp=cam.ramp))
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
        cam = Cam(c["open_deg"], c["close_deg"], c["lift_max"], c["lash"], c["ramp"])
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
FRICTION_KEYS = ("fmep", "P_friction", "P_rings", "P_skirt", "P_mains", "P_rods", "P_valvetrain",
                 "Pb_valvetrain", "h_ring_mid", "v_seating")


def friction_inputs():
    from dieselsim.acoustics import EngineSound
    from dieselsim.grid import solve_cell
    cases = []
    for preset, rpm, load in (("crdi15", 1800.0, 0.6), ("hd_i6", 1300.0, 1.0)):
        spec = DieselEngine(preset=preset).spec
        src, perf = solve_cell(spec, rpm, load)
        grid = EngineSound(spec).grid
        for T_oil in (373.0, 273.0):
            cases.append(dict(preset=preset, rpm=rpm, T_oil=T_oil, fuel_mg=float(perf["fuel_mg"]),
                              p_rail=float(perf["p_rail"]), grid_deg=lst(grid), p_cyl=lst(src["p_cyl"])))
    return dict(cases=cases)


def friction_outputs(inp):
    from dieselsim.grid import cell_friction
    out = []
    for c in inp["cases"]:
        eng = DieselEngine(preset=c["preset"])
        eng.oil.cond.T_oil = c["T_oil"]
        r = cell_friction(eng, c["rpm"], c["p_cyl"], c["grid_deg"], c["fuel_mg"], c["p_rail"])
        out.append({k: float(r[k]) for k in FRICTION_KEYS if k in r})
    return out


MODULES = {"kinematics": (kinematics_inputs, kinematics_outputs),
           "thermo": (thermo_inputs, thermo_outputs),
           "friction": (friction_inputs, friction_outputs)}


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


def main():
    os.makedirs(OUT, exist_ok=True)
    check = "--check" in sys.argv
    bad = 0
    for name, (gen_in, gen_out) in MODULES.items():
        path = os.path.join(OUT, f"{name}.json")
        if check:
            with open(path) as fh:
                fx = json.load(fh)
            now = gen_out(fx["inputs"])
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
