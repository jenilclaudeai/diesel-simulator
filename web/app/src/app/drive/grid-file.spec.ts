import { describe, expect, it } from 'vitest';
import { gridFileProblem } from './grid-file';

/** The smallest object gridFileProblem accepts: a 2 x 3 converged grid. */
function grid(): Record<string, unknown> {
  const table = [[{}, {}, {}], [{}, {}, {}]];
  return {
    preset: 'my20', name: 'My engine', grid_hash: 'h', converged: true, rpms: [800, 4000], loads: [0, 0.5, 1],
    perf: table, perf_cold: table, p_cyl_f32: table, p_cyl_cold_f32: table, src_f32: table, src_cold_f32: table,
    src_meta: table, src_meta_cold: table, spec: {}, engine_view: {},
  };
}

describe('gridFileProblem', () => {
  it('accepts a converged grid with consistent axes', () => {
    expect(gridFileProblem(grid())).toBeNull();
  });
  it('refuses what is not an object', () => {
    for (const x of [null, 3, 'grid', [1, 2]]) expect(gridFileProblem(x)).toMatch(/not a grid file/);
  });
  it('names every missing field', () => {
    const g = grid();
    delete g['spec'];
    delete g['perf_cold'];
    expect(gridFileProblem(g)).toBe('not a grid file: missing perf_cold, spec');
  });
  it('refuses a fast (unconverged) grid: driving needs the converged pair', () => {
    expect(gridFileProblem({ ...grid(), converged: false })).toMatch(/not converged/);
  });
  it('refuses a custom engine that names no known vehicle, rather than giving it the fallback', () => {
    expect(gridFileProblem({ ...grid(), custom: true, vehicle: 'crdi22' })).toBeNull();
    expect(gridFileProblem({ ...grid(), custom: true, vehicle: 'spaceship' })).toMatch(/"vehicle" must be one of/);
    expect(gridFileProblem({ ...grid(), custom: true })).toMatch(/got null/);
  });
  it('refuses a perf table that does not match its axes', () => {
    expect(gridFileProblem({ ...grid(), rpms: [800, 2000, 4000] })).toMatch(/does not match/);
    expect(gridFileProblem({ ...grid(), loads: [0, 1] })).toMatch(/does not match/);
  });
});
