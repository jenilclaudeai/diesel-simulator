import type { PresetInfo } from '@dieselsim/solver';

// Pure, so its tests need no solver (and not the generated physics-version.ts).

/** The grid the real-time loop reads: play.py's default, 8 speeds x 6 loads. */
export const N_RPM = 8;
export const N_LOAD = 6;

/**
 * Evenly spaced from idle to maximum speed, and from no load to full load --
 * with the same float operations as e2e/native_grid.py, so the browser and
 * the native reference solve exactly the same cells.
 */
export function gridAxes(s: Pick<PresetInfo, 'idle_rpm' | 'max_rpm'>): { rpms: number[]; loads: number[] } {
  const lin = (a: number, b: number, n: number) => Array.from({ length: n }, (_, i) => a + (b - a) * i / (n - 1));
  return { rpms: lin(s.idle_rpm, s.max_rpm, N_RPM), loads: lin(0, 1, N_LOAD) };
}
