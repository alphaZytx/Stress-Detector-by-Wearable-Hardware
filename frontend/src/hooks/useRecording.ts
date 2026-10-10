/**
 * Recording session lifecycle for the Live view. Wraps /session/start + /stop and
 * exposes an elapsed timer. Recording is global to the backend (one active session
 * at a time), so this state is held in a small Zustand store rather than local
 * component state, surviving navigation away from Live.
 */

import { useEffect, useState } from "react";
import { create } from "zustand";
import { sessionApi } from "@/api/session";
import { useSettingsStore } from "@/stores/settingsStore";

interface RecordingState {
  sessionId: string | null;
  startedAtMs: number | null;
  busy: boolean;
  setBusy: (b: boolean) => void;
  setActive: (id: string | null) => void;
}

const useRecordingStore = create<RecordingState>((set) => ({
  sessionId: null,
  startedAtMs: null,
  busy: false,
  setBusy: (busy) => set({ busy }),
  setActive: (id) =>
    set({ sessionId: id, startedAtMs: id ? Date.now() : null }),
}));

export function useRecording() {
  const { sessionId, startedAtMs, busy, setBusy, setActive } =
    useRecordingStore();
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    if (startedAtMs == null) {
      setElapsedMs(0);
      return;
    }
    const tick = () => setElapsedMs(Date.now() - startedAtMs);
    tick();
    const id = window.setInterval(tick, 500);
    return () => window.clearInterval(id);
  }, [startedAtMs]);

  const start = async (label?: string, notes?: string) => {
    // Per-session opt-in to calibration comes from settings (toggle in Settings).
    const useCalibration = useSettingsStore.getState().useCalibration;
    setBusy(true);
    try {
      const { session_id } = await sessionApi.start(label, notes, useCalibration);
      setActive(session_id);
      return session_id;
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      await sessionApi.stop();
      setActive(null);
    } finally {
      setBusy(false);
    }
  };

  return {
    isRecording: sessionId != null,
    sessionId,
    elapsedMs,
    busy,
    start,
    stop,
  };
}
