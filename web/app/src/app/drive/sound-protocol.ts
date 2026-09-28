// Messages for the engine sound (Phase 4): page -> worklet (node.port),
// loop -> worklet (a MessageChannel handed to both), worklet -> page.

/** What the 60 Hz loop sends the synth every frame. */
export interface LoopSound {
  rpm: number; load: number; T: number;       // the operating point the sources are blended at
  live: Record<string, number>;               // LiveEngine.sound_inputs()
  running: boolean;
}

export type ToWorklet =
  | { type: 'grid'; spec: unknown; grid: unknown; mic: string }
  | { type: 'loop'; port: MessagePort }
  | { type: 'mic'; mic: string }
  | { type: 'volume'; volume: number }
  | { type: 'capture'; seconds: number }
  | { type: 'reset' };                          // the loop stopped: fall silent

export type FromWorklet =
  | { type: 'level'; rms: number; peak: number; quanta: number }
  | { type: 'capture'; samples: Float32Array; rate: number }
  | { type: 'error'; message: string };
