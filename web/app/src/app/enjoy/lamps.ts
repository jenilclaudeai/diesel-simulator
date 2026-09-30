/** The charge-air derate below which the Derate lamp lights: a real loss, not a warm day. */
export const DERATE_LAMP = 0.95;

/**
 * The Derate lamp means engine protection: the overheat derate acting at all,
 * or a charge cooler losing over 5%. `derate` also carries a continuous
 * charge-density term (the charge air's reference temperature over its
 * temperature) that sits at 0.999 at idle once the charge air warms; the lamp
 * first used `derate < 0.999` and lit for that in ordinary driving.
 */
export function derateLit(derate: number, derateHeat: number): boolean {
  return derateHeat < 1 || derate < DERATE_LAMP;
}
