"""P09 (reviews/PROPOSAL-P09.md, FINDING-029): what altitude does to ignition delay, the premixed burn and the
knock the sound reads (acoustics `_meta["dpdt_max"]`).

    python3 tools/p09_altitude_knock.py TREE [engine,engine,...]      (default: crdi15,single10,truck127)

TREE is a checkout (its dieselsim/ and engines/). Three airs: sea level (101325 Pa, 298 K), Leh (3500 m,
20 C) and 5000 m (10 C); three points per engine: idle at 5%, half rated rpm at 30%, 60% of rated at full
pedal. About 2 min on this Mac.
"""
import os
import sys
import time

REPO = sys.argv[1]
sys.path.insert(0, REPO)
from dieselsim.builder import load_engine_dir  # noqa: E402
load_engine_dir(os.path.join(REPO, "engines"))
from dieselsim.engine import DieselEngine  # noqa: E402
from dieselsim.config import PRESETS  # noqa: E402
from dieselsim.acoustics import EngineSound  # noqa: E402
from dieselsim.environment import pressure_at  # noqa: E402

ENGINES = sys.argv[2].split(",") if len(sys.argv) > 2 else ["crdi15", "single10", "truck127"]
AIRS = (("sea", 101325.0, 298.0), ("Leh 3500 m", pressure_at(3500.0), 293.15),
        ("5000 m", pressure_at(5000.0), 283.15))

for key in ENGINES:
    s0 = PRESETS[key]()
    idle = float(getattr(s0, "idle_rpm", 800.0) or 800.0)
    pts = ((idle, 0.05), (0.5 * s0.rated_rpm, 0.3), (0.6 * s0.rated_rpm, 1.0))
    print(f"\n{key}: turbo={getattr(s0, 'ecu_modern', None)} cetane={s0.inj.cetane_number}", flush=True)
    for rpm, ld in pts:
        for name, p, T in AIRS:
            s = PRESETS[key]()
            s.thermal.ambient_p, s.thermal.ambient_T = p, T
            t0 = time.time()
            eng = DieselEngine(spec=s)
            op = eng.operating_point(rpm, load=ld, n_cycles=9)
            c = op.cycle
            meta = EngineSound(s).build_sources(op)["_meta"]
            print(f"  {rpm:5.0f} rpm {ld:4.2f}  {name:11s} p {p/1e3:5.1f} kPa  boost {op.boost_pr:4.2f}  "
                  f"fuel {op.fuel_mg:5.1f} mg  delay {c.ign_delay_deg:5.2f} deg {c.ign_delay_ms:5.3f} ms  "
                  f"premix {c.premix_fraction:5.3f}  dpdth_comb {c.dpdtheta_comb:5.2f}  dpdth_max {c.dpdtheta_max:5.2f} bar/deg  "
                  f"sound dpdt_max {meta['dpdt_max']/1e9:5.2f}e9  ({time.time()-t0:.0f} s)", flush=True)
