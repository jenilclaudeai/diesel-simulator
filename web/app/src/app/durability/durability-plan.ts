/**
 * What a durability run costs before it starts (ADR-015): measured natively
 * on crdi15, 2026-10-05, 200 h in 34 s (2.8 min per 1,000 h); the browser's
 * Python is about 2.65x slower (ADR-014). An estimate, said as one.
 */
export const NATIVE_S_PER_H = 34 / 200;
export const BROWSER_FACTOR = 2.65;

export function estimateS(hours: number): number {
  return hours * NATIVE_S_PER_H * BROWSER_FACTOR;
}

/** "about 8 min" / "about 45 s" */
export function fmtDuration(s: number): string {
  return s < 90 ? `about ${Math.round(s)} s` : `about ${Math.round(s / 60)} min`;
}
