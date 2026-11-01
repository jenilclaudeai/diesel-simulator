// The trip computer's figures (Phase 5). FINDING-009: the fuel comes from
// steady-state grid cells, about 29% leaner than mixed real-world driving at
// a 90 km/h cruise -- so the page labels them "steady-state" and never sets
// them beside brochure figures.

/** Average consumption over a trip, L/100 km; null until 0.1 km has been driven. */
export function avgL100(trip_L: number, trip_km: number): number | null {
  return trip_km >= 0.1 ? (100 * trip_L) / trip_km : null;
}

/** live.py's _totals: its fuel density [kg/L], and the flow below which it counts no fuel [L/h]. */
const FUEL_DENSITY = 0.832;
const FUEL_CUT_LPH = 1e-6;

/**
 * Instantaneous consumption, L/100 km, from km/L; null when stopped or coasting (no meaningful figure).
 *
 * Coasting is read from the fuel flow, not from km/L (ENJ-01): on an overrun fuel cut the loop feeds
 * 0 km/L into a 0.8 s filter that only decays, so inst_kmpl is never 0 -- 3e-19 after 35 s, which
 * read as 3e20 L/100 km.
 */
export function nowL100(inst_kmpl: number, kmh: number, fuel_kg_h: number): number | null {
  if (!(kmh >= 3) || !(fuel_kg_h / FUEL_DENSITY > FUEL_CUT_LPH)) return null;
  if (!(inst_kmpl > 0) || !Number.isFinite(inst_kmpl)) return null;
  return 100 / inst_kmpl;
}

/** Range left on the tank at the trip's average, km; null without an average. */
export function rangeKm(tank_L: number, trip_L: number, trip_km: number): number | null {
  const a = avgL100(trip_L, trip_km);
  return a && a > 0 ? (100 * tank_L) / a : null;
}
