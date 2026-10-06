import { beforeEach, describe, expect, it } from 'vitest';
import { EDITS_KEY, parseSpecFile, SpecEdits } from './spec-edits';

// REVIEW-008 m-3: a reload lost the edits. A fresh SpecEdits is a reload.
describe('SpecEdits are kept across a reload', () => {
  beforeEach(() => localStorage.clear());

  it('restores every kind of change: set, reset, reset all, base, load', () => {
    const a = new SpecEdits();
    a.set('geom.compression_ratio', 17, 16.5);
    a.set('turbo.vgt', false, true);
    expect(new SpecEdits().overrides()).toEqual({ 'geom.compression_ratio': 17, 'turbo.vgt': false });
    a.reset('turbo.vgt');
    expect(new SpecEdits().overrides()).toEqual({ 'geom.compression_ratio': 17 });
    a.resetAll();
    expect(new SpecEdits().count()).toBe(0);
    a.setBase('hd_i6');
    expect(new SpecEdits().base()).toBe('hd_i6');
    a.load({ preset: 'ld_i4', overrides: { 'inj.n_holes': 8 } });
    const b = new SpecEdits();
    expect([b.base(), b.overrides()]).toEqual(['ld_i4', { 'inj.n_holes': 8 }]);
  });

  it('starts clean, and keeps nothing for the untouched default engine', () => {
    expect([new SpecEdits().base(), new SpecEdits().count()]).toEqual(['crdi15', 0]);
    const a = new SpecEdits();
    a.set('geom.compression_ratio', 17, 16.5);
    a.resetAll();
    expect(localStorage.getItem(EDITS_KEY)).toBeNull();
  });

  it('drops kept edits that no longer pass the schema, rather than showing them', () => {
    localStorage.setItem(EDITS_KEY, '{"preset":"crdi15","overrides":{"geom.renamed_since":1}}');
    expect(new SpecEdits().count()).toBe(0);
    localStorage.setItem(EDITS_KEY, 'not json');
    expect(new SpecEdits().count()).toBe(0);
  });
});

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
