/// <reference lib="webworker" />
// P06 tier 2 (PROPOSAL-P06-goals): the par a goal is set against -- a ghost lap of the
// driver's route, at a constant throttle with the automatic, from the start the driver
// gets (make-engine.ts), at their place's air and fuel. Its own thread, so the 60 Hz drive
// worker never waits for it; @dieselsim/physics's parRun is held to live.par_run.
import { parRun } from '@dieselsim/physics';
import { makeEngine } from './make-engine';
import type { FromParWorker, ToParWorker } from './protocol';

addEventListener('message', (ev: MessageEvent<ToParWorker>) => {
  const m = ev.data;
  try {
    const t0 = performance.now();
    const result = parRun(makeEngine({ ...m, trans: 'tc' }));
    postMessage({ type: 'par', result, ms: performance.now() - t0 } satisfies FromParWorker);
  } catch (e) {
    postMessage({ type: 'error', message: e instanceof Error ? e.message : String(e) } satisfies FromParWorker);
  }
});
