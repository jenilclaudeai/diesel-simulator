import { describe, expect, it } from 'vitest';
import { FIELDS, GROUPS, groupFields, groupOf, label, noteRest, readOnly, UNIT_FOR, unitFor, unitOf } from './spec-meta';

describe('spec editor metadata', () => {
  it('every field belongs to exactly one group', () => {
    const counts = FIELDS.map(f => GROUPS.filter(g => g.classes.includes(f.cls)).length);
    expect(FIELDS.length).toBe(188);
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

  it('text, lists and n_cyl are read-only: 180 editable (181 by type in Python, less n_cyl)', () => {
    expect(FIELDS.filter(f => !readOnly(f)).length).toBe(180);
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
      'inj.cetane_number', 'turbo.enabled', 'turbo.vgt', 'turbo.pr_max_ref', 'oil.viscosity_index']);
    for (const g of GROUPS) for (const p of g.primary) {
      const f = FIELDS.find(x => x.path === p)!;
      if (!unitless.has(p)) expect(unitFor(f), p).not.toBe('');
    }
    for (const p of Object.keys(UNIT_FOR)) expect(FIELDS.some(f => f.path === p), p).toBe(true);
  });
});
