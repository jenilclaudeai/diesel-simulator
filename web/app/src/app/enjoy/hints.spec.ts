import { describe, expect, it } from 'vitest';
import { touchHint } from './hints';

describe('touchHint', () => {
  it('names the touch controls, not keys, for every keyboard-worded hint the loop gives', () => {
    const keyboard = [
      'stalled -- clutch down (z) and press i to restart',
      'clutch down (z) or neutral to start',
      'clutch down (z) to change gear',
      'manual box: . and , shift, z is the clutch, a is auto-clutch',
    ];
    for (const h of keyboard) {
      const t = touchHint(h);
      expect(t).not.toBe(h);
      expect(t).not.toMatch(/\(z\)|press i|\bz is\b/);
    }
    expect(touchHint('stalled -- clutch down (z) and press i to restart')).toMatch(/Restart/);
  });

  it("P06: says the loop's breaker hint in the driver's units", () => {
    const h = 'speed breaker at 95 km/h -- take them at 15';
    expect(touchHint(h)).toBe('Speed breaker at 95 km/h: take them at 15');
    expect(touchHint(h, 'metric')).toBe('Speed breaker at 95 km/h: take them at 15');
    expect(touchHint(h, 'us')).toBe('Speed breaker at 59 mph: take them at 9');
    expect(touchHint(h, 'uk')).toBe('Speed breaker at 59 mph: take them at 9');
  });

  it('passes other hints through unchanged', () => {
    expect(touchHint('started')).toBe('started');
    expect(touchHint('')).toBe('');
  });
});
