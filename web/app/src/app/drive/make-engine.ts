// The LiveEngine a drive starts from, shared by the drive worker and the par worker
// (P06 tier 2), so a par is set from exactly the start the driver gets.
import { Adr011Grid, LiveEngine, routeFrom, type Transmission } from '@dieselsim/physics';
import type { GridFile } from './protocol';

export interface EngineStart {
  grid: GridFile;
  trans: Transmission;
  air?: { p: number; T: number };   // Phase 7 step 4: the place's air; absent is standard air
  cfpp?: number;                    // Phase 7 step 6: the fuel picked [K]
  route?: string;                   // P06: 'pass', 'city', 'desert', 'random:<seed>'
}

export function makeEngine(m: EngineStart): LiveEngine {
  // the place's air is set before the engine is made (its coolant starts at the ambient);
  // the grid carries its weather table, if it has one
  const spec = structuredClone(m.grid.spec);
  if (m.air) { spec.thermal.ambient_p = m.air.p; spec.thermal.ambient_T = m.air.T; }
  const grid = new Adr011Grid(spec, m.grid);
  // a custom engine names its vehicle (ADR-014); a roster grid's preset picks its own
  const live = new LiveEngine(grid, m.grid.vehicle ?? m.grid.preset, m.trans, m.grid.engine_view);
  if (m.cfpp !== undefined) live.fuel_cfpp = m.cfpp;
  if (m.route) live.setRoute(routeFrom(m.route));
  return live;
}
