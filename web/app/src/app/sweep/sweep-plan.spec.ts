import { describe, expect, it } from 'vitest';
import { defaultRange, sweepValues } from './sweep-plan';

describe('sweep values', () => {
  it('evenly spaced, ends included', () => {
    expect(sweepValues(15, 18, 4, false)).toEqual([15, 16, 17, 18]);
    expect(sweepValues(0.1, 0.2, 3, false)).toEqual([0.1, 0.15, 0.2]);
  });
  it('integer fields are rounded, without repeats', () => {
    expect(sweepValues(6, 8, 7, true)).toEqual([6, 7, 8]);
  });
  it('a sweep has 2 to 25 points', () => {
    expect(sweepValues(0, 1, 1, false)).toHaveLength(2);
    expect(sweepValues(0, 1, 100, false)).toHaveLength(25);
  });
});

describe('default range', () => {
  it('the value plus and minus 20%, to 3 significant figures', () => {
    expect(defaultRange(16.5, false)).toEqual({ from: 13.2, to: 19.8 });
    expect(defaultRange(-5, false)).toEqual({ from: -6, to: -4 });
  });
  it('integers move by at least one', () => {
    expect(defaultRange(2, true)).toEqual({ from: 1, to: 3 });
    expect(defaultRange(8, true)).toEqual({ from: 6, to: 10 });
  });
});
