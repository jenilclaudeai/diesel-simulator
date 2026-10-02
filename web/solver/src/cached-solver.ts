/**
 * A SolverPort that caches grids in front of another SolverPort.
 *
 * The property that matters: a cache HIT never touches the inner solver, so
 * reopening an engine you have already built does not boot Pyodide at all.
 * That is why the physics version is supplied by the app (from its build
 * manifest — see sourceHash()) rather than asked of the worker.
 *
 * On a MISS the inner solver has to load anyway, so the supplied version is
 * checked against what the worker actually loaded. A mismatch means a stale
 * bundle, and caching its output under the new version's key would poison the
 * cache — so it fails loudly instead.
 */
import { gridCacheKey } from "./cache-key.js";
import type { GridCache, PutResult } from "./grid-cache.js";
import {
  SolverError,
  type EngineInfo, type EngineRef, type Grid, type GridOptions, type GridRequest, type PointRequest,
  type PointResult, type RuntimeInfo, type SolverPort,
} from "./solver-port.js";

export interface CacheEvent {
  key: string;
  outcome: "hit" | "miss";
  /** present on a miss: whether the new grid was stored, and what was evicted */
  put?: PutResult;
}

export class CachedSolver implements SolverPort {
  /** Most recent cache outcome, e.g. for a "loaded from cache" badge. */
  lastCacheEvent: CacheEvent | undefined;
  private verified: Promise<RuntimeInfo> | undefined;

  constructor(
    private readonly inner: SolverPort,
    private readonly cache: GridCache,
    private readonly solverVersion: string,
  ) {}

  ready(): Promise<RuntimeInfo> {
    return (this.verified ??= this.inner.ready().then(info => {
      if (info.source_hash !== this.solverVersion) {
        throw new SolverError("protocol",
          `stale solver bundle: the app expects physics ${this.solverVersion.slice(0, 12)}… ` +
          `but the worker loaded ${info.source_hash.slice(0, 12)}…`);
      }
      return info;
    }));
  }

  solvePoint(req: PointRequest): Promise<PointResult> {
    return this.ready().then(() => this.inner.solvePoint(req));
  }

  describeEngine(engine: EngineRef): Promise<EngineInfo> {
    return this.ready().then(() => this.inner.describeEngine(engine));
  }

  async buildGrid(req: GridRequest, opts: GridOptions = {}): Promise<Grid> {
    const keyIn = { solverVersion: this.solverVersion, engine: req.engine, rpms: req.rpms, loads: req.loads };
    const key = await gridCacheKey(req.n_cycles === undefined ? keyIn : { ...keyIn, n_cycles: req.n_cycles });

    const hit = await this.cache.get(key);
    if (hit) {
      const total = req.rpms.length * req.loads.length;
      opts.onProgress?.({ done: total, total, rpm: req.rpms.at(-1) ?? 0, load: req.loads.at(-1) ?? 0 });
      this.lastCacheEvent = { key, outcome: "hit" };
      return hit;
    }

    await this.ready();                         // verifies the physics version
    const grid = await this.inner.buildGrid(req, opts);
    const put = await this.cache.put(key, grid);
    this.lastCacheEvent = { key, outcome: "miss", put };
    return grid;
  }

  dispose(): void { this.inner.dispose(); }
}
