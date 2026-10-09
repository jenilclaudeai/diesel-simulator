// Pure: what a drivable-grid build in the browser includes, from the page's query string, so its
// test needs no worker and not the generated physics-version.ts.

/**
 * Phase 7 step 4 (owner, 2026-10-08: "browser should be able to build the weather table"): the
 * build includes the weather table. Only an e2e run may leave it out (`?e2e&noweather`), so CI's
 * 2 x 2 custom-engine check fits its job; the real thing is web/solver's test:live-real.
 */
export function buildsWeather(search: string): boolean {
  const q = new URLSearchParams(search);
  return !(q.has('e2e') && q.has('noweather'));
}
