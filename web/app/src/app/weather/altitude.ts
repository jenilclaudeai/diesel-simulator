/**
 * What the model does in thin air, said where the air is chosen (FINDING-026, option D; the owner
 * declined option C, a turbo-overspeed fuel cut, on 2026-10-08). Pure: the solving pages' picker and
 * /spec's notes both read it, and the unit tests run without the solver.
 */

/** Below this ambient pressure (about 1000 m) the note shows. Of the presets, only the plateau (Leh) is. */
export const THIN_AIR_PA = 90000;

export const ALTITUDE_NOTE =
  'In thin air, a turbocharged engine with a modern ECU holds its sea-level boost up to the compressor\'s ' +
  'limit. At light load that costs pumping work (crdi15 at Leh, 4057 rpm and 20% load: 37% less torque, ' +
  'converged), and at high rpm and full load the turbo runs at the model\'s speed ceiling: no ' +
  'turbo-overspeed protection is modelled (FINDING-026).';

/** The note for an ambient pressure [Pa], or '' at or near sea level. */
export function altitudeNote(p_amb: number | null | undefined): string {
  return p_amb != null && p_amb < THIN_AIR_PA ? ALTITUDE_NOTE : '';
}
