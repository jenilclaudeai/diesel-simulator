// The trip computer's figures (Phase 5). FINDING-009: the fuel comes from
// steady-state grid cells, about 29% leaner than mixed real-world driving at
// a 90 km/h cruise -- so the page labels them "steady-state" and never sets
// them beside brochure figures.

/** Average consumption over a trip, L/100 km; null until 0.1 km has been driven. */
export function avgL100(trip_L: number, trip_km: number): number | null {
  return trip_km >= 0.1 ? (100 * trip_L) / trip_km : null;
}

/** Instantaneous consumption, L/100 km, from km/L; null when stopped or coasting (no meaningful figure). */
export function nowL100(inst_kmpl: number, kmh: number): number | null {
  if (!(kmh >= 3) || !(inst_kmpl > 0) || !Number.isFinite(inst_kmpl)) return null;
  return 100 / inst_kmpl;
}

/** Range left on the tank at the trip's average, km; null without an average. */
export function rangeKm(tank_L: number, trip_L: number, trip_km: number): number | null {
  const a = avgL100(trip_L, trip_km);
  return a && a > 0 ? (100 * tank_L) / a : null;
}
