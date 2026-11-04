/**
 * Live store - the single source of truth for the streaming pipeline state.
 * Fed by useLiveStream (WS or demo replay); read by every Live-view widget so
 * there is no prop drilling.
 *
 * Buffers:
 *   samples     - rolling, hard-capped (view slices by settings.bufferSeconds)
 *   features    - last 24 emits (~2 min at 5s stride)
 *   predictions - last 24 emits
 */

import { create } from "zustand";
import type { FeatureVector, Prediction, SensorSample } from "@/api/types";

export type ConnectionStatus =
  | "connecting"
  | "open"
  | "closed"
  | "reconnecting"
  | "demo";

const MAX_SAMPLES = 600; // 10 min at 1 Hz - view slices to bufferSeconds
const MAX_EMITS = 24; // ~2 min at 5s stride

interface LiveState {
  status: ConnectionStatus;
  lastMessageMs: number | null;
  samples: SensorSample[];
  features: FeatureVector[];
  predictions: Prediction[];
  latestSample: SensorSample | null;
  latestFeatures: FeatureVector | null;
  latestPrediction: Prediction | null;
  /** Stream time (not wall clock) of the most recent feature emit, if the
   * server sent one. ModelInputPanel uses it to run the stride countdown. */
  latestFeatureTs: number | null;
  /** Feature emits seen this connection - the "emit #N" counter. */
  emitCount: number;

  setStatus: (s: ConnectionStatus) => void;
  pushSample: (s: SensorSample) => void;
  pushFeatures: (f: FeatureVector, timestampMs?: number | null) => void;
  pushPrediction: (p: Prediction) => void;
  reset: () => void;
}

function capTail<T>(arr: T[], item: T, max: number): T[] {
  const next = arr.length >= max ? arr.slice(arr.length - max + 1) : arr.slice();
  next.push(item);
  return next;
}

export const useLiveStore = create<LiveState>((set) => ({
  status: "connecting",
  lastMessageMs: null,
  samples: [],
  features: [],
  predictions: [],
  latestSample: null,
  latestFeatures: null,
  latestPrediction: null,
  latestFeatureTs: null,
  emitCount: 0,

  setStatus: (status) => set({ status }),

  pushSample: (s) =>
    set((state) => ({
      samples: capTail(state.samples, s, MAX_SAMPLES),
      latestSample: s,
      // A prediction belongs to a valid contact window. Clear the displayed
      // value immediately on contact loss instead of leaving a stale percent.
      ...(s.finger_present === false
        ? {
            latestFeatures: null,
            latestPrediction: null,
            latestFeatureTs: null,
          }
        : {}),
      lastMessageMs: Date.now(),
    })),

  pushFeatures: (f, timestampMs) =>
    set((state) => ({
      features: capTail(state.features, f, MAX_EMITS),
      latestFeatures: f,
      latestFeatureTs: timestampMs ?? state.latestFeatureTs,
      emitCount: state.emitCount + 1,
      lastMessageMs: Date.now(),
    })),

  pushPrediction: (p) =>
    set((state) => ({
      predictions: capTail(state.predictions, p, MAX_EMITS),
      latestPrediction: p,
      lastMessageMs: Date.now(),
    })),

  reset: () =>
    set({
      samples: [],
      features: [],
      predictions: [],
      latestSample: null,
      latestFeatures: null,
      latestPrediction: null,
      latestFeatureTs: null,
      emitCount: 0,
      lastMessageMs: null,
    }),
}));
