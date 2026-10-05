/**
 * The spec editor's metadata (Phase 6, ADR-015): which subsystem each field
 * belongs to, which fields come first in it (by influence on what the engine
 * does), which are read-only, and each field's label and unit.
 *
 * The field list itself is generated from config.py (spec-schema.json,
 * tools/spec_schema.py --check), so it can't drift; this file only curates
 * order and words on top of it, and spec-meta.spec.ts checks that every
 * curated path exists.
 */
import SCHEMA from './spec-schema.json';

export interface SchemaRow { path: string; cls: string; type: 'number' | 'int' | 'bool' | 'string' | 'list'; note: string }
export const FIELDS: readonly SchemaRow[] = SCHEMA as SchemaRow[];

export interface Group { key: string; title: string; classes: string[]; primary: string[] }

/** Grouped by physical subsystem, not class name (PLAN.md Phase 6); most influential first. */
export const GROUPS: readonly Group[] = [
  { key: 'ratings', title: 'Ratings and limits', classes: ['EngineSpec'],
    primary: ['idle_rpm', 'rated_rpm', 'max_rpm', 'afr_limit', 'torque_limit', 'power_limit', 'p_max_limit', 'T_exh_limit', 'boost_map_rise'] },
  { key: 'cylinder', title: 'Cylinder and crank', classes: ['Geometry'],
    primary: ['geom.bore', 'geom.stroke', 'geom.compression_ratio', 'geom.conrod', 'geom.flywheel_inertia'] },
  { key: 'injection', title: 'Injection and fuel', classes: ['Injection'],
    primary: ['inj.soi_deg_btdc', 'inj.rail_pressure_max', 'inj.n_holes', 'inj.hole_dia', 'inj.pilot_enabled',
      'inj.pilot_fraction', 'inj.pilot_advance_deg', 'inj.cetane_number'] },
  { key: 'valves', title: 'Valvetrain', classes: ['ValveTrain'],
    primary: ['valves.ivo_deg', 'valves.ivc_deg', 'valves.evo_deg', 'valves.evc_deg', 'valves.intake_lift_max',
      'valves.exhaust_lift_max', 'valves.intake_valve_dia', 'valves.exhaust_valve_dia'] },
  { key: 'air', title: 'Turbo and air path', classes: ['Turbo', 'AirPath'],
    primary: ['turbo.enabled', 'turbo.vgt', 'turbo.pr_max_ref', 'turbo.turbine_area_eff', 'turbo.comp_eff_peak',
      'turbo.turb_eff_peak', 'turbo.intercooler_eff', 'air.egr_max_fraction'] },
  { key: 'friction', title: 'Lubrication and friction', classes: ['Lubricant', 'Tribology'],
    primary: ['oil.hths', 'oil.viscosity_index', 'trib.ring_tangential_load', 'trib.skirt_clearance_new',
      'trib.main_clearance_new', 'trib.rod_clearance_new'] },
  { key: 'thermal', title: 'Thermal and cooling', classes: ['Thermal', 'Cooling'],
    primary: ['thermal.ambient_T', 'thermal.ambient_p', 'thermal.coolant_T', 'thermal.thermostat_open_T',
      'cooling.T_warn', 'cooling.T_derate'] },
];

/** Not editable here: text, lists, and n_cyl (it must agree with the firing order). */
export function readOnly(f: SchemaRow): boolean {
  return f.type === 'string' || f.type === 'list' || f.path === 'geom.n_cyl';
}

export function groupOf(f: SchemaRow): Group | undefined {
  return GROUPS.find(g => g.classes.includes(f.cls));
}

/** A group's fields: its primary ones in the curated order, then the rest in dataclass order. */
export function groupFields(g: Group): { primary: SchemaRow[]; more: SchemaRow[] } {
  const mine = FIELDS.filter(f => g.classes.includes(f.cls));
  const primary = g.primary.map(p => mine.find(f => f.path === p)).filter((f): f is SchemaRow => !!f);
  return { primary, more: mine.filter(f => !g.primary.includes(f.path)) };
}

const LABELS: Record<string, string> = {
  idle_rpm: 'Idle speed', rated_rpm: 'Rated speed', max_rpm: 'Maximum speed (governor)',
  afr_limit: 'Smoke limit (minimum air-fuel ratio)', torque_limit: 'Torque limit', power_limit: 'Power limit',
  p_max_limit: 'Peak cylinder pressure limit', T_exh_limit: 'Exhaust temperature limit',
  boost_map_rise: 'Boost map rise', 'geom.bore': 'Bore', 'geom.stroke': 'Stroke',
  'geom.compression_ratio': 'Compression ratio', 'geom.conrod': 'Connecting rod length',
  'geom.flywheel_inertia': 'Flywheel inertia', 'inj.soi_deg_btdc': 'Main injection start (before TDC)',
  'inj.rail_pressure_max': 'Maximum rail pressure', 'inj.n_holes': 'Nozzle holes', 'inj.hole_dia': 'Nozzle hole diameter',
  'inj.pilot_enabled': 'Pilot injection', 'inj.pilot_fraction': 'Pilot fraction of the fuel',
  'inj.pilot_advance_deg': 'Pilot advance before main', 'inj.cetane_number': 'Cetane number',
  'valves.ivo_deg': 'Intake opens (IVO)', 'valves.ivc_deg': 'Intake closes (IVC)',
  'valves.evo_deg': 'Exhaust opens (EVO)', 'valves.evc_deg': 'Exhaust closes (EVC)',
  'valves.intake_lift_max': 'Intake valve lift', 'valves.exhaust_lift_max': 'Exhaust valve lift',
  'valves.intake_valve_dia': 'Intake valve diameter', 'valves.exhaust_valve_dia': 'Exhaust valve diameter',
  'turbo.enabled': 'Turbocharger', 'turbo.vgt': 'Variable-geometry turbine', 'turbo.pr_max_ref': 'Compressor pressure ratio at reference speed',
  'turbo.turbine_area_eff': 'Turbine effective area', 'turbo.comp_eff_peak': 'Compressor peak efficiency',
  'turbo.turb_eff_peak': 'Turbine peak efficiency', 'turbo.intercooler_eff': 'Intercooler effectiveness',
  'air.egr_max_fraction': 'Maximum EGR fraction', 'oil.hths': 'Oil HTHS viscosity', 'oil.viscosity_index': 'Oil viscosity index',
  'trib.ring_tangential_load': 'Ring tangential load', 'trib.skirt_clearance_new': 'Piston skirt clearance (new)',
  'trib.main_clearance_new': 'Main bearing clearance (new)', 'trib.rod_clearance_new': 'Rod bearing clearance (new)',
  'thermal.ambient_T': 'Ambient temperature', 'thermal.ambient_p': 'Ambient pressure', 'thermal.coolant_T': 'Coolant temperature',
  'thermal.thermostat_open_T': 'Thermostat opens at', 'cooling.T_warn': 'Coolant warning at', 'cooling.T_derate': 'Derate starts at',
};

/** A label: curated for the influential fields, otherwise the field name in words. */
export function label(path: string): string {
  if (LABELS[path]) return LABELS[path]!;
  const name = path.split('.').pop()!;
  const words = name.replace(/_/g, ' ').replace(/\b(deg|btdc)\b/g, m => (m === 'deg' ? 'degrees' : 'before TDC'));
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Units config.py's comments start with, longest first so "m^2" wins over "m". */
const UNITS = ['kg m^2', 'J/kg/K', 'kg/s', 'N/m', 'W/K', 'N.m', 'Pa.s', 'm^3', 'm^2', 'mm', 'rpm', 'deg', 'Pa', 'bar', 'kg', 'N', 'K', 'W', 's', 'm', '%'];
/** How a unit is shown. */
const SHOW: Record<string, string> = { 'N.m': 'N·m', 'Pa.s': 'Pa·s', deg: '°' };

/** The unit a field's note begins with, or '' if it doesn't name one. */
export function unitOf(note: string): string {
  const n = note.trim();
  for (const u of UNITS) {
    if (n === u || n.startsWith(u + ' ') || n.startsWith(u + ',') || n.startsWith(u + '\t')) return SHOW[u] ?? u;
  }
  return '';
}

/** A note without the unit it starts with: what's left to show beside the field. */
export function noteRest(note: string): string {
  const n = note.trim();
  for (const u of UNITS) {
    if (n === u) return '';
    if (n.startsWith(u + ' ') || n.startsWith(u + ',') || n.startsWith(u + '\t')) return n.slice(u.length).replace(/^[,\s]+/, '');
  }
  return n;
}

/** Units for curated fields whose config.py comment doesn't start with one (checked by hand against the model). */
export const UNIT_FOR: Record<string, string> = {
  idle_rpm: 'rpm', rated_rpm: 'rpm', max_rpm: 'rpm', p_max_limit: 'Pa', T_exh_limit: 'K',
  'inj.soi_deg_btdc': '° before TDC', 'inj.pilot_advance_deg': '° before main', 'inj.pilot_fraction': 'of the fuel (0–1)',
  'valves.ivo_deg': '°', 'valves.ivc_deg': '°', 'valves.evo_deg': '°', 'valves.evc_deg': '°',
  'valves.exhaust_lift_max': 'm', 'valves.exhaust_valve_dia': 'm', 'trib.rod_clearance_new': 'm',
  'turbo.comp_eff_peak': '(0–1)', 'turbo.turb_eff_peak': '(0–1)', 'turbo.intercooler_eff': '(0–1)',
  'air.egr_max_fraction': 'of trapped mass (0–1)',
};

/** A field's unit: curated, else from its note, else from its name (_deg, _rpm). */
export function unitFor(f: SchemaRow): string {
  return UNIT_FOR[f.path] ?? (unitOf(f.note) || (/_deg(_|$)/.test(f.path) ? '°' : /_rpm$/.test(f.path) ? 'rpm' : ''));
}
