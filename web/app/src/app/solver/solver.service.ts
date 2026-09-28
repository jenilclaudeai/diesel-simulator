import { Injectable, signal } from '@angular/core';
import {
  CachedSolver, IndexedDbGridCache, SolverError, WorkerSolver,
  type Endpoint, type Grid, type GridOptions, type GridRequest, type PointRequest, type PointResult,
  type RuntimeInfo, type SolverPort,
} from '@dieselsim/solver';
import { NUMPY_BUNDLED, PHYSICS_BUNDLE, PHYSICS_VERSION } from './physics-version';

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

  /** A full grid, cell by cell, served from the IndexedDB cache when it can be. */
  async buildGrid(req: GridRequest, opts?: GridOptions): Promise<Grid> {
    await this.start();
    return this.port!.buildGrid(req, opts);
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
      const worker = new Worker(new URL('./solver.worker', import.meta.url), {
        type: 'module',
        name: JSON.stringify({ assetBase: new URL('.', document.baseURI).href, bundle: PHYSICS_BUNDLE }),
      });
      const workerFailed = new Promise<never>((_, reject) =>
        worker.addEventListener('error', e =>
          reject(new SolverError('load', `the solver worker failed to start: ${e.message || 'script error'}`))));
      const ep: Endpoint = {
        post: (m, t) => worker.postMessage(m, t ?? []),
        listen: h => worker.addEventListener('message', e => h(e.data)),
        close: () => worker.terminate(),
      };
      const inner = new WorkerSolver(ep);
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
