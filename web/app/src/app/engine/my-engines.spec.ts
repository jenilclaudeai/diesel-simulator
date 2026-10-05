import { describe, expect, it } from 'vitest';
import { poolSize } from '../solver/pool-size';
import { EXAMPLE_ENGINE } from './custom-engine';
import { editedEngine, MemoryEngineLibrary, vehicleKeyFor } from './my-engines';

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

describe('vehicleKeyFor', () => {
  it('names the vehicle key whose vehicle is the preset\'s own, else the tractor', () => {
    expect(vehicleKeyFor('crdi15')).toBe('crdi15');
    expect(vehicleKeyFor('hatch15')).toBe('hatch15');
    expect(vehicleKeyFor('truck127')).toBe('hd_i6');
    expect(vehicleKeyFor('v8hd')).toBe('hd_i6');
    expect(vehicleKeyFor('single10')).toBe('tractor');
  });
});

describe('editedEngine', () => {
  it('keys an edited preset by its base and edits, in any order, and names it for the reader', () => {
    const a = editedEngine('truck127', '12.7 L six', { 'geom.compression_ratio': 18, idle_rpm: 650 });
    const b = editedEngine('truck127', '12.7 L six', { idle_rpm: 650, 'geom.compression_ratio': 18 });
    const c = editedEngine('truck127', '12.7 L six', { idle_rpm: 660, 'geom.compression_ratio': 18 });
    expect(a.key).toMatch(/^truck127-edited-[0-9a-f]{8}$/);
    expect(b.key).toBe(a.key);
    expect(c.key).not.toBe(a.key);
    expect(a.name).toBe('12.7 L six, edited (2 fields)');
    expect(editedEngine('crdi15', 'CRDi', { idle_rpm: 800 }).name).toBe('CRDi, edited (1 field)');
    expect(a.vehicle).toBe('hd_i6');
    expect(a.edits).toEqual({ preset: 'truck127', overrides: { 'geom.compression_ratio': 18, idle_rpm: 650 } });
  });
});
