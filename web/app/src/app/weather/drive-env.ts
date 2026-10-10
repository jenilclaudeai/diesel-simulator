import { computed, Injectable, signal } from '@angular/core';
import ENVS from './environments.json';
import FUELS_JSON from './fuels.json';

/**
 * The place Drive and Enjoy drive in (Phase 7 step 4, ADR-016 item 1). The five places come from a
 * file generated from dieselsim/environment.py (tools/environments_json.py), because these pages
 * must never fetch Pyodide. The choice is kept per browser, apart from the solving pages' own.
 */
export interface Place {
  key: string; name: string; place: string; altitude_m: number; T_C: number; rh_pct: number;
  fuel: string; p_amb: number; T_amb: number; cfpp_C: number | null;
}

/** Phase 7 step 6: a fuel grade a driver can fill up with (environment.FUELS). */
export interface Fuel { key: string; name: string; cfpp_C: number; sources: string }

export const FUELS = FUELS_JSON as unknown as readonly Fuel[];
/** The place's own fuel: what's sold there (the standard air's: the engine's own, no waxing). */
export const SOLD_HERE = 'local';
export const DRIVE_FUEL_KEY = 'dieselsim-drive-fuel';

/** The fuel's cold-filter plugging point [K] for the worker, or undefined: no waxing. */
export function cfppOf(placeKey: string, fuelKey: string): number | undefined {
  const f = FUELS.find(x => x.key === fuelKey);
  const c = f ? f.cfpp_C : PLACES.find(x => x.key === placeKey)?.cfpp_C;
  return c == null ? undefined : c + 273.15;
}

/** What the page says about the fuel at this place: '' when it's the place's own and safe. */
export function fuelLine(placeKey: string, fuelKey: string): string {
  const pl = PLACES.find(x => x.key === placeKey);
  const f = FUELS.find(x => x.key === fuelKey);
  if (!pl || !f) return '';
  const c = f.cfpp_C, t = pl.T_C;
  const at = `${f.name} (CFPP ${fmt0.format(c)} °C) at ${fmt0.format(t)} °C`;
  if (t >= c + 2) return `${at}: it flows.`;
  if (t <= c - 6) return `${at}: it gels, and the engine won't start. Real drivers carry the local grade.`;
  return `${at}: the filter is waxing, so the engine is short of fuel until it warms (if it starts).`;
}

export const PLACES = ENVS as unknown as readonly Place[];
export const STANDARD = 'standard';
export const DRIVE_ENV_KEY = 'dieselsim-drive-environment';

const fmt1 = new Intl.NumberFormat('en', { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt0 = new Intl.NumberFormat('en', { maximumFractionDigits: 0 });

/** The air the drive worker takes for a place, or undefined at the standard air. */
export function airOf(key: string): { p: number; T: number } | undefined {
  const pl = PLACES.find(x => x.key === key);
  return !pl || pl.key === STANDARD ? undefined : { p: pl.p_amb, T: pl.T_amb };
}

/**
 * What the page says about the air, from the place and the engine's weather state
 * (DashInfo.weather, DashInfo.weather_check_pct). '' at the standard air.
 */
export function weatherLine(key: string, state: 'standard' | 'table' | 'no table' | undefined,
                            checkPct: number | null | undefined): string {
  const pl = PLACES.find(x => x.key === key);
  if (!pl || pl.key === STANDARD) return '';
  const air = `${pl.place}: ${fmt1.format(pl.p_amb / 1000)} kPa, ${fmt1.format(pl.T_C)} °C.`;
  if (state === 'table') {
    const pct = checkPct != null ? ` (measured within ${fmt1.format(checkPct)}% of full-load torque at Leh)` : '';
    return `${air} Torque, fuel, boost and the exhaust follow this air through the engine's weather table${pct}. ` +
      'Friction and sound stay sea level\'s; the cooling and the cold start see the ambient.';
  }
  if (state === 'no table') {
    return `${air} This engine's grid has no weather table, so its torque, fuel and boost stay standard air's; ` +
      `only the cooling and the cold start see ${fmt0.format(pl.T_C)} °C.`;
  }
  return air;
}

function restore(): string {
  try {
    const k = globalThis.localStorage?.getItem(DRIVE_ENV_KEY);
    return k && PLACES.some(x => x.key === k) ? k : STANDARD;
  } catch { return STANDARD; }
}

function restoreFuel(): string {
  try {
    const k = globalThis.localStorage?.getItem(DRIVE_FUEL_KEY);
    return k && FUELS.some(x => x.key === k) ? k : SOLD_HERE;
  } catch { return SOLD_HERE; }
}

@Injectable({ providedIn: 'root' })
export class DriveEnv {
  readonly current = signal(restore());
  readonly air = computed(() => airOf(this.current()));
  /** Phase 7 step 6: the fuel in the tank, and its CFPP for the worker */
  readonly fuel = signal(restoreFuel());
  readonly cfpp = computed(() => cfppOf(this.current(), this.fuel()));

  setFuel(key: string): void {
    if (key !== SOLD_HERE && !FUELS.some(x => x.key === key)) return;
    this.fuel.set(key);
    try {
      if (key === SOLD_HERE) globalThis.localStorage?.removeItem(DRIVE_FUEL_KEY);
      else globalThis.localStorage?.setItem(DRIVE_FUEL_KEY, key);
    } catch { /* private mode: the choice lasts the page */ }
  }

  set(key: string): void {
    if (!PLACES.some(x => x.key === key)) return;
    this.current.set(key);
    try {
      if (key === STANDARD) globalThis.localStorage?.removeItem(DRIVE_ENV_KEY);
      else globalThis.localStorage?.setItem(DRIVE_ENV_KEY, key);
    } catch { /* private mode: the choice lasts the page */ }
  }
}
