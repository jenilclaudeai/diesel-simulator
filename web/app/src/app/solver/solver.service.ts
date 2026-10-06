import { Injectable, signal } from '@angular/core';
import {
  buildLiveGrid, CachedSolver, IndexedDbGridCache, IndexedDbPieceStore, liveBuildKey, SolverError, WorkerSolver,
  type CompressorMap, type CycleResult, type LiveBuildProgress, type SpecDescription,
  type EngineInfo, type EngineRef, type Endpoint, type Grid, type GridOptions, type GridRequest, type PointRequest, type PointResult,
  type RuntimeInfo, type SolverPort,
} from '@dieselsim/solver';
import { NUMPY_BUNDLED, PHYSICS_BUNDLE, PHYSICS_VERSION } from './physics-version';
import { poolSize } from './pool-size';

export type SolverStatus = 'idle' | 'loading' | 'ready' | 'error';

/**
 * The app's single handle on the physics (ADR-001, ADR-010). Components talk
 * to this; this talks to the SolverPort; nothing in the UI knows about Python.
 */
@Injectable({ providedIn: 'root' })
export class SolverService {
  readonly status = signal<SolverStatus>('idle');
  readonly info = signal<RuntimeInfo | undefined>(undefined);
  readonly error = signal<string | undefined>(undefined);

  /**
   * The grid cache keys with WebCrypto, which browsers only expose on https
   * or localhost. Elsewhere the app still works, just without the cache.
   */
  readonly cacheAvailable = !!globalThis.crypto?.subtle;

  private port: SolverPort | undefined;
  private starting: Promise<RuntimeInfo> | undefined;

  /** Load Python and numpy into the worker. Idempotent. */
  start(): Promise<RuntimeInfo> {
    return (this.starting ??= this.boot());
  }

  async solvePoint(req: PointRequest): Promise<PointResult> {
    await this.start();
    return this.port!.solvePoint(req);
  }

  /**
   * A durability run, stepped (Phase 6, ADR-015): start one, take its blocks a
   * few at a time (so the page shows progress and can stop between them), stop.
   * Rows are DieselEngine.durability_run's log rows; `health` is life consumed.
   */
  async durabilityStart(engine: EngineRef, hours: number, stepH: number): Promise<{ id: string; blocks_at_least: number }> {
    await this.start();
    return JSON.parse(await this.port!.durabilityCall('durability_start', JSON.stringify({ engine, hours, step_h: stepH }))) as
      { id: string; blocks_at_least: number };
  }

  async durabilityNext(id: string, n = 1): Promise<{ rows: Record<string, number>[]; done: boolean }> {
    await this.start();
    return JSON.parse(await this.port!.durabilityCall('durability_next', JSON.stringify({ id, n }))) as
      { rows: Record<string, number>[]; done: boolean };
  }

  async durabilityStop(id: string): Promise<void> {
    await this.start();
    await this.port!.durabilityCall('durability_stop', JSON.stringify({ id }));
  }

  /** The compressor's map, from the solver's own model, for the spec page's schematic (ADR-009). */
  async compressorMap(engine: EngineRef): Promise<CompressorMap> {
    await this.start();
    return this.port!.compressorMap(engine);
  }

  /** Every spec field of an engine, overrides applied: the spec editor's view (Phase 6, ADR-015). */
  async describeSpec(engine: EngineRef): Promise<SpecDescription> {
    await this.start();
    return this.port!.describeSpec(engine);
  }

  /** One point's crank-angle traces, for the cycle page (Phase 6, ADR-015). */
  async solveCycle(req: PointRequest): Promise<CycleResult> {
    await this.start();
    return this.port!.solveCycle(req);
  }

  /** Name, rpm range and requested numbers of an engine, without a solve (ADR-014). */
  async describeEngine(engine: EngineRef): Promise<EngineInfo> {
    await this.start();
    return this.port!.describeEngine(engine);
  }

  /** A full grid, cell by cell, served from the IndexedDB cache when it can be. */
  async buildGrid(req: GridRequest, opts?: GridOptions): Promise<Grid> {
    await this.start();
    return this.port!.buildGrid(req, opts);
  }

  /**
   * A custom engine's drivable grid, built in this browser by a pool of solver
   * workers (ADR-014 step 3): the grid file's JSON. Pieces are kept in
   * IndexedDB as they finish, so a closed tab or a cancel resumes; they are
   * dropped once the file is returned (the caller keeps the file).
   */
  async buildLiveGrid(engine: EngineRef, opts: { key: string; extra?: Record<string, unknown>; size?: [number, number];
                                                 workers?: number; onProgress?: (p: LiveBuildProgress) => void;
                                                 signal?: AbortSignal }): Promise<string> {
    const n = opts.workers ?? poolSize();
    const pool = Array.from({ length: n }, () => newWorkerSolver());
    // a pool worker that fails to start fails the build, as the main worker would
    const failed = Promise.race(pool.map(p => p.failed));
    const size = opts.size ?? [8, 6];
    const resumable = this.cacheAvailable && !!globalThis.indexedDB;
    const store = resumable ? new IndexedDbPieceStore() : undefined;
    const storeKey = resumable ? await liveBuildKey(PHYSICS_VERSION, engine, size) : undefined;
    try {
      const build = buildLiveGrid(engine, pool.map(p => p.solver), {
        key: opts.key, size, ...(opts.extra ? { extra: opts.extra } : {}), ...(store ? { store } : {}),
        ...(storeKey ? { storeKey } : {}), ...(opts.onProgress ? { onProgress: opts.onProgress } : {}),
        ...(opts.signal ? { signal: opts.signal } : {}),
      });
      const text = await Promise.race([build, failed]);
      if (store && storeKey) await store.clear(storeKey).catch(() => { /* space is reclaimed next time */ });
      return text;
    } finally {
      for (const p of pool) p.solver.dispose();
    }
  }

  private async boot(): Promise<RuntimeInfo> {
    this.status.set('loading');
    try {
      if (!NUMPY_BUNDLED) {
        // npm start could not download the numpy wheel (prepare-assets said
        // why); fail here with that, not with a 404 deep inside Pyodide
        // (a plain Error: describe() shows it as is -- "check your connection
        // and reload" would not help here)
        throw new Error('numpy is missing from this local build: npm start could not download it. ' +
          'The Drive page works without it. To fix it, follow the warning npm start printed ' +
          '(a proxy setting, or PYODIDE_WHEEL_DIR), then restart it.');
      }
      const { solver: inner, failed: workerFailed } = newWorkerSolver();
      this.port = this.cacheAvailable
        ? new CachedSolver(inner, new IndexedDbGridCache(), PHYSICS_VERSION)
        : inner;

      const info = await Promise.race([this.port.ready(), workerFailed]);
      // CachedSolver already refuses a stale bundle; check here too so the
      // no-cache path cannot quietly run physics the app was not built with.
      if (info.source_hash !== PHYSICS_VERSION) {
        throw new SolverError('protocol', 'this page and its physics bundle are from different builds; reload the page');
      }
      this.info.set(info);
      this.status.set('ready');
      return info;
    } catch (e) {
      this.error.set(describe(e));
      this.status.set('error');
      this.starting = undefined;          // allow a retry
      throw e;
    }
  }
}

/** A solver worker on this page's own physics bundle. */
function newWorkerSolver(): { solver: WorkerSolver; failed: Promise<never> } {
  const worker = new Worker(new URL('./solver.worker', import.meta.url), {
    type: 'module',
    name: JSON.stringify({ assetBase: new URL('.', document.baseURI).href, bundle: PHYSICS_BUNDLE }),
  });
  const failed = new Promise<never>((_, reject) =>
    worker.addEventListener('error', e =>
      reject(new SolverError('load', `the solver worker failed to start: ${e.message || 'script error'}`))));
  failed.catch(() => { /* observed by whoever races it */ });
  const ep: Endpoint = {
    post: (m, t) => worker.postMessage(m, t ?? []),
    listen: h => worker.addEventListener('message', e => h(e.data)),
    close: () => worker.terminate(),
  };
  return { solver: new WorkerSolver(ep), failed };
}

/** Errors say what happened and what to do; they never apologise. */
export function describe(e: unknown): string {
  if (e instanceof SolverError) {
    switch (e.kind) {
      case 'load': return `The solver could not load: ${e.message}. Check your connection and reload.`;
      case 'invalid-request': return `That request was rejected: ${e.message}.`;
      case 'non-finite': return `The physics produced an invalid number at this point: ${e.message}.`;
      case 'cancelled': return 'Stopped.';
      default: return e.message;
    }
  }
  return e instanceof Error ? e.message : String(e);
}
