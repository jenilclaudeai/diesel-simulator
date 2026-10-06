/**
 * Main-thread SolverPort. Talks to worker-main.ts over an Endpoint.
 *
 * In the browser the Endpoint wraps a Worker; in tests it wraps a Node
 * worker_threads Worker. Either way this is what the UI holds.
 */
import type { DurabilityFn, Endpoint, LiveFn, Reply, Request } from "./protocol.js";
import {
  SolverError,
  type CycleResult, type CompressorMap, type SpecDescription, type EngineInfo, type EngineRef, type Grid, type GridOptions, type GridRequest, type PointRequest,
  type PointResult, type RuntimeInfo, type SolverPort,
} from "./solver-port.js";

interface Pending {
  resolve(v: unknown): void;
  reject(e: SolverError): void;
  onProgress?: GridOptions["onProgress"];
}

export class WorkerSolver implements SolverPort {
  private nextId = 1;
  private readonly pending = new Map<number, Pending>();
  private readyPromise: Promise<RuntimeInfo> | undefined;
  private disposed = false;

  constructor(private readonly ep: Endpoint) {
    ep.listen(raw => this.onReply(raw as Reply));
  }

  ready(): Promise<RuntimeInfo> {
    return (this.readyPromise ??= this.call<RuntimeInfo>({ type: "init" }));
  }

  async solvePoint(req: PointRequest): Promise<PointResult> {
    await this.ready();
    return this.call<PointResult>({ type: "solvePoint", req });
  }

  async solveCycle(req: PointRequest): Promise<CycleResult> {
    await this.ready();
    return this.call<CycleResult>({ type: "solveCycle", req });
  }

  async compressorMap(engine: EngineRef): Promise<CompressorMap> {
    await this.ready();
    return this.call<CompressorMap>({ type: "compressorMap", engine });
  }

  async describeSpec(engine: EngineRef): Promise<SpecDescription> {
    await this.ready();
    return this.call<SpecDescription>({ type: "describeSpec", engine });
  }

  async describeEngine(engine: EngineRef): Promise<EngineInfo> {
    await this.ready();
    return this.call<EngineInfo>({ type: "describeEngine", engine });
  }

  /** A durability run's step (Phase 6): durability_start / _next / _stop, JSON in and out. */
  async durabilityCall(fn: DurabilityFn, arg: string): Promise<string> {
    await this.ready();
    return this.call<string>({ type: "durabilityCall", fn, arg });
  }

  /** One drivable-grid piece (ADR-014 step 3): a bridge function, JSON in and out. */
  async liveCall(fn: LiveFn, arg: string): Promise<string> {
    await this.ready();
    return this.call<string>({ type: "liveCall", fn, arg });
  }

  async buildGrid(req: GridRequest, opts: GridOptions = {}): Promise<Grid> {
    if (opts.signal?.aborted) throw new SolverError("cancelled", "aborted before start");
    await this.ready();
    const id = this.nextId;             // the id call() is about to use
    const onAbort = () => this.ep.post({ type: "cancel", id } satisfies Request);
    opts.signal?.addEventListener("abort", onAbort, { once: true });
    try {
      return await this.call<Grid>({ type: "buildGrid", req }, opts.onProgress);
    } finally {
      opts.signal?.removeEventListener("abort", onAbort);
    }
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    for (const p of this.pending.values()) p.reject(new SolverError("cancelled", "solver disposed"));
    this.pending.clear();
    this.ep.close?.();
  }

  private call<T>(body: Omit<Extract<Request, { type: "init" }>, "id"> |
                        Omit<Extract<Request, { type: "solvePoint" }>, "id"> |
                        Omit<Extract<Request, { type: "solveCycle" }>, "id"> |
                        Omit<Extract<Request, { type: "describeEngine" }>, "id"> |
                        Omit<Extract<Request, { type: "describeSpec" }>, "id"> |
                        Omit<Extract<Request, { type: "compressorMap" }>, "id"> |
                        Omit<Extract<Request, { type: "liveCall" }>, "id"> |
                        Omit<Extract<Request, { type: "durabilityCall" }>, "id"> |
                        Omit<Extract<Request, { type: "buildGrid" }>, "id">,
                  onProgress?: GridOptions["onProgress"]): Promise<T> {
    if (this.disposed) return Promise.reject(new SolverError("cancelled", "solver disposed"));
    const id = this.nextId++;
    return new Promise<T>((resolve, reject) => {
      const entry: Pending = { resolve: v => resolve(v as T), reject };
      if (onProgress) entry.onProgress = onProgress;
      this.pending.set(id, entry);
      this.ep.post({ ...body, id } as Request);
    });
  }

  private onReply(msg: Reply): void {
    const p = this.pending.get(msg.id);
    if (!p) return;                                   // late reply after dispose
    if (msg.type === "progress") { p.onProgress?.(msg.progress); return; }
    this.pending.delete(msg.id);
    if (msg.type === "result") p.resolve(msg.value);
    else p.reject(new SolverError(msg.error.kind, msg.error.message, msg.error.traceback));
  }
}
