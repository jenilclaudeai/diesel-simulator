// An imported grid file (ADR-014): a custom engine's converged grid, built
// natively by `python3 tools/build_live_grids.py --engine my.json` (or, later,
// in the browser). Checked here before anything trusts it.
import { VEHICLE_KEYS } from '@dieselsim/physics';
import type { GridFile } from './protocol';

/** The key the engine selects use for the imported grid. */
export const IMPORTED = '__imported';

const REQUIRED = ['preset', 'name', 'grid_hash', 'rpms', 'loads', 'perf', 'perf_cold',
  'p_cyl_f32', 'p_cyl_cold_f32', 'src_f32', 'src_cold_f32', 'src_meta', 'src_meta_cold',
  'spec', 'engine_view'] as const;

/** Why a parsed file is not a drivable grid, or null if it is. */
export function gridFileProblem(x: unknown): string | null {
  if (typeof x !== 'object' || x === null || Array.isArray(x)) return 'not a grid file (expected a JSON object)';
  const o = x as Record<string, unknown>;
  const missing = REQUIRED.filter(k => !(k in o));
  if (missing.length) return `not a grid file: missing ${missing.join(', ')}`;
  if (!o['converged']) return 'this grid is not converged: build it with tools/build_live_grids.py';
  const rpms = o['rpms'], loads = o['loads'], perf = o['perf'];
  if (!Array.isArray(rpms) || !Array.isArray(loads) || !Array.isArray(perf) || perf.length !== rpms.length
      || perf.some(r => !Array.isArray(r) || r.length !== loads.length))
    return 'not a grid file: its perf table does not match its rpm and load axes';
  // a custom engine must name its vehicle, or it would silently get the fallback tractor
  if (o['custom'] && !(VEHICLE_KEYS as readonly unknown[]).includes(o['vehicle']))
    return `its "vehicle" must be one of ${VEHICLE_KEYS.join(', ')} (got ${JSON.stringify(o['vehicle'] ?? null)})`;
  return null;
}

/** Read and check a grid file the user picked. Throws with the reason. */
export async function readGridFile(file: File): Promise<GridFile> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(await file.text());
  } catch {
    throw new Error(`${file.name} is not JSON`);
  }
  const problem = gridFileProblem(parsed);
  if (problem) throw new Error(`${file.name}: ${problem}`);
  return parsed as GridFile;
}
