// A mono 16-bit PCM WAV file from float samples in [-1, 1] -- the drive
// page's "Record" button, for listening outside the browser (Phase 4).

export function wavBytes(samples: Float32Array, rate: number): Uint8Array {
  const n = samples.length, out = new Uint8Array(44 + 2 * n), v = new DataView(out.buffer);
  const text = (at: number, s: string) => { for (let i = 0; i < s.length; i++) out[at + i] = s.charCodeAt(i); };
  text(0, 'RIFF'); v.setUint32(4, 36 + 2 * n, true); text(8, 'WAVE');
  text(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, 2 * rate, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  text(36, 'data'); v.setUint32(40, 2 * n, true);
  for (let i = 0; i < n; i++) {
    const x = Math.max(-1, Math.min(1, samples[i]!));
    v.setInt16(44 + 2 * i, Math.round(x < 0 ? x * 32768 : x * 32767), true);
  }
  return out;
}
