// Phase 8: the driver pages' units (/drive, /enjoy and their place notes). The
// owner's choice (2026-10-19): Metric, US or UK, on the driver pages only; the
// engineering pages (Dyno, Cycle, Sweep, Grid, Spec, Durability) stay SI.
// Kept per browser, like the place, the fuel and the gearbox (DriveEnv).
import { Injectable, signal } from '@angular/core';

export type UnitSystem = 'metric' | 'us' | 'uk';

export const UNIT_SYSTEMS: readonly { key: UnitSystem; name: string }[] = [
  { key: 'metric', name: 'Metric' },
  { key: 'us', name: 'US' },
  { key: 'uk', name: 'UK' },
];

export const UNITS_KEY = 'dieselsim-units';

// exact by definition
export const KM_PER_MILE = 1.609344;
export const L_PER_US_GAL = 3.785411784;
export const L_PER_UK_GAL = 4.54609;
export const PA_PER_PSI = 6894.757293168361;     // 0.45359237 kg x 9.80665 / 0.0254^2
export const PA_PER_INHG = 3386.389;             // at 0 deg C

/** Speed: km/h, or mph in the US and the UK. */
export function speed(kmh: number, s: UnitSystem): number {
  return s === 'metric' ? kmh : kmh / KM_PER_MILE;
}
export function speedUnit(s: UnitSystem): string {
  return s === 'metric' ? 'km/h' : 'mph';
}

/** Distance: km, or miles in the US and the UK. */
export function distance(km: number, s: UnitSystem): number {
  return s === 'metric' ? km : km / KM_PER_MILE;
}
export function distanceUnit(s: UnitSystem): string {
  return s === 'metric' ? 'km' : 'mi';
}

/** Fuel volume: litres, or US gallons in the US. UK fuel is sold, and a UK trip meter reads, in litres. */
export function volume(L: number, s: UnitSystem): number {
  return s === 'us' ? L / L_PER_US_GAL : L;
}
export function volumeUnit(s: UnitSystem): string {
  return s === 'us' ? 'gal' : 'L';
}

/**
 * Consumption: L/100 km, or miles per (US or imperial) gallon. mpg is the
 * inverse, so a figure that isn't positive and finite stays null.
 */
export function economy(L100: number | null, s: UnitSystem): number | null {
  if (L100 === null || !(L100 > 0) || !Number.isFinite(L100)) return null;
  if (s === 'metric') return L100;
  const gal = s === 'us' ? L_PER_US_GAL : L_PER_UK_GAL;
  return (100 / L100) * gal / KM_PER_MILE;      // km/L x L/gal / km/mi
}
export function economyUnit(s: UnitSystem): string {
  return s === 'metric' ? 'L/100 km' : s === 'us' ? 'mpg (US)' : 'mpg (UK)';
}

/** Temperature from deg C: deg F in the US; the UK reads deg C. */
export function temperature(C: number, s: UnitSystem): number {
  return s === 'us' ? C * 9 / 5 + 32 : C;
}
export function temperatureUnit(s: UnitSystem): string {
  return s === 'us' ? '°F' : '°C';
}

/** The live loop's waxed-fuel hint gives the CFPP as "N C" (live.py's string, a whole degree for every fuel the app has). */
const WAX = /gels below (-?\d+) C /;

/**
 * A hint from the live loop, in the driver's units. The loop's strings stay as they are
 * (the Python reference and its fixtures); only the page's copy changes. Others pass through.
 */
export function hintInUnits(hint: string, s: UnitSystem): string {
  return hint.replace(WAX, (_, c: string) => `gels below ${Math.round(temperature(Number(c), s))} ${temperatureUnit(s)} `);
}

/** A pressure in bar (FMEP on the driver pages): bar, or psi in the US and the UK. */
export function pressureBar(bar: number, s: UnitSystem): number {
  return s === 'metric' ? bar : bar * 1e5 / PA_PER_PSI;
}
export function pressureUnit(s: UnitSystem): string {
  return s === 'metric' ? 'bar' : 'psi';
}

/** The air's pressure, from Pa, as each country's weather reports it: kPa, inHg (US), hPa (UK). */
export function airPressure(Pa: number, s: UnitSystem): number {
  return s === 'metric' ? Pa / 1000 : s === 'us' ? Pa / PA_PER_INHG : Pa / 100;
}
export function airPressureUnit(s: UnitSystem): string {
  return s === 'metric' ? 'kPa' : s === 'us' ? 'inHg' : 'hPa';
}

function restoreUnits(): UnitSystem {
  try {
    const k = globalThis.localStorage?.getItem(UNITS_KEY);
    return UNIT_SYSTEMS.some(u => u.key === k) ? (k as UnitSystem) : 'metric';
  } catch { return 'metric'; }
}

@Injectable({ providedIn: 'root' })
export class Units {
  readonly system = signal<UnitSystem>(restoreUnits());

  set(key: string): void {
    if (!UNIT_SYSTEMS.some(u => u.key === key)) return;
    this.system.set(key as UnitSystem);
    try {
      if (key === 'metric') globalThis.localStorage?.removeItem(UNITS_KEY);
      else globalThis.localStorage?.setItem(UNITS_KEY, key);
    } catch { /* private mode: the choice lasts the page */ }
  }
}
