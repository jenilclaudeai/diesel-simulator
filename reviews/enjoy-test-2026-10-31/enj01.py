from harness import make, run, snap

e = make("hatch15")
run(e, 3)
run(e, 14, throttle=1.0)
print("after 14 s full:", snap(e))
log = []
run(e, 40, throttle=0.0, every=5, log=log)
for r in log:
    k = r["inst_kmpl"]
    print(r["kmh"], r["gear"], "fuel", r["fuel_kg_h"], "inst_kmpl %.3e" % k, "Now L/100 %.3e" % (100 / k) if k > 0 else None)
