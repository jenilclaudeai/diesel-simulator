// "My engines" (ADR-014 step 3): custom engines with a drivable grid, kept in
// this browser so /drive and /enjoy can offer them. Listing reads only the
// small records; a grid's text (~5 MB) is fetched when it is driven.
import { VEHICLE_KEYS, vehicleFor } from '@dieselsim/physics';
import type { GridFile } from '../drive/protocol';
import type { CustomEngine } from './custom-engine';

/** A saved engine: a custom one (ADR-014, `engine`) or an edited preset (the spec editor, Phase 6, `edits`). */
export interface MyEngine {
  key: string; name: string; vehicle: string; savedAt: number;
  engine?: CustomEngine;
  edits?: { preset: string; overrides: Record<string, number | boolean> };
}

/**
 * The vehicle key (live.VEHICLE_KEYS, which a grid file must name) that
 * drives a preset: the one whose vehicle is the preset's own, else the
 * tractor, as the live loop itself falls back.
 */
export function vehicleKeyFor(preset: string): string {
  const own = vehicleFor(preset).name;
  return VEHICLE_KEYS.find(k => vehicleFor(k).name === own) ?? 'tractor';
}

/**
 * "Your engines"' record for an edited preset: keyed by the base and the
 * edits (the same edits, the same key, so a rebuild resumes and replaces),
 * named for the reader, in the base preset's vehicle.
 */
export function editedEngine(preset: string, presetName: string, overrides: Record<string, number | boolean>):
    Omit<MyEngine, 'savedAt'> {
  const sorted = Object.keys(overrides).sort().map(k => [k, overrides[k]]);
  let h = 0x811c9dc5;                                       // FNV-1a, 32 bit
  for (const c of JSON.stringify(sorted)) h = Math.imul(h ^ c.charCodeAt(0), 0x01000193) >>> 0;
  const n = sorted.length;
  return {
    key: `${preset}-edited-${h.toString(16).padStart(8, '0')}`,
    name: `${presetName}, edited (${n} ${n === 1 ? 'field' : 'fields'})`,
    vehicle: vehicleKeyFor(preset),
    edits: { preset, overrides: { ...overrides } },
  };
}

/** The prefix /drive's and /enjoy's engine selects use for a saved engine. */
export const MY = 'my:';

export interface EngineLibrary {
  list(): Promise<MyEngine[]>;
  grid(key: string): Promise<GridFile | undefined>;
  save(e: MyEngine, gridText: string): Promise<void>;
  remove(key: string): Promise<void>;
}

export class MemoryEngineLibrary implements EngineLibrary {
  private readonly engines = new Map<string, MyEngine>();
  private readonly grids = new Map<string, string>();
  async list() { return [...this.engines.values()].sort((a, b) => b.savedAt - a.savedAt); }
  async grid(key: string) { const t = this.grids.get(key); return t ? (JSON.parse(t) as GridFile) : undefined; }
  async save(e: MyEngine, text: string) { this.engines.set(e.key, e); this.grids.set(e.key, text); }
  async remove(key: string) { this.engines.delete(key); this.grids.delete(key); }
}

export class IndexedDbEngineLibrary implements EngineLibrary {
  private dbp: Promise<IDBDatabase> | undefined;
  constructor(private readonly dbName = 'dieselsim-my-engines') {}
  private db(): Promise<IDBDatabase> {
    return (this.dbp ??= new Promise((ok, fail) => {
      const open = indexedDB.open(this.dbName, 1);
      open.onupgradeneeded = () => {
        open.result.createObjectStore('engines', { keyPath: 'key' });
        open.result.createObjectStore('grids');
      };
      open.onsuccess = () => ok(open.result);
      open.onerror = () => fail(open.error);
    }));
  }
  private async run<T>(stores: string[], mode: IDBTransactionMode, f: (t: IDBTransaction) => IDBRequest<T> | void): Promise<T | undefined> {
    const t = (await this.db()).transaction(stores, mode);
    const r = f(t);
    return new Promise((ok, fail) => {
      t.oncomplete = () => ok(r ? r.result : undefined);
      t.onerror = () => fail(t.error);
      t.onabort = () => fail(t.error);
    });
  }
  async list() {
    const all = (await this.run(['engines'], 'readonly', t => t.objectStore('engines').getAll())) as MyEngine[] | undefined;
    return (all ?? []).sort((a, b) => b.savedAt - a.savedAt);
  }
  async grid(key: string) {
    const t = (await this.run(['grids'], 'readonly', tx => tx.objectStore('grids').get(key))) as string | undefined;
    return t ? (JSON.parse(t) as GridFile) : undefined;
  }
  async save(e: MyEngine, text: string) {
    await this.run(['engines', 'grids'], 'readwrite', t => { t.objectStore('grids').put(text, e.key); t.objectStore('engines').put(e); });
  }
  async remove(key: string) {
    await this.run(['engines', 'grids'], 'readwrite', t => { t.objectStore('grids').delete(key); t.objectStore('engines').delete(key); });
  }
}

let shared: EngineLibrary | undefined;
/** The page's library: IndexedDB where there is one, else this session only. */
export function engineLibrary(): EngineLibrary {
  return (shared ??= globalThis.indexedDB ? new IndexedDbEngineLibrary() : new MemoryEngineLibrary());
}
