// Kept apart from solver.service.ts, which imports the generated
// physics-version.ts: unit tests run before prepare-assets makes it (CI).

/**
 * How many workers a drivable-grid build uses: one per core but one (the
 * page keeps a core), at most 6 (each worker holds its own Python, ~150 MB);
 * 2 on a device that says it has under 4 GB.
 */
export function poolSize(cores = navigator.hardwareConcurrency || 2,
                         memGb = (navigator as Navigator & { deviceMemory?: number }).deviceMemory): number {
  const n = Math.max(1, Math.min(6, cores - 1));
  return memGb !== undefined && memGb < 4 ? Math.min(n, 2) : n;
}
