import { describe, expect, it } from 'vitest';
import { wavBytes } from './wav';

describe('wavBytes', () => {
  const b = wavBytes(Float32Array.from([0, 0.5, -0.5, 1, -1, 2, -2]), 44100);
  const v = new DataView(b.buffer);
  const text = (at: number, n: number) => String.fromCharCode(...b.subarray(at, at + n));

  it('writes a RIFF/WAVE header for mono 16-bit PCM', () => {
    expect(text(0, 4)).toBe('RIFF');
    expect(text(8, 8)).toBe('WAVEfmt ');
    expect(v.getUint32(4, true)).toBe(b.length - 8);
    expect([v.getUint16(20, true), v.getUint16(22, true), v.getUint32(24, true), v.getUint16(34, true)])
      .toEqual([1, 1, 44100, 16]);
    expect(v.getUint32(28, true)).toBe(88200);
    expect(text(36, 4)).toBe('data');
    expect(v.getUint32(40, true)).toBe(14);
  });

  it('scales to full range and clips outside [-1, 1]', () => {
    const s = Array.from({ length: 7 }, (_, i) => v.getInt16(44 + 2 * i, true));
    expect(s).toEqual([0, 16384, -16384, 32767, -32768, 32767, -32768]);
  });
});
