import { TestBed } from '@angular/core/testing';
import { speedScale } from '../enjoy/gauge';
import { weatherLine } from '../weather/drive-env';
import {
  airPressure, distance, economy, economyUnit, elevation, elevationUnit, pressureBar, speed, temperature, Units, UNITS_KEY, volume,
} from './units';

const near = (a: number, b: number, tol = 1e-9) => Math.abs(a - b) <= tol * Math.max(1, Math.abs(b));

describe('driver units (Phase 8: Metric, US, UK)', () => {
  it('P06: a climb in metres, or feet in the US', () => {
    expect(elevation(267, 'metric')).toBe(267);
    expect(elevation(267, 'uk')).toBe(267);
    expect(near(elevation(1000, 'us'), 3280.839895013123)).toBe(true);
    expect([elevationUnit('metric'), elevationUnit('us'), elevationUnit('uk')]).toEqual(['m', 'ft', 'm']);
  });

  it('metric passes every figure through unchanged', () => {
    expect(speed(123.4, 'metric')).toBe(123.4);
    expect(distance(5.5, 'metric')).toBe(5.5);
    expect(volume(2.25, 'metric')).toBe(2.25);
    expect(economy(6.2, 'metric')).toBe(6.2);
    expect(temperature(88, 'metric')).toBe(88);
    expect(pressureBar(1.5, 'metric')).toBe(1.5);
  });

  it('converts by the exact definitions', () => {
    expect(near(speed(100, 'us'), 62.13711922373339)).toBe(true);        // 100 km/h in mph
    expect(speed(100, 'uk')).toBe(speed(100, 'us'));
    expect(near(distance(1.609344, 'uk'), 1)).toBe(true);
    expect(near(volume(3.785411784, 'us'), 1)).toBe(true);               // a US gallon
    expect(volume(10, 'uk')).toBe(10);                                     // UK fuel is in litres
    expect(temperature(100, 'us')).toBe(212);
    expect(temperature(-40, 'us')).toBe(-40);
    expect(temperature(90, 'uk')).toBe(90);                                // the UK reads deg C
    expect(near(pressureBar(1, 'us'), 14.503773773, 1e-9)).toBe(true);    // 1 bar in psi
  });

  it('mpg is the inverse of L/100 km, with the right gallon, and no figure where there is none', () => {
    expect(near(economy(4.70429, 'us')!, 50, 1e-5)).toBe(true);            // 235.215 / 4.70429 = 50 mpg (US)
    expect(near(economy(5.64962, 'uk')!, 50, 1e-5)).toBe(true);            // 282.481 / 5.64962 = 50 mpg (UK)
    expect(economy(6, 'uk')! / economy(6, 'us')!).toBeCloseTo(4.54609 / 3.785411784, 12);
    for (const s of ['metric', 'us', 'uk'] as const) {
      expect(economy(null, s)).toBeNull();
      expect(economy(0, s)).toBeNull();
      expect(economy(Infinity, s)).toBeNull();
    }
    expect(economyUnit('us')).toBe('mpg (US)');
    expect(economyUnit('uk')).toBe('mpg (UK)');
  });

  it('the air as each country reports it', () => {
    expect(airPressure(101325, 'metric')).toBeCloseTo(101.325, 9);
    expect(airPressure(101325, 'us')).toBeCloseTo(29.921, 3);              // standard atmosphere in inHg
    expect(airPressure(101325, 'uk')).toBeCloseTo(1013.25, 9);             // hPa
  });

  it('the speedometer in mph keeps the km/h rules, capped at 150 mph', () => {
    expect(speedScale(200)).toEqual(speedScale(200, 'metric'));
    const mph = speedScale(200, 'us');                                     // 124.3 mph -> 140
    expect(mph.unit).toBe('mph');
    expect(mph.max).toBe(140);
    expect(speedScale(400, 'uk').max).toBe(150);
    expect(speedScale(400).max).toBe(240);
  });

  it("the place's note follows the units (kPa / inHg / hPa, deg C / deg F)", () => {
    const m = weatherLine('plateau', undefined, undefined);
    expect(m).toMatch(/65\.8 kPa, 20\.0 °C/);
    expect(weatherLine('plateau', undefined, undefined, 'metric')).toBe(m);
    expect(weatherLine('plateau', undefined, undefined, 'us')).toMatch(/19\.42 inHg, 68\.0 °F/);
    expect(weatherLine('plateau', undefined, undefined, 'uk')).toMatch(/658 hPa, 20\.0 °C/);
  });

  it('the choice is kept per browser; metric clears it; an unknown key is ignored', () => {
    localStorage.removeItem(UNITS_KEY);
    TestBed.resetTestingModule();
    const u = TestBed.inject(Units);
    expect(u.system()).toBe('metric');
    u.set('uk');
    expect(u.system()).toBe('uk');
    expect(localStorage.getItem(UNITS_KEY)).toBe('uk');
    u.set('furlongs');
    expect(u.system()).toBe('uk');
    u.set('metric');
    expect(localStorage.getItem(UNITS_KEY)).toBeNull();
  });
});
