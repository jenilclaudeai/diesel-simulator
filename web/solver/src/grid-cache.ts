/**
 * Grid storage. Addresses REVIEW-001 M-3: a byte budget, least-recently-used
 * eviction, and defined behaviour when the browser's storage quota runs out.
 *
 * Two rules:
 *  1. Failing to STORE a grid never fails the BUILD. The caller still gets
 *     its grid; `put` reports what happened instead of throwing. Losing
 *     minutes of solving to a full disk would be the worst outcome.
 *  2. Callers never share an object with the cache. IndexedDB copies by
 *     nature; the memory cache clones explicitly — the same aliasing bug
 *     builder.register had in Python.
 */
import type { Grid } from "./solver-port.js";

export const DEFAULT_BUDGET_BYTES = 50 * 1024 * 1024;   // ~30 default grids

export interface PutResult {
  stored: boolean;
  evicted: string[];
  reason?: "larger-than-budget" | "quota" | "error";
  detail?: string;
}

export interface CacheUsage { entries: number; bytes: number; budget: number; }

export interface GridCache {
  get(key: string): Promise<Grid | undefined>;
  put(key: string, grid: Grid): Promise<PutResult>;
  delete(key: string): Promise<void>;
  clear(): Promise<void>;
  usage(): Promise<CacheUsage>;
}

interface Entry { key: string; grid: Grid; bytes: number; lastUsed: number; }

/** Approximate stored size: the float32 sources dominate everything else. */
export function gridBytes(g: Grid): number {
  let n = 64 * g.cells.length;
  for (const c of g.cells) {
    for (const a of Object.values(c.src)) n += a.byteLength;
    n += 24 * (Object.keys(c.perf).length + Object.keys(c.meta).length);
  }
  return n;
}

/** Strictly increasing, so two operations in one millisecond still order. */
function monotonicClock(): () => number {
  let last = 0;
  return () => (last = Math.max(Date.now(), last + 1));
}

// ------------------------------------------------------------------ memory

export class MemoryGridCache implements GridCache {
  private readonly m = new Map<string, Entry>();
  constructor(readonly budget = DEFAULT_BUDGET_BYTES, private readonly now = monotonicClock()) {}

  async get(key: string) {
    const e = this.m.get(key);
    if (!e) return undefined;
    e.lastUsed = this.now();
    return structuredClone(e.grid);
  }

  async put(key: string, grid: Grid): Promise<PutResult> {
    const bytes = gridBytes(grid);
    if (bytes > this.budget) return { stored: false, evicted: [], reason: "larger-than-budget" };
    this.m.delete(key);
    const evicted: string[] = [];
    while (this.used() + bytes > this.budget) {
      const oldest = [...this.m.values()].sort((a, b) => a.lastUsed - b.lastUsed)[0]!;
      this.m.delete(oldest.key);
      evicted.push(oldest.key);
    }
    this.m.set(key, { key, grid: structuredClone(grid), bytes, lastUsed: this.now() });
    return { stored: true, evicted };
  }

  async delete(key: string) { this.m.delete(key); }
  async clear() { this.m.clear(); }
  async usage() { return { entries: this.m.size, bytes: this.used(), budget: this.budget }; }
  private used() { let n = 0; for (const e of this.m.values()) n += e.bytes; return n; }
}

// --------------------------------------------------------------- indexeddb

const STORE = "grids";

function req<T>(r: IDBRequest<T>): Promise<T> {
  return new Promise((ok, fail) => { r.onsuccess = () => ok(r.result); r.onerror = () => fail(r.error); });
}
function done(tx: IDBTransaction): Promise<void> {
  return new Promise((ok, fail) => {
    tx.oncomplete = () => ok();
    tx.onerror = () => fail(tx.error);
    tx.onabort = () => fail(tx.error ?? new Error("transaction aborted"));
  });
}

export class IndexedDbGridCache implements GridCache {
  private dbp: Promise<IDBDatabase> | undefined;

  constructor(
    readonly dbName = "dieselsim-grids",
    readonly budget = DEFAULT_BUDGET_BYTES,
    private readonly idb: IDBFactory = globalThis.indexedDB,
    private readonly now = monotonicClock(),
  ) {}

  private db(): Promise<IDBDatabase> {
    return (this.dbp ??= new Promise((ok, fail) => {
      const open = this.idb.open(this.dbName, 1);
      open.onupgradeneeded = () => {
        const s = open.result.createObjectStore(STORE, { keyPath: "key" });
        s.createIndex("lastUsed", "lastUsed");
      };
      open.onsuccess = () => ok(open.result);
      open.onerror = () => fail(open.error);
    }));
  }

  async get(key: string) {
    const tx = (await this.db()).transaction(STORE, "readwrite");
    const store = tx.objectStore(STORE);
    const e = await req(store.get(key)) as Entry | undefined;
    if (e) { e.lastUsed = this.now(); store.put(e); }
    await done(tx);
    return e?.grid;
  }

  async put(key: string, grid: Grid): Promise<PutResult> {
    const bytes = gridBytes(grid);
    if (bytes > this.budget) return { stored: false, evicted: [], reason: "larger-than-budget" };
    const evicted = await this.evictUntil(this.budget - bytes, key);
    const entry: Entry = { key, grid, bytes, lastUsed: this.now() };
    try {
      await this.rawPut(entry);
      return { stored: true, evicted };
    } catch (e) {
      if ((e as DOMException)?.name !== "QuotaExceededError") {
        return { stored: false, evicted, reason: "error", detail: String(e) };
      }
      // The browser's own quota is tighter than our budget. Free one more
      // entry and try once more; if that fails, give up quietly.
      const more = await this.evictOldest(key);
      if (more) evicted.push(more);
      try {
        await this.rawPut(entry);
        return { stored: true, evicted };
      } catch (e2) {
        return { stored: false, evicted, reason: "quota", detail: String(e2) };
      }
    }
  }

  /** Separate so tests can simulate the browser refusing a write. */
  protected async rawPut(entry: Entry): Promise<void> {
    const tx = (await this.db()).transaction(STORE, "readwrite");
    tx.objectStore(STORE).put(entry);
    await done(tx);
  }

  private async all(): Promise<Entry[]> {
    const tx = (await this.db()).transaction(STORE, "readonly");
    const rows = await req(tx.objectStore(STORE).getAll()) as Entry[];
    await done(tx);
    return rows;
  }

  private async evictUntil(target: number, keep: string): Promise<string[]> {
    const rows = (await this.all()).filter(r => r.key !== keep).sort((a, b) => a.lastUsed - b.lastUsed);
    let used = rows.reduce((n, r) => n + r.bytes, 0);
    const gone: string[] = [];
    for (const r of rows) {
      if (used <= target) break;
      await this.delete(r.key);
      used -= r.bytes;
      gone.push(r.key);
    }
    return gone;
  }

  private async evictOldest(keep: string): Promise<string | undefined> {
    const oldest = (await this.all()).filter(r => r.key !== keep).sort((a, b) => a.lastUsed - b.lastUsed)[0];
    if (oldest) await this.delete(oldest.key);
    return oldest?.key;
  }

  async delete(key: string) {
    const tx = (await this.db()).transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete(key);
    await done(tx);
  }

  async clear() {
    const tx = (await this.db()).transaction(STORE, "readwrite");
    tx.objectStore(STORE).clear();
    await done(tx);
  }

  async usage() {
    const rows = await this.all();
    return { entries: rows.length, bytes: rows.reduce((n, r) => n + r.bytes, 0), budget: this.budget };
  }

  close() { void this.dbp?.then(d => d.close()); this.dbp = undefined; }
}
