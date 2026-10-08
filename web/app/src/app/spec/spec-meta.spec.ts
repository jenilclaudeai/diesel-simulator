import { describe, expect, it } from 'vitest';
import { ALTITUDE_NOTE } from '../weather/altitude';
import { HUMIDITY_NOTE } from '../weather/humidity';
import { FIELDS, GROUPS, groupFields, groupOf, label, NOTE_EXTRA, noteFor, noteRest, readOnly, UNIT_FOR, unitFor, unitOf } from './spec-meta';

describe('spec editor metadata', () => {
  it('every field belongs to exactly one group', () => {
    const counts = FIELDS.map(f => GROUPS.filter(g => g.classes.includes(f.cls)).length);
    expect(FIELDS.length).toBe(190);   // 188 + ecu_modern + ambient_humidity (ADR-016 items 2, 3)
    expect(counts.every(c => c === 1)).toBe(true);
  });

  it('every curated field exists, in its own group, and is editable', () => {
    for (const g of GROUPS) {
      for (const p of g.primary) {
        const f = FIELDS.find(x => x.path === p);
        expect(f, `${g.key}: ${p}`).toBeDefined();
        expect(groupOf(f!)?.key, p).toBe(g.key);
        expect(readOnly(f!), p).toBe(false);
      }
    }
  });

  it('a group lists its curated fields first, then all the rest, none twice', () => {
    for (const g of GROUPS) {
      const { primary, more } = groupFields(g);
      expect(primary.map(f => f.path)).toEqual(g.primary);
      const all = [...primary, ...more].map(f => f.path);
      expect(new Set(all).size).toBe(all.length);
      expect(all.length).toBe(FIELDS.filter(f => g.classes.includes(f.cls)).length);
    }
  });

  it('text, lists and n_cyl are read-only: 182 editable (183 by type in Python, less n_cyl)', () => {
    expect(FIELDS.filter(f => !readOnly(f)).length).toBe(182);
    expect(readOnly(FIELDS.find(f => f.path === 'geom.n_cyl')!)).toBe(true);
    expect(readOnly(FIELDS.find(f => f.path === 'geom.firing_order')!)).toBe(true);
  });

  it('labels: curated where given, the field name in words otherwise', () => {
    expect(label('geom.compression_ratio')).toBe('Compression ratio');
    expect(label('inj.soi_deg_btdc')).toBe('Main injection start (before TDC)');
    expect(label('trib.ring_axial_width')).toBe('Ring axial width');
  });

  it('units are read from the start of config.py\'s comments', () => {
    expect(['m', 'm  (centre-to-centre)', 'kg m^2', 'rpm, speed giving pr_max_ref at u=1',
      'm^2 effective nozzle area (A/R proxy)', 'full+splitter blade count (tone source)', ''].map(unitOf))
      .toEqual(['m', 'm', 'kg m^2', 'rpm', 'm^2', '', '']);
    expect(['N.m brake, flat cap', 'Pa.s at 150 C, 1e6 1/s'].map(unitOf)).toEqual(['N·m', 'Pa·s']);
  });

  it('the note beside a field is what is left after its unit', () => {
    expect(['m', 'm  (centre-to-centre)', 'kg m^2 (flywheel + crank + damper)', 'm, inner seat diameter', 'geometric', '']
      .map(noteRest)).toEqual(['', '(centre-to-centre)', '(flywheel + crank + damper)', 'inner seat diameter', 'geometric', '']);
  });

  it('every curated field has a unit, or is a ratio or a switch', () => {
    const unitless = new Set(['afr_limit', 'boost_map_rise', 'geom.compression_ratio', 'inj.n_holes', 'inj.pilot_enabled',
      'inj.cetane_number', 'turbo.enabled', 'turbo.vgt', 'ecu_modern', 'turbo.pr_max_ref', 'oil.viscosity_index']);
    for (const g of GROUPS) for (const p of g.primary) {
      const f = FIELDS.find(x => x.path === p)!;
      if (!unitless.has(p)) expect(unitFor(f), p).not.toBe('');
    }
    for (const p of Object.keys(UNIT_FOR)) expect(FIELDS.some(f => f.path === p), p).toBe(true);
  });

  it("FINDING-026's thin-air limits are said beside ambient pressure and the ECU switch, after their own notes", () => {
    for (const p of Object.keys(NOTE_EXTRA)) expect(FIELDS.some(f => f.path === p), p).toBe(true);
    const field = (p: string) => FIELDS.find(f => f.path === p)!;
    const amb = noteFor(field('thermal.ambient_p')), ecu = noteFor(field('ecu_modern'));
    expect(amb).toContain('Below 90 kPa');
    expect(amb).toContain(ALTITUDE_NOTE);
    expect(ecu.startsWith(noteRest(field('ecu_modern').note) + ' ')).toBe(true);
    expect(ecu).toContain('no turbo-overspeed');
    expect(ecu).toContain('FINDING-026');
    // ADR-016 item 3: the humidity field, its unit and that it corrects NOx only
    const hum = field('thermal.ambient_humidity');
    expect(unitFor(hum)).toBe('g/kg');
    expect(noteFor(hum)).toContain(HUMIDITY_NOTE);
    expect(label('thermal.ambient_humidity')).toBe('Ambient humidity');
    // every other field: its own note, unchanged
    for (const f of FIELDS) if (!(f.path in NOTE_EXTRA)) expect(noteFor(f), f.path).toBe(noteRest(f.note));
  });
});
