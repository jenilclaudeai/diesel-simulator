import { describe, expect, it } from 'vitest';
import { ALTITUDE_NOTE, altitudeNote, THIN_AIR_PA } from './altitude';

describe('thin-air note (FINDING-026, option D)', () => {
  it('shows below 90 kPa (Leh, 65.8 kPa), and not at or near sea level', () => {
    expect(altitudeNote(65764.1)).toBe(ALTITUDE_NOTE);
    expect(altitudeNote(THIN_AIR_PA - 1)).toBe(ALTITUDE_NOTE);
    // the other presets (environment.py's p_amb): standard, Jaisalmer, Rovaniemi, Mumbai: no note
    for (const p of [101325, 98651.1, 98933.5, 101156.9, THIN_AIR_PA]) expect(altitudeNote(p), String(p)).toBe('');
    expect(altitudeNote(undefined)).toBe('');
    expect(altitudeNote(null)).toBe('');
  });

  it('says both limits, with the measured number and the finding', () => {
    for (const s of ['compressor', 'pumping', '37% less torque', 'speed ceiling', 'no turbo-overspeed protection', 'FINDING-026']) {
      expect(ALTITUDE_NOTE, s).toContain(s);
    }
  });
});
