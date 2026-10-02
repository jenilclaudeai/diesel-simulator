/**
 * The charge-air temperature above which the Derate lamp lights [K]: about
 * 80 °C, roughly where diesel engine controllers start protecting on intake
 * temperature. A judgement, chosen by the owner (2026-10-03), not a
 * measurement.
 */
export const T_CHARGE_LAMP = 353.15;

/**
 * The Derate lamp means engine protection: the overheat derate acting at
 * all, or charge air genuinely hot.
 *
 * History:
 * - First it lit for `derate < 0.999`. `derate` carries a continuous
 *   charge-density term that sits at 0.999 at idle once the charge air
 *   warms, so it lit in ordinary driving (#76).
 * - Then for a charge-air loss over 5% (`derate < 0.95`). The truck crossed
 *   that at full throttle and low speed, with 66 °C charge air, little
 *   cooling air and the fan off. The loss is real, but a real dash would not
 *   warn at 66 °C.
 * - Now on the charge air's temperature itself. The fuel cut from a warm
 *   charge cooler stays in the physics; only the lamp ignores it.
 */
export function derateLit(T_charge: number, derateHeat: number): boolean {
  return derateHeat < 1 || T_charge > T_CHARGE_LAMP;
}
