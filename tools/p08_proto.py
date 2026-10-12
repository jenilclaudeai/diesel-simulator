"""P08 prototype: a demand-based automatic schedule, patched onto live.py's
Gearbox for measurement only (nothing in the repo changes).

The pedal is a fuel fraction, so the reserve in the CURRENT gear is ~1 - throttle
in every gear; a reserve test against the current gear cascades. The demand is
read from the pedal as POWER instead, which carries across gears:
    P_dem = throttle * P_peak
A gear is feasible if its full-load power at its rpm covers P_dem with a reserve
(R_UP to move into it, R_STAY to stay), and its rpm is above a floor.
  B: the highest feasible gear (torque reserve only).
  C: among feasible gears, the least fuel for the power being delivered now,
     read from the engine's own grid; a move needs >= MIN_GAIN.
No feasible gear (full throttle): today's power schedule, unchanged. Kickdown
unchanged. Off throttle: no upshifts; downshift below the floor.
  C2: C with a fixed rpm ceiling (0.95 x rated), and today's schedule every
      frame once no gear can qualify.
  C3: C2 with the delivered power low-passed (2 s), a 6% saving for any move,
      and demand read as throttle**1.5.
  C4: C3 with an asymmetric bar: an upshift needs 1%, a downshift for fuel 6%
      (the recommendation in reviews/PROPOSAL-P08.md).
  base: today's schedule, through the same harness.
Friction is updated once per simulated second (the app: every 6 frames), the
same for every mode, so the modes compare like with like.

Usage: python3 tools/p08_proto.py <repo> <base|B|C|C2|C3|C4> [preset ...]
"""
import json, math, os, sys

REPO, MODE = sys.argv[1], sys.argv[2]
sys.path.insert(0, REPO)
from dieselsim.builder import load_engine_dir  # noqa: E402
load_engine_dir(os.path.join(REPO, "engines"))
from dieselsim import live as L  # noqa: E402

DT = 1 / 60
R_UP, R_STAY, MIN_GAIN, EVAL_S, FLOOR_K = 0.20, 0.05, 0.04, 0.2, 1.25
C3 = MODE in ("C3", "C4")
UP_GAIN = 0.01 if MODE == "C4" else None   # C4: an upshift needs 1%, a downshift for fuel alone 6%
if C3:
    MIN_GAIN = 0.06
DEMAND_EXP = 1.5 if C3 else 1.0       # P_dem = throttle**DEMAND_EXP * P_peak
P_TAU = 2.0 if C3 else 0.0            # s, low-pass on the delivered power the fuel comparison uses
orig = L.Gearbox.update_schedule


def attach(live):
    gb = live.dl.gb
    perf = lambda rpm, load: live.g.blend_perf_T(rpm, load, live.T_coolant)  # noqa: E731
    w = lambda rpm: rpm * 2 * math.pi / 60  # noqa: E731
    s = live.spec
    rs = [s.idle_rpm + k * (s.rated_rpm - s.idle_rpm) / 40 for k in range(41)]
    gb._p_peak = max(perf(r, 1.0)["torque"] * w(r) for r in rs)
    gb._floor = FLOOR_K * s.idle_rpm
    gb._eval = 0.0
    gb._live = live
    gb._p_f = 0.0

    def fuel_at(rpm, P):
        """kg/h to deliver brake power P at rpm (bisection on load)."""
        T = max(P, 0.0) / w(rpm)
        lo, hi = 0.0, 1.0
        for _ in range(12):
            mid = 0.5 * (lo + hi)
            if perf(rpm, mid)["torque"] < T: lo = mid
            else: hi = mid
        return perf(rpm, hi)["fuel_kg_h"]

    def schedule(self, dt, n_turbine, throttle, d_throttle):
        if self.shifting() or self.neutral or not self.auto:
            return
        self.hold_t = max(0.0, self.hold_t - dt)
        P_now = max(live.torque * w(live.rpm), 0.0)
        self._p_f += (P_now - self._p_f) * (min(1.0, dt / P_TAU) if P_TAU > 0 else 1.0)
        if self.hold_t > 0.0:
            return
        r = self.veh.gears
        # kickdown: as today
        if d_throttle > 1.2 and throttle > 0.55 and self.gear > 0:
            return orig(self, dt, n_turbine, throttle, d_throttle)
        if MODE in ("C2", "C3", "C4") and throttle ** DEMAND_EXP >= 1 - R_UP:   # >= 0.8: no gear can be feasible; today's schedule, every frame
            return orig(self, dt, n_turbine, throttle, d_throttle)
        self._eval -= dt
        if self._eval > 0.0:
            return
        self._eval = EVAL_S
        P_dem = throttle ** DEMAND_EXP * self._p_peak
        cand = []
        for g in range(self.n):
            rpm_g = n_turbine * r[g] / r[self.gear]
            ceil = 0.95 * s.rated_rpm if MODE in ("C2", "C3", "C4") else self.up_rpm * (0.80 + 0.28 * throttle)
            if rpm_g < self._floor or rpm_g > ceil:
                continue
            Pmax = perf(rpm_g, 1.0)["torque"] * w(rpm_g)
            R = R_STAY if g == self.gear else R_UP
            if P_dem <= (1 - R) * Pmax:
                cand.append((g, rpm_g))
        if not cand:                                  # full throttle, or nothing fits: today's schedule
            return orig(self, dt, n_turbine, throttle, d_throttle)
        if throttle < 0.03:                           # off throttle: hold, or drop below the floor
            if all(g != self.gear for g, _ in cand) and self.gear > 0:
                self.request(-1, coast=True)
            return
        if MODE == "B":
            best = max(g for g, _ in cand)
        else:
            P_act = self._p_f if C3 else max(live.torque * w(live.rpm), 0.0)
            fuel = {g: fuel_at(rpm_g, P_act) for g, rpm_g in cand}
            best = min(fuel, key=fuel.get)
            gain = MIN_GAIN if (UP_GAIN is None or best < self.gear) else UP_GAIN
            if self.gear in fuel and fuel[best] > (1 - gain) * fuel[self.gear]:
                best = self.gear
        if best != self.gear:
            self.request(1 if best > self.gear else -1, coast=False)

    gb.update_schedule = schedule.__get__(gb)


def make(preset):
    gj = json.load(open(os.path.join(REPO, "web/app/public/grids", preset + ".json")))
    live = L.LiveEngine(L.Adr011Grid.from_json(gj), preset, "tc")
    live.T_coolant, live.T_oil = 361.0, 373.0
    live.FRICTION_EVERY = 60
    if MODE != "base":
        attach(live)
    return live


def launch(preset, thr, secs):
    live = make(preset)
    gb, dl = live.dl.gb, live.dl
    shifts, last, t50, t100, fuel = [], gb.gear, None, None, 0.0
    for n in range(int(secs / DT)):
        live.throttle = thr if n * DT >= 0.5 else 0.0
        n_t, rpm0 = dl.w_in * 60 / (2 * math.pi), live.rpm
        live.step(DT)
        fuel += live.fuel_kg_h * DT / 3600
        k = dl.speed_kmh()
        if t50 is None and k >= 50: t50 = round(n * DT, 1)
        if t100 is None and k >= 100: t100 = round(n * DT, 1)
        if gb.gear != last:
            shifts.append(f"{last + 1}>{gb.gear + 1} {round(rpm0)}@{round(k)}")
            last = gb.gear
    return shifts, t50, t100, fuel / 0.832 / max(live.odo_m / 1000, 1e-9) * 100


def cruise(preset, v):
    live = make(preset)
    dl, gb = live.dl, live.dl.gb
    i, n_sh, last = 0.0, 0, gb.gear
    acc = [0.0, 0.0, 0.0, 0]
    for n in range(int(90 / DT)):
        e = (v - dl.speed_kmh()) / 10
        i = min(1.0, max(-1.0, i + e * DT * 0.8))
        live.throttle = min(1.0, max(0.0, 0.25 + 1.5 * e + i))
        live.step(DT)
        if gb.gear != last:
            if n * DT >= 40: n_sh += 1
            last = gb.gear
        if n * DT >= 60:
            acc[0] += live.fuel_kg_h; acc[1] += dl.speed_kmh(); acc[2] += live.rpm; acc[3] += 1
    f, k, rpm = acc[0] / acc[3], acc[1] / acc[3], acc[2] / acc[3]
    return gb.gear + 1, rpm, f / 0.832 / k * 100, n_sh


def tipin(preset):
    """Cruise at 50, then the pedal to 0.6 for 6 s: the gears it takes and km/h gained."""
    live = make(preset)
    dl, gb = live.dl, live.dl.gb
    i = 0.0
    for n in range(int(60 / DT)):
        e = (50 - dl.speed_kmh()) / 10
        i = min(1.0, max(-1.0, i + e * DT * 0.8))
        live.throttle = min(1.0, max(0.0, 0.25 + 1.5 * e + i))
        live.step(DT)
    g0, v0, gears = gb.gear + 1, dl.speed_kmh(), []
    for n in range(int(6 / DT)):
        live.throttle = 0.6
        live.step(DT)
        if not gears or gears[-1] != gb.gear + 1: gears.append(gb.gear + 1)
    return g0, gears, round(dl.speed_kmh() - v0, 1)


if __name__ == "__main__":
    for p in sys.argv[3:]:
        truck = p in ("truck127", "hd_i6", "v8hd")
        print(f"=== {p} [{MODE}]", flush=True)
        for thr in (0.2, 0.5, 1.0):
            sh, t50, t100, l100 = launch(p, thr, 120 if truck else 45)
            print(f"  launch {thr:.1f}: 0-50 {t50} s, 0-100 {t100} s; up " + "; ".join(x for x in sh), flush=True)
        for v in ((30, 50, 70, 90) if truck else (30, 50, 80, 110)):
            g, rpm, l100, n_sh = cruise(p, v)
            print(f"  cruise {v}: gear {g} at {rpm:.0f} rpm, {l100:.2f} L/100 km, shifts in the last 50 s: {n_sh}", flush=True)
        g0, gears, dv = tipin(p)
        print(f"  tip-in 0.6 from 50 km/h in gear {g0}: gears {gears}, +{dv} km/h in 6 s", flush=True)
