import { describe, expect, it } from 'vitest';
import { avgL100, nowL100, rangeKm } from './economy';
import { dialMax, gaugeAngle, speedScale, SWEEP, tachScale, type Scale } from './gauge';
import { derateLit, T_CHARGE_LAMP } from './lamps';

describe('gaugeAngle', () => {
  it('sweeps 240 degrees from zero to full scale, straight up at half', () => {
    expect(gaugeAngle(0, 5000)).toBe(-SWEEP / 2);
    expect(gaugeAngle(2500, 5000)).toBe(0);
    expect(gaugeAngle(5000, 5000)).toBe(SWEEP / 2);
    expect(gaugeAngle(1250, 5000)).toBeCloseTo(-60, 12);
  });
  it('pins at the stops, and a broken input rests at zero', () => {
    expect(gaugeAngle(-100, 5000)).toBe(-120);
    expect(gaugeAngle(9000, 5000)).toBe(120);
    expect(gaugeAngle(NaN, 5000)).toBe(-120);
    expect(gaugeAngle(100, 0)).toBe(-120);
  });
});

describe('dialMax', () => {
  it('rounds a top speed up to a tidy full scale', () => {
    expect(dialMax(187.3, 20)).toBe(200);
    expect(dialMax(200, 20)).toBe(200);
    expect(dialMax(3, 20)).toBe(20);
  });
});

describe('dial scales: the end is always labelled, and labels never crowd', () => {
  const labels = (s: Scale) => Math.round(s.max / (s.step * s.labelEvery)) + 1;
  const endLabelled = (s: Scale) => Math.abs(s.max / (s.step * s.labelEvery) - Math.round(s.max / (s.step * s.labelEvery))) < 1e-9;
  it('tachometers from 800 to 6000 rpm', () => {
    for (let m = 800; m <= 6000; m += 50) {
      const s = tachScale(m);
      expect(s.max).toBeGreaterThanOrEqual(m);
      expect(endLabelled(s), `max rpm ${m}: scale ${s.max}`).toBe(true);
      expect(labels(s)).toBeLessThanOrEqual(8);
    }
  });
  it('speedometers from 20 to 300 km/h (capped at 240)', () => {
    for (let v = 20; v <= 300; v += 1) {
      const s = speedScale(v);
      expect(s.max).toBeGreaterThanOrEqual(Math.min(v, 240));
      expect(endLabelled(s), `vmax ${v}: scale ${s.max}`).toBe(true);
      expect(labels(s)).toBeLessThanOrEqual(9);
    }
  });
  it('a truck reads x100 rpm, a car x1000', () => {
    expect(tachScale(2100)).toMatchObject({ max: 2500, labelScale: 100 });
    expect(tachScale(4600)).toMatchObject({ max: 5000, labelScale: 1000 });
  });
});

describe('economy (steady-state, FINDING-009)', () => {
  it('averages over the trip, only once there is a trip', () => {
    expect(avgL100(0.5, 10)).toBeCloseTo(5, 12);
    expect(avgL100(0.001, 0.05)).toBeNull();
  });
  it('gives an instantaneous figure only when moving on fuel', () => {
    expect(nowL100(20, 90)).toBeCloseTo(5, 12);
    expect(nowL100(20, 1)).toBeNull();
    expect(nowL100(0, 90)).toBeNull();
    expect(nowL100(Infinity, 90)).toBeNull();
  });
  it('estimates range from the tank at the trip average', () => {
    expect(rangeKm(40, 0.5, 10)).toBeCloseTo(800, 9);
    expect(rangeKm(40, 0, 0.01)).toBeNull();
  });
});

describe('derateLit', () => {
  const C = (c: number) => c + 273.15;
  it('stays dark in ordinary hard driving: the truck at full throttle and low speed, 66 °C charge air', () => {
    expect(derateLit(C(66), 1)).toBe(false);
    expect(derateLit(C(25), 1)).toBe(false);
    expect(derateLit(T_CHARGE_LAMP, 1)).toBe(false);
  });
  it('lights for genuinely hot charge air, and for any overheat derate', () => {
    expect(derateLit(T_CHARGE_LAMP + 1e-9, 1)).toBe(true);
    expect(derateLit(C(95), 1)).toBe(true);
    expect(derateLit(C(30), 0.999)).toBe(true);
  });
});
