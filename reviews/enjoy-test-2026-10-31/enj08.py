"""ENJ-08: the highest rpm each roster engine reaches at full throttle, in neutral and in 1st (manual),
against max_rpm and P01's LIMITER threshold (0.985 * max_rpm)."""
from harness import make, run, handle_key

ROSTER = ["hatch15", "crdi22", "vw19tdi", "mhawk75", "mhawk22", "gd28", "duratorq32", "b57", "truck127", "v8hd", "single10"]
print("engine | idle | rated | max | 0.985*max | peak neutral | peak 1st | free-rev peak/max")
for k in ROSTER:
    e = make(k, trans="manual")
    sp = e.spec
    run(e, 2)
    # neutral (the manual starts in neutral), full throttle 8 s
    peak_n = 0
    for _ in range(8 * 60):
        run(e, 1 / 60, throttle=1.0)
        peak_n = max(peak_n, e.rpm)
    run(e, 4, throttle=0.0)
    # 1st gear: clutch down, shift, full throttle, clutch out over 1 s, then 15 s
    e2 = make(k, trans="manual")
    run(e2, 2)
    run(e2, 0.5, held=("z",))
    handle_key(e2, ".")
    run(e2, 0.5, held=("z",), throttle=0.5)
    peak_1 = 0
    for _ in range(15 * 60):
        run(e2, 1 / 60, throttle=1.0)
        peak_1 = max(peak_1, e2.rpm)
    mx = sp.max_rpm
    print(f"{k} | {sp.idle_rpm:.0f} | {sp.rated_rpm:.0f} | {mx:.0f} | {0.985*mx:.0f} | {peak_n:.0f} | {peak_1:.0f} gear {e2.dl.gb.gear+1} | {peak_n/mx:.3f}")
