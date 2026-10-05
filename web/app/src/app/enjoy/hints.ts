/**
 * The live loop's hints name keyboard keys (they were written for play.py's
 * terminal, and /drive still has a keyboard). On /enjoy's touchscreen they name
 * the controls instead: "clutch down (z) or neutral to start" meant nothing on
 * a phone (B-01). The loop's own strings stay as they are, so the Python
 * reference and its fixtures are untouched.
 */
const TOUCH: Record<string, string> = {
  'stalled -- clutch down (z) and press i to restart': 'Stalled: hold the clutch and tap Restart',
  'clutch down (z) or neutral to start': 'Hold the clutch, then tap Restart',
  'clutch down (z) to change gear': 'Hold the clutch to change gear',
  'manual box: . and , shift, z is the clutch, a is auto-clutch': 'Manual box: the paddles shift, the left pedal is the clutch',
};

export function touchHint(hint: string): string {
  return TOUCH[hint] ?? hint;
}
