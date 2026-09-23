#!/usr/bin/env python3
"""
play.py -- drive the dieselsim engine in real time, with sound.

    python play.py                    # heavy-duty I6
    python play.py --preset ld_i4     # 2.0 L common-rail four
    python play.py --no-audio         # telemetry only
    python play.py --audio-test       # 2 s of noise, to prove the device works
    python play.py --rebuild          # discard the cached grid and re-solve

WHY THERE IS A CACHE
--------------------
One crank-angle operating point takes seconds to solve: 720 deg x n_cyl with
bidirectional valve flow, a bisection on bearing eccentricity and two-zone
chemistry.  You cannot do that sixty times a second, so:

  * offline, once: solve a grid of (rpm, load) points and keep the
    crank-angle-domain acoustic sources for each;
  * at runtime: integrate only the cheap things -- the flywheel and the
    turbo shaft -- and interpolate the sources between grid points.

What stays honest: flywheel inertia, governor, smoke limit, turbo lag and
the fact that pitch comes from integrating the real crank phase.
What is approximated: combustion phasing is interpolated from the grid
rather than re-solved every frame.  That is the same trade every driving
simulator makes, and it is stated here rather than hidden.

CONTROLS
--------
    w / s      throttle up / down        space  full throttle
    x          cut throttle              b      service brake (hold it)
    , / .      manual down / upshift     m      auto <-> manual gearbox
    n          neutral                   e      exhaust brake
    [ / ]      grade down / up           l      allow / forbid lockup
    1 - 5      microphone position       r      reset to a standstill
    q          quit

OFFLINE
-------
    --curve                  full-load torque/power curve, then exit
    --curve-points N         how many speeds to solve (default 9)
    --curve-load 0.5         part-load curve instead of full load
    --curve-png f.png        also write it as a figure
    --curve-csv f.csv        also write it as csv

DRIVELINE
---------
Engine -> torque converter -> 6-speed automatic -> final drive -> vehicle.
The converter is a real fluid coupling with a stator: torque ratio falls from
about 2 at stall to exactly 1 at the coupling point, capacity falls to zero at
a 1:1 speed ratio and goes negative beyond it (engine braking), and efficiency
is the product of torque ratio and speed ratio -- which is why the lockup
clutch exists and why fuel burn drops the moment it engages.
"""
from __future__ import annotations

import argparse
import math
import os
import pickle
import select
import sys
import termios
import threading
import multiprocessing as mp
import time
import tty

import numpy as np
from scipy import signal

from dieselsim.acoustics import MICS, EngineSound
from dieselsim.engine import DieselEngine
from dieselsim.grid import GRID_CYCLES, solve_cell

FS = 44100
BLOCK = 1024
CACHE_VERSION = 6   # 6: grid solved per-cell on fresh engines at GRID_CYCLES

# GRID_CYCLES and the cell solve live in dieselsim.grid (FINDING-011).

# ======================================================================
# THE SWITCH.  "tc" = torque-converter automatic, "dct" = dual clutch.
# Change this one string (or pass --transmission) and the whole driveline
# changes: coupling, launch behaviour, shift feel and efficiency.
# ======================================================================
TRANSMISSION = "dct"


# ==========================================================================
# streaming DSP -- the same models as acoustics.py, but block-by-block with
# persistent state so they can run inside an audio callback
# ==========================================================================
class Comb:
    """
    Feedback comb = a pipe with a reflecting end.

    y[n] = x[n] + refl * lowpass(y[n-D])

    Every read is of a sample written at least D ago, so a chunk of up to D
    samples has no internal dependency and can be done with numpy.  Only the
    one-pole wall loss is sequential, and lfilter handles that.
    """

    def __init__(self, delay_s: float, refl: float, fs: int, a_lp: float = 0.55):
        self.D = max(4, int(round(delay_s * fs)))
        self.buf = np.zeros(self.D)
        self.idx = 0
        self.refl = refl
        self.b = np.array([1.0 - a_lp])
        self.a = np.array([1.0, -a_lp])
        self.zi = np.zeros(1)

    def process(self, x: np.ndarray) -> np.ndarray:
        out = np.empty_like(x)
        n = 0
        while n < len(x):
            L = min(self.D - self.idx, len(x) - n)
            d = self.buf[self.idx:self.idx + L]
            lp, self.zi = signal.lfilter(self.b, self.a, d, zi=self.zi)
            y = x[n:n + L] + self.refl * lp
            self.buf[self.idx:self.idx + L] = y
            out[n:n + L] = y
            self.idx = (self.idx + L) % self.D
            n += L
        return out


class Biquad:
    """Any 2-pole/2-zero section, carrying its state between blocks."""

    def __init__(self, b, a):
        self.b = np.asarray(b, dtype=float)
        self.a = np.asarray(a, dtype=float)
        self.zi = np.zeros(max(len(self.b), len(self.a)) - 1)

    def process(self, x):
        y, self.zi = signal.lfilter(self.b, self.a, x, zi=self.zi)
        return y


def resonator_coeffs(f0, Q, fs, gain=1.0):
    f0 = min(f0, 0.45 * fs)
    r = math.exp(-math.pi * f0 / (Q * fs))
    th = 2 * math.pi * f0 / fs
    b = [gain * (1 - r), 0.0, -gain * (1 - r) * r]
    a = [1.0, -2 * r * math.cos(th), r * r]
    return b, a


def butter_sos_filter(kind, cutoff, fs, order=2):
    ny = 0.5 * fs
    if kind == "band":
        lo = max(20.0, min(cutoff[0], 0.9 * ny))
        hi = max(lo * 1.05, min(cutoff[1], 0.95 * ny))
        Wn = [lo / ny, hi / ny]
    else:
        Wn = max(5.0, min(cutoff, 0.95 * ny)) / ny
    sos = signal.butter(order, Wn, btype=kind, output="sos")
    return SosStream(sos)


class SosStream:
    def __init__(self, sos):
        self.sos = sos
        self.zi = np.zeros((sos.shape[0], 2))

    def process(self, x):
        y, self.zi = signal.sosfilt(self.sos, x, zi=self.zi)
        return y


# ==========================================================================
# the pre-solved grid
# ==========================================================================
def _grid_cell(task):
    """Worker entry for EngineGrid.build. Module-level so spawn can pickle it.
    The cell itself lives in dieselsim.grid, shared with the browser."""
    spec, i, j, rpm, ld, n_cycles = task
    src, perf = solve_cell(spec, rpm, ld, n_cycles=n_cycles, fs=FS)
    return i, j, src, perf


class EngineGrid:
    """Crank-angle acoustic sources + scalar performance on an (rpm, load) grid."""

    def __init__(self, preset: str, n_rpm: int = 8, n_load: int = 6):
        self.preset = preset
        self.n_rpm = n_rpm
        self.n_load = n_load
        self.rpms = None
        self.loads = None
        self.peak_torque = 1.0
        self.peak_power = 1.0
        self.src = None        # [i][j] -> dict of crank-angle arrays
        self.perf = None       # [i][j] -> dict of scalars
        self.grid_deg = None
        self.spec = None

    # ------------------------------------------------------------------
    def path(self):
        return f".dieselsim_grid_{self.preset}_v{CACHE_VERSION}.pkl"

    def build(self, verbose=True, torque_limit=0.0, power_limit=0.0,
              jobs=None):
        eng = DieselEngine(preset=self.preset)
        s = eng.spec
        if torque_limit > 0.0:
            s.torque_limit = torque_limit
        if power_limit > 0.0:
            s.power_limit = power_limit * 1000.0
        self.spec = s
        self.rpms = np.linspace(s.idle_rpm, s.max_rpm, self.n_rpm)
        self.loads = np.linspace(0.0, 1.0, self.n_load)
        self.grid_deg = EngineSound(s, fs=FS).grid
        self.src = [[None] * self.n_load for _ in range(self.n_rpm)]
        self.perf = [[None] * self.n_load for _ in range(self.n_rpm)]
        tasks = [(s, i, j, rpm, ld, GRID_CYCLES)
                 for i, rpm in enumerate(self.rpms)
                 for j, ld in enumerate(self.loads)]
        total = len(tasks)
        jobs = max(1, min(jobs or os.cpu_count() or 1, total))
        t0 = time.time()
        k = 0

        def _store(res):
            nonlocal k
            i, j, src, perf = res
            self.src[i][j] = src
            self.perf[i][j] = perf
            k += 1
            if verbose:
                el = time.time() - t0
                eta = el / k * (total - k)
                sys.stdout.write(
                    f"\r  solving grid {k:3d}/{total} on {jobs} worker"
                    f"{'s' if jobs > 1 else ''}  eta {eta:5.0f} s   ")
                sys.stdout.flush()

        if jobs == 1:
            # in-process: no spawn overhead, and still one fresh engine per
            # cell, so results are identical to the parallel path
            for t in tasks:
                _store(_grid_cell(t))
        else:
            ctx = mp.get_context("spawn")     # matches batch.py
            with ctx.Pool(jobs) as pool:
                for res in pool.imap_unordered(_grid_cell, tasks):
                    _store(res)
        self.peak_torque = max(self.perf[i][j]["torque"]
                               for i in range(self.n_rpm)
                               for j in range(self.n_load))
        self.peak_power = max(self.perf[i][j]["power"]
                              for i in range(self.n_rpm)
                              for j in range(self.n_load))
        if verbose:
            print(f"\r  grid solved: {total} points in "
                  f"{time.time()-t0:.0f} s{' ' * 24}")
        return self

    # ------------------------------------------------------------------
    def save(self):
        with open(self.path(), "wb") as f:
            pickle.dump(dict(preset=self.preset, rpms=self.rpms,
                             loads=self.loads, src=self.src, perf=self.perf,
                             grid_deg=self.grid_deg,
                             peak_torque=self.peak_torque,
                             peak_power=self.peak_power), f)

    def load(self):
        with open(self.path(), "rb") as f:
            d = pickle.load(f)
        self.rpms, self.loads = d["rpms"], d["loads"]
        self.src, self.perf, self.grid_deg = d["src"], d["perf"], d["grid_deg"]
        self.n_rpm, self.n_load = len(self.rpms), len(self.loads)
        self.peak_torque = d.get("peak_torque") or max(
            self.perf[i][j]["torque"] for i in range(self.n_rpm)
            for j in range(self.n_load))
        self.peak_power = d.get("peak_power") or max(
            self.perf[i][j]["power"] for i in range(self.n_rpm)
            for j in range(self.n_load))
        self.spec = DieselEngine(preset=self.preset).spec
        return self

    # ------------------------------------------------------------------
    def weights(self, rpm, load):
        """Bilinear weights and the four surrounding grid indices."""
        r = np.clip(rpm, self.rpms[0], self.rpms[-1])
        l = np.clip(load, self.loads[0], self.loads[-1])
        i = int(np.clip(np.searchsorted(self.rpms, r) - 1, 0, self.n_rpm - 2))
        j = int(np.clip(np.searchsorted(self.loads, l) - 1, 0, self.n_load - 2))
        fr = (r - self.rpms[i]) / (self.rpms[i + 1] - self.rpms[i])
        fl = (l - self.loads[j]) / (self.loads[j + 1] - self.loads[j])
        return i, j, fr, fl

    def blend_sources(self, rpm, load):
        i, j, fr, fl = self.weights(rpm, load)
        w = ((1 - fr) * (1 - fl), (1 - fr) * fl, fr * (1 - fl), fr * fl)
        q = (self.src[i][j], self.src[i][j + 1],
             self.src[i + 1][j], self.src[i + 1][j + 1])
        out = {}
        for k in ("exh_flow", "int_flow", "dpdth", "inj", "valve", "slap"):
            out[k] = (w[0] * q[0][k] + w[1] * q[1][k]
                      + w[2] * q[2][k] + w[3] * q[3][k])
        meta = {}
        for k in q[0]["_meta"]:
            try:
                meta[k] = sum(wi * qi["_meta"][k] for wi, qi in zip(w, q))
            except TypeError:
                meta[k] = q[0]["_meta"][k]
        out["_meta"] = meta
        return out

    def blend_perf(self, rpm, load):
        i, j, fr, fl = self.weights(rpm, load)
        w = ((1 - fr) * (1 - fl), (1 - fr) * fl, fr * (1 - fl), fr * fl)
        q = (self.perf[i][j], self.perf[i][j + 1],
             self.perf[i + 1][j], self.perf[i + 1][j + 1])
        return {k: sum(wi * qi[k] for wi, qi in zip(w, q)) for k in q[0]}


# ==========================================================================
# vehicle, torque converter and gearbox
# ==========================================================================
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
        if preset == "hd_i6":                     # tractor unit, laden
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
        T_ref = 1.05 * max(0.1, spec.geom.displacement * 1.9e6 / (4 * math.pi))
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

    # ------------------------------------------------------------------
    def ratio(self, g=None):
        g = self.gear if g is None else g
        return self.veh.gears[g] * self.veh.final

    def shifting(self):
        return self.phase != self.IDLE

    def request(self, delta, kickdown=False):
        g = int(np.clip(self.gear + delta, 0, self.n - 1))
        if g == self.gear or self.shifting():
            return False
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
            self.request(-1)


def s_inertia(dl, gb):
    """Extra clutch capacity that clears the latched slip on schedule."""
    J = dl.spec_J
    return J * gb.err0 / max(gb.T_INERTIA, 0.03)


class Driveline:
    """
    Converter + clutch-to-clutch gearbox + vehicle.

    The transmission input shaft is now a STATE, not a kinematic function of
    road speed.  That is what makes a shift look like a shift: during the
    inertia phase the input is slipping against the oncoming clutch, so its
    speed ramps instead of teleporting, and the engine gets dragged with it.
    """

    C_LOCK = 900.0
    T_LOCK_MAX = 4500.0

    def __init__(self, spec, veh):
        self.spec = spec
        self.veh = veh
        self.kind = veh.trans
        self.tc = (LaunchClutch(spec, veh) if self.kind == "dct"
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
        return self._step_tc(dt, w_e, T_eng, throttle)

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
            x = min(1.0, gb.phase_t / gb.T_TORQUE)
            gb.blend = x
            i_use = (1.0 - x) * i_old + x * i_new
            T_cl = T_eng
            self.rigid = False
            if gb.phase_t >= gb.T_TORQUE:
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
            if abs(err) < 2.0 or gb.phase_t > 2.5 * gb.T_INERTIA:
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

        T_p, T_t = self.tc.torques(w_e, self.w_in)
        T_lock = 0.0
        if self.lockup:
            T_lock = float(np.clip(self.C_LOCK * (w_e - self.w_in),
                                   -self.T_LOCK_MAX, self.T_LOCK_MAX))
        T_in = T_t + T_lock                      # torque into the gearbox
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
            x = min(1.0, gb.phase_t / gb.T_TORQUE)
            gb.blend = x
            self.w_in = self.w_out_at_input(gb.gear_from)
            i_use = (1.0 - x) * i_old + x * i_new
            T_out_i = T_in
            if gb.phase_t >= gb.T_TORQUE:
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
            cap = abs(T_in) + self.J_in * gb.err0 / max(gb.T_INERTIA, 0.05)
            cap = min(cap, 8.0 * max(abs(T_in), 50.0))
            T_cl = math.copysign(cap, err) if abs(err) > 1e-3 else T_in
            # ask the engine to back off while the clutch does the work --
            # less heat in the pack and a much smoother handover
            gb.torque_cut = 0.35 if err > 0 else 0.0
            self.w_in += (T_in - T_cl) / self.J_in * dt
            T_out_i, i_use = T_cl, i_new
            done = abs(err) < 2.0 or \
                   (gb.err0 > 0 and err * math.copysign(1.0, gb.err0) < 0) or \
                   gb.phase_t > 2.5 * gb.T_INERTIA
            if done:
                self.w_in = w_sync
                gb.phase, gb.phase_t, gb.blend = gb.IDLE, 0.0, 0.0
                gb.gear_from = gb.gear
        else:
            # locked to the output: the input shaft is kinematically tied
            self.w_in = w_sync
            T_out_i, i_use = T_in, i_new

        self.torque_cut = gb.torque_cut
        self.T_pump = T_p * (0.06 if gb.neutral else 1.0) + T_lock
        self.T_turb = T_out_i
        self.T_clutch = T_out_i

        # ---- vehicle ----------------------------------------------------
        F_trac = T_out_i * i_use * veh.eta / veh.r_wheel
        f_res, f_brake = self.resistance()
        m_eff = veh.mass + (veh.J_wheel + (veh.J_trans + self.J_in)
                            * i_use ** 2) / veh.r_wheel ** 2
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
    def __init__(self, grid: EngineGrid, preset: str = "hd_i6"):
        self.g = grid
        self.spec = grid.spec
        self.veh = _finish_vehicle(Vehicle(preset))
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
        for _ in range(n_sub):
            self._sub(dt / n_sub)
        self._totals(dt)
        self._thermal(dt)

    # ------------------------------------------------------------------
    def _sub(self, h):
        s = self.spec
        g = self.g
        rpm = self.rpm

        # ---- governor: idle hold, droop above rated --------------------
        demand = self.throttle
        if rpm < s.idle_rpm:
            demand = max(demand, min(0.75, 0.010 * (s.idle_rpm - rpm)))
        if rpm > s.rated_rpm:
            x = (rpm - s.rated_rpm) / max(s.max_rpm - s.rated_rpm, 1.0)
            demand *= max(0.02, 1.0 - 0.98 * x ** 1.4)

        # ---- turbo lag --------------------------------------------------
        target = g.blend_perf(rpm, demand)
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

        p = g.blend_perf(rpm, self.load_eff)
        self.perf = p
        self.torque = p["torque"]
        self.fuel_kg_h = p["fuel_kg_h"]
        if self.engine_stopped:
            # no fuel at all: what is left is motoring friction
            self.torque = min(self.torque, g.blend_perf(rpm, 0.0)["torque"])
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
        if self.dl.snap_w_e is not None:
            om = max(self.dl.snap_w_e, 2.0 * math.pi * 60.0 / 60.0)
            self.dl.snap_w_e = None
        else:
            J = s.geom.flywheel_inertia + J_add
            om += (self.torque - self.T_load) / J * h
            om = max(om, 2.0 * math.pi * 60.0 / 60.0)
        self.dl.sync(om)
        rpm_new = max(om * 60.0 / (2.0 * math.pi), 60.0)
        # a converter slips, so a torque-converter automatic does not stall
        self.stalled = False
        self.rpm = min(rpm_new, s.max_rpm * 1.06)


# ==========================================================================
# real-time sound
# ==========================================================================
class LiveSound:
    def __init__(self, grid: EngineGrid, mic: str = "exterior_7m"):
        self.g = grid
        self.spec = grid.spec
        self.fs = FS
        self.grid_deg = grid.grid_deg
        self.theta = 0.0
        self.mic = mic
        self.rng = np.random.default_rng(7)
        self.src = grid.blend_sources(self.spec.idle_rpm, 0.0)
        self.src_target = self.src
        self.level = 0.0
        self._build_chain()

    # ------------------------------------------------------------------
    def _build_chain(self):
        s = self.spec
        fs = self.fs
        c_exh = math.sqrt(1.4 * 287.0 * 750.0)
        self.exh_wg = Comb(2.0 * s.air.exhaust_pipe_length / c_exh, -0.62, fs)
        self.exh_lp = butter_sos_filter(
            "low", 900.0 * (0.02 / max(s.air.muffler_volume, 1e-4)) ** 0.25,
            fs, 2)
        self.exh_hp = butter_sos_filter("high", 35.0, fs, 1)
        self.exh_turb_lp = butter_sos_filter("low", 1400.0, fs, 1) \
            if s.turbo.enabled else None

        self.int_wg = Comb(4.0 * s.air.runner_length_int / 343.0, -0.45, fs)
        A_n, L_n, V_b = (s.air.airbox_neck_area, s.air.airbox_neck_len,
                         s.air.airbox_volume)
        f_h = 343.0 / (2 * math.pi) * math.sqrt(
            A_n / max(V_b * (L_n + 0.85 * math.sqrt(A_n / math.pi)), 1e-9))
        self.int_helm = Biquad(*resonator_coeffs(max(f_h, 25.0), 3.5, fs, 2.0))
        self.hiss_bp = butter_sos_filter("band", (700.0, 6500.0), fs, 2)

        self.knock = [Biquad(*resonator_coeffs(f0, Q, fs, gn))
                      for f0, Q, gn in ((680.0, 11.0, 1.00),
                                        (1450.0, 14.0, 0.72),
                                        (2350.0, 16.0, 0.55),
                                        (3600.0, 18.0, 0.42),
                                        (5200.0, 20.0, 0.26))]
        self.knock_f = np.array([680.0, 1450.0, 2350.0, 3600.0, 5200.0])
        self.knock_g = np.array([1.00, 0.72, 0.55, 0.42, 0.26])

        self.tick = [Biquad(*resonator_coeffs(3100.0, 26.0, fs)),
                     Biquad(*resonator_coeffs(5400.0, 30.0, fs))]
        self.injr = [Biquad(*resonator_coeffs(4200.0, 34.0, fs)),
                     Biquad(*resonator_coeffs(6800.0, 36.0, fs))]
        self.slapr = [Biquad(*resonator_coeffs(900.0, 9.0, fs)),
                      Biquad(*resonator_coeffs(1750.0, 12.0, fs))]

        self.whoosh_bp = butter_sos_filter("band", (1200.0, 9000.0), fs, 2)
        self.rumble_bp = butter_sos_filter("band", (40.0, 480.0), fs, 2)
        self.turbo_phase = 0.0
        self.gear_phase = 0.0
        self._set_mic(self.mic)

    def _set_mic(self, name):
        self.mic = name
        m = MICS[name]
        self.mic_gains = m.gains
        self.out_lp = butter_sos_filter("low", m.lp_hz, self.fs, 3)
        self.out_hp = butter_sos_filter("high", m.hp_hz, self.fs, 2)
        self.dist = max(1.0, m.distance_m) ** 0.55
        self.reverb_mix = m.reverb
        self.rev_buf = np.zeros(int(0.09 * self.fs))
        self.rev_idx = 0

    def set_mic(self, name):
        if name in MICS:
            self._set_mic(name)

    # ------------------------------------------------------------------
    def update_operating_point(self, rpm, load):
        self.src_target = self.g.blend_sources(rpm, load)

    # ------------------------------------------------------------------
    def block(self, n, rpm, load_eff, boost, turbo_rpm, running=True):
        fs = self.fs
        # crossfade the source set so grid changes never click
        a = min(1.0, n / (0.25 * fs))
        for k in ("exh_flow", "int_flow", "dpdth", "inj", "valve", "slap"):
            self.src[k] = (1 - a) * self.src[k] + a * self.src_target[k]

        # ---- crank phase: this is where pitch comes from ---------------
        dth = 6.0 * rpm / fs
        th = (self.theta + dth * np.arange(1, n + 1)) % 720.0
        self.theta = float(th[-1])

        def samp(name):
            return np.interp(th, self.grid_deg, self.src[name], period=720.0)

        if not running:
            return np.zeros(n, dtype=np.float32)

        spd = rpm / max(self.spec.rated_rpm, 1.0)
        meta = self.src["_meta"]
        out = {}

        # ---- exhaust ---------------------------------------------------
        q = samp("exh_flow")
        dq = np.diff(q, prepend=q[0]) * fs
        y = self.exh_wg.process(dq)
        y = self.exh_lp.process(y)
        if self.exh_turb_lp is not None:
            y = self.exh_turb_lp.process(y)
        y = self.exh_hp.process(y)
        out["exhaust"] = y / (np.std(y) + 1e-9)

        # ---- intake ----------------------------------------------------
        qi = samp("int_flow")
        dqi = np.diff(qi, prepend=qi[0]) * fs
        y = self.int_wg.process(dqi)
        y = self.int_helm.process(y) + 0.5 * y
        hiss = self.hiss_bp.process(self.rng.standard_normal(n))
        y = y / (np.std(y) + 1e-9) + 0.45 * hiss / (np.std(hiss) + 1e-9) * \
            min(2.0, spd * (0.3 + 0.7 * load_eff))
        out["intake"] = y

        # ---- combustion: dp/dtheta into the block modes -----------------
        exc = samp("dpdth") * (rpm / 60.0 * 360.0)
        exc = exc / (np.std(exc) + 1e-9)
        sharp = min(3.0, float(meta.get("dpdt_max", 0.0)) / 6.0e6)
        kn = np.zeros(n)
        for r, f0, gn in zip(self.knock, self.knock_f, self.knock_g):
            kn += r.process(exc) * (1.0 + sharp * (f0 / 2000.0) ** 1.1) * gn
        out["combustion"] = kn / (np.std(kn) + 1e-9)

        # ---- mechanical impulses ---------------------------------------
        tk = samp("valve") * (float(meta.get("v_seating", 1.0)) / 1.2) ** 1.5
        tk = self.tick[0].process(tk) + 0.6 * self.tick[1].process(tk)
        ij = samp("inj")
        ij = self.injr[0].process(ij) + 0.5 * self.injr[1].process(ij)
        sl = samp("slap") * (float(meta.get("skirt_clr", 30e-6)) / 30e-6) ** 0.6
        sl = self.slapr[0].process(sl) + 0.7 * self.slapr[1].process(sl)
        mech = (tk / (np.std(tk) + 1e-9) + 0.75 * ij / (np.std(ij) + 1e-9)
                + 0.9 * sl / (np.std(sl) + 1e-9))
        out["mech"] = mech / (np.std(mech) + 1e-9)

        # ---- turbo ------------------------------------------------------
        if self.spec.turbo.enabled and turbo_rpm > 1000.0:
            f_shaft = turbo_rpm / 60.0
            ph = self.turbo_phase + 2 * math.pi * f_shaft / fs * \
                np.arange(1, n + 1)
            self.turbo_phase = float(ph[-1] % (2 * math.pi))
            whine = np.sin(ph) + 0.45 * np.sin(2 * ph + 0.7) + \
                0.22 * np.sin(3 * ph + 1.4)
            wh = self.whoosh_bp.process(self.rng.standard_normal(n))
            amp = max(0.0, boost - 1.0)
            y = (0.55 * whine + 0.45 * wh / (np.std(wh) + 1e-9)) * amp
            out["turbo"] = y / (np.std(y) + 1e-9) if np.std(y) > 1e-9 \
                else np.zeros(n)
        else:
            out["turbo"] = np.zeros(n)

        # ---- gear train -------------------------------------------------
        s = self.spec
        f_mesh = s.crank_gear_teeth * rpm / 60.0
        if f_mesh < 0.45 * fs:
            ph = self.gear_phase + 2 * math.pi * f_mesh / fs * \
                np.arange(1, n + 1)
            self.gear_phase = float(ph[-1] % (2 * math.pi))
            gr = np.sin(ph) + 0.35 * np.sin(2 * ph + 1.1)
            out["gear"] = gr * (0.3 + 0.7 * load_eff)
        else:
            out["gear"] = np.zeros(n)

        # ---- rumble ------------------------------------------------------
        rum = self.rumble_bp.process(self.rng.standard_normal(n))
        out["rumble"] = rum / (np.std(rum) + 1e-9)

        # ---- mix ----------------------------------------------------------
        y = np.zeros(n)
        for k, gn in self.mic_gains.items():
            y += gn * out[k]
        y = self.out_lp.process(y)
        y = self.out_hp.process(y)
        y /= self.dist
        if self.reverb_mix > 0.0:
            y = y + self.reverb_mix * self._reverb(y)

        lvl = (0.25 + 0.75 * min(1.6, load_eff)) * (0.45 + 0.55 * spd)
        self.level += (lvl - self.level) * min(1.0, n / (0.08 * fs))
        y = y / (np.std(y) + 1e-9) * 0.22 * self.level
        y = np.tanh(1.1 * y) / math.tanh(1.1)
        return y.astype(np.float32)

    def _reverb(self, x):
        n = len(x)
        y = np.zeros(n)
        for d, g in ((0.021, 0.42), (0.037, 0.33), (0.053, 0.26)):
            D = int(d * self.fs)
            if D < len(self.rev_buf):
                z = np.concatenate([self.rev_buf[-D:], x])[:n]
                y += g * z
        self.rev_buf = np.concatenate([self.rev_buf, x])[-len(self.rev_buf):]
        return y


# ==========================================================================
# terminal UI
# ==========================================================================
class Keyboard:
    def __enter__(self):
        self.fd = sys.stdin.fileno()
        try:
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
            self.ok = True
        except termios.error:
            self.ok = False
        return self

    def __exit__(self, *a):
        if getattr(self, "ok", False):
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

    def get(self):
        if not getattr(self, "ok", False):
            return None
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None


BAR = "\u2588"


def bar(x, n=22):
    k = int(np.clip(x, 0, 1) * n)
    return BAR * k + "\u00b7" * (n - k)


# ANSI codes are kept as plain names: an escape inside an f-string
# expression is a SyntaxError before Python 3.12.
ESC = "\033["
RED, GRN, YEL, MAG, CYN, DIM, BLD, OFF = (ESC + c for c in
                                          ("31m", "32m", "33m", "35m", "36m",
                                           "2m", "1m", "0m"))


def draw(live: LiveEngine, snd: LiveSound, t, audio_on, dropouts):
    s = live.spec
    p = live.perf
    dl = live.dl
    gb = dl.gb
    rpm_frac = live.rpm / s.max_rpm
    rpm_col = RED if live.rpm > s.rated_rpm else GRN
    smoke = (YEL + "<< SMOKE LIMITED" + OFF
             if live.load_eff < live.throttle - 0.06 else "")
    drops = f"   dropouts: {dropouts}" if dropouts else ""
    gear = "N" if gb.neutral else str(gb.gear + 1)
    phase = ""
    if gb.phase == gb.TORQUE:
        gear = YEL + gear + OFF
        phase = YEL + "torque phase" + OFF
    elif gb.phase == gb.INERTIA:
        gear = YEL + gear + OFF
        phase = YEL + f"inertia phase  cut {gb.torque_cut*100:.0f} %" + OFF
    mode = "auto" if gb.auto else MAG + "manual" + OFF
    kind = "DCT" if dl.kind == "dct" else "auto"
    lock = GRN + "LOCKED" + OFF if dl.lockup else DIM + "slip  " + OFF
    slip_in = (dl.w_in - dl.w_out_at_input()) * 60.0 / (2 * math.pi)
    v_kmh = dl.speed_kmh()
    v_frac = v_kmh / (130.0 if s.geom.n_cyl > 4 else 200.0)
    ebrk = MAG + "[EXH BRAKE]" + OFF if live.engine_brake else ""
    if live.cruise_on:
        cruise = GRN + f"CRUISE {live.cruise_set*3.6:5.1f} km/h" + OFF
    else:
        cruise = DIM + "cruise off" + OFF
    # ---- gauges -------------------------------------------------------
    Tc = live.coolant_C()
    if Tc < 60:
        t_col = CYN
    elif Tc < 103:
        t_col = GRN
    else:
        t_col = RED
    t_frac = (Tc - 20.0) / 100.0
    fuel_f = live.fuel_frac()
    f_col = RED if fuel_f < 0.12 else (YEL if fuel_f < 0.25 else GRN)
    pk_T = max(getattr(live.g, "peak_torque", 1.0), 1.0)
    pk_P = max(getattr(live.g, "peak_power", 1.0), 1.0)
    T_now = max(0.0, live.torque)
    P_now = max(0.0, p["power"])
    fan = (MAG + f"FAN {live.fan_frac*100:3.0f}%" + OFF
           if live.fan_on else "        ")
    if live.engine_stopped:
        warn = RED + live.overheat_msg + OFF
    elif live.derate_heat < 0.999:
        warn = RED + live.overheat_msg + OFF
    elif live.overheat_msg:
        warn = YEL + live.overheat_msg + OFF
    elif live.hint and live.hint_t > 0.0:
        warn = YEL + live.hint + OFF
    else:
        warn = ""
    dry = RED + " OUT OF FUEL" + OFF if live.out_of_fuel else ""
    inst = f"{live.inst_kmpl:5.1f}" if live.inst_kmpl > 0.05 else "  -- "
    trip = f"{live.trip_kmpl():5.1f}" if live.trip_L > 1e-6 else "  -- "
    avg = f"{live.avg_kmpl():5.1f}" if live.fuel_L > 1e-6 else "  -- "

    lines = [
        f"  {BLD}{s.geom.n_cyl}-cyl {s.geom.displacement*1e3:.2f} L diesel{OFF}"
        f"  in  {live.veh.name}      mic: {CYN}{snd.mic}{OFF}"
        f"   t = {t:6.1f} s",
        "",
        f"  speed  {v_kmh:7.1f} km/h {CYN}{bar(v_frac, 30)}{OFF}",
        f"  rpm    {live.rpm:7.0f}      {rpm_col}{bar(rpm_frac, 30)}{OFF}",
        f"  throttle {live.throttle*100:5.0f} %  {bar(live.throttle)}",
        f"  fuelling {live.load_eff*100:5.0f} %  {bar(live.load_eff)}  {smoke}",
        f"  brake    {dl.brake*100:5.0f} %  {bar(dl.brake)}  {ebrk}  {cruise}",
        "",
        f"  odo    {live.odo_m/1000.0:8.2f} km      trip  "
        f"{live.trip_m/1000.0:7.2f} km   used {live.trip_L:6.2f} L",
        f"  now    {inst} km/L      trip  {trip} km/L      avg  {avg} km/L",
        "",
        f"  coolant  {Tc:5.1f} C  {t_col}{bar(t_frac)}{OFF} {fan} {warn}",
        f"  charge   {live.T_charge-273.15:5.1f} C   IC eff "
        f"{live.ic_eff*100:3.0f} %   core air {live.rad_air:5.2f} kg/s"
        f"   derate {live.derate*100:3.0f} %",
        f"  fuel     {live.tank_L:5.1f} L  {f_col}{bar(fuel_f)}{OFF}"
        f"  range {live.range_km():5.0f} km{dry}",
        f"  torque   {T_now:5.0f} Nm {GRN}{bar(T_now/pk_T)}{OFF} "
        f"peak {pk_T:.0f}",
        f"  power    {P_now/1000:5.0f} kW {CYN}{bar(P_now/pk_P)}{OFF} "
        f"peak {pk_P/1000:.0f}",
        "",
        f"  gear     {gear:>7}  ({kind}/{mode})  grade  {dl.grade*100:6.1f} %"
        f"   {phase}",
        f"  input sh {dl.w_in*60/(2*math.pi):7.0f} rpm    clutch slip"
        f"{slip_in:7.0f} rpm",
        (f"  clutch     slip {dl.tc.SR:5.2f}  "
         f"{'CLAMPED' if dl.rigid else 'slipping'}         "
         f"{GRN + 'rigid' + OFF if dl.rigid else DIM + 'open ' + OFF}"
         if dl.kind == "dct" else
         f"  converter  SR {dl.tc.SR:5.2f}  TR {dl.tc.TR:4.2f}  "
         f"eff {dl.tc.eff*100:4.0f} %   {lock}"),
        f"  eng torque {live.torque:7.0f} N.m    pump load{dl.T_pump:7.0f} N.m",
        f"  turbine    {dl.T_turb:7.0f} N.m    tractive {dl.F_trac/1e3:7.2f} kN",
        f"  resistance {dl.F_res/1e3:7.2f} kN     power    "
        f"{p['power']/1000:7.1f} kW",
        "",
        f"  boost {live.boost:5.2f} PR   turbo {live.turbo_rpm/1000:6.1f} krpm"
        f"   AFR {p['afr']:5.1f}   p_max {p['p_max']/1e5:5.1f} bar",
        f"  BSFC  {p['bsfc']:5.0f} g/kWh  fuel  {live.fuel_kg_h:6.2f} kg/h"
        f"   EGR {p['egr']:4.1f} %  soot {p['soot']:5.2f} g/h",
        "",
        f"  audio: {'on' if audio_on else 'OFF'}{drops}",
        DIM + "  w/s throttle  space full  x cut  b brake  n neutral  "
        "m auto/man  ,/. gear  [/] grade  c cruise  +/- set  o trip" + OFF,
        DIM + "  f refuel   1-5 mic   l lockup   e exh brake   r reset   "
        "q quit" + OFF,
    ]
    sys.stdout.write("\033[H\033[J" + "\n".join(lines) + "\n")
    sys.stdout.flush()


# ==========================================================================
# --curve : full-load torque and power curve, straight from the solver
# ==========================================================================
def ascii_chart(x, series, height=16, width=64):
    """
    Two-series overlay chart in the terminal.  series = [(label, y, char,
    colour), ...]; each is scaled to its own full range, so this shows the
    SHAPE of each curve, not their relative magnitudes.
    """
    xs = np.asarray(x, dtype=float)
    grid = [[" "] * width for _ in range(height)]
    for label, y, ch, col in series:
        y = np.asarray(y, dtype=float)
        lo, hi = float(np.min(y)), float(np.max(y))
        rng = max(hi - lo, 1e-9)
        xi = np.linspace(xs[0], xs[-1], width)
        yi = np.interp(xi, xs, y)
        for c in range(width):
            r = int(round((1.0 - (yi[c] - lo) / rng) * (height - 1)))
            r = min(max(r, 0), height - 1)
            grid[r][c] = col + ch + OFF
    out = []
    for r, row in enumerate(grid):
        out.append("     |" + "".join(row))
    out.append("     +" + "-" * width)
    lab = f"{xs[0]:.0f}".ljust(width // 2) + f"{xs[-1]:.0f}".rjust(
        width - width // 2)
    out.append("      " + lab + "   rpm")
    return "\n".join(out)


def curve_mode(preset: str, n_points: int, load: float, png: str = None,
               csv: str = None, torque_limit: float = 0.0,
               power_limit: float = 0.0, jobs: int = None):
    """
    Full-load curve.

    Every speed on the curve is an independent solve, so this farms them out
    across CPU cores.  Note PROCESSES, not threads: the solver is pure
    scalar Python, so the GIL means threads would serialise it and buy
    nothing.  jobs=1 stays in-process, which keeps tracebacks readable.
    """
    from dieselsim import batch

    eng = DieselEngine(preset=preset)
    s = eng.spec
    overrides = {}
    if torque_limit > 0.0:
        s.torque_limit = torque_limit
        overrides["torque_limit"] = torque_limit
    if power_limit > 0.0:
        s.power_limit = power_limit * 1000.0
        overrides["power_limit"] = power_limit * 1000.0
    print(s.summary())
    if overrides:
        print(f"  rated limits: torque {s.torque_limit or 0:.0f} N.m, "
              f"power {(s.power_limit or 0)/1000:.0f} kW")

    lo = s.idle_rpm + 50.0
    rpms = np.linspace(lo, s.max_rpm, n_points)
    jobs = jobs or max(1, (os.cpu_count() or 1))
    jobs = min(jobs, n_points)
    print(f"\nsolving {n_points} operating points at {load*100:.0f} % load "
          f"({lo:.0f} - {s.max_rpm:.0f} rpm) on {jobs} core"
          f"{'s' if jobs > 1 else ''}\n")

    t0 = time.time()
    ops = batch.solve_points(preset, [(r, load) for r in rpms],
                             n_cycles=9, jobs=jobs, overrides=overrides,
                             verbose=(jobs > 1))
    el = time.time() - t0

    print(BLD + ("   rpm   torque   power   BMEP   BSFC  p_max  boost   AFR  "
                 "T_exh    NOx   soot") + OFF)
    print("        [N.m]    [kW]  [bar] [g/kWh] [bar]   [PR]        [K] "
          "[g/kWh] [g/kWh]")
    for rpm, o in zip(rpms, ops):
        if o.power > 0.0:
            tail = (f"{o.bsfc:7.1f} {o.p_max/1e5:6.1f} {o.boost_pr:6.2f} "
                    f"{o.afr:5.1f} {o.T_exh:6.0f} "
                    f"{o.nox_g_kwh:6.2f} {o.soot_g_kwh:7.4f}")
        else:
            tail = (f"{'-':>7} {o.p_max/1e5:6.1f} {o.boost_pr:6.2f} "
                    f"{'-':>5} {o.T_exh:6.0f} {'-':>6} {'-':>7}"
                    + DIM + "  motoring" + OFF)
        print(f"  {rpm:5.0f} {o.torque:8.1f} {o.power/1e3:7.1f} "
              f"{o.bmep/1e5:6.2f} " + tail)

    T = np.array([o.torque for o in ops])
    P = np.array([o.power / 1e3 for o in ops])
    ok = P > 0.0
    if not np.any(ok):
        print("\n  every point is motoring -- nothing to summarise")
        return 0
    B = np.where(ok, [o.bsfc for o in ops], np.inf)
    idx = np.arange(len(ops))
    i_t = int(idx[ok][np.argmax(T[ok])])
    i_p = int(idx[ok][np.argmax(P[ok])])
    i_b = int(np.argmin(B))
    print(f"\n  peak torque  {T[i_t]:7.1f} N.m ({T[i_t]/9.80665:5.2f} kg.m) "
          f"@ {rpms[i_t]:5.0f} rpm")
    print(f"  rated power  {P[i_p]:7.1f} kW  ({P[i_p]*1000/735.5:5.1f} ps) "
          f"@ {rpms[i_p]:5.0f} rpm")
    print(f"  best BSFC    {B[i_b]:7.1f} g/kWh @ {rpms[i_b]:5.0f} rpm")
    rise = (T[i_t] / T[i_p] - 1) * 100 if abs(T[i_p]) > 1e-6 else 0.0
    print(f"  torque rise  {rise:6.1f} %   solved in {el:.0f} s")
    if not np.all(ok):
        print(DIM + f"  ({int((~ok).sum())} point(s) above rated are "
              f"motoring -- the governor has cut the fuel)" + OFF)
    print(f"\n  {GRN}T{OFF} = torque    {CYN}P{OFF} = power   "
          f"(each scaled to its own range)")
    print(ascii_chart(rpms, [("torque", T, "T", GRN),
                             ("power", P, "P", CYN)]))

    if csv:
        with open(csv, "w") as f:
            f.write("rpm,torque_Nm,power_kW,bmep_bar,bsfc_g_kWh,pmax_bar,"
                    "boost_PR,afr,T_exh_K,nox_g_kWh,soot_g_kWh,fmep_bar,"
                    "eta_mech,fuel_mg\n")
            for rpm, o in zip(rpms, ops):
                f.write(f"{rpm:.0f},{o.torque:.2f},{o.power/1e3:.3f},"
                        f"{o.bmep/1e5:.3f},{o.bsfc:.2f},{o.p_max/1e5:.2f},"
                        f"{o.boost_pr:.3f},{o.afr:.2f},{o.T_exh:.1f},"
                        f"{o.nox_g_kwh:.3f},{o.soot_g_kwh:.5f},"
                        f"{o.fmep/1e5:.3f},{o.eta_mech:.4f},"
                        f"{o.fuel_mg:.2f}\n")
        print(f"\n  wrote {csv}")

    if png:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            print("  matplotlib not available -- skipping the png")
            return 0
        fig, axs = plt.subplots(2, 3, figsize=(11, 5.4))
        axs = axs.ravel()
        axs[0].plot(rpms, T, "o-", ms=3, color="tab:green")
        axs[0].set_ylabel("torque [N.m]")
        a2 = axs[0].twinx()
        a2.plot(rpms, P, "s--", ms=3, color="tab:blue")
        a2.set_ylabel("power [kW]", color="tab:blue")
        a2.grid(False)
        axs[1].plot(rpms, B, "o-", ms=3)
        axs[1].set_ylabel("BSFC [g/kWh]")
        axs[2].plot(rpms, [o.p_max / 1e5 for o in ops], "o-", ms=3,
                    label="p_max")
        axs[2].plot(rpms, [o.boost_pr * 10 for o in ops], "s--", ms=3,
                    label="boost x10")
        axs[2].legend(fontsize=6)
        axs[2].set_ylabel("bar")
        axs[3].plot(rpms, [o.afr for o in ops], "o-", ms=3)
        axs[3].set_ylabel("AFR [-]")
        axs[4].plot(rpms, [o.eta_mech * 100 for o in ops], "o-", ms=3)
        axs[4].set_ylabel("mech. efficiency [%]")
        axs[5].plot(rpms, [o.nox_g_kwh for o in ops], "o-", ms=3, label="NOx")
        a3 = axs[5].twinx()
        a3.plot(rpms, [o.soot_g_kwh for o in ops], "s--", ms=3, color="k")
        a3.set_ylabel("soot [g/kWh]")
        a3.grid(False)
        axs[5].set_ylabel("NOx [g/kWh]")
        for a in axs:
            a.set_xlabel("engine speed [rpm]")
            a.grid(alpha=0.25)
        fig.suptitle(f"{preset}: {load*100:.0f} % load", y=1.0)
        fig.tight_layout()
        fig.savefig(png, dpi=120, bbox_inches="tight")
        print(f"  wrote {png}")
    return 0


# ==========================================================================
def audio_test(mic="exterior_7m"):
    try:
        import sounddevice as sd
    except ImportError:
        print("sounddevice is not installed:  pip install sounddevice")
        print("and on Debian/Ubuntu:  sudo apt install libportaudio2")
        return 1
    print("devices:")
    print(sd.query_devices())
    print("\nplaying 2 s of filtered noise at 25 % ...")
    n = 2 * FS
    y = signal.sosfilt(signal.butter(2, [80 / (FS / 2), 2000 / (FS / 2)],
                                     btype="band", output="sos"),
                       np.random.default_rng(0).standard_normal(n))
    y = (y / np.max(np.abs(y)) * 0.25).astype(np.float32)
    try:
        sd.play(np.stack([y, y], axis=1), FS, blocking=True)
        print("done -- if you heard nothing, the problem is the device, "
              "not the simulator")
    except Exception as e:
        print(f"playback failed: {e!r}")
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    # engines/*.json are registered before the parser is built, so a new
    # engine needs no code change at all -- drop the file in and it appears
    # in --preset
    from dieselsim.builder import load_engine_dir
    from dieselsim.config import PRESETS
    load_engine_dir(os.environ.get("DIESELSIM_ENGINES", "engines"))
    ap.add_argument("--preset", default="hd_i6", choices=sorted(PRESETS))
    ap.add_argument("--mic", default="exterior_7m", choices=list(MICS))
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--audio-test", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--rpm-points", type=int, default=8)
    ap.add_argument("--load-points", type=int, default=6)
    ap.add_argument("--torque-limit", type=float, default=0.0,
                    metavar="NM", help="cap brake torque (0 = no cap)")
    ap.add_argument("--power-limit", type=float, default=0.0,
                    metavar="KW", help="cap brake power (0 = no cap)")
    ap.add_argument("--curve", action="store_true",
                    help="print a full-load torque/power curve and exit")
    ap.add_argument("--curve-points", type=int, default=9)
    ap.add_argument("--curve-load", type=float, default=1.0,
                    help="load fraction for --curve (default 1.0 = full load)")
    ap.add_argument("--curve-png", metavar="PNG",
                    help="also write the curve as a figure")
    ap.add_argument("--transmission", "--trans", default=None,
                    choices=["tc", "dct"],
                    help="tc = torque-converter auto, dct = dual clutch "
                         "(default: the TRANSMISSION constant in this file)")
    ap.add_argument("--load", type=float, default=0.0, metavar="FRAC",
                    help="throttle the interactive sim starts at, 0-1 "
                         "(the live equivalent of --curve-load)")
    ap.add_argument("--start-kmh", type=float, default=0.0, metavar="V",
                    help="road speed to start rolling at")
    ap.add_argument("--jobs", "-j", type=int, default=0,
                    metavar="N", help="parallel processes for --curve and grid builds "
                    "(0 = one per core)")
    ap.add_argument("--curve-csv", metavar="CSV",
                    help="also write the curve as csv")
    ap.add_argument("--record", metavar="WAV",
                    help="also write everything you hear to a wav file")
    args = ap.parse_args()

    # Nothing should be accepted and then quietly dropped: tell the user
    # which flags do not apply to the mode they picked.
    _curve_only = {"curve_points": 9, "curve_load": 1.0, "curve_png": None,
                   "curve_csv": None, "jobs": 0}
    _live_only = {"load": 0.0, "start_kmh": 0.0, "mic": "exterior_7m",
                  "rpm_points": 8, "load_points": 6, "record": None,
                  "no_audio": False}
    _stray = _curve_only if not args.curve else _live_only
    _names = [f"--{k.replace('_', '-')}" for k, d in _stray.items()
              if getattr(args, k) != d]
    if _names and not args.audio_test:
        where = "--curve" if not args.curve else "the interactive sim"
        print(f"note: {', '.join(_names)} only apply to {where}; ignoring")

    if args.transmission:
        globals()["TRANSMISSION"] = args.transmission

    if args.audio_test:
        return audio_test(args.mic)

    if args.curve:
        return curve_mode(args.preset, args.curve_points, args.curve_load,
                          args.curve_png, args.curve_csv,
                          args.torque_limit, args.power_limit,
                          args.jobs or None)

    grid = EngineGrid(args.preset, args.rpm_points, args.load_points)
    if os.path.exists(grid.path()) and not args.rebuild:
        print(f"loading cached grid {grid.path()}")
        try:
            grid.load()
        except Exception as e:
            print(f"  cache unreadable ({e!r}) -- rebuilding")
            grid.build(True, args.torque_limit,
                       args.power_limit, jobs=args.jobs or None).save()
    else:
        print(f"solving the physics grid for '{args.preset}' "
              f"({args.rpm_points} x {args.load_points} points).")
        print("this happens once; the result is cached next to this script.")
        grid.build().save()

    if args.torque_limit > 0.0:
        grid.spec.torque_limit = args.torque_limit
    if args.power_limit > 0.0:
        grid.spec.power_limit = args.power_limit * 1000.0
    live = LiveEngine(grid, args.preset)
    # --load is the live twin of --curve-load: it sets the demand the engine
    # starts at.  It is a THROTTLE, not a delivered load -- the smoke limiter
    # and turbo lag still stand between it and the fuelling, exactly as they
    # do when you press "w".
    if args.load:
        live.throttle = float(np.clip(args.load, 0.0, 1.0))
    if args.start_kmh:
        live.dl.v = max(0.0, args.start_kmh / 3.6)
        # pick a gear that does not bounce off the limiter at that speed
        gb = live.dl.gb
        for g in range(gb.n):
            gb.gear = g
            if live.dl.w_turbine() * 60.0 / (2 * math.pi) < gb.up_rpm:
                break
    snd = LiveSound(grid, args.mic)

    stream = None
    dropouts = [0]
    rec = [] if args.record else None
    if not args.no_audio:
        try:
            import sounddevice as sd

            def callback(outdata, frames, time_info, status):
                if status:
                    dropouts[0] += 1
                try:
                    with live.lock:
                        rpm, le = live.rpm, live.load_eff
                        b, tr = live.boost, live.turbo_rpm
                        run = not live.stalled
                    y = snd.block(frames, rpm, le, b, tr, run)
                    if rec is not None:
                        rec.append(y.copy())
                    outdata[:, 0] = y
                    if outdata.shape[1] > 1:
                        outdata[:, 1] = y
                except Exception:
                    # never swallow a callback exception in silence -- that is
                    # exactly how audio bugs stay invisible for hours
                    import traceback
                    traceback.print_exc()
                    outdata.fill(0)

            stream = sd.OutputStream(samplerate=FS, channels=2,
                                     blocksize=BLOCK, dtype="float32",
                                     callback=callback)
            stream.start()
        except ImportError:
            print("sounddevice not installed -- running silent. "
                  "pip install sounddevice")
            time.sleep(1.5)
        except Exception as e:
            print(f"audio device failed ({e!r}) -- running silent")
            time.sleep(1.5)

    dt = 1.0 / 60.0
    t = 0.0
    last_draw = 0.0
    last_src = 0.0
    try:
        with Keyboard() as kb:
            if not kb.ok:
                print("stdin is not a tty -- keyboard control unavailable")
            while True:
                c = kb.get()
                if c:
                    if c == "q":
                        break
                    elif c == "w":
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
                        # key auto-repeat keeps it applied; it decays below
                        live.dl.brake = min(1.0, live.dl.brake + 0.35)
                    elif c == "e":
                        live.engine_brake = not live.engine_brake
                    elif c == "n":
                        live.dl.gb.neutral = not live.dl.gb.neutral
                    elif c == "m":
                        live.dl.gb.auto = not live.dl.gb.auto
                    elif c == ".":
                        live.dl.gb.auto = False
                        live.dl.gb.request(+1)
                    elif c == ",":
                        live.dl.gb.auto = False
                        live.dl.gb.request(-1)
                    elif c == "]":
                        live.dl.grade = min(0.20, live.dl.grade + 0.01)
                    elif c == "[":
                        live.dl.grade = max(-0.20, live.dl.grade - 0.01)
                    elif c == "l":
                        # BUG-6: lock_allowed is only read in _step_tc. A DCT
                        # has no torque converter, so there is nothing to lock
                        # up and the key previously toggled a flag nothing
                        # read -- silently, which is the worst outcome.
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
                    elif c in "12345":
                        snd.set_mic(list(MICS)[int(c) - 1])

                # the brake pedal returns by itself, so holding "b" (key
                # auto-repeat) keeps it on and letting go releases it
                live.dl.brake = max(0.0, live.dl.brake - dt / 0.45)
                with live.lock:
                    live.step(dt)
                # refresh the interpolated source set 20 times a second;
                # the audio thread crossfades to it
                if t - last_src > 0.05:
                    snd.update_operating_point(live.rpm, live.load_eff)
                    last_src = t
                if t - last_draw > 0.1:
                    draw(live, snd, t, stream is not None, dropouts[0])
                    last_draw = t
                t += dt
                time.sleep(dt)
    except KeyboardInterrupt:
        pass
    finally:
        if stream is not None:
            stream.stop()
            stream.close()
        sys.stdout.write("\033[?25h\n")
        if rec:
            import wave
            y = np.concatenate(rec)
            y = y / (np.max(np.abs(y)) + 1e-9) * 0.89
            pcm = (np.stack([y, y], axis=1) * 32767).astype("<i2")
            with wave.open(args.record, "wb") as w:
                w.setnchannels(2)
                w.setsampwidth(2)
                w.setframerate(FS)
                w.writeframes(pcm.tobytes())
            print(f"wrote {args.record}  ({len(y)/FS:.1f} s)")
        print("bye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
