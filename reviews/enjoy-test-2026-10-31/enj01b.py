"""ENJ-01: what "Now" reads in the first seconds after a long coast ends (the filter recovering from ~0)."""
from harness import make, run

e = make("hatch15")
run(e, 3)
run(e, 14, throttle=1.0)
run(e, 40, throttle=0.0)
print("after the coast: kmh %.1f inst_kmpl %.2e" % (e.dl.v * 3.6, e.inst_kmpl))
out = []
for i in range(60 * 4):
    run(e, 1 / 60, throttle=0.3)
    if i % 6 == 0:
        lph = e.fuel_kg_h / 0.832
        out.append(f"{(i+1)/60:.2f}s {100 / e.inst_kmpl if e.inst_kmpl > 0 else float('inf'):.3g} (true {100 * lph / (e.dl.v*3.6):.3g})")
print(" | ".join(out[:14]))
print(" | ".join(out[14:]))
