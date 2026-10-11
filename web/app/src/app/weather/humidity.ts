/**
 * Humidity reaches NOx only, as a test cell's correction (ADR-016 item 3; dieselsim/engine.py's
 * nox_humidity_factor). Said where the air is chosen and beside the field. Pure, for the unit tests.
 */

/** ISO 8178's reference humidity, g water / kg dry air: no correction there (engine.H_REF). */
export const H_REF = 10.71;

export const HUMIDITY_NOTE =
  'Humidity corrects the reported NOx only, the way a test cell does (40 CFR 1065.670, normalised to ' +
  'ISO 8178\'s 10.71 g/kg): humid air gives less NOx. Water vapour isn\'t in the cycle, so torque, fuel ' +
  'and smoke don\'t move.';

/** The note for a place's spec overrides, or '' at the reference humidity (or none given). */
export function humidityNote(overrides: Record<string, number> | null | undefined): string {
  const h = overrides?.['thermal.ambient_humidity'];
  return h != null && h !== H_REF ? HUMIDITY_NOTE : '';
}
