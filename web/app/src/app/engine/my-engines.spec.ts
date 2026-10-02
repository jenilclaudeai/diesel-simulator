import { describe, expect, it } from 'vitest';
import { poolSize } from '../solver/pool-size';
import { EXAMPLE_ENGINE } from './custom-engine';
import { MemoryEngineLibrary } from './my-engines';

describe('MemoryEngineLibrary', () => {
  it('lists saved engines newest first, hands back the grid, and forgets on remove', async () => {
    const lib = new MemoryEngineLibrary();
    await lib.save({ key: 'a', name: 'A', vehicle: 'crdi15', savedAt: 1, engine: EXAMPLE_ENGINE }, '{"preset":"a"}');
    await lib.save({ key: 'b', name: 'B', vehicle: 'hd_i6', savedAt: 2, engine: EXAMPLE_ENGINE }, '{"preset":"b"}');
    expect((await lib.list()).map(e => e.key)).toEqual(['b', 'a']);
    expect((await lib.grid('a'))?.preset).toBe('a');
    await lib.remove('a');
    expect((await lib.list()).map(e => e.key)).toEqual(['b']);
    expect(await lib.grid('a')).toBeUndefined();
  });
});

describe('poolSize', () => {
  it('keeps a core for the page, caps at 6, and uses 2 on a small-memory device', () => {
    expect(poolSize(1)).toBe(1);
    expect(poolSize(4)).toBe(3);
    expect(poolSize(16)).toBe(6);
    expect(poolSize(8, 3)).toBe(2);
    expect(poolSize(8, 8)).toBe(6);
  });
});
