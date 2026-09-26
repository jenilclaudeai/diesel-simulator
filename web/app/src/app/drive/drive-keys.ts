// Pure pieces of the drive page, so their tests need no worker, no Angular
// and not the generated physics-version.ts.

/** The presets with prebuilt converged grids (tools/build_live_grids.py). */
export const DRIVE_PRESETS: readonly { key: string; name: string }[] = [
  { key: 'crdi15', name: 'CRDi-I4 1.5L 115ps' },
  { key: 'crdi_1p5', name: 'CRDi-I4 1.5L' },
  { key: 'ld_i4', name: 'LD-I4 2.0L CRD' },
  { key: 'hd_i6', name: 'HD-I6 12.7L' },
  { key: 'single', name: 'IND-1 0.58L NA' },
];

/** The engine controls, as play.py and dieselsim.live.handle_key map them. */
const KEYS = new Set(['w', 's', ' ', 'x', 'b', 'e', 'n', 'm', '.', ',', ']', '[', 'l', 'c', '+', '=', '-',
  'o', 'f', 'r', 'z', 'a', 'i']);

/** A keyboard event's key, as the loop names it -- or undefined if it is not a control. */
export function controlKey(eventKey: string): string | undefined {
  const k = eventKey.length === 1 ? eventKey.toLowerCase() : eventKey;
  return KEYS.has(k) ? k : undefined;
}

export const KEY_HELP: readonly [string, string][] = [
  ['w / s', 'throttle up / down (hold)'], ['space / x', 'full throttle / off'], ['b', 'brake (hold)'],
  ['. / ,', 'shift up / down'], ['n', 'neutral'], ['m', 'automatic / manual shifting'],
  ['z', 'clutch (hold, manual box)'], ['a', 'auto-clutch (manual box)'], ['i', 'restart after a stall'],
  ['l', 'lock-up allowed (converter)'], ['c / + / -', 'cruise on-off / faster / slower'],
  ['[ / ]', 'grade down / up'], ['e', 'engine brake'], ['o / f / r', 'trip reset / refuel / reset car'],
];
