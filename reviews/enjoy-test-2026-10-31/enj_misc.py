"""ENJ-11 cruise, ENJ-07 braking downshifts, ENJ-14 derate lamp vs charge air."""
from harness import make, run, snap, handle_key

# ENJ-11: hatch15 auto, up to ~117 km/h, cruise on, 90 s
e = make("hatch15")
run(e, 2)
while e.dl.v * 3.6 < 117:
    run(e, 1 / 60, throttle=1.0)
e.throttle = 0.4
handle_key(e, "c")
print("ENJ-11 set", round(e.cruise_set * 3.6, 2), "km/h, cruise", e.cruise_on)
for t in (5, 10, 20, 40, 60, 90):
    run(e, 5 if t == 5 else t - prev)
    prev = t
    print(f"  t+{t:>2}s  {e.dl.v*3.6:.2f} km/h  thr {e.throttle:.3f}  i {e._cruise_i:.3f}")

# ENJ-07: hatch15 auto from ~135 km/h, throttle off, full brake (held b), until stopped; then 30 % throttle
e = make("hatch15")
run(e, 2)
while e.dl.v * 3.6 < 135:
    run(e, 1 / 60, throttle=1.0)
log = []
for i in range(60 * 30):
    run(e, 1 / 60, throttle=0.0, held=("b",))
    if i % 15 == 0:
        s = snap(e)
        log.append((round(i / 60, 2), s["gear"], s["rpm"], s["kmh"]))
    if e.dl.v < 0.05:
        break
print("ENJ-07 braking (t, gear, rpm, km/h):", log[::2])
print("  stopped in gear", e.dl.gb.gear + 1, "rpm", round(e.rpm))
run(e, 3, throttle=0.0)
print("  3 s later at rest: gear", e.dl.gb.gear + 1, "rpm", round(e.rpm))
pull = []
for i in range(60 * 4):
    run(e, 1 / 60, throttle=0.3)
    if i % 30 == 0:
        pull.append((round(i / 60, 1), e.dl.gb.gear + 1, round(e.rpm), round(e.dl.v * 3.6, 1)))
print("  pull-away at 30 %:", pull)

# ENJ-14: v8hd, desert, pass, auto, full throttle 200 s: the lamp rule is derate_heat < 1 or T_charge > 80 C
e = make("v8hd", place="desert", route="pass")
run(e, 2)
worst = None
for i in range(60 * 210):
    run(e, 1 / 60, throttle=1.0)
    if i % 600 == 0:
        s = snap(e)
        lamp = s["derate_heat"] < 1 or e.T_charge > 353.15
        print(f"  ENJ-14 t {i/60:5.0f}s gear {s['gear']} {s['kmh']:5.1f} km/h Tc {s['Tc']} Tcharge {s['Tch']} derate {s['derate']} heat {s['derate_heat']} lamp {lamp}")
    tch = e.T_charge - 273.15
    worst = tch if worst is None else max(worst, tch)
print("  ENJ-14 highest charge air over 210 s:", round(worst, 2), "C")
