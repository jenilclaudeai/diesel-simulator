import { describe, expect, it } from 'vitest';
import { isStale, refKey } from './spec-status';

describe('stale results', () => {
  it('equal edits give equal keys, whatever their order', () => {
    expect(refKey({ preset: 'crdi15', overrides: { 'a.x': 1, 'b.y': 2 } }))
      .toBe(refKey({ preset: 'crdi15', overrides: { 'b.y': 2, 'a.x': 1 } }));
    expect(refKey({ preset: 'crdi15' })).toBe(refKey({ preset: 'crdi15', overrides: {} }));
  });

  it('results are stale once the edits, or the engine, differ from what they were solved with', () => {
    const solved = refKey({ preset: 'crdi15', overrides: { 'geom.compression_ratio': 17 } });
    expect(isStale(solved, { preset: 'crdi15', overrides: { 'geom.compression_ratio': 17 } })).toBe(false);
    expect(isStale(solved, { preset: 'crdi15', overrides: { 'geom.compression_ratio': 18 } })).toBe(true);
    expect(isStale(solved, { preset: 'crdi15' })).toBe(true);
    expect(isStale(solved, { preset: 'hd_i6', overrides: { 'geom.compression_ratio': 17 } })).toBe(true);
  });

  it('no results, nothing stale', () => {
    expect(isStale(undefined, { preset: 'crdi15', overrides: { x: 1 } })).toBe(false);
  });
});
