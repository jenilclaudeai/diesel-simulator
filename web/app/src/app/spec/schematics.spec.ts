import { describe, expect, it } from 'vitest';
import { arcPath, clearanceHeight, CLEARANCE_X, cylinderSection, dialPoint, pistonDisplacement, ringPack, valveDial } from './schematics';

// crdi15, pin offset 0.8 mm: dieselsim.kinematics.SliderCrank.displacement, native, 2026-10-06
const CRDI15 = { bore: 0.077, stroke: 0.0805, conrod: 0.137, compression_ratio: 16, pin_offset: 0.0008 };
const NATIVE: [number, number][] = [[0, 0], [30, 0.006759966694864644], [90, 0.04605049389356969], [180, 0.08050000000000002],
  [270, 0.04654227985632456]];

describe('cylinder cross-section', () => {
  it('the piston moves exactly as the solver\'s slider-crank does, pin offset included', () => {
    for (const [deg, x] of NATIVE) expect(pistonDisplacement(CRDI15.stroke, CRDI15.conrod, CRDI15.pin_offset, deg)).toBeCloseTo(x, 12);
  });
  it('the clearance at TDC is the clearance volume over the piston area', () => {
    expect(clearanceHeight(0.0805, 16) * 1000).toBeCloseTo(5.3667, 3);
  });
  it('to scale: the bore spans the liner, and the drawn gap at TDC is the clearance', () => {
    const s = cylinderSection(CRDI15, 0);
    const k = (s.liner.x1 - s.liner.x0) / CRDI15.bore;              // px per m
    expect(s.gap.y1 - s.gap.y0).toBeCloseTo(clearanceHeight(CRDI15.stroke, 16) * k, 6);
    expect(s.piston.y).toBeCloseTo(s.gap.y1, 6);                       // at TDC the crown meets the gap's bottom
    const b = cylinderSection(CRDI15, 180);
    expect(b.piston.y - s.piston.y).toBeCloseTo(CRDI15.stroke * k, 6);  // TDC to BDC is the stroke
  });
  it('a higher compression ratio draws a smaller gap', () => {
    expect(cylinderSection({ ...CRDI15, compression_ratio: 20 }, 0).gap.mm).toBeLessThan(cylinderSection(CRDI15, 0).gap.mm);
  });
});

describe('valve-timing dial', () => {
  it('durations, overlap and injection from the spec (crdi15: IVO 354, IVC 558, EVO 142, EVC 372, SOI 4 before TDC)', () => {
    const d = valveDial(354, 558, 142, 372, 4);
    expect(d.intake).toEqual({ from: 354, to: 198, deg: 204 });
    expect(d.exhaust).toEqual({ from: 142, to: 12, deg: 230 });
    expect(d.overlap).toBe(18);
    expect(d.injection).toBe(356);
  });
  it('no overlap when exhaust closes before intake opens', () => {
    expect(valveDial(370, 560, 140, 360, 4).overlap).toBe(0);
  });
  it('arcs run clockwise from TDC at the top', () => {
    expect(dialPoint(0, 0, 10, 0)).toEqual({ x: 0, y: -10 });
    expect(dialPoint(0, 0, 10, 90).x).toBeCloseTo(10, 9);
    expect(arcPath(0, 0, 10, 0, 270)).toMatch(/A 10 10 0 1 1/);
  });
});

describe('ring pack', () => {
  it('one groove per compression ring at its axial width, then the oil ring (drawn twice that: its spec width is a contact land)', () => {
    const r = ringPack(2, 0.0015);
    expect(r.rings.map(x => x.kind)).toEqual(['compression', 'compression', 'oil']);
    expect(r.rings[0]!.h).toBe(0.0015);
    expect(r.rings[2]!.h).toBe(0.003);
  });
  it('clearances are drawn exaggerated by a stated factor', () => {
    expect(CLEARANCE_X).toBe(100);
  });
});
