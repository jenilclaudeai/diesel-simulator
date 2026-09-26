import { controlKey, DRIVE_PRESETS, KEY_HELP } from './drive-keys';

describe('controlKey', () => {
  it('maps letters case-insensitively and keeps punctuation', () => {
    expect(controlKey('W')).toBe('w');
    expect(controlKey(' ')).toBe(' ');
    expect(controlKey('.')).toBe('.');
    expect(controlKey('z')).toBe('z');
  });
  it('ignores keys that are not controls', () => {
    expect(controlKey('q')).toBeUndefined();
    expect(controlKey('ArrowUp')).toBeUndefined();
    expect(controlKey('Shift')).toBeUndefined();
  });
  it('every documented key is a control, and every preset is listed once', () => {
    const documented = KEY_HELP.flatMap(([k]) => k.split(' / ').map(s => s.trim()))
      .map(s => (s === 'space' ? ' ' : s));
    for (const k of documented) expect(controlKey(k)).toBe(k);
    expect(new Set(DRIVE_PRESETS.map(p => p.key)).size).toBe(DRIVE_PRESETS.length);
  });
});
