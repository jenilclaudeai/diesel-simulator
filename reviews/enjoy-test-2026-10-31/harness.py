"""Build a LiveEngine the way web/app's make-engine.ts does, for the ENJ triage."""
import copy, json, os, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]) else os.getcwd()
sys.path.insert(0, ROOT)
from dieselsim.live import Adr011Grid, LiveEngine, handle_key, pedal_return, route_from  # noqa: E402
from dieselsim.builder import load_engine_dir  # noqa: E402

load_engine_dir(os.path.join(ROOT, "engines"))

GRIDS = os.path.join(ROOT, "web", "app", "public", "grids")
PLACES = {p["key"]: p for p in json.load(open(os.path.join(ROOT, "web/app/src/app/weather/environments.json")))}
_cache = {}


def make(key, trans="tc", place="standard", route=None, cfpp=None):
    if key not in _cache:
        _cache[key] = json.load(open(os.path.join(GRIDS, key + ".json")))
    gj = _cache[key]
    g0 = Adr011Grid.from_json(gj)
    spec = copy.deepcopy(g0.spec)
    if place != "standard":
        spec.thermal.ambient_p = PLACES[place]["p_amb"]
        spec.thermal.ambient_T = PLACES[place]["T_amb"]
    grid = Adr011Grid.from_json(gj, spec)
    live = LiveEngine(grid, gj.get("vehicle") or gj["preset"], trans)
    if cfpp is not None:
        live.fuel_cfpp = cfpp
    if route:
        live.set_route(route_from(route))
    return live


DT = 1.0 / 60.0


def run(live, seconds, throttle=None, brake=None, held=(), every=None, log=None):
    """Advance `seconds`; throttle/brake fixed if given; `held` keys re-fired each frame as the worker does."""
    n = int(round(seconds / DT))
    for i in range(n):
        if throttle is not None and not live.cruise_on:
            live.throttle = throttle
        for k in held:
            handle_key(live, k)
        if brake is not None:
            live.dl.brake = brake
        pedal_return(live, DT)
        live.step(DT)
        if log is not None and every and i % int(round(every / DT)) == 0:
            log.append(snap(live))
    return live


def snap(e):
    gb = e.dl.gb
    return dict(rpm=round(e.rpm), kmh=round(e.dl.v * 3.6, 1), gear="N" if gb.neutral else gb.gear + 1,
                thr=round(e.throttle, 2), fuel_kg_h=round(e.fuel_kg_h, 4), inst_kmpl=e.inst_kmpl,
                Tc=round(e.T_coolant - 273.15, 1), Tch=round(e.T_charge - 273.15, 1), derate=round(e.derate, 3),
                derate_heat=round(e.derate_heat, 3), stalled=e.stalled, stopped=e.engine_stopped,
                cruise=e.cruise_on, hint=e.hint)
