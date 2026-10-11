import { describe, expect, it } from 'vitest';
import { buildsWeather } from './build-options';

describe('what a browser grid build includes (Phase 7 step 4)', () => {
  it('builds the weather table, unless an e2e run asks it not to', () => {
    expect(buildsWeather('')).toBe(true);
    expect(buildsWeather('?engine=my:x')).toBe(true);
    expect(buildsWeather('?noweather')).toBe(true);                 // only with e2e
    expect(buildsWeather('?e2e&gridsize=2x2')).toBe(true);
    expect(buildsWeather('?e2e&gridsize=2x2&noweather')).toBe(false);
  });
});
