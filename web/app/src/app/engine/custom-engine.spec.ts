import { describe, expect, it } from 'vitest';
import { achieved, engineJson, engineProblems, EXAMPLE_ENGINE, headline, parseEngineJson } from './custom-engine';

describe('engine files', () => {
  it('round-trips: export then import gives the same engine', () => {
    expect(parseEngineJson(engineJson(EXAMPLE_ENGINE))).toEqual(EXAMPLE_ENGINE);
  });
  it('reads a roster file as written in engines/ (no vehicle: refused, naming it)', () => {
    const roster = '{"key":"hatch15","name":"1.5 L four, 115 ps","displacement":1.5,"n_cyl":4,"rated_rpm":4000,' +
      '"peak_torque":260,"peak_power":85,"plateau":[2000,2750],"boost_map_rise":0.12,"afr_limit":16.0}';
    expect(() => parseEngineJson(roster)).toThrow(/vehicle must be one of/);
    const e = parseEngineJson(roster.replace('}', ',"vehicle":"hatch15"}'));
    expect(e.afr_limit).toBe(16);
    expect(e.boost_map_rise).toBe(0.12);
    expect(e.plateau).toEqual([2000, 2750]);
  });
  it('says what is wrong, every problem at once', () => {
    expect(() => parseEngineJson('nope')).toThrow('not JSON');
    expect(engineProblems({ ...EXAMPLE_ENGINE, n_cyl: 4.5, peak_power: -1, plateau: [3000, 2000] })).toEqual([
      'peak_power -1 is outside 2–1500', 'n_cyl must be a whole number', 'plateau must be [from, to] rpm, from < to']);
    expect(engineProblems({ ...EXAMPLE_ENGINE, plateau: [1750, 4500] })).toEqual(['the plateau must end at or below rated rpm']);
  });
  it('writes only what the builder needs: no null plateau, no default turbocharged', () => {
    const d = JSON.parse(engineJson({ ...EXAMPLE_ENGINE, plateau: null }));
    expect('plateau' in d).toBe(false);
    expect('turbocharged' in d).toBe(false);
    expect(JSON.parse(engineJson({ ...EXAMPLE_ENGINE, turbocharged: false }))['turbocharged']).toBe(false);
    expect(headline(EXAMPLE_ENGINE)['peak_torque']).toBe(320);
  });
});

describe('achieved', () => {
  const pts = [{ rpm: 1000, torque: 200, powerKw: 21 }, { rpm: 2000, torque: 300, powerKw: 63 },
               { rpm: 3000, torque: 310, powerKw: 97 }, { rpm: 4000, torque: 240, powerKw: 100 }];
  it('reports peaks and the plateau start as verify() does', () => {
    const a = achieved(pts, { peak_torque: 320, peak_power_kw: 103, plateau: [1750, 2500] })!;
    expect(a.torque).toEqual({ got: 310, want: 320, pct: 100 * 310 / 320, rpm: 3000 });
    expect(a.power.rpm).toBe(4000);
    expect(a.plateauStart!.got).toBeCloseTo(275, 12);         // interpolated at 1750
    expect(a.plateauStart!.pct).toBeCloseTo(100 * 275 / 320, 12);
  });
  it('needs a curve', () => {
    expect(achieved(pts.slice(0, 1), { peak_torque: 1, peak_power_kw: 1, plateau: null })).toBeNull();
  });
});
