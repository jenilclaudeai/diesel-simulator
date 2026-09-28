import { ACCURACY, ACCURACY_SOLVER, type PresetAccuracy } from './accuracy';

/**
 * The dyno page's statement of its own accuracy (FINDING-013).
 *
 * The page solves each point on the fast path (9 accelerated cycles) so a
 * pull takes about a minute. That path is not converged wherever the VGT or
 * EGR loop is active. The measured gap to converged solves is shown -- but
 * only when it was measured on the solver build the page is running (the
 * grid hash: the live loop and the synth never run in a pull); any other
 * build gets a plain "not measured" rather than a stale number.
 */
export function accuracyNote(
  preset: string,
  solver: string,
  fmtRpm: (rpm: number) => string = String,
  table: Record<string, PresetAccuracy> = ACCURACY,
  tableSolver: string = ACCURACY_SOLVER,
): string {
  const lead = 'Each point is solved in 9 fast cycles so a pull takes about a minute.';
  const a = solver === tableSolver ? table[preset] : undefined;
  if (!a) {
    return `${lead} How far that is from a fully converged solve has not been measured for this solver build.`;
  }
  if (a.worstPct === 0 && a.governedNm === 0) {
    return `${lead} For this engine that matches a fully converged solve.`;
  }
  const pct = Math.abs(a.worstPct).toFixed(1);
  let s = `${lead} Against fully converged solves, this engine's torque is within ${pct}% ` +
    `(the largest gap is at ${fmtRpm(a.worstRpm)} rpm)`;
  if (a.governedNm > 0) s += `, and within ${a.governedNm.toFixed(1)} N·m where the governor has cut fuel`;
  return s + '.';
}
