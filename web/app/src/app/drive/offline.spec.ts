import { gridFetchError } from './offline';

describe('ADR-024: a grid that cannot be fetched', () => {
  const OFFLINE = /isn't on this device yet: start it once while online/;

  it('offline: says the engine was never kept, not "no prebuilt grid"', () => {
    expect(gridFetchError('hatch15', 504, false)).toMatch(OFFLINE);
    expect(gridFetchError('hatch15', undefined, false)).toMatch(OFFLINE);
    expect(gridFetchError('hatch15', 504, false)).not.toMatch(/no prebuilt grid/);
  });

  it("the service worker's 504 and a failed fetch say it too while navigator.onLine claims a network", () => {
    expect(gridFetchError('hatch15', 504, true)).toMatch(OFFLINE);
    expect(gridFetchError('hatch15', undefined, true)).toMatch(OFFLINE);
  });

  it('online, a missing grid is still a missing grid', () => {
    expect(gridFetchError('nope', 404, true)).toBe('no prebuilt grid for nope (HTTP 404)');
  });
});
