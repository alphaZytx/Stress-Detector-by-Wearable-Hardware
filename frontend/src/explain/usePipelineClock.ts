/**
 * Drives the Explain page from the public /demo/session asset.
 *
 * Why the demo asset and not the live WebSocket: this page is deliberately
 * reachable WITHOUT logging in (it is the "show someone the whole pipeline"
 * page), and /demo/session is the only unauthenticated data source the
 * backend exposes. The asset is not faked - build_demo_session.py runs real
 * samples through the real FeatureStreamer and the real deployed ensemble, so
 * every number animated here was produced by the actual pipeline.
 *
 * The clock replays that session at 1 sample/second of stream time, which is
 * the rate the hardware actually emits at. Features/predictions land every 5 s
 * exactly as they do live.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE } from "@/api/client";
import type { FeatureVector, Prediction, SensorSample } from "@/api/types";

export interface DemoEvent {
  t_s: number;
  phase: string;
  narration: string;
}

interface DemoSession {
  session_id: string;
  duration_s: number;
  events: DemoEvent[];
  samples: SensorSample[];
  features: (FeatureVector & { timestamp_ms: number })[];
  predictions: Prediction[];
}

export type LoadState = "loading" | "ready" | "error";

/** How many stream-seconds advance per real second at 1x. */
const BASE_RATE = 1;

/**
 * Where the replay starts, and where it loops back to.
 *
 * Not 0: the first 30 s of any session are the window filling up, so stages
 * 3-7 have genuinely nothing to show yet and a visitor would land on a page of
 * empty "waiting…" boxes. Starting just past the first emit means the whole
 * chain is populated immediately. The warm-up is still reachable by scrubbing
 * back to 0, which is where it's interesting rather than confusing.
 */
const START_S = 31;

export interface PipelineClock {
  state: LoadState;
  error: string | null;

  /** Current position in stream time (seconds since session start). */
  t: number;
  durationS: number;

  playing: boolean;
  speed: number;
  setPlaying: (p: boolean) => void;
  setSpeed: (s: number) => void;
  seek: (t: number) => void;
  restart: () => void;

  /** The 30 s of raw samples the current window covers. */
  windowSamples: SensorSample[];
  /** Every sample up to now - for the wide context trace. */
  samplesSoFar: SensorSample[];
  latestSample: SensorSample | null;

  /** Most recent completed feature emit at or before `t`. */
  features: (FeatureVector & { timestamp_ms: number }) | null;
  prediction: Prediction | null;
  /** Prediction history up to now, for the smoothing trace. */
  predictionsSoFar: Prediction[];

  /** Seconds until the next feature emit (the 5 s stride countdown). */
  nextEmitIn: number;
  /** 0..1 fill of the 30 s window during the initial warm-up. */
  warmup: number;

  phase: string;
  narration: string;
}

const WINDOW_S = 30;
const STRIDE_S = 5;

export function usePipelineClock(): PipelineClock {
  const [session, setSession] = useState<DemoSession | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);

  const [t, setT] = useState(START_S);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);

  // rAF loop state kept in refs so the effect never re-subscribes on tick.
  const rafRef = useRef<number | null>(null);
  const lastTsRef = useRef<number | null>(null);
  const playingRef = useRef(playing);
  const speedRef = useRef(speed);
  const durationRef = useRef(0);
  playingRef.current = playing;
  speedRef.current = speed;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/demo/session`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: DemoSession = await res.json();
        if (cancelled) return;
        setSession(data);
        durationRef.current = data.duration_s;
        setState("ready");
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof Error ? e.message : "Could not reach the service.",
        );
        setState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Single rAF loop. Advances stream time; wraps at the end so the page loops
  // forever without attention (it's a display piece as much as a tool).
  useEffect(() => {
    if (state !== "ready") return;

    const tick = (ts: number) => {
      const last = lastTsRef.current;
      lastTsRef.current = ts;
      if (last !== null && playingRef.current) {
        const dt = ((ts - last) / 1000) * BASE_RATE * speedRef.current;
        setT((prev) => {
          const next = prev + dt;
          // Loop back to START_S, not 0, so the replay never parks on the
          // empty warm-up stretch.
          return next >= durationRef.current ? START_S : next;
        });
      }
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      lastTsRef.current = null;
    };
  }, [state]);

  const seek = useCallback((next: number) => {
    setT(Math.max(0, Math.min(next, durationRef.current)));
  }, []);

  const restart = useCallback(() => {
    // Back to the start of the *session* (0), not START_S - if someone
    // deliberately hits restart they're asking to watch the warm-up too.
    setT(0);
    setPlaying(true);
  }, []);

  const derived = useMemo(() => {
    if (!session) {
      return {
        windowSamples: [] as SensorSample[],
        samplesSoFar: [] as SensorSample[],
        latestSample: null as SensorSample | null,
        features: null,
        prediction: null,
        predictionsSoFar: [] as Prediction[],
        nextEmitIn: STRIDE_S,
        warmup: 0,
        phase: "",
        narration: "",
      };
    }

    const nowMs = t * 1000;

    const samplesSoFar = session.samples.filter(
      (s) => s.timestamp_ms <= nowMs,
    );
    const windowSamples = samplesSoFar.filter(
      (s) => s.timestamp_ms > nowMs - WINDOW_S * 1000,
    );
    const latestSample = samplesSoFar[samplesSoFar.length - 1] ?? null;

    const featuresSoFar = session.features.filter(
      (f) => f.timestamp_ms <= nowMs,
    );
    const features = featuresSoFar[featuresSoFar.length - 1] ?? null;

    const predictionsSoFar = session.predictions.filter(
      (p) => p.timestamp_ms <= nowMs,
    );
    const prediction = predictionsSoFar[predictionsSoFar.length - 1] ?? null;

    // Next emit: strides land on multiples of 5 s once the 30 s window fills.
    const nextEmitIn =
      t < WINDOW_S ? WINDOW_S - t : STRIDE_S - ((t - WINDOW_S) % STRIDE_S);

    const warmup = Math.min(1, t / WINDOW_S);

    // Latest event at or before now.
    let phase = "";
    let narration = "";
    for (const ev of session.events) {
      if (ev.t_s <= t) {
        phase = ev.phase;
        narration = ev.narration;
      }
    }

    return {
      windowSamples,
      samplesSoFar,
      latestSample,
      features,
      prediction,
      predictionsSoFar,
      nextEmitIn,
      warmup,
      phase,
      narration,
    };
  }, [session, t]);

  return {
    state,
    error,
    t,
    durationS: session?.duration_s ?? 0,
    playing,
    speed,
    setPlaying,
    setSpeed,
    seek,
    restart,
    ...derived,
  };
}
