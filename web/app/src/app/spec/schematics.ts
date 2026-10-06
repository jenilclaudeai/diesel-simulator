/**
 * ADR-009's live schematics, as pure geometry (Phase 6, ADR-015). Every
 * dimension that carries meaning comes from a spec field; the few that are
 * not in the spec (a piston's crown height and length, the land between ring
 * grooves) are fixed drawing proportions, said so where they are used.
 */

/** Piston distance from TDC, m: dieselsim's SliderCrank.displacement, exactly (TDC taken at theta = 0, pin offset included). */
export function pistonDisplacement(stroke: number, conrod: number, pinOffset: number, thetaDeg: number): number {
  const a = stroke / 2, l = conrod, e = pinOffset;
  const xRaw = (th: number) => {
    const sb = (a * Math.sin(th) - e) / l;
    return -a * Math.cos(th) - l * Math.sqrt(Math.max(1e-12, 1 - sb * sb));
  };
  return xRaw(thetaDeg * Math.PI / 180) - xRaw(0);
}

/** The gap between piston and head at TDC, m: clearance volume over piston area, stroke / (CR - 1). */
export function clearanceHeight(stroke: number, compressionRatio: number): number {
  return stroke / (compressionRatio - 1);
}

export interface Geom { bore: number; stroke: number; conrod: number; compression_ratio: number; pin_offset: number }
export interface Section {
  W: number; H: number;
  liner: { x0: number; x1: number; y0: number; y1: number };
  head: number;            // y of the head's face
  piston: { x: number; y: number; w: number; h: number };
  pin: { x: number; y: number }; crankPin: { x: number; y: number }; crank: { x: number; y: number; r: number };
  gap: { y0: number; y1: number; mm: number };   // the clearance at TDC, where the piston is drawn at TDC
}

/** Drawing proportions not in the spec: crown above the pin, and skirt below it, as fractions of the bore. */
export const CROWN = 0.35, SKIRT = 0.45;

/**
 * A cylinder cross-section at a crank angle, in SVG units (y down). Bore,
 * stroke, rod, pin offset and the clearance gap are to scale.
 */
export function cylinderSection(g: Geom, thetaDeg: number, W = 260, H = 420): Section {
  const a = g.stroke / 2, l = g.conrod, e = g.pin_offset;
  const hc = clearanceHeight(g.stroke, g.compression_ratio);
  const pinUp = (deg: number) => -(-a * Math.cos(deg * Math.PI / 180) - l * Math.sqrt(Math.max(1e-12,
    1 - ((a * Math.sin(deg * Math.PI / 180) - e) / l) ** 2)));          // pin height above the crank centre, m
  const headUp = pinUp(0) + CROWN * g.bore + hc;
  const span = headUp + a + 0.06 * g.bore;                               // head to below the crank circle
  const k = Math.min((H - 20) / span, (W - 40) / (Math.max(g.bore, 2 * a) * 1.15));
  const cx = W / 2, cy = 10 + headUp * k;                                // crank centre
  const yUp = (m: number) => cy - m * k;
  const p = pinUp(thetaDeg), th = thetaDeg * Math.PI / 180;
  const bx0 = cx + e * k - g.bore * k / 2, bx1 = cx + e * k + g.bore * k / 2;
  return {
    W, H,
    liner: { x0: bx0, x1: bx1, y0: yUp(headUp), y1: yUp(pinUp(180) - SKIRT * g.bore) },
    head: yUp(headUp),
    piston: { x: bx0 + 1, y: yUp(p + CROWN * g.bore), w: g.bore * k - 2, h: (CROWN + SKIRT) * g.bore * k },
    pin: { x: cx + e * k, y: yUp(p) },
    crankPin: { x: cx + a * Math.sin(th) * k, y: yUp(a * Math.cos(th)) },
    crank: { x: cx, y: cy, r: a * k },
    gap: { y0: yUp(headUp), y1: yUp(headUp - hc), mm: hc * 1000 },
  };
}

/** The valve events on a crank circle: TDC at the top, clockwise, 720 degrees folded onto 360. */
export interface Dial {
  intake: { from: number; to: number; deg: number }; exhaust: { from: number; to: number; deg: number };
  overlap: number; injection: number;
}
export function valveDial(ivo: number, ivc: number, evo: number, evc: number, soiBtdc: number): Dial {
  const fold = (x: number) => ((x % 360) + 360) % 360;
  return {
    intake: { from: fold(ivo), to: fold(ivc), deg: ivc - ivo },
    exhaust: { from: fold(evo), to: fold(evc), deg: evc - evo },
    overlap: Math.max(0, evc - ivo),
    injection: fold(720 - soiBtdc),
  };
}

/** An SVG arc path on a circle (cx, cy, r) from `from` through `deg` degrees clockwise, 0 at the top. */
export function arcPath(cx: number, cy: number, r: number, from: number, deg: number): string {
  const pt = (d: number) => [cx + r * Math.sin(d * Math.PI / 180), cy - r * Math.cos(d * Math.PI / 180)];
  const [x0, y0] = pt(from), [x1, y1] = pt(from + deg);
  return `M ${x0!.toFixed(2)} ${y0!.toFixed(2)} A ${r} ${r} 0 ${deg > 180 ? 1 : 0} 1 ${x1!.toFixed(2)} ${y1!.toFixed(2)}`;
}

/** A point on the dial at `deg` clockwise from TDC. */
export function dialPoint(cx: number, cy: number, r: number, deg: number): { x: number; y: number } {
  return { x: cx + r * Math.sin(deg * Math.PI / 180), y: cy - r * Math.cos(deg * Math.PI / 180) };
}

/** Clearances are tens of microns: drawn this many times larger, and labelled with their true values. */
export const CLEARANCE_X = 100;

export interface RingPack { rings: { y: number; h: number; kind: 'compression' | 'oil' }[]; height: number }
/**
 * Ring grooves down the piston's top land: compression rings (their axial
 * width, `ring_axial_width`), then the oil ring. The spec's `oil_ring_width`
 * is the oil ring's contact land (friction.py: 'thin land, mostly
 * boundary'), not its axial size, so the oil ring is drawn at a drawing
 * proportion, twice a compression ring, and labelled with its land. The
 * lands between grooves are one ring width (drawing proportion too).
 */
export function ringPack(nComp: number, ringWidth: number): RingPack {
  const rings: RingPack['rings'] = [];
  let y = ringWidth * 1.5;
  for (let i = 0; i < nComp; i++) { rings.push({ y, h: ringWidth, kind: 'compression' }); y += ringWidth * 2; }
  rings.push({ y, h: ringWidth * 2, kind: 'oil' });
  return { rings, height: y + ringWidth * 3.5 };
}
