/// <reference lib="webworker" />
// The browser adapter for the solver worker. The loop itself is
// @dieselsim/solver's serveSolver(), the same code the Node tests run; this
// file only says how to reach the network in a browser.
//
// Config arrives through the Worker's `name` (see solver.service.ts) so that
// asset URLs resolve against the page's real base address. GitHub Pages
// serves this project from a subfolder, and guessing from the worker's own
// URL would break if the bundler ever moved the worker file.
import type { PyodideInterface } from 'pyodide';
import { serveSolver } from '@dieselsim/solver/worker';

interface WorkerConfig { assetBase: string; bundle: string; }
const cfg = JSON.parse(self.name) as WorkerConfig;
const asset = (p: string) => new URL(p, cfg.assetBase).href;

serveSolver(
  {
    post: (m, t) => postMessage(m, { transfer: t ?? [] }),
    listen: h => addEventListener('message', e => h((e as MessageEvent).data)),
  },
  {
    async loadPyodide(): Promise<PyodideInterface> {
      // Loaded from our own origin at runtime, deliberately not bundled:
      // Pyodide loads its WebAssembly relative to indexURL (ADR-010).
      const mod = await import(/* @vite-ignore */ asset('pyodide/pyodide.mjs'));
      return mod.loadPyodide({
        indexURL: asset('pyodide/'),
        // Route Python's output explicitly, or it can be lost (ADR-010).
        stdout: (s: string) => console.log('[py]', s),
        stderr: (s: string) => console.warn('[py]', s),
      });
    },
    async loadSources() {
      const r = await fetch(asset(`physics/${cfg.bundle}`));
      if (!r.ok) throw new Error(`physics bundle ${cfg.bundle}: HTTP ${r.status}`);
      return (await r.json() as { files: Record<string, string> }).files;
    },
  },
);
