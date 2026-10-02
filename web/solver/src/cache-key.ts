/**
 * Grid cache keys. Addresses REVIEW-001 M-2, which found the key undefined and
 * warned that Python's float formatting is not stable across versions.
 *
 * The key is computed here, in TypeScript, where number formatting is fixed by
 * the language spec (ECMA-262 Number::toString, shortest round-trip) and
 * identical in every engine. Objects are serialised with sorted keys, so the
 * same engine gives the same key however the request was written.
 */
import type { EngineRef } from "./solver-port.js";

/** Bump when the stored Grid shape changes, to orphan old entries. */
// 2: cells carry p_cyl, cylinder 1's pressure trace (ADR-011), and
//    perf.p_rail; grids cached in format 1 lack them and must rebuild.
export const GRID_FORMAT = 2;

export function canonicalJson(value: unknown): string {
  if (value === null) return "null";
  switch (typeof value) {
    case "boolean":
    case "string":
      return JSON.stringify(value);
    case "number":
      if (!Number.isFinite(value)) throw new RangeError(`non-finite number in cache key: ${value}`);
      return Object.is(value, -0) ? "0" : JSON.stringify(value);
    case "object": {
      if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
      const obj = value as Record<string, unknown>;
      const keys = Object.keys(obj).filter(k => obj[k] !== undefined).sort();
      return `{${keys.map(k => `${JSON.stringify(k)}:${canonicalJson(obj[k])}`).join(",")}}`;
    }
    default:
      throw new TypeError(`cannot put a ${typeof value} in a cache key`);
  }
}

async function sha256Hex(data: Uint8Array): Promise<string> {
  // WebCrypto exists only in secure contexts: https, or localhost. Served
  // over plain http on a LAN address it is undefined - say so, rather than
  // failing with "cannot read properties of undefined".
  if (!globalThis.crypto?.subtle) {
    throw new Error("WebCrypto unavailable: this page must be served over https or from localhost");
  }
  const digest = await crypto.subtle.digest("SHA-256", data as Uint8Array<ArrayBuffer>);
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, "0")).join("");
}

export interface GridKeyInput {
  /** fingerprint of the physics — see sourceHash() */
  solverVersion: string;
  engine: EngineRef;
  rpms: number[];
  loads: number[];
  n_cycles?: number;
}

/**
 * The key a drivable-grid build (ADR-014 step 3) files its finished pieces
 * under, so a reload resumes: the physics, the engine and the grid size.
 */
export function liveBuildKey(solverVersion: string, engine: EngineRef, size: [number, number]): Promise<string> {
  return sha256Hex(new TextEncoder().encode(canonicalJson({ live: 1, solver: solverVersion, engine, size })));
}

export function gridCacheKey(k: GridKeyInput): Promise<string> {
  return sha256Hex(new TextEncoder().encode(canonicalJson({
    format: GRID_FORMAT,
    solver: k.solverVersion,
    engine: k.engine,
    rpms: k.rpms,        // order matters: it is the grid's layout
    loads: k.loads,
    n_cycles: k.n_cycles ?? "default",
  })));
}

/**
 * The same fingerprint dieselsim/bridge.py's source_hash() computes: for each
 * .py file in sorted name order, name + NUL + raw bytes + NUL, SHA-256.
 *
 * Exists so the main thread (or a build step) can know the physics version
 * WITHOUT booting Pyodide — which is what lets a cached grid open instantly.
 */
export function sourceHash(files: Record<string, Uint8Array>): Promise<string> {
  const enc = new TextEncoder();
  const parts: Uint8Array[] = [];
  for (const name of Object.keys(files).filter(n => n.endsWith(".py")).sort()) {
    parts.push(enc.encode(name), new Uint8Array([0]), files[name]!, new Uint8Array([0]));
  }
  const all = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) { all.set(p, o); o += p.length; }
  return sha256Hex(all);
}
