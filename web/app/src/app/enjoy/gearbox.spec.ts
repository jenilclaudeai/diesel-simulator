import { describe, expect, it } from 'vitest';
import { enjoyGearbox } from './gearbox';

describe('enjoyGearbox (ENJ-02)', () => {
  it('keeps Manual, and Auto as the converter', () => {
    expect(enjoyGearbox(true, 'tc')).toBe('manual');
    expect(enjoyGearbox(false, 'manual')).toBe('tc');
    expect(enjoyGearbox(false, 'tc')).toBe('tc');
  });
  it('keeps a dual clutch from /drive when Auto is tapped, but Manual replaces it', () => {
    expect(enjoyGearbox(false, 'dct')).toBe('dct');
    expect(enjoyGearbox(true, 'dct')).toBe('manual');
  });
});
