import { describe, expect, it } from 'vitest';
import { parseSpecFile } from './spec-edits';

describe('parseSpecFile', () => {
  it('accepts a base engine and editable fields of the right type', () => {
    expect(parseSpecFile('{"preset":"crdi15","overrides":{"geom.compression_ratio":17,"inj.n_holes":8,"turbo.vgt":false}}'))
      .toEqual({ preset: 'crdi15', overrides: { 'geom.compression_ratio': 17, 'inj.n_holes': 8, 'turbo.vgt': false } });
    expect(parseSpecFile('{"preset":"crdi15"}')).toEqual({ preset: 'crdi15', overrides: {} });
  });

  it('refuses, with the reason, anything the bridge would refuse or the editor cannot show', () => {
    expect(parseSpecFile('nope')).toBe('not JSON');
    expect(parseSpecFile('{"overrides":{}}')).toMatch(/no "preset"/);
    expect(parseSpecFile('{"preset":"x","overrides":{"geom.compresion_ratio":17}}')).toMatch(/unknown field/);
    expect(parseSpecFile('{"preset":"x","overrides":{"geom.n_cyl":6}}')).toMatch(/can't be edited/);
    expect(parseSpecFile('{"preset":"x","overrides":{"geom.bore":"big"}}')).toMatch(/must be a number/);
    expect(parseSpecFile('{"preset":"x","overrides":{"turbo.vgt":1}}')).toMatch(/true\/false/);
    expect(parseSpecFile('{"preset":"x","overrides":{"inj.n_holes":7.5}}')).toMatch(/whole number/);
  });
});
