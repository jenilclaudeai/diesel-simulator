// A custom engine (ADR-014): the roster's JSON format (engines/*.json, the
// parameters of dieselsim.builder.build_engine) plus the vehicle it drives
// in. The form edits it, the file import/export reads and writes it, and the
// solver takes it as { headline: ... }.
import { VEHICLE_KEYS } from '@dieselsim/physics';

export type VehicleKey = (typeof VEHICLE_KEYS)[number];

export interface CustomEngine {
  key: string;
  name: string;
  displacement: number;   // litres
  n_cyl: number;
  rated_rpm: number;
  peak_torque: number;    // N·m
  peak_power: number;     // kW
  plateau: [number, number] | null;
  turbocharged: boolean;
  vehicle: VehicleKey;
  // optional tuning, as the roster uses (engines/ROSTER.md)
  afr_limit?: number;
  boost_map_rise?: number;
}

export const VEHICLE_NAMES: Record<VehicleKey, string> = {
  hatch15: '1.3 t hatchback', crdi15: '1.5 t compact', ld_i4: '1.75 t car',
  crdi22: '1.9 t SUV', hd_i6: '40 t truck', tractor: '3 t utility tractor',
};

export const EXAMPLE_ENGINE: CustomEngine = {
  key: 'my20', name: '2.0 L four, 140 ps', displacement: 2.0, n_cyl: 4, rated_rpm: 4000,
  peak_torque: 320, peak_power: 103, plateau: [1750, 2500], turbocharged: true, vehicle: 'crdi15',
};

const NUMBERS = ['displacement', 'n_cyl', 'rated_rpm', 'peak_torque', 'peak_power'] as const;
/** Generous sanity bounds: the builder decides what an engine makes, these only catch typos. */
const BOUNDS: Record<(typeof NUMBERS)[number], [number, number]> = {
  displacement: [0.1, 30], n_cyl: [1, 16], rated_rpm: [800, 6000], peak_torque: [5, 10000], peak_power: [2, 1500],
};

/** The problems with an engine, in words; empty if the builder may try it. */
export function engineProblems(e: Partial<CustomEngine>): string[] {
  const out: string[] = [];
  if (!e.name || typeof e.name !== 'string') out.push('a name');
  for (const k of NUMBERS) {
    const v = e[k], [lo, hi] = BOUNDS[k];
    if (typeof v !== 'number' || !Number.isFinite(v)) out.push(`${k} must be a number`);
    else if (v < lo || v > hi) out.push(`${k} ${v} is outside ${lo}–${hi}`);
  }
  if (typeof e.n_cyl === 'number' && !Number.isInteger(e.n_cyl)) out.push('n_cyl must be a whole number');
  if (e.plateau != null) {
    const [a, b] = e.plateau;
    if (!(Number.isFinite(a) && Number.isFinite(b) && a < b)) out.push('plateau must be [from, to] rpm, from < to');
    else if (typeof e.rated_rpm === 'number' && b > e.rated_rpm) out.push('the plateau must end at or below rated rpm');
  }
  if (!(VEHICLE_KEYS as readonly unknown[]).includes(e.vehicle)) out.push(`vehicle must be one of ${VEHICLE_KEYS.join(', ')}`);
  return out;
}

/** Read an engine file (engines/*.json format). Throws with the problems. */
export function parseEngineJson(text: string): CustomEngine {
  let d: Record<string, unknown>;
  try {
    d = JSON.parse(text) as Record<string, unknown>;
  } catch {
    throw new Error('not JSON');
  }
  if (typeof d !== 'object' || d === null || Array.isArray(d)) throw new Error('not an engine (expected a JSON object)');
  const plateau = Array.isArray(d['plateau']) ? (d['plateau'] as [number, number]) : null;
  const e: CustomEngine = {
    key: typeof d['key'] === 'string' ? d['key'] : 'custom',
    name: d['name'] as string, displacement: d['displacement'] as number, n_cyl: d['n_cyl'] as number,
    rated_rpm: d['rated_rpm'] as number, peak_torque: d['peak_torque'] as number, peak_power: d['peak_power'] as number,
    plateau, turbocharged: d['turbocharged'] !== false, vehicle: d['vehicle'] as VehicleKey,
  };
  if (typeof d['afr_limit'] === 'number') e.afr_limit = d['afr_limit'];
  if (typeof d['boost_map_rise'] === 'number') e.boost_map_rise = d['boost_map_rise'];
  const p = engineProblems(e);
  if (p.length) throw new Error(p.join('; '));
  return e;
}

/** The engine as its file: what export writes and the native build reads. */
export function engineJson(e: CustomEngine): string {
  const d: Record<string, unknown> = { ...e };
  if (d['plateau'] === null) delete d['plateau'];
  if (d['turbocharged'] === true) delete d['turbocharged'];      // the builder's default
  return JSON.stringify(d, null, 2) + '\n';
}

/** What the solver takes: build_engine's parameters (the bridge ignores "vehicle" and "key"). */
export function headline(e: CustomEngine): Record<string, unknown> {
  return JSON.parse(engineJson(e)) as Record<string, unknown>;
}

export interface Achieved {
  torque: { got: number; want: number; pct: number; rpm: number };
  power: { got: number; want: number; pct: number; rpm: number };
  /** torque at the plateau's start, as a share of the requested peak (verify()'s low-end check) */
  plateauStart: { rpm: number; got: number; pct: number } | null;
}

/** A dyno pull against the brochure, as builder.verify() reports it. */
export function achieved(points: { rpm: number; torque: number; powerKw: number }[],
                         want: { peak_torque: number; peak_power_kw: number; plateau: [number, number] | null }): Achieved | null {
  if (points.length < 2) return null;
  const t = points.reduce((a, b) => (b.torque > a.torque ? b : a));
  const w = points.reduce((a, b) => (b.powerKw > a.powerKw ? b : a));
  let plateauStart: Achieved['plateauStart'] = null;
  if (want.plateau) {
    const r = want.plateau[0], s = [...points].sort((a, b) => a.rpm - b.rpm);
    const i = s.findIndex(p => p.rpm >= r);
    if (i > 0) {
      const a = s[i - 1]!, b = s[i]!, got = a.torque + (b.torque - a.torque) * (r - a.rpm) / (b.rpm - a.rpm);
      plateauStart = { rpm: r, got, pct: 100 * got / want.peak_torque };
    } else if (i === 0) plateauStart = { rpm: r, got: s[0]!.torque, pct: 100 * s[0]!.torque / want.peak_torque };
  }
  return {
    torque: { got: t.torque, want: want.peak_torque, pct: 100 * t.torque / want.peak_torque, rpm: t.rpm },
    power: { got: w.powerKw, want: want.peak_power_kw, pct: 100 * w.powerKw / want.peak_power_kw, rpm: w.rpm },
    plateauStart,
  };
}
