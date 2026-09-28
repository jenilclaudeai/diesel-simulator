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
from dieselsim.livesound import LiveSynth
from dieselsim.live import (  # noqa: F401  (the real-time loop, Phase 3)
    Driveline, Gearbox, LaunchClutch, LiveEngine, PerfGrid, TorqueConverter,
    Vehicle, handle_key, pedal_return)

FS = 44100
BLOCK = 1024
CACHE_VERSION = 7   # 7: cells carry p_cyl and p_rail (ADR-011); 6: per-cell fresh engines at GRID_CYCLES

# GRID_CYCLES and the cell solve live in dieselsim.grid (FINDING-011).

# ======================================================================
# THE SWITCH.  "tc" = torque-converter automatic, "dct" = dual clutch.
# Change this one string (or pass --transmission) and the whole driveline
# changes: coupling, launch behaviour, shift feel and efficiency.
# ======================================================================
TRANSMISSION = "dct"


# ==========================================================================
# the pre-solved grid
# ==========================================================================
def _grid_cell(task):
    """Worker entry for EngineGrid.build. Module-level so spawn can pickle it.
    The cell itself lives in dieselsim.grid, shared with the browser."""
    spec, i, j, rpm, ld, n_cycles, converged, flim = task
    src, perf = solve_cell(spec, rpm, ld, n_cycles=n_cycles, fs=FS,
                           converged=converged, fuel_limit=flim)
    return i, j, src, perf


def _row_fuel_limit(task):
    """Worker entry: the converged full-load fuel at one rpm, calibrated once
    and shared by every cell in that row (FINDING-013)."""
    spec, i, rpm = task
    eng = DieselEngine(spec=spec)
    eng.converged_mode = True
    return i, eng.fuel_limit(float(rpm))


class EngineGrid(PerfGrid):
    """Crank-angle acoustic sources + scalar performance on an (rpm, load) grid."""

    def __init__(self, preset: str, n_rpm: int = 8, n_load: int = 6,
                 converged: bool = False):
        self.preset = preset
        # converged: solve every cell at real time until settled
        # (DieselEngine.converged_mode, FINDING-013). For prebuilt grids;
        # much slower than the default fast cells.
        self.converged = converged
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
        conv = "_converged" if self.converged else ""
        return f".dieselsim_grid_{self.preset}{conv}_v{CACHE_VERSION}.pkl"

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
        flims = [None] * self.n_rpm
        total = self.n_rpm * self.n_load
        jobs = max(1, min(jobs or os.cpu_count() or 1, total))
        t0 = time.time()
        if self.converged:
            # one converged limiter calibration per rpm row, shared by its cells
            rows = [(s, i, rpm) for i, rpm in enumerate(self.rpms)]
            if jobs == 1:
                res = [_row_fuel_limit(r) for r in rows]
            else:
                with mp.get_context("spawn").Pool(min(jobs, len(rows))) as pool:
                    res = pool.map(_row_fuel_limit, rows)
            for i, f in res:
                flims[i] = f
            if verbose:
                print(f"  converged fuel limits: {len(rows)} rows in "
                      f"{time.time() - t0:.0f} s")
        tasks = [(s, i, j, rpm, ld, GRID_CYCLES, self.converged, flims[i])
                 for i, rpm in enumerate(self.rpms)
                 for j, ld in enumerate(self.loads)]
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

# ==========================================================================
# vehicle, gearbox, driveline and the live engine: dieselsim/live.py
# ==========================================================================


# ==========================================================================
# real-time sound
# ==========================================================================
class LiveSound:
    """The audio callback's view of dieselsim.livesound.LiveSynth, the
    streaming synth shared with the browser (FINDING-021: the copy that lived
    here had drifted from acoustics.py and ignored the physics its sources
    carry). sounddevice asks for BLOCK frames; the synth makes LS.BLOCK."""

    def __init__(self, grid: EngineGrid, mic: str = "exterior_7m"):
        self.g = grid
        self.spec = grid.spec
        self.mic = mic
        self.syn = LiveSynth(grid.spec, mic, fs=FS)
        self.syn.set_sources(grid.blend_sources(self.spec.idle_rpm, 0.0))
        self.buf = np.zeros(0)

    def set_mic(self, name):
        if name in MICS:
            self.mic = name
            self.syn.set_mic(name)

    def update_operating_point(self, rpm, load):
        # the synth glides to the new set; one dict assignment, so the audio
        # thread never sees half of it
        self.syn.set_sources(self.g.blend_sources(rpm, load))

    def block(self, n, rpm, load_eff, boost, turbo_rpm, running=True):
        live = dict(load=load_eff, boost=boost, turbo_rpm=turbo_rpm)
        parts = [self.buf]
        have = len(self.buf)
        while have < n:
            y = self.syn.block(rpm, live, running)
            parts.append(y)
            have += len(y)
        y = np.concatenate(parts)
        self.buf = y[n:]
        return y[:n].astype(np.float32)


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
    ap.add_argument("--converged-grid", action="store_true",
                    help="solve the grid at real time until every cell settles "
                         "(FINDING-013); much slower, for prebuilt grids")
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
                    choices=["tc", "dct", "manual"],
                    help="tc = torque-converter auto, dct = dual clutch, "
                         "manual = clutch pedal (z) and lever (. ,) "
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

    grid = EngineGrid(args.preset, args.rpm_points, args.load_points,
                      converged=args.converged_grid)
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
        # --torque-limit, --power-limit and --jobs used to be dropped here and
        # honoured only when an unreadable cache forced a rebuild
        grid.build(True, args.torque_limit, args.power_limit,
                   jobs=args.jobs or None).save()

    if args.torque_limit > 0.0:
        grid.spec.torque_limit = args.torque_limit
    if args.power_limit > 0.0:
        grid.spec.power_limit = args.power_limit * 1000.0
    live = LiveEngine(grid, args.preset, trans=TRANSMISSION)
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
                    elif c in "12345":
                        snd.set_mic(list(MICS)[int(c) - 1])
                    else:
                        # every engine control lives in dieselsim.live, so the
                        # browser's drive page maps the same keys the same way
                        handle_key(live, c)

                pedal_return(live, dt)
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
