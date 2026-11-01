"""Estimated native build time (cells + weather, 6 workers, this M2) of the
recommended ten, from P09's rebuild log (out/p09_rebuild.log, per grid)
scaled by R5's measured speed-ups (ADR-020: cells x1.77, weather x1.28).
Each candidate takes the time of the shipped grid with its cylinder layout."""
P09 = {  # grid: (cells s, weather s), out/p09_rebuild.log
    "crdi22": (903, 2550), "hatch15": (905, 2571), "truck127": (1192, 3553),
    "v8hd": (1509, 4550), "single10": (304, 853)}
R5_CELLS, R5_WX = 1.77, 1.28


def mins(ref):
    c, w = P09[ref]
    return (c / R5_CELLS + w / R5_WX) / 60.0


# a 3- and 5-cylinder have no shipped grid: interpolate per cylinder between the single and the four
per_cyl = (mins("crdi22") - mins("single10")) / 3.0
TEN = [("vw19tdi", "I4", mins("hatch15")), ("mhawk75", "I3", mins("single10") + 2 * per_cyl),
       ("mhawk22", "I4", mins("crdi22")), ("gd28", "I4", mins("crdi22")),
       ("duratorq32", "I5", mins("crdi22") + per_cyl), ("b57", "I6", mins("truck127")),
       ("cummins59", "I6", mins("truck127")), ("cummins67", "I6", mins("truck127")),
       ("duramax66", "V8", mins("v8hd")), ("powerstroke73", "V8", mins("v8hd"))]
for k, lay, m in TEN:
    print(f"{k:14s} {lay}  {m:5.0f} min")
b1 = sum(m for _, _, m in TEN[:6])
b2 = sum(m for _, _, m in TEN[6:])
print(f"batch 1 (first six): {b1 / 60:.1f} h; batch 2 (four pickups): {b2 / 60:.1f} h; total {(b1 + b2) / 60:.1f} h")
today = 7.2  # ADR-020: R5's rebuild of the ten shipped grids
print(f"a full rebuild: today's ten {today} h, twenty {today + (b1 + b2) / 60:.1f} h")
