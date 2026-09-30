// Port of the running skirt clearance (dieselsim/acoustics.py, FINDING-023
// option A) and the wall-follow constants it shares with
// engine._apply_thermal_state (dieselsim/config.py). Held to Python through
// the live-drive and sound fixtures.

/** Kelvin each wall moves per kelvin of coolant away from the warm reference. */
export const T_COOLANT_REF = 361.0;
export const WALL_FOLLOW = { piston_T: 0.72, head_T: 0.85, liner_T_top: 0.88, liner_T_bot: 0.95, port_T_exh: 0.45 } as const;

export const ALPHA_PISTON = 21e-6;   // 1/K, Al-Si piston alloy
export const ALPHA_BORE = 11e-6;     // 1/K, grey cast iron bore
/** The slap level's reference: a film on its 0.32 x clearance cap keeps its old level. */
export const SLAP_CLR_REF = 30e-6 / 0.32;

/** Diametral skirt clearance [m] at this coolant; c_ref is the warm reference's (wear included). */
export function running_skirt_clearance(c_ref: number, bore: number, T_coolant: number): number {
  const f = T_coolant - T_COOLANT_REF;
  const dT_piston = WALL_FOLLOW.piston_T * f;
  const dT_bore = (0.55 * WALL_FOLLOW.liner_T_top + 0.45 * WALL_FOLLOW.liner_T_bot) * f;
  return Math.max(c_ref - bore * (ALPHA_PISTON * dT_piston - ALPHA_BORE * dT_bore), 0.25 * c_ref);
}
