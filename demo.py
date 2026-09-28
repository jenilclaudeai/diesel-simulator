#!/usr/bin/env python3
"""
demo.py -- exercise the whole dieselsim package and write every artefact.

Run:  python3 demo.py [outdir]
"""
import os
import sys
import time

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec

from dieselsim.engine import DieselEngine
from dieselsim.acoustics import EngineSound, MICS

OUT = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/outputs"
STAGE = sys.argv[2] if len(sys.argv) > 2 else "all"
os.makedirs(OUT, exist_ok=True)
CACHE = os.path.join(OUT, ".cache")
os.makedirs(CACHE, exist_ok=True)


def run(tag):
    return STAGE in ("all", tag)


import pickle


def store(name, obj):
    with open(os.path.join(CACHE, name + ".pkl"), "wb") as f:
        pickle.dump(obj, f)


def load_cached(name):
    with open(os.path.join(CACHE, name + ".pkl"), "rb") as f:
        return pickle.load(f)
plt.rcParams.update({"figure.dpi": 120, "font.size": 8,
                     "axes.grid": True, "grid.alpha": 0.25,
                     "axes.titlesize": 9, "figure.facecolor": "white"})
T0 = time.time()


def log(msg):
    print(f"[{time.time()-T0:6.1f}s] {msg}", flush=True)


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    log(f"wrote {name}")
    return p


# ==========================================================================
log("building engine (12.74 L heavy-duty inline-6, VGT, cooled EGR)")
eng = DieselEngine(preset="hd_i6")
print(eng.spec.summary())

# --------------------------------------------------------------------------
# 1. in-cylinder cycle
# --------------------------------------------------------------------------
if run("s1"):
 log("solving reference operating point 1500 rpm / full load")
 op = eng.operating_point(1500, load=1.0, n_cycles=9)
 print("   ", op)
 cyc = op.cycle
 th, p = cyc.traces.theta, cyc.traces.p[0]
 V = cyc.traces.V

 fig = plt.figure(figsize=(11, 6.5))
 gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.32, wspace=0.26)

 ax = fig.add_subplot(gs[0, 0])
 ax.plot(V * 1e3, p / 1e5, lw=1.0)
 ax.set_xscale("log"); ax.set_yscale("log")
 ax.set_xlabel("volume [L]"); ax.set_ylabel("pressure [bar]")
 ax.set_title("p-V (log-log)")

 ax = fig.add_subplot(gs[0, 1])
 m = (th > 630) | (th < 90)
 x = np.where(th > 360, th - 720, th)
 o = np.argsort(x)
 ax.plot(x[o], p[o] / 1e5, lw=1.1)
 ax.set_xlim(-60, 90); ax.set_xlabel("crank angle ATDC [deg]")
 ax.set_ylabel("pressure [bar]"); ax.set_title(
     f"cylinder pressure   p_max={op.p_max/1e5:.0f} bar")

 ax = fig.add_subplot(gs[0, 2])
 ax.plot(x[o], cyc.traces.hrr[0][o], lw=1.0, color="crimson")
 ax.set_xlim(-30, 90); ax.set_xlabel("crank angle ATDC [deg]")
 ax.set_ylabel("dQ/dtheta [J/deg]")
 ax.set_title(f"heat release  (delay {cyc.ign_delay_deg:.1f}deg, "
              f"CA50 {cyc.mfb50:.1f}deg)")

 ax = fig.add_subplot(gs[1, 0])
 ax.plot(th, cyc.traces.T[0], lw=0.9, label="bulk")
 ax.plot(th, cyc.traces.T_burned[0], lw=0.9, label="burned zone")
 ax.set_xlabel("crank angle [deg]"); ax.set_ylabel("T [K]")
 ax.legend(fontsize=6); ax.set_title("two-zone temperature")

 ax = fig.add_subplot(gs[1, 1])
 ax.plot(th, cyc.traces.valve_lift_int * 1e3, lw=0.9, label="intake")
 ax.plot(th, cyc.traces.valve_lift_exh * 1e3, lw=0.9, label="exhaust")
 ax.set_xlabel("crank angle [deg]"); ax.set_ylabel("lift [mm]")
 ax.legend(fontsize=6); ax.set_title("valve lift")

 ax = fig.add_subplot(gs[1, 2])
 ax.plot(th, cyc.traces.p_int_manifold / 1e5, lw=0.9, label="intake manifold")
 ax.plot(th, cyc.traces.p_exh_manifold / 1e5, lw=0.9, label="exhaust manifold")
 ax.set_xlabel("crank angle [deg]"); ax.set_ylabel("p [bar]")
 ax.legend(fontsize=6); ax.set_title("gas exchange")
 fig.suptitle("In-cylinder process, 1500 rpm full load", y=0.97)
 save(fig, "01_cycle.png")

 # --------------------------------------------------------------------------
 # 2. full-load curve
 # --------------------------------------------------------------------------
 log("full-load curve")
 rpms = np.array([700, 900, 1100, 1300, 1500, 1700, 1800, 1900, 2000])
 curve = [eng.operating_point(float(r), load=1.0, n_cycles=7) for r in rpms]
 for o in curve:
     print("   ", o)

 fig, axs = plt.subplots(2, 3, figsize=(11, 5.6))
 axs = axs.ravel()
 axs[0].plot(rpms, [o.torque for o in curve], "o-", ms=3)
 axs[0].set_ylabel("torque [N.m]"); axs[0].set_title("torque")
 a2 = axs[0].twinx(); a2.plot(rpms, [o.power / 1e3 for o in curve], "s--",
                              ms=3, color="crimson")
 a2.set_ylabel("power [kW]", color="crimson"); a2.grid(False)
 axs[1].plot(rpms, [o.bsfc for o in curve], "o-", ms=3)
 axs[1].set_ylabel("BSFC [g/kWh]"); axs[1].set_title("brake specific fuel cons.")
 axs[2].plot(rpms, [o.p_max / 1e5 for o in curve], "o-", ms=3, label="p_max")
 axs[2].plot(rpms, [o.boost_pr * 1.013 * 10 for o in curve], "s--", ms=3,
             label="boost x10")
 axs[2].legend(fontsize=6); axs[2].set_ylabel("bar"); axs[2].set_title(
     "peak pressure / boost")
 axs[3].plot(rpms, [o.cycle.afr for o in curve], "o-", ms=3)
 axs[3].set_ylabel("AFR [-]"); axs[3].set_title("air-fuel ratio (smoke limit)")
 axs[4].plot(rpms, [o.eta_mech * 100 for o in curve], "o-", ms=3)
 axs[4].set_ylabel("%"); axs[4].set_title("mechanical efficiency")
 axs[5].plot(rpms, [o.nox_g_kwh for o in curve], "o-", ms=3, label="NOx")
 a3 = axs[5].twinx()
 a3.plot(rpms, [o.soot_g_kwh for o in curve], "s--", ms=3, color="k")
 a3.set_ylabel("soot [g/kWh]"); a3.grid(False)
 axs[5].set_ylabel("NOx [g/kWh]"); axs[5].set_title("engine-out emissions")
 for a in axs:
     a.set_xlabel("engine speed [rpm]")
 fig.suptitle("Full-load performance", y=1.0)
 fig.tight_layout()
 save(fig, "02_full_load.png")

 # --------------------------------------------------------------------------
 # 3. friction / tribology
 # --------------------------------------------------------------------------
 log("friction breakdown and film thicknesses")
 keys = ["rings", "skirt", "piston_pin", "rod_bearings", "main_bearings",
         "valvetrain", "windage", "oil_pump", "water_pump", "fan",
         "alternator", "air_compressor", "fuel_pump"]
 stack = np.array([[o.friction_breakdown[k] / 1e3 for o in curve] for k in keys])

 fig, axs = plt.subplots(1, 3, figsize=(11.5, 3.6))
 axs[0].stackplot(rpms, stack, labels=keys)
 axs[0].legend(fontsize=5, ncol=2, loc="upper left")
 axs[0].set_xlabel("rpm"); axs[0].set_ylabel("kW")
 axs[0].set_title("friction & parasitic power")
 axs[1].plot(rpms, [o.fmep / 1e5 for o in curve], "o-", ms=3, label="FMEP")
 axs[1].plot(rpms, [o.pmep / 1e5 for o in curve], "s-", ms=3, label="PMEP")
 axs[1].plot(rpms, [o.bmep / 1e5 for o in curve], "^-", ms=3, label="BMEP")
 axs[1].legend(fontsize=6); axs[1].set_xlabel("rpm"); axs[1].set_ylabel("bar")
 axs[1].set_title("mean effective pressures")

 fr = op.friction
 axs[2].semilogy(op.theta, np.abs(fr["torque"]) + 1e-3, lw=0.7)
 axs[2].set_xlabel("crank angle [deg]")
 axs[2].set_ylabel("friction torque [N.m]")
 axs[2].set_title("instantaneous friction torque")
 fig.tight_layout()
 save(fig, "03_friction.png")

 # ---- Stribeck / film ----
 log("Stribeck sweep: film thickness vs oil temperature")
 temps = np.linspace(273, 403, 12)
 h_ring, h_rod, fmep_T, pgal = [], [], [], []
 T_save = eng.oil.cond.T_oil
 for T in temps:
     eng.oil.cond.T_oil = float(T)
     f = eng.friction.evaluate(op.theta, op.cycle.traces.p[0], 1500.0,
                               eng.oil, eng.wear, fuel_mg=op.fuel_mg,
                               p_rail=op.cycle.rail_pressure)
     h_ring.append(f["h_ring"] * 1e6); h_rod.append(f["h_rod"] * 1e6)
     fmep_T.append(f["fmep"] / 1e5); pgal.append(f["gallery_pressure"] / 1e5)
 eng.oil.cond.T_oil = T_save

 fig, axs = plt.subplots(1, 3, figsize=(11, 3.2))
 axs[0].plot(temps - 273.15, fmep_T, "o-", ms=3)
 axs[0].set_xlabel("oil temperature [C]"); axs[0].set_ylabel("FMEP [bar]")
 axs[0].set_title("cold oil = thick oil = friction")
 axs[1].plot(temps - 273.15, h_rod, "o-", ms=3, label="rod bearing h_min")
 axs[1].set_xlabel("oil temperature [C]"); axs[1].set_ylabel("h_min [um]")
 axs[1].legend(fontsize=6); axs[1].set_title("minimum oil film")
 axs[2].plot(temps - 273.15, pgal, "o-", ms=3)
 axs[2].set_xlabel("oil temperature [C]"); axs[2].set_ylabel("gallery p [bar]")
 axs[2].set_title("oil pressure")
 fig.tight_layout()
 save(fig, "04_tribology.png")

 store("curve", [op] + curve)

# --------------------------------------------------------------------------
# 4. EGR trade-off
# --------------------------------------------------------------------------
if run("s2"):
 log("EGR sweep: the NOx / soot / fuel trade-off")
 egrs = np.linspace(0.0, 1.0, 6)
 sw = [eng.operating_point(1400, load=0.65, egr=float(e_), n_cycles=8)
       for e_ in egrs]
 fig, axs = plt.subplots(1, 3, figsize=(11, 3.2))
 x = [o.egr_pct for o in sw]
 axs[0].plot(x, [o.nox_g_kwh for o in sw], "o-", ms=3)
 axs[0].set_ylabel("NOx [g/kWh]")
 axs[1].plot(x, [o.soot_g_kwh * 1e3 for o in sw], "o-", ms=3, color="k")
 axs[1].set_ylabel("soot [mg/kWh]")
 axs[2].plot(x, [o.bsfc for o in sw], "o-", ms=3, color="crimson")
 axs[2].set_ylabel("BSFC [g/kWh]")
 for a, t in zip(axs, ("NOx falls with flame temperature",
                       "soot rises as oxygen is displaced",
                       "and you pay for it in fuel")):
     a.set_xlabel("EGR fraction [%]"); a.set_title(t)
 fig.suptitle("EGR trade-off at 1400 rpm, 65 % load -- emergent, not scripted",
              y=1.04)
 fig.tight_layout()
 save(fig, "05_egr_tradeoff.png")

# --------------------------------------------------------------------------
# 5. warm-up
# --------------------------------------------------------------------------
if run("s3"):
 log("cold start warm-up (-1 C oil and coolant)")
 eng_w = DieselEngine(preset="hd_i6")
 wl = eng_w.warmup(minutes=10.0, load=0.25, dt_s=25.0, T_start=272.0)
 t_w = np.array([r["t"] / 60 for r in wl])
 fig, axs = plt.subplots(1, 4, figsize=(12.5, 2.9))
 axs[0].plot(t_w, [r["T_oil"] - 273.15 for r in wl]); axs[0].set_ylabel("oil T [C]")
 axs[1].semilogy(t_w, [r["visc"] * 1e3 for r in wl]); axs[1].set_ylabel("mu [mPa.s]")
 axs[2].plot(t_w, [r["fmep"] / 1e5 for r in wl]); axs[2].set_ylabel("FMEP [bar]")
 axs[3].plot(t_w, [r["oil_p"] / 1e5 for r in wl]); axs[3].set_ylabel("oil press [bar]")
 for a in axs:
     a.set_xlabel("time [min]")
 fig.suptitle("Cold start: viscosity, friction and oil pressure during warm-up",
              y=1.06)
 fig.tight_layout()
 save(fig, "06_warmup.png")

# --------------------------------------------------------------------------
# 6. durability
# --------------------------------------------------------------------------
if run("s4"):
 log("durability: 12000 h duty cycle with wear + oil ageing feedback")
 eng_d = DieselEngine(preset="hd_i6")
 dl = eng_d.durability_run(12000.0, step_h=100.0, verbose=False,
                           resolve_every=5)
 for r in dl[::8]:
     print(f"   {r['hours']:7.0f} h | {r['power']/1e3:6.1f} kW | "
           f"BSFC {r['bsfc']:6.1f} | blowby {r['blowby']:5.1f} L/min | "
           f"bore {r['bore_wear_um']:5.1f} um | oil p {r['oil_p']/1e5:4.2f} bar "
           f"| soot {r['oil_soot']:4.2f}% | life {r['health']:5.1f}%")
 h = np.array([r["hours"] for r in dl])
 fig, axs = plt.subplots(3, 4, figsize=(12.8, 7.4))
 axs = axs.ravel()
 pairs = [("power", 1e-3, "rated power [kW]"),
          ("bsfc", 1.0, "BSFC [g/kWh]"),
          ("blowby", 1.0, "blow-by [L/min]"),
          ("p_max", 1e-5, "peak pressure [bar]"),
          ("bore_wear_um", 1.0, "bore wear at TDC [um]"),
          ("ring_gap_mm", 1.0, "top ring gap [mm]"),
          ("oil_cons", 1.0, "oil consumption [g/h]"),
          ("health", 1.0, "life consumed [%]"),
          ("oil_soot", 1.0, "oil soot [% w/w]"),
          ("oil_tbn", 1.0, "oil TBN [mg KOH/g]"),
          ("oil_visc", 1.0, "oil viscosity multiplier"),
          ("oil_p", 1e-5, "oil gallery [bar]")]
 for a, (k, s_, lab) in zip(axs, pairs):
     a.plot(h, [r[k] * s_ for r in dl], lw=1.0)
     a.set_ylabel(lab); a.set_xlabel("hours")
 fig.suptitle("Durability: wear, oil ageing and the 500 h drain interval "
              "(note the sawtooth -- oil is a consumable, and the engine "
              "feels it)", y=1.0)
 fig.tight_layout()
 save(fig, "07_durability.png")

# --------------------------------------------------------------------------
# 7. transient
# --------------------------------------------------------------------------
if run("s5"):
 log("transient: tip-in from idle (turbo lag + smoke)")
 eng_t = DieselEngine(preset="hd_i6")


 def load_torque(t, rpm):
     return 380.0 + 0.28 * rpm + 2.6e-4 * rpm ** 2


 tl = eng_t.transient(3.0, throttle_fn=lambda t: 0.08 if t < 0.5 else 1.0,
                      load_torque_fn=load_torque, dt=0.05, rpm0=650,
                      n_cycles=3)
 tt = np.array([r["t"] for r in tl])
 fig, axs = plt.subplots(1, 5, figsize=(13.5, 2.9))
 axs[0].plot(tt, [r["rpm"] for r in tl]); axs[0].set_ylabel("rpm")
 axs[1].plot(tt, [r["boost"] for r in tl]); axs[1].set_ylabel("boost [PR]")
 axs[2].plot(tt, [r["turbo_rpm"] / 1e3 for r in tl])
 axs[2].set_ylabel("turbo [krpm]")
 axs[3].plot(tt, [r["afr"] for r in tl]); axs[3].set_ylabel("AFR")
 axs[3].axhline(eng_t.spec.afr_limit, ls="--", lw=0.8, color="r")
 axs[4].plot(tt, [r["smoke"] for r in tl]); axs[4].set_ylabel("soot [g/h]")
 for a in axs:
     a.set_xlabel("time [s]")
 fig.suptitle("Free acceleration: turbo lag, the smoke limiter and the "
              "black puff", y=1.06)
 fig.tight_layout()
 save(fig, "08_transient.png")

 store("transient", tl)

# --------------------------------------------------------------------------
# 8. sound
# --------------------------------------------------------------------------
if run("s6"):
 log("rendering audio")
 snd = EngineSound(eng.spec)
 snd.wear = eng.wear
 wavs = []
 tl = load_cached("transient")
 eng_t = None

 op_idle = eng.operating_point(620, fuel_mg=22.0, n_cycles=7)
 op_cruise = eng.operating_point(1250, load=0.45, n_cycles=7)
 op_full = eng.operating_point(1800, load=1.0, n_cycles=7)

 for tag, o in (("idle_620rpm", op_idle), ("cruise_1250rpm", op_cruise),
                ("fullload_1800rpm", op_full)):
     y, _ = snd.render(o, duration=4.0, mic="exterior_7m")
     wavs.append(snd.write_wav(os.path.join(OUT, f"sound_{tag}.wav"), y))
     log(f"  {tag}")

 # microphone comparison at full load
 for mic in MICS:
     y, _ = snd.render(op_full, duration=3.0, mic=mic)
     wavs.append(snd.write_wav(os.path.join(OUT, f"sound_mic_{mic}.wav"), y))
 log("  mic positions")

 # rev sweep -- pitch comes from the integrated crank phase
 sweep_ops = {r: eng.operating_point(r, load=0.85, n_cycles=9)
              for r in (750, 950, 1150, 1350, 1550, 1750, 1950)}


 def rpm_of(t):
     return 700 + (2050 - 700) * min(1.0, t / 6.5)


 chunks = []
 edges = np.linspace(0, 6.8, 34)
 for a, b in zip(edges[:-1], edges[1:]):
     rr = rpm_of(0.5 * (a + b))
     key = min(sweep_ops, key=lambda k: abs(k - rr))
     y, _ = snd.render(sweep_ops[key], duration=(b - a), mic="exterior_7m",
                       rpm_traj=lambda x, o=a: rpm_of(o + x))
     chunks.append(y)
 sw_y = np.concatenate(chunks)
 wavs.append(snd.write_wav(os.path.join(OUT, "sound_rev_sweep.wav"), sw_y))
 log("  rev sweep")

 tr_y = snd.render_transient(eng_t, tl, mic="exterior_7m", blend=0.25)
 wavs.append(snd.write_wav(os.path.join(OUT, "sound_transient_tipin.wav"), tr_y))
 log("  transient tip-in")

 # ---- what 12 000 h of wear sounds like -------------------------------
 eng_old = DieselEngine(preset="hd_i6")
 eng_old.durability_run(12000.0, step_h=500.0, verbose=False,
                        resolve_every=4)
 snd_old = EngineSound(eng_old.spec)
 snd_old.wear = eng_old.wear
 op_old = eng_old.operating_point(1250, load=0.45, n_cycles=7)
 y_old, _ = snd_old.render(op_old, duration=4.0, mic="engine_bay")
 wavs.append(snd_old.write_wav(
     os.path.join(OUT, "sound_worn_12000h_1250rpm.wav"), y_old))
 y_new, _ = snd.render(op_cruise, duration=4.0, mic="engine_bay")
 wavs.append(snd.write_wav(
     os.path.join(OUT, "sound_new_0h_1250rpm.wav"), y_new))
 log(f"  worn vs new  (lash +{eng_old.wear.state.lash_growth_exh*1e6:.0f} um, "
     f"skirt clr {eng_old.wear.eff_skirt_clearance()*1e6:.0f} um, "
     f"blowby {op_old.blowby_lpm:.0f} L/min)")

 # acoustic analysis figure
 fig = plt.figure(figsize=(11.5, 6.0))
 gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.34, wspace=0.26)
 y_full, parts = snd.render(op_full, duration=1.2, mic="exterior_7m")
 ax = fig.add_subplot(gs[0, 0])
 n0 = int(0.20 * snd.fs)
 ax.plot(np.arange(n0) / snd.fs * 1e3, y_full[:n0], lw=0.5)
 ax.set_xlabel("time [ms]"); ax.set_ylabel("p [a.u.]")
 ax.set_title("waveform, 1800 rpm full load")

 ax = fig.add_subplot(gs[0, 1])
 for tag, o, c in (("idle", op_idle, "tab:blue"),
                   ("cruise", op_cruise, "tab:orange"),
                   ("full load", op_full, "tab:red")):
     yy, _ = snd.render(o, duration=2.0, mic="exterior_7m")
     f, P = snd.spectrum(yy)
     ax.semilogx(f, P, lw=0.7, label=tag, color=c)
 ax.set_xlim(20, 12000); ax.set_xlabel("Hz"); ax.set_ylabel("dB")
 ax.legend(fontsize=6); ax.set_title("spectrum vs load")

 ax = fig.add_subplot(gs[0, 2])
 for k, c in (("exhaust", "tab:red"), ("intake", "tab:blue"),
              ("combustion", "k"), ("turbo", "tab:green")):
     f, P = snd.spectrum(parts[k])
     ax.semilogx(f, P, lw=0.7, label=k, color=c)
 ax.set_xlim(20, 15000); ax.set_xlabel("Hz"); ax.legend(fontsize=6)
 ax.set_title("source decomposition")

 ax = fig.add_subplot(gs[1, :2])
 f, t_, S = __import__("scipy.signal", fromlist=["spectrogram"]).spectrogram(
     sw_y, snd.fs, nperseg=2048, noverlap=1536)
 SdB = 10 * np.log10(S + 1e-18)
 vmax = float(np.percentile(SdB, 99.8))
 ax.pcolormesh(t_, f, SdB, shading="gouraud", cmap="magma",
               vmin=vmax - 55, vmax=vmax)
 ax.set_ylim(0, 4000); ax.set_xlabel("time [s]"); ax.set_ylabel("Hz")
 ax.set_title("rev sweep spectrogram -- engine orders fan out from the "
              "firing frequency")

 ax = fig.add_subplot(gs[1, 2])
 sources = snd.build_sources(op_full)
 ax.plot(snd.grid, sources["exh_flow"] / max(sources["exh_flow"].max(), 1e-9),
         lw=0.7, label="exhaust flow")
 ax.plot(snd.grid, sources["int_flow"] / max(sources["int_flow"].max(), 1e-9)
         - 1.15, lw=0.7, label="intake flow")
 dd = sources["dpdth"]
 ax.plot(snd.grid, dd / max(abs(dd).max(), 1e-9) + 1.3, lw=0.7,
         label="dp/dtheta")
 ax.plot(snd.grid, sources["valve"] / max(sources["valve"].max(), 1e-9) - 2.4,
         lw=0.7, label="valve seating")
 ax.set_yticks([]); ax.set_xlabel("crank angle [deg]")
 ax.legend(fontsize=5, loc="upper right")
 ax.set_title("crank-angle-domain sources (I6, all cylinders)")
 save(fig, "09_acoustics.png")

 log(f"done -- {len(wavs)} wav files, figures in {OUT}")
