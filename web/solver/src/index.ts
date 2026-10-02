// Public API for the UI. The worker side is a separate entry
// (worker-main.ts) so the main-thread bundle never pulls in worker code.
export * from "./solver-port.js";
export * from "./protocol.js";
export { WorkerSolver } from "./worker-client.js";
export { buildLiveGrid, IndexedDbPieceStore, MemoryPieceStore, type LiveBuildOptions, type LiveBuildProgress, type LiveCaller, type PieceStore } from "./live-grid-build.js";
export { CachedSolver, type CacheEvent } from "./cached-solver.js";
export { IndexedDbGridCache, MemoryGridCache, type GridCache } from "./grid-cache.js";
export { gridCacheKey, liveBuildKey, sourceHash, canonicalJson } from "./cache-key.js";
