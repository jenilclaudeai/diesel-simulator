import { describe, expect, it } from 'vitest';
import { ROUTES } from '@dieselsim/physics';
import { newSeed, parseRouteParam, roadAhead, ROUTE_CHOICES, routeKey, routeOf, routeSummary, SEED_MAX } from './road';

describe('the route link (?route=)', () => {
  it('round-trips every named route and a random seed', () => {
    for (const c of ROUTE_CHOICES.filter(c => c.key && c.key !== 'random')) {
      const p = parseRouteParam(c.key);
      expect(p).toEqual({ choice: c.key, seed: null });
      expect(routeKey(p.choice, p.seed)).toBe(c.key);
    }
    expect(parseRouteParam('random:1234')).toEqual({ choice: 'random', seed: 1234 });
    expect(routeKey('random', 1234)).toBe('random:1234');
  });

  it('reads anything else as the open road', () => {
    for (const q of [null, '', 'random', 'random:0', 'random:abc', 'random:1234567', 'moon', 'random:-5'])
      expect(parseRouteParam(q)).toEqual({ choice: '', seed: null });
    expect(routeKey('', null)).toBeUndefined();
    expect(routeKey('random', null)).toBeUndefined();
    expect(routeOf(undefined)).toBeUndefined();
    expect(routeOf('moon')).toBeUndefined();
  });

  it('makes seeds 1 to SEED_MAX', () => {
    expect(newSeed(() => 0)).toBe(1);
    expect(newSeed(() => 0.9999999999)).toBe(SEED_MAX);
  });
});

describe('roadAhead', () => {
  const city = ROUTES['city']!, pass = ROUTES['pass']!, desert = ROUTES['desert']!;

  it("puts the city's breakers where they are, and wraps to the next lap", () => {
    const a = roadAhead(city, 0);               // breakers at 250, 650, 1050, 1450 of a 2500 m lap
    expect(a.breakers).toEqual([50, 130, 210, 290]);
    expect(a.nextBreakerM).toBe(250);
    const b = roadAhead(city, 2400);            // the next lap's 250, 650, 1050 are 350, 750, 1150 m on
    expect(b.nextBreakerM).toBe(350);
    expect(b.breakers.map(x => Math.round(x))).toEqual([70, 150, 230]);
    expect(roadAhead(desert, 0).nextBreakerM).toBeNull();
  });

  it('draws a climb going up and a flat stretch flat', () => {
    const ys = (line: string) => line.slice(1).split(' L').map(p => Number(p.split(',')[1]));
    const up = ys(roadAhead(pass, 800).line);   // the 6 % climb starts at 800 m
    expect(up[up.length - 1]!).toBeLessThan(up[0]! - 20);   // SVG y grows downward
    const flat = ys(roadAhead(desert, 100, 1500).line);     // the first 3000 m are level
    expect(new Set(flat).size).toBe(1);
    // a set of NaNs is one value too (the first version of this test passed with the floor removed)
    expect(flat[0]!).toBeGreaterThan(10);
    expect(flat[0]!).toBeLessThan(30);
    // the city's 6 m rise is not stretched to the strip's full height: at most 6/40 of it
    const gentle = ys(roadAhead(city, 300, 1500).line);
    expect(Math.max(...gentle) - Math.min(...gentle)).toBeLessThan(0.16 * 40);
    expect(Math.max(...gentle) - Math.min(...gentle)).toBeGreaterThan(1);
  });

  it('covers the strip with surface bands, edge to edge, no gaps', () => {
    const a = roadAhead(desert, 2500);          // asphalt, asphalt (merged), then gravel at 3800 m
    expect(a.bands[0]!.x0).toBe(0);
    expect(a.bands[a.bands.length - 1]!.x1).toBeCloseTo(300, 9);
    for (let i = 1; i < a.bands.length; i++) expect(a.bands[i]!.x0).toBeCloseTo(a.bands[i - 1]!.x1, 9);
    expect(a.bands.map(b => b.surface)).toEqual(['asphalt', 'gravel']);
    expect(a.bands[1]!.x0).toBeCloseTo(((3800 - 2500) / 1500) * 300, 9);
    expect(a.surface).toBe('asphalt');
    expect(roadAhead(pass, 900).grade).toBe(0.06);
  });

  it("summarises a route for the picker", () => {
    const m = routeSummary(pass);                // climbs to 267 m, ends 60 m up
    expect(m.km).toBeCloseTo(9.3, 9);
    expect(m.top).toBeCloseTo(267, 9);
    expect(routeSummary(city).breakers).toBe(6);
  });
});
