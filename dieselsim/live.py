"""
live.py -- the real-time loop: vehicle, launch clutch, torque converter,
clutch-to-clutch gearbox, driveline and the LiveEngine that integrates them
at 60 Hz against a pre-solved (rpm, load) grid.

Moved out of play.py (Phase 3) so it is importable without a terminal or
scipy: it is the Python reference the TypeScript port is tested against
(ADR-004), and play.py uses it unchanged. numpy only -- a test enforces it.
"""
from __future__ import annotations

import copy
import math
import threading

import numpy as np

TRANSMISSION = "dct"     # default when a caller names none; play.py passes --transmission


class PerfGrid:
    """
    The performance half of a pre-solved grid: axes, per-cell perf dicts and
    the spec they were solved for. play.py's EngineGrid extends it with the
    acoustic sources; the live loop only needs this.
    """

    def __init__(self, spec, rpms, loads, perf):
        self.spec = spec
        self.rpms, self.loads, self.perf = rpms, loads, perf
        self.n_rpm, self.n_load = len(rpms), len(loads)

    def weights(self, rpm, load):
        """Bilinear weights and the four surrounding grid indices."""
        r = np.clip(rpm, self.rpms[0], self.rpms[-1])
        l = np.clip(load, self.loads[0], self.loads[-1])
        i = int(np.clip(np.searchsorted(self.rpms, r) - 1, 0, self.n_rpm - 2))
        j = int(np.clip(np.searchsorted(self.loads, l) - 1, 0, self.n_load - 2))
        fr = (r - self.rpms[i]) / (self.rpms[i + 1] - self.rpms[i])
        fl = (l - self.loads[j]) / (self.loads[j + 1] - self.loads[j])
        return i, j, fr, fl

    def blend_perf(self, rpm, load):
        i, j, fr, fl = self.weights(rpm, load)
        w = ((1 - fr) * (1 - fl), (1 - fr) * fl, fr * (1 - fl), fr * fl)
        q = (self.perf[i][j], self.perf[i][j + 1],
             self.perf[i + 1][j], self.perf[i + 1][j + 1])
        return {k: sum(wi * qi[k] for wi, qi in zip(w, q)) for k in q[0]}



class Adr011Grid(PerfGrid):
    """
    ADR-011: the grid the live loop reads when friction is computed live.

    Two sets of cells, solved with the walls at a warm and a cold coolant
    temperature (the combustion change with coolant is small and linear --
    REVIEW-002 -- so indicated performance is interpolated linearly between
    them). Every cell carries its cylinder-1 pressure trace, from which the
    live loop evaluates friction at the live oil and coolant state
    (grid.cell_friction). Indicated torque is the cell's brake torque plus
    the friction torque it was solved with, fmep * Vd / (4 pi).

    Phase 4: a cell may also carry its acoustic sources (livesound's six
    crank-angle waveforms and their "_meta" scalars), warm and cold, blended
    the same way for the streaming synth.
    """

    def __init__(self, spec, rpms, loads, perf, p_cyl, grid_deg, perf_cold, p_cyl_cold,
                 T_warm, T_cold, src=None, src_cold=None):
        super().__init__(spec, rpms, loads, perf)
        f64 = lambda cells: [[np.asarray(c, dtype=float) for c in row] for row in cells]  # noqa: E731
        self.p_cyl = f64(p_cyl)
        self.p_cyl_cold = f64(p_cyl_cold)
        self.grid_deg = np.asarray(grid_deg, dtype=float)
        self.perf_cold = perf_cold
        self.T_warm, self.T_cold = float(T_warm), float(T_cold)
        self.k_torque = spec.geom.displacement / (4.0 * math.pi)   # fmep [Pa] -> N.m

        def srcs(cells):
            if cells is None:
                return None
            return [[dict({k: np.asarray(v, dtype=float) for k, v in c.items() if k != "_meta"},
                          _meta={k: float(v) for k, v in c["_meta"].items()}) for c in row] for row in cells]
        self.src, self.src_cold = srcs(src), srcs(src_cold)

    @classmethod
    def from_json(cls, gj, spec=None):
        """A grid as tools/build_live_grids.py writes it (arrays as float32
        base64); `spec` defaults to the engine it records (a custom engine's
        JSON, ADR-014; or an edited engine's base preset and overrides, from
        the spec editor, Phase 6) or else its preset's."""
        import base64
        if spec is None and gj.get("engine_json"):
            from .builder import from_dict
            spec = from_dict(gj["engine_json"])
        if spec is None and gj.get("base"):
            from .config import PRESETS
            from .overrides import apply_overrides
            spec = copy.deepcopy(PRESETS[gj["base"]]())
            apply_overrides(spec, gj.get("overrides"))
        if spec is None:
            from .engine import DieselEngine
            spec = DieselEngine(preset=gj["preset"]).spec
        dec = lambda b: np.frombuffer(base64.b64decode(b), dtype="<f4")  # noqa: E731
        cells = lambda rows: [[dec(c) for c in row] for row in rows]  # noqa: E731

        def srcs(arrs, metas):
            return [[dict({k: dec(v) for k, v in a.items()}, _meta=m) for a, m in zip(ra, rm)]
                    for ra, rm in zip(arrs, metas)]
        has = "src_f32" in gj
        return cls(spec, gj["rpms"], gj["loads"], gj["perf"], cells(gj["p_cyl_f32"]), gj["grid_deg"],
                   gj["perf_cold"], cells(gj["p_cyl_cold_f32"]), gj["T_warm"], gj["T_cold"],
                   srcs(gj["src_f32"], gj["src_meta"]) if has else None,
                   srcs(gj["src_cold_f32"], gj["src_meta_cold"]) if has else None)

    def cold_weight(self, T_coolant):
        return float(np.clip((self.T_warm - T_coolant) / (self.T_warm - self.T_cold), 0.0, 1.0))

    def blend_perf_T(self, rpm, load, T_coolant):
        i, j, fr, fl = self.weights(rpm, load)
        w = ((1 - fr) * (1 - fl), (1 - fr) * fl, fr * (1 - fl), fr * fl)
        c = self.cold_weight(T_coolant)
        qw = (self.perf[i][j], self.perf[i][j + 1], self.perf[i + 1][j], self.perf[i + 1][j + 1])
        qc = (self.perf_cold[i][j], self.perf_cold[i][j + 1], self.perf_cold[i + 1][j],
              self.perf_cold[i + 1][j + 1])
        out = {}
        for k in qw[0]:
            warm = sum(wi * qi[k] for wi, qi in zip(w, qw))
            cold = sum(wi * qi[k] for wi, qi in zip(w, qc))
            out[k] = (1.0 - c) * warm + c * cold
        out["torque_ind"] = out["torque"] + out["fmep"] * self.k_torque
        return out

    def blend_p_cyl(self, rpm, load, T_coolant):
        i, j, fr, fl = self.weights(rpm, load)
        w = ((1 - fr) * (1 - fl), (1 - fr) * fl, fr * (1 - fl), fr * fl)
        c = self.cold_weight(T_coolant)
        P, Q = self.p_cyl, self.p_cyl_cold
        warm = w[0] * P[i][j] + w[1] * P[i][j + 1] + w[2] * P[i + 1][j] + w[3] * P[i + 1][j + 1]
        cold = w[0] * Q[i][j] + w[1] * Q[i][j + 1] + w[2] * Q[i + 1][j] + w[3] * Q[i + 1][j + 1]
        return (1.0 - c) * warm + c * cold

    def blend_sources(self, rpm, load, T_coolant):
        """The acoustic sources at the live point, as livesound.LiveSynth's
        set_sources takes them: arrays and scalars alike bilinear in (rpm,
        load) and linear from warm to cold, in blend_p_cyl's order."""
        i, j, fr, fl = self.weights(rpm, load)
        w = ((1 - fr) * (1 - fl), (1 - fr) * fl, fr * (1 - fl), fr * fl)
        c = self.cold_weight(T_coolant)
        W = (self.src[i][j], self.src[i][j + 1], self.src[i + 1][j], self.src[i + 1][j + 1])
        C = (self.src_cold[i][j], self.src_cold[i][j + 1], self.src_cold[i + 1][j],
             self.src_cold[i + 1][j + 1])

        def mix(get):
            warm = w[0] * get(W[0]) + w[1] * get(W[1]) + w[2] * get(W[2]) + w[3] * get(W[3])
            cold = w[0] * get(C[0]) + w[1] * get(C[1]) + w[2] * get(C[2]) + w[3] * get(C[3])
            return (1.0 - c) * warm + c * cold
        out = {k: mix(lambda q, k=k: q[k]) for k in W[0] if k != "_meta"}
        out["_meta"] = {k: mix(lambda q, k=k: q["_meta"][k]) for k in W[0]["_meta"]}
        return out


# ==========================================================================
# vehicle, torque converter and gearbox
# ==========================================================================
# The vehicles a grid can name (ADR-014: a custom engine's "vehicle"). They
# are keyed by the engine each was first made for; "tractor" is the
# fallback every other key gets.
VEHICLE_KEYS = ("hatch15", "crdi15", "ld_i4", "crdi22", "hd_i6", "tractor")


class Vehicle:
    """Everything downstream of the flywheel."""

    def __init__(self, preset: str, trans: str = None):
        self.trans = (trans or TRANSMISSION).lower()
        # A dual clutch has no fluid coupling to waste energy in, so it is
        # a couple of points more efficient, and it launches on a clamping
        # clutch rather than on slip -- which is why it does not creep.
        self.launch_rpm = 2000.0
        self.fuel_tank_L = 60.0
        self.clutch_cap_max = 0.0     # 0 -> derived from engine torque
        if preset in ("hd_i6", "truck127", "v8hd"):   # tractor unit, laden (truck127, v8hd: Enjoy roster, ADR-012)
            self.name = "40 t tractor-trailer"
            self.fuel_tank_L = 400.0
            self.stall_rpm = 1900.0
            self.mass = 24000.0                   # kg
            self.r_wheel = 0.506                  # m
            self.gears = [3.49, 1.86, 1.41, 1.00, 0.75, 0.65]
            self.final = 3.70
            self.CdA = 8.0                        # m^2, drag area
            self.Crr = 0.0068                     # rolling resistance
            self.eta = 0.94                       # driveline efficiency
            self.J_trans = 0.60                   # kg.m^2 at gearbox input
            self.J_wheel = 46.0                   # kg.m^2 all wheels
            self.TR_stall = 1.95
            self.tc_diameter_gain = 1.00
            self.v_lock_min = 8.0                 # m/s before lockup allowed
        elif preset == "ld_i4":                   # mid-size car / small van
            self.name = "1.75 t passenger car"
            self.fuel_tank_L = 55.0
            self.stall_rpm = 2250.0
            self.mass = 1750.0
            self.r_wheel = 0.320
            self.gears = [4.15, 2.37, 1.56, 1.16, 0.86, 0.69]
            self.final = 3.63
            self.CdA = 0.72
            self.Crr = 0.0100
            self.eta = 0.93
            self.J_trans = 0.085
            self.J_wheel = 4.2
            self.TR_stall = 2.10
            self.tc_diameter_gain = 1.00
            self.v_lock_min = 12.0
        elif preset == "crdi15":                  # compact car, 7-speed
            self.name = "1.5 t compact, 7-speed auto"
            self.fuel_tank_L = 45.0
            self.mass = 1500.0
            self.r_wheel = 0.315                  # 205/55 R16
            # Seven speeds means smaller steps, so the ratio spread can be
            # wider at both ends: a shorter first for launch and a longer
            # top for cruising, without the box falling out of the torque
            # plateau on every shift.
            self.gears = [3.62, 2.05, 1.36, 1.00, 0.79, 0.67, 0.58]
            self.final = 4.30
            self.CdA = 0.70
            self.Crr = 0.0092
            self.eta = 0.94
            self.launch_rpm = 2100.0
            self.J_trans = 0.070
            self.J_wheel = 3.6
            self.TR_stall = 1.85
            self.stall_rpm = 2100.0
            self.tc_diameter_gain = 1.00
            self.v_lock_min = 9.0
        elif preset == "hatch15":                 # Enjoy roster (ADR-012): hatchback, 6-speed
            self.name = "1.3 t hatchback, 6-speed"
            self.fuel_tank_L = 45.0
            self.mass = 1300.0
            self.r_wheel = 0.303                  # 195/55 R16
            self.gears = [3.73, 2.05, 1.32, 0.97, 0.76, 0.63]
            self.final = 3.94
            self.CdA = 0.64
            self.Crr = 0.0092
            self.eta = 0.94
            self.launch_rpm = 2100.0              # its torque arrives at 2000 rpm
            self.J_trans = 0.065
            self.J_wheel = 3.3
            self.TR_stall = 1.90
            self.stall_rpm = 2100.0
            self.tc_diameter_gain = 1.00
            self.v_lock_min = 9.0
        elif preset == "crdi22":                  # Enjoy roster (ADR-012): SUV, 8-speed auto
            self.name = "1.9 t SUV, 8-speed auto"
            self.fuel_tank_L = 65.0
            self.mass = 1900.0
            self.r_wheel = 0.355                  # 235/60 R18
            self.gears = [4.71, 3.14, 2.11, 1.67, 1.29, 1.00, 0.84, 0.67]
            self.final = 3.20
            self.CdA = 0.95
            self.Crr = 0.0110
            self.eta = 0.93
            self.J_trans = 0.11
            self.J_wheel = 6.5
            self.TR_stall = 2.00
            self.stall_rpm = 2000.0
            self.tc_diameter_gain = 1.00
            self.v_lock_min = 9.0
        else:                                     # small utility tractor
            self.name = "3 t utility tractor"
            self.fuel_tank_L = 60.0
            self.stall_rpm = 1800.0
            self.mass = 3000.0
            self.r_wheel = 0.420
            self.gears = [4.50, 2.20, 1.30, 0.90]
            self.final = 4.10
            self.CdA = 2.4
            self.Crr = 0.0180
            self.eta = 0.88
            self.J_trans = 0.12
            self.J_wheel = 9.0
            self.TR_stall = 2.00
            self.tc_diameter_gain = 1.00
            self.v_lock_min = 4.0


def _finish_vehicle(v: "Vehicle"):
    if v.trans == "dct":
        v.eta = min(0.975, v.eta + 0.035)   # no converter slip to pay for
    elif v.trans == "manual":
        v.eta = min(0.975, v.eta + 0.04)    # dry clutch: no converter, no wet-pack drag
    return v


class LaunchClutch:
    """
    The wet clutch a dual-clutch box launches on.

    A converter is a fluid coupling: it always slips, always multiplies
    torque at low speed, and never has to be told what to do.  A clutch is
    the opposite -- it has a commanded capacity, and the controller decides
    it.  During launch the capacity is set to hold the engine at a target
    speed while the car catches up; once the slip closes, the clutch clamps
    and the driveline is RIGID from crank to wheels.  That rigidity is why
    a DCT feels direct, why it engine-brakes properly, and why it does not
    creep at a standstill.
    """

    def __init__(self, spec, veh):
        T_pk = max(50.0, spec.geom.displacement * 1.9e6 / (4 * math.pi))
        self.cap_max = veh.clutch_cap_max or 1.8 * T_pk
        self.veh = veh
        self.spec = spec
        self.engaged = False
        self.cap = 0.0
        self.slip = 0.0
        self.SR = 0.0            # kept so the dashboard reads the same
        self.TR = 1.0            # a clutch cannot multiply torque
        self.eff = 0.0

    def target_speed(self, throttle):
        idle = 2.0 * math.pi * self.spec.idle_rpm / 60.0
        launch = 2.0 * math.pi * self.veh.launch_rpm / 60.0
        return idle + min(1.0, max(0.0, throttle)) * (launch - idle)

    def command(self, w_e, w_sync, T_eng, throttle, creep):
        """Capacity to command this instant, and whether we are stuck."""
        self.slip = w_e - w_sync
        w_t = self.target_speed(throttle)
        idle = 2.0 * math.pi * self.spec.idle_rpm / 60.0
        if w_sync < 0.80 * idle and throttle < 0.03:
            # rolling to a stop: let go before the engine is dragged down
            self.engaged = False
            self.cap = creep * 0.10 * self.cap_max
            return self.cap, False
        if self.engaged:
            need = abs(T_eng)
            if need > self.cap_max:
                self.cap = self.cap_max
                self.engaged = False
                return self.cap, False
            self.cap = self.cap_max
            return self.cap, True
        # slipping: feedforward the engine torque, then a proportional term
        # that pulls engine speed onto the launch target
        cap = T_eng + 9.0 * (w_e - w_t)
        self.cap = float(np.clip(cap, 0.0, self.cap_max))
        if abs(self.slip) < 3.0 and self.cap < self.cap_max:
            self.engaged = True
            return self.cap, True
        return self.cap, False

    # dashboard parity with the converter
    def report(self, w_e, w_in):
        self.SR = w_in / max(w_e, 1.0)
        self.TR = 1.0
        self.eff = min(1.0, self.SR) if not self.engaged else 1.0


class ManualClutch:
    """
    A dry, driver-operated clutch (Phase 3; play.py never had one).

    The pedal sets the clamp load: capacity = cap_max * (1 - pedal)^1.6, so
    the first travel off the floor does little and the bite comes in the
    last third, as on a real car. Slipping, it passes exactly its capacity
    in the direction of the slip -- so dumping the pedal at a standstill
    hands the whole capacity to a stationary car and drags the engine down,
    which is how a real one stalls. Once the slip closes with enough
    capacity it clamps, and the driveline is rigid from crank to wheels
    (solved as the DCT's clamped state is).

    The auto-clutch assist replaces the pedal with the DCT's launch law
    (hold the engine at a throttle-dependent target speed while the car
    catches up), sequences the pedal on a shift, and opens before a stall.
    """

    BITE_K = 1.6

    def __init__(self, spec, veh):
        T_pk = max(50.0, spec.geom.displacement * 1.9e6 / (4 * math.pi))
        self.cap_max = veh.clutch_cap_max or 1.8 * T_pk
        self.veh = veh
        self.spec = spec
        self.engaged = False
        self.cap = 0.0
        self.slip = 0.0
        self.SR = 0.0
        self.TR = 1.0
        self.eff = 0.0

    def capacity(self, pedal):
        return self.cap_max * max(0.0, 1.0 - pedal) ** self.BITE_K

    def target_speed(self, throttle):
        idle = 2.0 * math.pi * self.spec.idle_rpm / 60.0
        launch = 2.0 * math.pi * self.veh.launch_rpm / 60.0
        return idle + min(1.0, max(0.0, throttle)) * (launch - idle)

    def assist_capacity(self, w_e, w_sync, T_eng, throttle):
        """What the auto-clutch commands when it is not mid-shift."""
        idle = 2.0 * math.pi * self.spec.idle_rpm / 60.0
        if w_e <= 0.85 * idle:
            self.engaged = False              # open before the engine stalls
        if w_sync < 0.80 * idle and throttle < 0.03:
            return 0.0                        # stopped, no throttle: no creep
        if self.engaged:
            return self.cap_max
        cap = T_eng + 9.0 * (w_e - self.target_speed(throttle))
        return float(np.clip(cap, 0.0, self.cap_max))

    def report(self, w_e, w_in):
        self.SR = w_in / max(w_e, 1.0)
        self.TR = 1.0
        self.eff = min(1.0, self.SR) if not self.engaged else 1.0


class TorqueConverter:
    """
    Fluid coupling with a stator.

        T_pump    = k_cap * lambda(SR) * w_pump^2      (what the engine feels)
        T_turbine = TR(SR) * T_pump                    (what the box gets)

    lambda falls to zero at SR = 1 -- no slip, no torque -- and goes negative
    past it, which is the engine braking through the converter on a trailing
    throttle.  The stator multiplies torque below the coupling point and
    freewheels above it, so TR falls from ~2 at stall to exactly 1.
    Efficiency is TR*SR.

    The capacity curve is the part people get wrong.  A real converter's
    K-factor is nearly flat from stall to about SR 0.5 and then climbs
    steeply as the coupling point approaches; in the lambda form used here
    that means lambda stays high, then collapses.  A plain 1 - SR^n is too
    soft in the middle, which makes the engine bog where a real one pulls.
    """

    def __init__(self, spec, veh):
        # A converter is specified by its STALL SPEED -- the engine speed it
        # settles at against a braked output at full throttle -- not by the
        # engine's rated speed.  Sizing off rated speed gave the 1.5 L a
        # stall around 3800 rpm: the engine just flared and the car crawled.
        # T_ref is the engine's torque from a typical full-load BMEP: 19 bar
        # for a turbodiesel, 8 bar for a naturally aspirated one. With 19 bar
        # for every engine, roster B's 1.0 L NA single got a converter sized
        # for 159 N.m against its 58 (17.6 N.m of drag at idle on top of cold
        # friction) and was dragged down to the loop's floor in "Auto".
        bmep = 1.9e6 if getattr(spec.turbo, "enabled", True) else 0.8e6
        T_ref = 1.05 * max(0.1, spec.geom.displacement * bmep / (4 * math.pi))
        n_stall = getattr(veh, "stall_rpm", 0.0) or 0.52 * spec.rated_rpm
        w_stall = 2.0 * math.pi * n_stall / 60.0
        self.k_cap = T_ref / w_stall ** 2 * veh.tc_diameter_gain
        self.stall_rpm = n_stall
        self.TR_stall = veh.TR_stall
        self.SR_couple = 0.86
        self.SR = 0.0
        self.TR = veh.TR_stall
        self.eff = 0.0

    def _lam(self, SR):
        # flat-then-collapse capacity, ~real K-factor shape
        x = min(max(SR, -0.3), 1.4)
        if x < 0.0:
            return 1.0 + 0.9 * abs(x) ** 1.6
        return max(-1.2, 1.0 - x ** 4.2) if x <= 1.0 else -(x - 1.0) ** 1.6 * 3.0

    def torques(self, w_e, w_t):
        w_e = max(w_e, 1.0)
        SR = w_t / w_e
        self.SR = SR
        T_p = self.k_cap * self._lam(SR) * w_e ** 2
        if SR < self.SR_couple:
            # stator contribution decays faster than linearly
            f = max(0.0, 1.0 - SR / self.SR_couple)
            TR = 1.0 + (self.TR_stall - 1.0) * f ** 1.25
        else:
            TR = 1.0
        self.TR = TR
        self.eff = max(0.0, TR * min(SR, 1.0))
        return T_p, TR * T_p


class Gearbox:
    """
    Clutch-to-clutch automatic with a real two-phase shift.

    A production shift is not a ratio that changes instantly.  It has:

      TORQUE PHASE (~120-180 ms) -- the oncoming clutch takes over the load
      while the offgoing one lets go.  Input speed does not move yet.
      Because the new gear is numerically lower, output torque DROPS: this
      is the torque hole you feel as the brief slump in an upshift.

      INERTIA PHASE (~250-400 ms) -- the offgoing clutch is out, the
      oncoming one slips at a commanded capacity, and that slip is what
      drags the turbine and engine down to the new ratio.  Output torque
      here is the clutch capacity, and it usually sits a little above the
      steady value, which is the firm push at the end of a good shift.

    The controller commands a capacity that targets a fixed inertia-phase
    duration, and asks the engine for a torque cut while it does -- exactly
    what a real TCU does, and the reason a modern shift is quick AND smooth
    instead of one or the other.
    """

    IDLE, TORQUE, INERTIA = 0, 1, 2

    def __init__(self, spec, veh):
        self.spec = spec
        self.veh = veh
        self.n = len(veh.gears)
        self.gear = 0
        self.gear_from = 0
        self.auto = True
        self.neutral = False
        self.phase = self.IDLE
        self.phase_t = 0.0
        self.hold_t = 0.0
        heavy = min(2.0, max(0.7, (veh.mass / 1750.0) ** 0.18))
        if veh.trans == "dct":
            # The next gear is already engaged on the idle shaft, so a DCT
            # shift is only a clutch handover -- no synchro, no ratio to
            # find.  That is the whole reason it is quick.
            self.T_TORQUE = 0.045 * heavy
            self.T_INERTIA = 0.13 * heavy
        else:
            self.T_TORQUE = 0.11 * heavy
            self.T_INERTIA = 0.26 * heavy
        self.HOLD_S = 1.2
        self.up_rpm = 0.86 * spec.rated_rpm
        self.dn_rpm = 0.52 * spec.rated_rpm
        self.torque_cut = 0.0         # fraction the TCU asks the engine for
        self.blend = 0.0
        self.err0 = 0.0               # slip to be removed, latched at entry
        self.coast = False            # this shift is an off-throttle downshift (bug #11)

    # Bug #11: coast downshifts used the power-on calibration. Off throttle a
    # TCU has no hurry and nothing to hide the shift behind, so it stretches
    # both phases; the inertia phase then spins the input up with less
    # clutch capacity. Measured on crdi15 coasting from 100 km/h (FINDING-020):
    # the DCT's worst coast-downshift overshoot 6.49 -> 1.74 m/s^2 at x2 / x4.
    COAST_TORQUE_K = 2.0
    COAST_INERTIA_K = 4.0

    def t_torque(self):
        return self.T_TORQUE * (self.COAST_TORQUE_K if self.coast else 1.0)

    def t_inertia(self):
        return self.T_INERTIA * (self.COAST_INERTIA_K if self.coast else 1.0)

    # ------------------------------------------------------------------
    def ratio(self, g=None):
        g = self.gear if g is None else g
        return self.veh.gears[g] * self.veh.final

    def shifting(self):
        return self.phase != self.IDLE

    def request(self, delta, kickdown=False, coast=False):
        g = int(np.clip(self.gear + delta, 0, self.n - 1))
        if g == self.gear or self.shifting():
            return False
        self.coast = coast
        self.gear_from = self.gear
        self.gear = g
        self.phase = self.TORQUE
        self.phase_t = 0.0
        self.blend = 0.0
        self.hold_t = self.HOLD_S * (0.4 if kickdown else 1.0)
        return True

    # ------------------------------------------------------------------
    def update_schedule(self, dt, n_turbine, throttle, d_throttle):
        if self.shifting() or self.neutral or not self.auto:
            return
        self.hold_t = max(0.0, self.hold_t - dt)
        if self.hold_t > 0.0:
            return
        up = self.up_rpm * (0.80 + 0.28 * throttle)
        r = self.veh.gears
        if self.gear > 0:
            step_dn = r[self.gear - 1] / r[self.gear]
            dn = min(self.dn_rpm * (0.72 + 0.30 * throttle),
                     0.80 * up / step_dn)
        else:
            dn = 0.0
        # kickdown: a fast stab of throttle asks for the biggest downshift
        # that will not overspeed the engine, skipping gears if it can
        if d_throttle > 1.2 and throttle > 0.55 and self.gear > 0:
            for skip in (2, 1):
                g = self.gear - skip
                if g < 0:
                    continue
                n_after = n_turbine * r[g] / r[self.gear]
                if n_after < 0.95 * self.spec.rated_rpm:
                    self.request(-skip, kickdown=True)
                    return
        if n_turbine > up and self.gear < self.n - 1:
            self.request(+1)
        elif n_turbine < dn and self.gear > 0:
            self.request(-1, coast=throttle < 0.05)


def s_inertia(dl, gb):
    """Extra clutch capacity that clears the latched slip on schedule."""
    J = dl.spec_J
    return J * gb.err0 / max(gb.t_inertia(), 0.03)


class Driveline:
    """
    Converter + clutch-to-clutch gearbox + vehicle.

    The transmission input shaft is now a STATE, not a kinematic function of
    road speed.  That is what makes a shift look like a shift: during the
    inertia phase the input is slipping against the oncoming clutch, so its
    speed ramps instead of teleporting, and the engine gets dragged with it.
    """

    C_LOCK = 900.0          # retired: the lock-up spring (FINDING-020); kept for the record
    T_LOCK_MAX = 4500.0
    LOCK_ENGAGE_S = 0.5     # lock-up engagement: engine pulled onto input speed in this time

    def __init__(self, spec, veh):
        self.spec = spec
        self.veh = veh
        self.kind = veh.trans
        self.tc = (LaunchClutch(spec, veh) if self.kind == "dct"
                   else ManualClutch(spec, veh) if self.kind == "manual"
                   else TorqueConverter(spec, veh))
        self.gb = Gearbox(spec, veh)
        self.rigid = False          # DCT clamped: crank to wheels is solid
        self.i_eff = veh.gears[0] * veh.final
        self._sync_dt = 1.0 / 240.0
        self.snap_w_e = None
        self.v = 0.0
        self.w_in = 0.0              # transmission input (turbine) speed
        self.J_in = 0.055 * veh.mass / 1750.0 + 0.02
        self.spec_J = spec.geom.flywheel_inertia + self.J_in
        self.grade = 0.0
        self.brake = 0.0
        self.lockup = False
        self.lock_allowed = True
        self.slip_rpm = 0.0
        self.T_pump = 0.0
        self.T_turb = 0.0
        self.T_clutch = 0.0
        self.F_trac = 0.0
        self.F_res = 0.0
        self.torque_cut = 0.0
        self._thr_prev = 0.0
        # manual box (Phase 3): the pedal, the auto-clutch assist, and the
        # assist's shift sequence (timer < 0: none in progress)
        self.clutch_pedal = 0.0      # 0 = foot off (engaged), 1 = floored
        self.assist = False
        self.shift_t = -1.0
        self.shift_to = 0
        # converter lock-up clutch (FINDING-020): slip latched when an
        # engagement starts, and whether one is in progress
        self.lock_slip0 = 0.0
        self.lock_latched = False

    SHIFT_DOWN_S = 0.12              # assisted shift: pedal to the floor
    SHIFT_UP_S = 0.35                # ... and back up, slipping

    # ------------------------------------------------------------------
    def w_out_at_input(self, g=None):
        return self.v / self.veh.r_wheel * self.gb.ratio(g)

    def w_turbine(self):
        return self.w_in

    def speed_kmh(self):
        return self.v * 3.6

    def resistance(self):
        v = self.veh
        th = math.atan(self.grade)
        f_roll = v.Crr * v.mass * 9.81 * math.cos(th) * \
            (1.0 if self.v > 0.05 else 0.0)
        f_grade = v.mass * 9.81 * math.sin(th)
        f_aero = 0.5 * 1.20 * v.CdA * self.v ** 2
        f_brake = self.brake * 0.55 * v.mass * 9.81
        return f_roll + f_grade + f_aero, f_brake

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def sync(self, w_e):
        """
        After the engine has been integrated, drag the car with it.

        This MUST use the ratio the step actually drove through.  Using
        gb.ratio() instead teleports the car the instant a shift is
        requested -- the gear index changes, v = w*r/i jumps with it, and
        the log shows 700 kW of kinetic energy appearing from nowhere.
        """
        if self.rigid:
            i = max(self.i_eff, 1e-6)
            v_new = max(0.0, w_e * self.veh.r_wheel / i)
            # A rigid driveline cannot change road speed faster than the
            # tyres could push the car.  If it tries, something upstream is
            # wrong and silently accepting it would hide the bug.
            dv_max = 12.0 * max(self._sync_dt, 1e-4)
            self.v += float(np.clip(v_new - self.v, -dv_max, dv_max))

    # ------------------------------------------------------------------
    def step(self, dt, w_e, T_eng, throttle):
        if self.kind == "dct":
            return self._step_dct(dt, w_e, T_eng, throttle)
        if self.kind == "manual":
            return self._step_manual(dt, w_e, T_eng, throttle)
        return self._step_tc(dt, w_e, T_eng, throttle)

    # ------------------------------------------------------------------
    def _select(self, delta):
        """Move the lever: out of neutral into 1st, or one gear up/down."""
        gb = self.gb
        if gb.neutral:
            gb.neutral = False
            gb.gear = gb.gear_from = 0
            return
        g = int(np.clip(gb.gear + delta, 0, gb.n - 1))
        gb.gear = gb.gear_from = g

    def manual_shift(self, delta):
        """
        A shift request on the manual box. Returns the message for the
        driver, or "" if it went through. Without the assist the clutch has
        to be down -- no grinding is modelled, the lever simply will not go.
        """
        if self.assist:
            if self.shift_t < 0.0:
                self.shift_t = 0.0
                self.shift_to = delta
            return ""
        if self.clutch_pedal < 0.9:
            return "clutch down (z) to change gear"
        self._select(delta)
        self.tc.engaged = False
        return ""

    def _step_manual(self, dt, w_e, T_eng, throttle):
        """
        The dry clutch. Slipping: it passes its capacity in the direction of
        the slip and the engine and car move independently. Clamped: rigid,
        solved exactly as the DCT's clamped state (vehicle inertia reflected
        onto the crank, residual slip snapped into the engine).
        """
        veh, gb, cl = self.veh, self.gb, self.tc
        f_res, f_brake = self.resistance()

        # ---- the assist's shift: pedal down, lever across, pedal up ----
        if self.assist and self.shift_t >= 0.0:
            self.shift_t += dt
            if self.shift_t < self.SHIFT_DOWN_S:
                pedal = self.shift_t / self.SHIFT_DOWN_S
            else:
                if self.shift_to != 0:
                    self._select(self.shift_to)
                    self.shift_to = 0
                    cl.engaged = False
                up = (self.shift_t - self.SHIFT_DOWN_S) / self.SHIFT_UP_S
                pedal = max(0.0, 1.0 - up)
                if up >= 1.0:
                    self.shift_t = -1.0
            self.clutch_pedal = pedal

        i = gb.ratio()
        w_sync = self.v / veh.r_wheel * i
        if gb.neutral:
            cap = 0.0
            cl.engaged = False
        elif self.assist and self.shift_t < 0.0:
            cap = cl.assist_capacity(w_e, w_sync, T_eng, throttle)
        else:
            cap = cl.capacity(self.clutch_pedal)
        cl.cap = cap
        cl.slip = w_e - w_sync

        # ---- clamp and release ----
        if cl.engaged:
            if cap <= 0.0 or abs(T_eng) > cap:
                cl.engaged = False
        elif cap > 0.0 and abs(cl.slip) < 3.0 and abs(T_eng) <= cap:
            cl.engaged = True
            # the first instant of clamping: the residual slip goes into the
            # engine, not the car (see _step_dct)
            self.i_eff = i
            self.snap_w_e = w_sync
        self.rigid = cl.engaged
        if self.rigid:
            T_cl = T_eng
        elif gb.neutral or cap <= 0.0:
            T_cl = 0.0
        else:
            T_cl = math.copysign(cap, 1.0 if w_e >= w_sync else -1.0)

        cl.report(w_e, w_sync)
        self._sync_dt = dt
        self.i_eff = i
        self.w_in = w_sync
        self.T_pump = T_cl
        self.T_turb = T_cl
        self.T_clutch = T_cl
        gb.torque_cut = 0.0
        self.torque_cut = 0.0

        F_trac = T_cl * i * veh.eta / veh.r_wheel
        self.F_trac, self.F_res = F_trac, f_res + f_brake
        m_eff = veh.mass + (veh.J_wheel + veh.J_trans * i ** 2) \
            / veh.r_wheel ** 2
        if self.rigid:
            k = veh.r_wheel / max(i, 1e-6)
            J_add = m_eff * k * k / max(veh.eta, 0.5)
            T_react = (f_res + f_brake * np.sign(max(self.v, 0.0) + 1e-9)) \
                * k / max(veh.eta, 0.5)
            return T_react, J_add
        F_net = F_trac - f_res
        if self.v > 0.05 or F_net > f_brake:
            F_net -= f_brake * np.sign(max(self.v, 0.0) + 1e-9)
        self.v = max(0.0, self.v + F_net / m_eff * dt)
        return T_cl, 0.0

    # ------------------------------------------------------------------
    def _step_dct(self, dt, w_e, T_eng, throttle):
        """
        Dual clutch.  Two states and nothing in between:

        SLIPPING -- launching, or mid-shift.  The clutch passes exactly its
        commanded capacity, so the engine and the car accelerate
        independently and the difference is heat in the pack.

        CLAMPED  -- everything from crank to contact patch is one rigid
        body.  Solving that as a stiff spring is asking for trouble at
        60 Hz, so it is solved as what it is: the vehicle inertia is
        reflected through the ratio onto the crank and integrated as a
        single mass.  Unconditionally stable, and exactly rigid.
        """
        veh, gb = self.veh, self.gb
        d_thr = (throttle - self._thr_prev) / max(dt, 1e-6)
        self._thr_prev = throttle
        gb.update_schedule(dt, w_e * 60.0 / (2 * math.pi), throttle, d_thr)

        i_new = gb.ratio()
        i_old = gb.ratio(gb.gear_from)
        w_sync = self.v / veh.r_wheel * i_new
        creep = 1.0 if throttle > 0.02 else 0.0
        gb.torque_cut = 0.0
        f_res, f_brake = self.resistance()

        if gb.phase == gb.TORQUE:
            gb.phase_t += dt
            x = min(1.0, gb.phase_t / gb.t_torque())
            gb.blend = x
            i_use = (1.0 - x) * i_old + x * i_new
            T_cl = T_eng
            self.rigid = False
            if gb.phase_t >= gb.t_torque():
                gb.phase, gb.phase_t = gb.INERTIA, 0.0
                gb.err0 = abs(w_e - self.v / veh.r_wheel * i_new)
        elif gb.phase == gb.INERTIA:
            gb.phase_t += dt
            err = w_e - w_sync
            cap = abs(T_eng) + s_inertia(self, gb)
            T_cl = math.copysign(min(cap, self.tc.cap_max), err) \
                if abs(err) > 1e-3 else T_eng
            gb.torque_cut = 0.25 if err > 0 else 0.0
            self.rigid = False
            i_use = i_new
            if abs(err) < 2.0 or gb.phase_t > 2.5 * gb.t_inertia():
                gb.phase, gb.phase_t, gb.blend = gb.IDLE, 0.0, 0.0
                gb.gear_from = gb.gear
                self.tc.engaged = True
        elif gb.neutral:
            T_cl = 0.0
            self.rigid = False
            i_use = i_new
        else:
            cap, stuck = self.tc.command(w_e, w_sync, T_eng, throttle, creep)
            if stuck and not self.rigid:
                # First instant of clamping.  There is a little residual
                # slip, and it has to go somewhere.  It goes into the
                # ENGINE, not the car: reflected through the ratio, the
                # vehicle carries a thousand times the inertia, so the
                # crank is what gets snapped.  Doing it the other way round
                # accelerates two tonnes of car with a flywheel and shows
                # up as a 20 g spike.
                self.i_eff = i_new
                self.snap_w_e = w_sync
            self.rigid = stuck
            T_cl = T_eng if stuck else math.copysign(
                cap, 1.0 if w_e >= w_sync else -1.0)
            i_use = i_new

        self.tc.report(w_e, w_sync)
        self._sync_dt = dt
        self.i_eff = i_use
        self.w_in = w_sync
        self.T_pump = T_cl
        self.T_turb = T_cl
        self.T_clutch = T_cl
        self.torque_cut = gb.torque_cut

        F_trac = T_cl * i_use * veh.eta / veh.r_wheel
        self.F_trac, self.F_res = F_trac, f_res + f_brake
        m_eff = veh.mass + (veh.J_wheel + veh.J_trans * i_use ** 2) \
            / veh.r_wheel ** 2

        if self.rigid:
            # reflect the whole car onto the crank and hand the extra
            # inertia back to the caller
            k = veh.r_wheel / max(i_use, 1e-6)
            J_add = m_eff * k * k / max(veh.eta, 0.5)
            T_react = (f_res + f_brake * np.sign(max(self.v, 0.0) + 1e-9)) \
                * k / max(veh.eta, 0.5)
            return T_react, J_add

        F_net = F_trac - f_res
        if self.v > 0.05 or F_net > f_brake:
            F_net -= f_brake * np.sign(max(self.v, 0.0) + 1e-9)
        self.v = max(0.0, self.v + F_net / m_eff * dt)
        return T_cl, 0.0

    # ------------------------------------------------------------------
    def _step_tc(self, dt, w_e, T_eng, throttle):
        veh = self.veh
        gb = self.gb
        d_thr = (throttle - self._thr_prev) / max(dt, 1e-6)
        self._thr_prev = throttle

        gb.update_schedule(dt, self.w_in * 60.0 / (2 * math.pi),
                           throttle, d_thr)

        i_new = gb.ratio()
        i_old = gb.ratio(gb.gear_from)
        w_sync = self.w_out_at_input()

        # ---- lockup ----------------------------------------------------
        if self.lock_allowed and not gb.neutral and not gb.shifting():
            if not self.lockup:
                if (self.v > veh.v_lock_min and throttle < 0.88
                        and gb.gear >= 2 and self.tc.SR > 0.62):
                    self.lockup = True
            elif (self.v < 0.75 * veh.v_lock_min or throttle > 0.95
                    or w_e < 2 * math.pi * 1.05 * self.spec.idle_rpm / 60):
                self.lockup = False
        else:
            self.lockup = False

        # ---- the lock-up clutch: a clutch, not a spring (FINDING-020) ----
        # It was T = C_LOCK * slip, C_LOCK = 900 N.m per rad/s, integrated
        # explicitly against the flywheel: h*C/J = 17 at 240 Hz (explicit
        # Euler is stable below 2), so every locked frame sat on the
        # +-4500 N.m clamp with the sign flipping each sub-step, and a coast
        # downshift re-locked as a 1 g jolt (bug #11). Now it engages like the
        # other clutches: slipping at the capacity that pulls the engine onto
        # input speed in LOCK_ENGAGE_S (slip latched when engagement starts
        # -- recomputing it from the live slip is the shift trap in PLAN.md),
        # then clamped rigid once the slip closes or crosses zero.
        slip = w_e - self.w_in
        if not self.lockup:
            self.rigid = False
            self.lock_latched = False
        elif not self.lock_latched:
            self.lock_slip0 = slip
            self.lock_latched = True
        T_p, T_t = self.tc.torques(w_e, self.w_in)
        T_lock = 0.0
        if self.lockup and not self.rigid:
            cap = min(self.T_LOCK_MAX, abs(T_eng) + self.spec.geom.flywheel_inertia
                      * abs(self.lock_slip0) / self.LOCK_ENGAGE_S)
            if abs(slip) < 3.0 or slip * self.lock_slip0 <= 0.0:
                self.rigid = True
                self.snap_w_e = self.w_in     # the residual slip goes into the engine
            else:
                T_lock = math.copysign(cap, slip)
        if self.rigid and abs(T_eng) > self.T_LOCK_MAX:
            self.rigid = False                # beyond its capacity it slips
            self.lock_latched = False
        T_in = T_eng if self.rigid else T_t + T_lock   # torque into the gearbox
        self.slip_rpm = (w_e - self.w_in) * 60.0 / (2 * math.pi)

        gb.torque_cut = 0.0
        if gb.neutral:
            self.w_in += (T_t * 0.06) / self.J_in * dt
            T_out_i, i_use = 0.0, i_new

        elif gb.phase == gb.TORQUE:
            # Input stays tied to the OLD ratio; the oncoming clutch takes
            # over the load.  Output torque slides from old-gear to new-gear
            # for the same input torque, which IS the torque hole.
            gb.phase_t += dt
            x = min(1.0, gb.phase_t / gb.t_torque())
            gb.blend = x
            self.w_in = self.w_out_at_input(gb.gear_from)
            i_use = (1.0 - x) * i_old + x * i_new
            T_out_i = T_in
            if gb.phase_t >= gb.t_torque():
                gb.phase, gb.phase_t = gb.INERTIA, 0.0
                gb.err0 = abs(self.w_in - self.w_out_at_input())

        elif gb.phase == gb.INERTIA:
            gb.phase_t += dt
            err = self.w_in - w_sync
            # Capacity is latched from the slip present when the phase
            # STARTED.  Recomputing it from the live error makes the excess
            # capacity shrink as the error shrinks, so the slip decays
            # exponentially and the shift never actually finishes -- it just
            # asymptotes and hits the abort timer.  A real TCU commands a
            # pressure profile, which gives a near-linear ramp.
            cap = abs(T_in) + self.J_in * gb.err0 / max(gb.t_inertia(), 0.05)
            cap = min(cap, 8.0 * max(abs(T_in), 50.0))
            T_cl = math.copysign(cap, err) if abs(err) > 1e-3 else T_in
            # ask the engine to back off while the clutch does the work --
            # less heat in the pack and a much smoother handover
            gb.torque_cut = 0.35 if err > 0 else 0.0
            self.w_in += (T_in - T_cl) / self.J_in * dt
            T_out_i, i_use = T_cl, i_new
            done = abs(err) < 2.0 or \
                   (gb.err0 > 0 and err * math.copysign(1.0, gb.err0) < 0) or \
                   gb.phase_t > 2.5 * gb.t_inertia()
            if done:
                self.w_in = w_sync
                gb.phase, gb.phase_t, gb.blend = gb.IDLE, 0.0, 0.0
                gb.gear_from = gb.gear
        else:
            # locked to the output: the input shaft is kinematically tied
            self.w_in = w_sync
            T_out_i, i_use = T_in, i_new

        self.torque_cut = gb.torque_cut
        self.T_pump = T_in if self.rigid else T_p * (0.06 if gb.neutral else 1.0) + T_lock
        self.T_turb = T_out_i
        self.T_clutch = T_out_i

        # ---- vehicle ----------------------------------------------------
        F_trac = T_out_i * i_use * veh.eta / veh.r_wheel
        f_res, f_brake = self.resistance()
        m_eff = veh.mass + (veh.J_wheel + (veh.J_trans + self.J_in)
                            * i_use ** 2) / veh.r_wheel ** 2
        self._sync_dt = dt
        self.i_eff = i_use
        if self.rigid:
            # locked up: crank to wheels is one body, solved as the DCT's
            # clamped state -- the car's inertia reflected onto the crank
            self.F_trac, self.F_res = F_trac, f_res + f_brake
            k = veh.r_wheel / max(i_use, 1e-6)
            J_add = m_eff * k * k / max(veh.eta, 0.5)
            T_react = (f_res + f_brake * np.sign(max(self.v, 0.0) + 1e-9)) \
                * k / max(veh.eta, 0.5)
            return T_react, J_add
        F_net = F_trac - f_res
        if self.v > 0.05 or F_net > f_brake:
            F_net -= f_brake * np.sign(max(self.v, 0.0) + 1e-9)
        self.F_trac, self.F_res = F_trac, f_res + f_brake
        self.v = max(0.0, self.v + F_net / m_eff * dt)
        if not gb.shifting() and not gb.neutral:
            self.w_in = self.w_out_at_input()
        self.rigid = False
        return self.T_pump, 0.0


# ==========================================================================
# the live engine: what actually gets integrated in real time
# ==========================================================================
class LiveEngine:
    def __init__(self, grid: PerfGrid, preset: str = "hd_i6", trans: str = None):
        self.g = grid
        self.spec = grid.spec
        self.veh = _finish_vehicle(Vehicle(preset, trans))
        self.dl = Driveline(self.spec, self.veh)
        self.rpm = self.spec.idle_rpm
        self.throttle = 0.0
        self.engine_brake = False
        # turbo state: a first-order lag on boost, spooling faster than it
        # decays, which is what a real shaft does
        self.boost = 1.0
        self.turbo_rpm = 0.0
        self.load_eff = 0.0
        self.stalled = False
        self.T_load = 0.0
        self.torque = 0.0
        self.fuel_kg_h = 0.0
        # ---- trip computer -------------------------------------------
        # Diesel is ~0.832 kg/L at 15 C, so mass flow has to be divided by
        # density before it means anything at the pump.
        self.FUEL_DENSITY = 0.832          # kg/L
        self.odo_m = 0.0                   # lifetime distance
        self.trip_m = 0.0
        self.fuel_L = 0.0                  # lifetime fuel
        self.trip_L = 0.0
        self.inst_kmpl = 0.0
        # ---- cruise control -------------------------------------------
        self.cruise_on = False
        self.cruise_set = 0.0              # m/s
        self._cruise_i = 0.0               # integral term
        self.cruise_min_kmh = 25.0
        # ---- cooling system -------------------------------------------
        # Coolant and the metal it lives in are one lump; the thermostat
        # holds the heat in until it cracks, and the radiator only rejects
        # what the airflow through it allows -- so temperature depends on
        # ROAD SPEED as much as on load, which is why a truck cooks on a
        # slow climb and runs cool flat out on the level.
        self.T_coolant = self.spec.thermal.ambient_T
        self.fan_on = False
        self.fan_frac = 0.0            # 0..1 engagement, ramps
        self.fan_power = 0.0           # W taken off the crank
        self.T_charge = self.spec.thermal.ambient_T
        self.T_charge_ref = self.spec.thermal.ambient_T
        self.ic_eff = 0.0
        self.rad_air = 0.0             # kg/s through the core
        self.derate = 1.0              # combined power derate, 0..1
        self.derate_heat = 1.0
        self.derate_charge = 1.0
        self.engine_stopped = False
        self.overheat_msg = ""
        # BUG-6: short-lived feedback for key presses that cannot apply in
        # the current configuration. Without this, a key that does nothing
        # is indistinguishable from a key that did something invisible.
        self.hint = ""
        self.hint_t = 0.0
        self.tank_L = self.veh.fuel_tank_L
        self.out_of_fuel = False
        self.perf = grid.blend_perf(self.rpm, 0.0)
        self.lock = threading.Lock()
        if self.veh.trans == "manual":
            # a manual car is left in neutral; the driver picks a gear
            self.dl.gb.neutral = True
            self.dl.gb.auto = False
        # ---- ADR-011: friction live, from the cells' pressure traces -------
        self.adr011 = isinstance(grid, Adr011Grid)
        self.T_oil = self.spec.thermal.ambient_T     # cold start, like the coolant
        self.T_fric = 0.0          # mean friction torque [N.m], held between evaluations
        self.fmep_live = 0.0
        self.P_mech = 0.0          # friction heat into the oil [W]
        # the live friction's sound inputs (Phase 4), held like T_fric:
        # boundary friction power, skirt clearance (FINDING-023), valve seating speed
        self.Pb_live = 0.0
        self.skirt_live = 0.0
        self.vseat_live = 0.0
        self._frame = 0
        if self.adr011:
            # a private engine for the friction model: walls follow the live
            # coolant through _apply_thermal_state, oil state is ours
            from .engine import DieselEngine
            self._eng = DieselEngine(spec=copy.deepcopy(self.spec))
            self._update_friction()

    # a manual engine stalls when the clutch drags it below this fraction
    # of idle (the governor cannot hold it); an automatic cannot stall
    STALL_FRAC = 0.45
    FRICTION_EVERY = 6         # frames between live friction evaluations (10 Hz at 60 Hz)

    def _update_friction(self):
        """
        ADR-011: friction at the live oil and coolant state, from the
        pressure trace blended at the live operating point. Evaluated at no
        less than a quarter of idle: the model divides by speed, and a
        stopped engine's friction is handled where it is used.
        """
        from .acoustics import running_skirt_clearance
        from .grid import cell_friction
        g, e = self.g, self._eng
        e.T_coolant = self.T_coolant
        e._apply_thermal_state()
        e.oil.cond.T_oil = self.T_oil
        rpm = max(self.rpm, 0.25 * self.spec.idle_rpm)
        p = g.blend_perf_T(rpm, self.load_eff, self.T_coolant)
        fr = cell_friction(e, rpm, g.blend_p_cyl(rpm, self.load_eff, self.T_coolant), g.grid_deg,
                           p["fuel_mg"], p["p_rail"])
        self.fmep_live = float(fr["fmep"])
        self.P_mech = float(fr["P_mech"])
        self.T_fric = self.fmep_live * g.k_torque
        # acoustics.build_sources' definitions, at the live oil and coolant
        self.Pb_live = float(fr["Pb_rings"] + fr["Pb_skirt"] + fr["Pb_rods"] + fr["Pb_mains"] + fr["Pb_pin"])
        # FINDING-023: slap follows the running clearance, not the film
        self.skirt_live = running_skirt_clearance(e.wear.eff_skirt_clearance(), self.spec.geom.bore,
                                                  self.T_coolant)
        self.vseat_live = float(fr["v_seating"])

    def sound_inputs(self):
        """What the streaming synth takes live (livesound.LiveSynth.block's
        `live`): the loop's boost, turbo speed and load, and under ADR-011
        the live friction's, so a cold engine sounds cold."""
        out = {"boost": self.boost, "turbo_rpm": self.turbo_rpm, "load": self.load_eff}
        if self.adr011:
            out.update(Pb=self.Pb_live, skirt_clr=self.skirt_live, v_seating=self.vseat_live)
        return out

    def _perf(self, rpm, load):
        """Grid performance at the live state; torque is BRAKE torque either way."""
        g = self.g
        if self.adr011:
            p = g.blend_perf_T(rpm, load, self.T_coolant)
            p["torque"] = p["torque_ind"] - self.T_fric
            return p
        return g.blend_perf(rpm, load)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def cruise_toggle(self):
        if self.cruise_on:
            self.cruise_on = False
            return
        if self.dl.speed_kmh() >= self.cruise_min_kmh:
            self.cruise_on = True
            self.cruise_set = self.dl.v
            self._cruise_i = self.throttle      # bumpless: start where we are

    def cruise_adjust(self, d_kmh):
        if self.cruise_on:
            self.cruise_set = max(self.cruise_min_kmh / 3.6,
                                  self.cruise_set + d_kmh / 3.6)

    def _cruise(self, dt):
        """
        PI on road speed.  The integral term IS the steady throttle -- on a
        grade the error goes to zero only once the integral has found the
        throttle that balances the hill, which is exactly how a real cruise
        control finds its footing after a gradient change.
        """
        if not self.cruise_on:
            return
        if (self.dl.brake > 0.02 or self.dl.gb.neutral
                or self.dl.speed_kmh() < 0.6 * self.cruise_min_kmh):
            self.cruise_on = False           # brake or neutral cancels
            return
        err = self.cruise_set - self.dl.v
        self._cruise_i += 0.11 * err * dt
        self._cruise_i = float(np.clip(self._cruise_i, 0.0, 1.0))
        self.throttle = float(np.clip(0.22 * err + self._cruise_i, 0.0, 1.0))

    # ------------------------------------------------------------------
    @staticmethod
    def _eff_crossflow(NTU, Cr):
        """Effectiveness of a crossflow core, both fluids unmixed."""
        if NTU <= 1e-6:
            return 0.0
        if Cr < 1e-3:
            return 1.0 - math.exp(-NTU)
        e = 1.0 - math.exp((NTU ** 0.22 / Cr) *
                           (math.exp(-Cr * NTU ** 0.78) - 1.0))
        return float(min(max(e, 0.0), 0.99))

    def _thermal(self, dt):
        """
        The cooling stack, front to back: air comes in through the grille,
        goes through the charge cooler, then through the radiator, then out.
        Each core is solved with effectiveness-NTU on its own airflow.

        The consequence that matters: heat rejection scales with AIRFLOW,
        not with a fixed UA.  Crawl up a hill at full load and the ram air
        disappears, the fan has to make up the difference, and if it cannot,
        the temperature climbs.
        """
        t = self.spec.thermal
        c = self.spec.cooling
        cp_air, rho_air = 1005.0, 1.20
        T_amb = t.ambient_T

        # ---- airflow through the stack ---------------------------------
        v_face = self.dl.v * c.grille_recovery
        mdot_ram = rho_air * c.rad_core_area * v_face
        if self.T_coolant > c.fan_on_T:
            want = 1.0
        elif self.T_coolant < c.fan_off_T:
            want = 0.0
        else:
            want = self.fan_frac
        if c.fan_type == "fixed":
            want = 1.0
        self.fan_frac += (want - self.fan_frac) * min(1.0, dt / c.fan_ramp_s)
        self.fan_on = self.fan_frac > 0.05
        mdot_fan = c.fan_max_flow * self.fan_frac
        mdot_air = max(0.02, mdot_ram + mdot_fan)
        self.rad_air = mdot_air
        # a viscous or belt fan is driven by the engine and costs crank
        # power; an electric one comes off the alternator instead
        self.fan_power = c.fan_power_max * self.fan_frac ** 3

        # ---- charge-air cooler (sees ambient air) -----------------------
        afr = max(10.0, self.perf.get("afr", 20.0))
        mdot_charge = max(1e-4, self.fuel_kg_h / 3600.0 * afr)
        pr = max(1.0, self.boost)
        eta_c = max(0.4, self.spec.turbo.comp_eff_peak * 0.92)
        T_comp_out = T_amb * (1.0 + (pr ** 0.2857 - 1.0) / eta_c)
        C_ch = mdot_charge * cp_air
        C_ca = mdot_air * cp_air
        Cmin, Cmax = min(C_ch, C_ca), max(C_ch, C_ca)
        UA_ic = c.ic_UA_ref * (mdot_air / max(c.ic_air_ref, 1e-6)) ** 0.6
        self.ic_eff = self._eff_crossflow(UA_ic / max(Cmin, 1e-6),
                                          Cmin / max(Cmax, 1e-6))
        self.T_charge = T_comp_out - self.ic_eff * (T_comp_out - T_amb)
        Q_ic = self.ic_eff * Cmin * max(T_comp_out - T_amb, 0.0)
        # what the grid assumed when it was solved
        self.T_charge_ref = T_comp_out - self.spec.turbo.intercooler_eff * \
            (T_comp_out - T_amb)

        # ---- radiator (sees air already warmed by the charge cooler) ----
        T_air_rad = T_amb + (Q_ic / max(C_ca, 1e-6)
                             if c.ic_ahead_of_rad else 0.0)
        UA_rad = c.rad_UA_ref * (mdot_air / max(c.rad_air_ref, 1e-6)) ** 0.6
        eff_rad = 1.0 - math.exp(-UA_rad / max(C_ca, 1e-6))
        x = (self.T_coolant - t.thermostat_open_T) / \
            max(t.thermostat_full_T - t.thermostat_open_T, 1.0)
        x = min(1.0, max(0.0, x))
        Q_out = x * eff_rad * C_ca * max(self.T_coolant - T_air_rad, 0.0)

        # ---- coolant + metal node ---------------------------------------
        cp_cool, rho_cool, cp_metal = 3600.0, 1035.0, 480.0
        C = t.coolant_volume * rho_cool * cp_cool + t.metal_mass * cp_metal
        P_fuel = self.fuel_kg_h / 3600.0 * 42.7e6
        q_wall = float(np.clip(self.perf.get("q_wall", 0.20), 0.05, 0.45))
        Q_in = (q_wall + 0.02) * P_fuel
        if self.adr011:
            # ADR-011: an oil node, as engine.py's two-node warm-up --
            # friction heat and piston-cooling jets in, the oil cooler out to
            # the coolant. Oil temperature is what makes a cold engine cold.
            UA_o = self.spec.oil.cooler_UA * (0.35 + 0.65 * min(1.0, self.rpm / 1800.0))
            Q_oc = UA_o * (self.T_oil - self.T_coolant)
            Q_in += Q_oc
            m_oil = self.spec.oil.sump_volume * self._eng.oil.density(self.T_oil)
            self.T_oil += (self.P_mech + 0.055 * P_fuel - Q_oc) * dt / (m_oil * 1900.0)
            self.T_oil = min(max(self.T_oil, 240.0), 430.0)
        self.T_coolant += (Q_in - Q_out) * dt / C
        self.T_coolant = min(max(self.T_coolant, 240.0), 420.0)
        self._protect()

    # ------------------------------------------------------------------
    def _protect(self):
        """
        Charge-temperature and overheat derates.

        Torque follows trapped air mass, and air mass follows density, so a
        charge cooler that cannot keep up costs power in proportion to
        absolute temperature.  The overheat derate is a separate, blunter
        thing: pull fuel to cut heat rejection demand, and if that is not
        enough, stop.
        """
        c = self.spec.cooling
        # Clamped at 1.0 on the upside: a charge cooler that beats the one
        # the grid was solved with cannot invent torque the solver never
        # computed.  It can only take it away.
        self.derate_charge = float(np.clip(
            self.T_charge_ref / max(self.T_charge, 1.0), 0.70, 1.00))
        T = self.T_coolant
        if T <= c.T_derate:
            self.derate_heat = 1.0
        else:
            f = (T - c.T_derate) / max(c.T_derate_full - c.T_derate, 1.0)
            self.derate_heat = float(np.clip(
                1.0 - (1.0 - c.derate_floor) * f, c.derate_floor, 1.0))
        if c.allow_shutdown and T >= c.T_shutdown:
            self.engine_stopped = True
        if self.engine_stopped and T < c.T_restart:
            self.overheat_msg = "cooled down -- press r to restart"
        elif self.engine_stopped:
            self.overheat_msg = "ENGINE STOPPED: OVERHEAT"
        elif T >= c.T_derate:
            self.overheat_msg = "DERATING -- coolant temperature"
        elif T >= c.T_warn:
            self.overheat_msg = "coolant temperature high"
        else:
            self.overheat_msg = ""
        self.derate = self.derate_heat * self.derate_charge

    def coolant_C(self):
        return self.T_coolant - 273.15

    def fuel_frac(self):
        return max(0.0, self.tank_L / max(self.veh.fuel_tank_L, 1e-6))

    def range_km(self):
        e = self.trip_kmpl() or self.avg_kmpl()
        return self.tank_L * e if e > 0.05 else 0.0

    def refuel(self):
        self.tank_L = self.veh.fuel_tank_L
        self.out_of_fuel = False

    # ------------------------------------------------------------------
    def _totals(self, dt):
        d = self.dl.v * dt
        self.odo_m += d
        self.trip_m += d
        litres = self.fuel_kg_h / 3600.0 * dt / self.FUEL_DENSITY
        self.fuel_L += litres
        self.trip_L += litres
        self.tank_L = max(0.0, self.tank_L - litres)
        self.out_of_fuel = self.tank_L <= 0.0
        # instantaneous economy, smoothed -- the raw number is unreadable
        lph = self.fuel_kg_h / self.FUEL_DENSITY
        inst = (self.dl.speed_kmh() / lph) if lph > 1e-6 else 0.0
        a = min(1.0, dt / 0.8)
        self.inst_kmpl += (min(inst, 99.9) - self.inst_kmpl) * a

    def reset_trip(self):
        self.trip_m = 0.0
        self.trip_L = 0.0

    def trip_kmpl(self):
        return (self.trip_m / 1000.0 / self.trip_L) if self.trip_L > 1e-6 else 0.0

    def avg_kmpl(self):
        return (self.odo_m / 1000.0 / self.fuel_L) if self.fuel_L > 1e-6 else 0.0

    # ------------------------------------------------------------------
    def step(self, dt, n_sub: int = 4):
        """
        The converter couples two inertias stiffly, so integrate it in
        sub-steps -- a single 60 Hz Euler step rings.
        """
        if self.hint_t > 0.0:                      # BUG-6 hint decay
            self.hint_t = max(0.0, self.hint_t - dt)
            if self.hint_t == 0.0:
                self.hint = ""
        self._cruise(dt)
        if self.out_of_fuel or self.engine_stopped:
            self.throttle = 0.0
            self.cruise_on = False
        if self.adr011:
            if self._frame % self.FRICTION_EVERY == 0:
                self._update_friction()
            self._frame += 1
        for _ in range(n_sub):
            self._sub(dt / n_sub)
        self._totals(dt)
        self._thermal(dt)

    # ------------------------------------------------------------------
    def _sub(self, h):
        s = self.spec
        g = self.g
        rpm = self.rpm
        manual = self.veh.trans == "manual"
        if (manual and not self.stalled and rpm < self.STALL_FRAC * s.idle_rpm
                and not self.dl.gb.neutral and self.dl.tc.cap > 0.0):
            self.stalled = True
            self.hint = "stalled -- clutch down (z) and press i to restart"
            self.hint_t = 4.0

        # ---- governor: idle hold, droop above rated --------------------
        demand = 0.0 if self.stalled else self.throttle
        if rpm < s.idle_rpm and not self.stalled:
            demand = max(demand, min(0.75, 0.010 * (s.idle_rpm - rpm)))
        if rpm > s.rated_rpm:
            x = (rpm - s.rated_rpm) / max(s.max_rpm - s.rated_rpm, 1.0)
            demand *= max(0.02, 1.0 - 0.98 * x ** 1.4)

        # ---- turbo lag --------------------------------------------------
        target = self._perf(rpm, demand)
        tau = 0.55 if target["boost"] > self.boost else 0.32
        self.boost += (target["boost"] - self.boost) * min(1.0, h / tau)
        self.turbo_rpm += (target["turbo_rpm"] - self.turbo_rpm) * \
            min(1.0, h / tau)

        if target["boost"] > 1.02:
            boost_frac = float(np.clip(
                (self.boost - 1.0) / max(target["boost"] - 1.0, 1e-3),
                0.0, 1.0))
        else:
            boost_frac = 1.0
        self.load_eff = float(demand * (0.35 + 0.65 * boost_frac))

        p = self._perf(rpm, self.load_eff)
        self.perf = p
        self.torque = p["torque"]
        self.fuel_kg_h = p["fuel_kg_h"]
        if self.engine_stopped:
            # no fuel at all: what is left is motoring friction
            self.torque = min(self.torque, self._perf(rpm, 0.0)["torque"])
            self.fuel_kg_h = 0.0
        if self.stalled:
            # stalled: no fuel, and friction fades to nothing as it stops
            # (the grid's lowest row is idle, so scale it down to 0 rpm)
            self.torque = min(0.0, self._perf(rpm, 0.0)["torque"]) * \
                min(1.0, rpm / s.idle_rpm)
            self.fuel_kg_h = 0.0
        if self.engine_brake and self.throttle < 0.02:
            self.torque -= 0.30 * s.rated_rpm * 0.55

        # ---- driveline takes torque, gives back the pump load -----------
        om = 2.0 * math.pi * rpm / 60.0
        self.T_load, J_add = self.dl.step(h, om, self.torque, self.throttle)
        # The TCU asks for engine torque reduction during the inertia phase.
        # A diesel does it by pulling fuel, so it is nearly instant.
        if self.dl.torque_cut > 0.0:
            self.torque *= (1.0 - self.dl.torque_cut)
        # charge-temperature and overheat derates, then the fan it takes to
        # drive the cooling itself
        self.torque *= self.derate
        if self.fan_power > 0.0 and self.spec.cooling.fan_type != "electric":
            self.torque -= self.fan_power / max(om, 1.0)

        # ---- flywheel + converter pump ----------------------------------
        # an automatic's crank never drops below 60 rpm (it cannot stall);
        # a manual's can stop
        om_min = 0.0 if manual else 2.0 * math.pi * 60.0 / 60.0
        if self.dl.snap_w_e is not None:
            om = max(self.dl.snap_w_e, om_min)
            self.dl.snap_w_e = None
        else:
            J = s.geom.flywheel_inertia + J_add
            om += (self.torque - self.T_load) / J * h
            om = max(om, om_min)
        self.dl.sync(om)
        rpm_new = max(om * 60.0 / (2.0 * math.pi), 0.0 if manual else 60.0)
        # a converter slips, so a torque-converter automatic does not stall
        if not manual:
            self.stalled = False
        self.rpm = min(rpm_new, s.max_rpm * 1.06)


# ==========================================================================
# driver input: one key at a time, as play.py's terminal loop reads them
# ==========================================================================
def _say(live, msg, t=2.5):
    live.hint = msg
    live.hint_t = t


def handle_key(live: LiveEngine, c: str) -> None:
    """
    Apply one driver key to the live engine -- the controls play.py maps
    onto its keyboard, moved here so they are testable (bug #6) and so the
    TypeScript drive page maps the same keys to the same actions. Keys that
    are not engine controls (quit, microphone) are the caller's.

    Manual box (Phase 3): z clutch (hold), . and , shift (clutch down, or
    the assist does it), n neutral, a auto-clutch, i restart after a stall.
    """
    manual = live.veh.trans == "manual"
    if c == "w":
        live.cruise_on = False
        live.throttle = min(1.0, live.throttle + 0.08)
    elif c == "s":
        live.throttle = max(0.0, live.throttle - 0.08)
    elif c == " ":
        live.throttle = 1.0
    elif c == "x":
        live.cruise_on = False
        live.throttle = 0.0
    elif c == "b":
        # key auto-repeat keeps it applied; it decays in pedal_return()
        live.dl.brake = min(1.0, live.dl.brake + 0.35)
    elif c == "e":
        live.engine_brake = not live.engine_brake
    elif c == "n":
        if manual:
            live.dl.gb.neutral = True     # out of gear any time; into gear with . ,
        else:
            live.dl.gb.neutral = not live.dl.gb.neutral
    elif c == "m":
        if manual:
            _say(live, "manual box: . and , shift, z is the clutch, a is auto-clutch")
        else:
            live.dl.gb.auto = not live.dl.gb.auto
    elif c in ".,":
        delta = +1 if c == "." else -1
        if manual:
            msg = live.dl.manual_shift(delta)
            if msg:
                _say(live, msg)
        else:
            live.dl.gb.auto = False
            live.dl.gb.request(delta)
    elif c == "z":
        if manual:
            # key auto-repeat holds it down; it returns in pedal_return()
            live.dl.clutch_pedal = min(1.0, live.dl.clutch_pedal + 0.5)
        else:
            _say(live, "no clutch pedal -- this box is automatic")
    elif c == "a":
        if manual:
            live.dl.assist = not live.dl.assist
            _say(live, "auto-clutch on" if live.dl.assist else "auto-clutch off")
        else:
            _say(live, "auto-clutch is for the manual box")
    elif c == "i":
        if not live.stalled:
            _say(live, "engine is running")
        elif live.dl.clutch_pedal >= 0.9 or live.dl.gb.neutral or live.dl.assist:
            live.stalled = False
            live.rpm = live.spec.idle_rpm
            _say(live, "started")
        else:
            _say(live, "clutch down (z) or neutral to start")
    elif c == "]":
        live.dl.grade = min(0.20, live.dl.grade + 0.01)
    elif c == "[":
        live.dl.grade = max(-0.20, live.dl.grade - 0.01)
    elif c == "l":
        # BUG-6: lock_allowed is only read in _step_tc. A DCT has no torque
        # converter, so there is nothing to lock up and the key previously
        # toggled a flag nothing read -- silently, which is the worst outcome.
        if live.dl.veh.trans == "tc":
            live.dl.lock_allowed = not live.dl.lock_allowed
            live.hint = ("lockup allowed" if live.dl.lock_allowed
                         else "lockup blocked")
        else:
            live.hint = "lockup does not apply -- DCT has no converter"
        live.hint_t = 2.5
    elif c == "c":
        live.cruise_toggle()
    elif c in "+=":
        live.cruise_adjust(+5.0)
    elif c == "-":
        live.cruise_adjust(-5.0)
    elif c == "o":
        live.reset_trip()
    elif c == "f":
        live.refuel()
    elif c == "r":
        if (live.engine_stopped and live.T_coolant <
                live.spec.cooling.T_restart):
            live.engine_stopped = False
        live.rpm = live.spec.idle_rpm
        live.throttle = 0.0
        live.dl.v = 0.0
        live.dl.gb.gear = 0
        live.dl.brake = 0.0
        live.stalled = False


def pedal_return(live: LiveEngine, dt: float) -> None:
    """The pedals return by themselves, so holding "b" or "z" (key
    auto-repeat) keeps one down and letting go releases it. The clutch comes
    up over 1.4 s -- slowly enough to slip a launch on a keyboard (at 0.9 s a
    launch at 0.4 throttle stalled when the clutch left the floor with the
    throttle; measured, session 5)."""
    live.dl.brake = max(0.0, live.dl.brake - dt / 0.45)
    live.dl.clutch_pedal = max(0.0, live.dl.clutch_pedal - dt / 1.4)
