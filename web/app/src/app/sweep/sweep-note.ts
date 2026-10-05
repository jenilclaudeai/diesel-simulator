import { ACCURACY, ACCURACY_SOLVER, type PresetAccuracy } from '../dyno/accuracy';

/**
 * The sweep page's statement of its resolution (FINDING-013). Each point is a
 * fast 9-cycle solve, so two points closer than that solve's error can't be
 * told apart: measured on crdi15, its compression-ratio sweep dipped 0.3% at
 * 16 between 15 and 17. The measured full-load error is quoted only for the
 * build it was measured on, as the Dyno page's note does.
 */
export function sweepNote(
  preset: string, solver: string,
  table: Record<string, PresetAccuracy> = ACCURACY, tableSolver: string = ACCURACY_SOLVER,
): string {
  const lead = 'Each point is a fast 9-cycle solve, so differences between points smaller than its error are noise, not physics.';
  const a = solver === tableSolver ? table[preset] : undefined;
  const part = ' At part load, with EGR and the VGT working, that error can be far larger (FINDING-013).';
  if (!a) return `${lead} For this engine it has not been measured on this solver build.${part}`;
  if (a.worstPct === 0) return `${lead} For this engine at full load it matches a fully converged solve.${part}`;
  return `${lead} For this engine at full load it is up to ${Math.abs(a.worstPct).toFixed(1)}% in torque.${part}`;
}
