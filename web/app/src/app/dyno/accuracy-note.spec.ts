import { accuracyNote } from './accuracy-note';

const table = {
  eng: { worstPct: -5.9, worstRpm: 1650, governedNm: 2.0 },
  na: { worstPct: 0, worstRpm: 0, governedNm: 0 },
};

describe('accuracyNote', () => {
  it('gives the measured gap when the solver build matches', () => {
    const s = accuracyNote('eng', 'abc', String, table, 'abc');
    expect(s).toContain('within 5.9%');
    expect(s).toContain('1650 rpm');
    expect(s).toContain('within 2.0 N·m');
  });
  it('never shows a number measured on a different solver build', () => {
    const s = accuracyNote('eng', 'other', String, table, 'abc');
    expect(s).toContain('has not been measured for this solver build');
    expect(s).not.toMatch(/\d%/);
  });
  it('says so for an engine that was not measured', () => {
    expect(accuracyNote('custom', 'abc', String, table, 'abc')).toContain('has not been measured');
  });
  it('says an exact match plainly', () => {
    expect(accuracyNote('na', 'abc', String, table, 'abc')).toContain('matches a fully converged solve');
  });
  it('uses the supplied rpm formatter', () => {
    expect(accuracyNote('eng', 'abc', r => `#${r}`, table, 'abc')).toContain('#1650 rpm');
  });
  it('ships a table for every preset the page offers', async () => {
    const { ACCURACY, ACCURACY_SOLVER } = await import('./accuracy');
    expect(Object.keys(ACCURACY).sort()).toEqual(['crdi15', 'crdi_1p5', 'hd_i6', 'ld_i4', 'single']);
    expect(ACCURACY_SOLVER).toMatch(/^[0-9a-f]{64}$/);
  });
});
