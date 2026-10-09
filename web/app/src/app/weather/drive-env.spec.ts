import { beforeEach, describe, expect, it } from 'vitest';
import { airOf, DRIVE_ENV_KEY, DriveEnv, PLACES, STANDARD, weatherLine } from './drive-env';

describe('the place Drive and Enjoy drive in (Phase 7 step 4)', () => {
  beforeEach(() => localStorage.clear());

  it('has the five places from environment.py, standard air first', () => {
    expect(PLACES.map(p => p.key)).toEqual(['standard', 'desert', 'winter', 'plateau', 'tropics']);
    const leh = PLACES.find(p => p.key === 'plateau')!;
    expect(leh.p_amb).toBeCloseTo(65764.1, 1);
    expect(leh.T_amb).toBeCloseTo(293.15, 9);
  });

  it('gives the worker no air at the standard air, and the place\'s otherwise', () => {
    expect(airOf(STANDARD)).toBeUndefined();
    expect(airOf('atlantis')).toBeUndefined();
    const leh = PLACES.find(p => p.key === 'plateau')!;
    expect(airOf('plateau')).toEqual({ p: leh.p_amb, T: leh.T_amb });
  });

  it('says what the loop does with the air: nothing at standard, the table, or no table', () => {
    expect(weatherLine(STANDARD, 'standard', null)).toBe('');
    const table = weatherLine('plateau', 'table', 2.04);
    expect(table).toContain('65.8 kPa');
    expect(table).toContain("weather table (measured within 2.0% of full-load torque at Leh)");
    expect(table).toContain("Friction and sound stay sea level's");
    const none = weatherLine('plateau', 'no table', null);
    expect(none).toContain('no weather table');
    expect(none).toContain("stay standard air's");
    // before an engine runs, just the air
    expect(weatherLine('winter', undefined, undefined)).toMatch(/^Rovaniemi.*kPa, -20\.0 °C\.$/);
  });

  it('keeps the choice in this browser, and ignores an unknown one', () => {
    const env = new DriveEnv();
    expect(env.current()).toBe(STANDARD);
    env.set('plateau');
    expect(localStorage.getItem(DRIVE_ENV_KEY)).toBe('plateau');
    expect(new DriveEnv().current()).toBe('plateau');
    env.set('atlantis');
    expect(env.current()).toBe('plateau');
    env.set(STANDARD);
    expect(localStorage.getItem(DRIVE_ENV_KEY)).toBeNull();
    localStorage.setItem(DRIVE_ENV_KEY, 'atlantis');
    expect(new DriveEnv().current()).toBe(STANDARD);
  });
});
