/**
 * The live loop's hints name keyboard keys (they were written for play.py's
 * terminal, and /drive still has a keyboard). On /enjoy's touchscreen they name
 * the controls instead: "clutch down (z) or neutral to start" meant nothing on
 * a phone (B-01). The loop's own strings stay as they are, so the Python
 * reference and its fixtures are untouched.
 */
import { speed, speedUnit, type UnitSystem } from '../units/units';

const TOUCH: Record<string, string> = {
  'stalled -- clutch down (z) and press i to restart': 'Stalled: hold the clutch and tap Restart',
  'clutch down (z) or neutral to start': 'Hold the clutch, then tap Restart',
  'clutch down (z) to change gear': 'Hold the clutch to change gear',
  'manual box: . and , shift, z is the clutch, a is auto-clutch': 'Manual box: the paddles shift, the left pedal is the clutch',
};

/** P06: the loop's breaker hint is in km/h (live.py's string); here it is in the driver's units. */
const BREAKER = /^speed breaker at (\d+) km\/h -- take them at (\d+)$/;

export function touchHint(hint: string, units: UnitSystem = 'metric'): string {
  const b = BREAKER.exec(hint);
  if (b) {
    const r = (kmh: number) => Math.round(speed(kmh, units));
    return `Speed breaker at ${r(Number(b[1]))} ${speedUnit(units)}: take them at ${r(Number(b[2]))}`;
  }
  return TOUCH[hint] ?? hint;
}
