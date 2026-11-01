import type { Transmission } from '@dieselsim/physics';

/**
 * The gearbox to keep (DriveEnv, Phase 7 step 7) when /enjoy's Auto/Manual is tapped
 * (ENJ-02: Enjoy read the kept gearbox but never wrote it, so a reload forgot Manual).
 * Enjoy has no dual clutch, so its Auto keeps a dual clutch chosen on /drive or /spec.
 */
export function enjoyGearbox(manual: boolean, kept: Transmission): Transmission {
  if (manual) return 'manual';
  return kept === 'dct' ? 'dct' : 'tc';
}
