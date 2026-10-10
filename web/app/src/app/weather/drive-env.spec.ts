import { beforeEach, describe, expect, it } from 'vitest';
import { airOf, cfppOf, DRIVE_ENV_KEY, DRIVE_FUEL_KEY, DriveEnv, FUELS, fuelLine, PLACES, SOLD_HERE, STANDARD,
  weatherLine } from './drive-env';

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

  it('Phase 7 step 6: the fuel picked gives the worker its CFPP; sold here is the place\'s own', () => {
    expect(FUELS.map(f => [f.key, f.cfpp_C])).toEqual([['summer', 18], ['winter', 6], ['arctic', -32]]);
    expect(cfppOf('standard', SOLD_HERE)).toBeUndefined();          // the engine's own fuel: no waxing
    expect(cfppOf('winter', SOLD_HERE)).toBeCloseTo(-32 + 273.15, 9);  // Rovaniemi sells arctic diesel
    expect(cfppOf('winter', 'summer')).toBeCloseTo(18 + 273.15, 9);
    expect(cfppOf('standard', 'arctic')).toBeCloseTo(-32 + 273.15, 9);
    expect(cfppOf('plateau', 'nonsense')).toBeCloseTo(6 + 273.15, 9);  // unknown: the place's own
  });

  it('says what the fuel does at the place: flows, waxes, or gels', () => {
    expect(fuelLine('winter', 'arctic')).toContain('it flows');
    expect(fuelLine('winter', 'summer')).toMatch(/Summer diesel \(CFPP 18 °C\) at -20 °C: it gels, and the engine won't start/);
    expect(fuelLine('winter', 'winter')).toContain("won't start");    // CFPP 6 C at -20 C
    // Leh's 20 C is exactly CFPP 18 + 2: full flow, as the live loop's filter share (1.0) says
    expect(fuelLine('plateau', 'summer')).toContain('it flows');
    expect(fuelLine('winter', SOLD_HERE)).toBe('');                   // the place's own: nothing to say
  });

  it('keeps the fuel in this browser, and ignores an unknown one', () => {
    const env = new DriveEnv();
    expect(env.fuel()).toBe(SOLD_HERE);
    env.set('winter');
    env.setFuel('summer');
    expect(localStorage.getItem(DRIVE_FUEL_KEY)).toBe('summer');
    expect(new DriveEnv().cfpp()).toBeCloseTo(18 + 273.15, 9);
    env.setFuel('kerosene');
    expect(env.fuel()).toBe('summer');
    env.setFuel(SOLD_HERE);
    expect(localStorage.getItem(DRIVE_FUEL_KEY)).toBeNull();
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
