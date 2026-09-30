import { describe, expect, it } from 'vitest';
import { pedalValue } from './pedal';

describe('pedalValue (ADR-012: pressed harder by sliding up)', () => {
  // a pedal 200 px tall with its top at y = 100: the bottom edge is y = 300
  it('is 0 at the bottom and 1 at the top, with a dead band at each end', () => {
    expect(pedalValue(300, 100, 200)).toBe(0);
    expect(pedalValue(300 - 0.08 * 200, 100, 200)).toBe(0);      // the edge of the lower dead band
    expect(pedalValue(100, 100, 200)).toBe(1);
    expect(pedalValue(100 + 0.08 * 200, 100, 200)).toBeCloseTo(1, 12);
  });
  it('is linear between, and halfway up is half travel', () => {
    expect(pedalValue(200, 100, 200)).toBeCloseTo(0.5, 12);
    const a = pedalValue(250, 100, 200), b = pedalValue(225, 100, 200), c = pedalValue(200, 100, 200);
    expect(b - a).toBeCloseTo(c - b, 12);
  });
  it('clamps a finger dragged outside the pedal, and a zero-height pedal gives 0', () => {
    expect(pedalValue(500, 100, 200)).toBe(0);
    expect(pedalValue(-50, 100, 200)).toBe(1);
    expect(pedalValue(150, 100, 0)).toBe(0);
  });
});
