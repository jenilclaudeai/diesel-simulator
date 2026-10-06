import { describe, expect, it } from 'vitest';
import { sweepNote } from './sweep-note';

const T = { a: { worstPct: -5.8, worstRpm: 1650, governedNm: 1.8 }, b: { worstPct: 0, worstRpm: 0, governedNm: 0 } };

describe('the sweep page states its resolution', () => {
  it('quotes the measured full-load error, only for the build it was measured on', () => {
    expect(sweepNote('a', 'h1', T, 'h1')).toMatch(/up to 5\.8% in torque/);
    expect(sweepNote('a', 'h2', T, 'h1')).toMatch(/not been measured on this solver build/);
    expect(sweepNote('x', 'h1', T, 'h1')).toMatch(/not been measured/);
    expect(sweepNote('b', 'h1', T, 'h1')).toMatch(/matches a fully converged solve/);
  });
  it('always says points closer than the error are noise, and that part load is worse', () => {
    for (const n of [sweepNote('a', 'h1', T, 'h1'), sweepNote('x', 'h1', T, 'h1')]) {
      expect(n).toMatch(/noise, not physics/);
      expect(n).toMatch(/part load.*far larger/);
    }
  });
});
