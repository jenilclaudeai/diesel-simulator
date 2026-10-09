import { computed, Injectable, signal } from '@angular/core';
import ENVS from './environments.json';

/**
 * The place Drive and Enjoy drive in (Phase 7 step 4, ADR-016 item 1). The five places come from a
 * file generated from dieselsim/environment.py (tools/environments_json.py), because these pages
 * must never fetch Pyodide. The choice is kept per browser, apart from the solving pages' own.
 */
export interface Place {
  key: string; name: string; place: string; altitude_m: number; T_C: number; rh_pct: number;
  fuel: string; p_amb: number; T_amb: number;
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

@Injectable({ providedIn: 'root' })
export class DriveEnv {
  readonly current = signal(restore());
  readonly air = computed(() => airOf(this.current()));

  set(key: string): void {
    if (!PLACES.some(x => x.key === key)) return;
    this.current.set(key);
    try {
      if (key === STANDARD) globalThis.localStorage?.removeItem(DRIVE_ENV_KEY);
      else globalThis.localStorage?.setItem(DRIVE_ENV_KEY, key);
    } catch { /* private mode: the choice lasts the page */ }
  }
}
