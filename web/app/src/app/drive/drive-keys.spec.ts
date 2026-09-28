import { controlKey, DRIVE_PRESETS, KEY_HELP, MIC_KEYS, MICS } from './drive-keys';

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
    const documented = KEY_HELP.filter(([k]) => k !== '1 - 5').flatMap(([k]) => k.split(' / ').map(s => s.trim()))
      .map(s => (s === 'space' ? ' ' : s));
    for (const k of documented) expect(controlKey(k)).toBe(k);
    expect(new Set(DRIVE_PRESETS.map(p => p.key)).size).toBe(DRIVE_PRESETS.length);
  });
  it('keys 1-5 pick the microphones in play.py order (acoustics.MICS), and are not loop controls', () => {
    expect(MICS.map(m => m.key)).toEqual(['exhaust_tip', 'intake', 'engine_bay', 'cabin', 'exterior_7m']);
    expect(['1', '2', '3', '4', '5'].map(k => MIC_KEYS[k])).toEqual(MICS.map(m => m.key));
    for (const k of Object.keys(MIC_KEYS)) expect(controlKey(k)).toBeUndefined();
  });
});
