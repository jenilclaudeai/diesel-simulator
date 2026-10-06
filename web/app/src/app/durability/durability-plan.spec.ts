import { describe, expect, it } from 'vitest';
import { estimateS, fmtDuration } from './durability-plan';

describe('durability cost, before it starts', () => {
  it('the default 1,000 h is about 7.5 minutes in the browser (ADR-015)', () => {
    expect(estimateS(1000) / 60).toBeCloseTo(7.5, 1);
    expect(fmtDuration(estimateS(1000))).toBe('about 8 min');
  });
  it('short runs in seconds, long ones in minutes', () => {
    expect(fmtDuration(45)).toBe('about 45 s');
    expect(fmtDuration(estimateS(12000))).toBe('about 90 min');
  });
});
