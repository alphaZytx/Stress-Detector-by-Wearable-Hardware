/**
 * useLiveStream - the bridge between the data source and the liveStore.
 *
 * Two modes (transparent to consuming components, which only read liveStore):
 *   LIVE  - connects to ws://…/ws/stream?token=… and dispatches sample/features/
 *           prediction frames into the store.
 *   DEMO  - when settings.demoMode is on, skips the WS, fetches /demo/session
 *           once, and replays samples/features/predictions at 1 Hz wall-clock so
 *           the Live view looks identical without a wearable or even a login.
 *
 * Mount this ONCE high in the tree (AppShell) so the store is always fed.
 */

import { useCallback, useEffect, useRef } from "react";
import { WS_BASE } from "@/api/client";
import { demoApi } from "@/api/demo";
import type { DemoSession, WsMessage } from "@/api/types";
import { useAuth } from "@/hooks/useAuth";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useLiveStore } from "@/stores/liveStore";
import { useSettingsStore } from "@/stores/settingsStore";

export function useLiveStream() {
  const { token } = useAuth();
  const demoMode = useSettingsStore((s) => s.demoMode);

  const setStatus = useLiveStore((s) => s.setStatus);
  const pushSample = useLiveStore((s) => s.pushSample);
  const pushFeatures = useLiveStore((s) => s.pushFeatures);
  const pushPrediction = useLiveStore((s) => s.pushPrediction);
  const reset = useLiveStore((s) => s.reset);

  const handleMessage = useCallback(
    (raw: unknown) => {
      const msg = raw as WsMessage;
      switch (msg.type) {
        case "sample":
          pushSample(msg.data);
          break;
        case "features":
          // timestamp_ms is stream time for this emit - the panel's stride clock.
          pushFeatures(msg.data, msg.timestamp_ms);
          break;
        case "prediction":
          pushPrediction(msg.data);
          break;
      }
    },
    [pushSample, pushFeatures, pushPrediction],
  );

  // --- LIVE mode: WebSocket ---
  const wsUrl =
    !demoMode && token ? `${WS_BASE}/ws/stream?token=${encodeURIComponent(token)}` : null;

  useWebSocket({
    url: wsUrl,
    onMessage: handleMessage,
    onStatus: setStatus,
  });

  // --- DEMO mode: replay the canned session at 1 Hz ---
  const demoTimer = useRef<number | null>(null);
  useEffect(() => {
    if (!demoMode) return;

    let cancelled = false;
    reset();
    setStatus("demo");

    demoApi
      .session()
      .then((demo: DemoSession) => {
        if (cancelled) return;
        const featByTs = new Map(demo.features.map((f) => [f.timestamp_ms, f]));
        const predByTs = new Map(demo.predictions.map((p) => [p.timestamp_ms, p]));
        let i = 0;

        const tick = () => {
          if (cancelled) return;
          const sample = demo.samples[i];
          if (!sample) {
            i = 0; // loop the demo
            return;
          }
          pushSample(sample);
          const f = featByTs.get(sample.timestamp_ms);
          if (f) pushFeatures(f, f.timestamp_ms);
          const p = predByTs.get(sample.timestamp_ms);
          if (p) pushPrediction(p);
          i += 1;
        };

        tick();
        demoTimer.current = window.setInterval(tick, 1000);
      })
      .catch(() => {
        if (!cancelled) setStatus("closed");
      });

    return () => {
      cancelled = true;
      if (demoTimer.current != null) {
        window.clearInterval(demoTimer.current);
        demoTimer.current = null;
      }
    };
  }, [demoMode, reset, setStatus, pushSample, pushFeatures, pushPrediction]);
}
