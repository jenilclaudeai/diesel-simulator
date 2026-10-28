import { describe, expect, it } from 'vitest';
import { ROSTER, rosterGroups } from './roster';

describe('the Enjoy roster (ADR-012, ADR-023)', () => {
  it('keeps hatch15 first, the page default, and every key once', () => {
    expect(ROSTER[0]!.key).toBe('hatch15');
    expect(new Set(ROSTER.map(e => e.key)).size).toBe(ROSTER.length);
  });

  it('groups every engine once, in order of first appearance', () => {
    const g = rosterGroups();
    expect(g.map(x => x.label)).toEqual(['Cars and SUVs', 'Trucks', 'Tractors']);
    expect(g.flatMap(x => x.engines.map(e => e.key)).sort()).toEqual(ROSTER.map(e => e.key).sort());
    expect(rosterGroups([{ key: 'a', name: 'A', group: 'y' }, { key: 'b', name: 'B', group: 'x' },
      { key: 'c', name: 'C', group: 'y' }]).map(x => [x.label, x.engines.map(e => e.key)]))
      .toEqual([['y', ['a', 'c']], ['x', ['b']]]);
  });

  it('names a P14 engine by what it is, and the real engine only as "modelled on" (N2)', () => {
    const p14 = ['vw19tdi', 'mhawk75', 'mhawk22', 'gd28', 'duratorq32', 'b57'];
    for (const key of p14) {
      const e = ROSTER.find(x => x.key === key)!;
      expect(e.modelledOn, key).toBeTruthy();
      // the label is "<body> · <litres> L <layout>, <power>": no maker in it
      expect(e.name, key).toMatch(/^(Hatchback|Car|SUV) · \d\.\d L (three|four|five|six), \d+ (ps|bhp)$/);
    }
    expect(ROSTER.filter(e => e.modelledOn).map(e => e.key).sort()).toEqual([...p14].sort());
  });
});
