import { describe, expect, it } from 'vitest';
import { H_REF, HUMIDITY_NOTE, humidityNote } from './humidity';

describe('humidity note (ADR-016 item 3)', () => {
  it('shows off the reference humidity, and not at it or without one', () => {
    // the presets' overrides (environment.py): Mumbai 21.63 g/kg, Leh 7.82; standard air sets exactly 10.71
    expect(humidityNote({ 'thermal.ambient_humidity': 21.63 })).toBe(HUMIDITY_NOTE);
    expect(humidityNote({ 'thermal.ambient_humidity': 7.82 })).toBe(HUMIDITY_NOTE);
    expect(humidityNote({ 'thermal.ambient_humidity': H_REF })).toBe('');
    expect(humidityNote({ 'thermal.ambient_p': 65764 })).toBe('');
    expect(humidityNote(undefined)).toBe('');
    expect(H_REF).toBe(10.71);
  });

  it('says it is a correction, on NOx only, with its source and reference', () => {
    for (const s of ['NOx only', '40 CFR 1065.670', '10.71 g/kg', 'less NOx', "isn't in the cycle", "don't move"]) {
      expect(HUMIDITY_NOTE, s).toContain(s);
    }
  });
});
