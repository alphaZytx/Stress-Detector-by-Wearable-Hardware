/**
 * Generic auto-reconnecting WebSocket hook.
 *
 * - Connects to `url` (pass null to stay disconnected, e.g. in demo mode).
 * - Exponential backoff: 1s, 2s, 4s, … capped at 30s.
 * - Dispatches parsed messages to `onMessage`.
 * - Reports connection state through `onStatus`.
 *
 * Close code 4401 (auth) is treated as terminal - we don't reconnect a bad
 * token in a tight loop; the caller should refresh auth.
 *
 * LIFECYCLE NOTE: the "is this socket still wanted?" flag is a plain closure
 * variable scoped to ONE effect run, never a ref. A ref is shared across runs,
 * and under StrictMode's mount → unmount → mount the ordering is:
 *     connect A · cleanup sets flag=true, closes A · new run resets flag=false
 *     · A's onclose finally fires, sees false, and schedules a reconnect
 * - so the discarded socket resurrects itself and the app ends up with two live
 * connections pushing duplicate, interleaved frames into the store. Keeping the
 * flag per-run means a closed socket can never outlive the effect that made it.
 */

import { useEffect, useRef } from "react";
import type { ConnectionStatus } from "@/stores/liveStore";

const BACKOFF_BASE_MS = 1000;
const BACKOFF_MAX_MS = 30_000;
export const WS_AUTH_CLOSE_CODE = 4401;

interface Options {
  url: string | null;
  onMessage: (data: unknown) => void;
  onStatus?: (status: ConnectionStatus) => void;
  onAuthError?: () => void;
}

export function useWebSocket({ url, onMessage, onStatus, onAuthError }: Options) {
  // Keep latest callbacks without re-triggering the connect effect.
  const cbRef = useRef({ onMessage, onStatus, onAuthError });
  cbRef.current = { onMessage, onStatus, onAuthError };

  useEffect(() => {
    if (!url) {
      cbRef.current.onStatus?.("closed");
      return;
    }

    // Per-run state. Scoped to this effect invocation on purpose - see above.
    let cancelled = false;
    let socket: WebSocket | null = null;
    let timer: number | null = null;
    let attempt = 0;
    let downSince: number | null = null;

    // After this long without a connection, report "closed" (red Disconnected)
    // even though we keep retrying in the background.
    const DOWN_GRACE_MS = 5000;

    const connect = () => {
      if (cancelled) return;

      cbRef.current.onStatus?.(attempt === 0 ? "connecting" : "reconnecting");
      const ws = new WebSocket(url);
      socket = ws;

      ws.onopen = () => {
        if (cancelled) {
          ws.close();
          return;
        }
        attempt = 0;
        downSince = null;
        cbRef.current.onStatus?.("open");
      };

      ws.onmessage = (ev) => {
        if (cancelled) return;
        try {
          cbRef.current.onMessage(JSON.parse(ev.data));
        } catch {
          /* ignore malformed frames */
        }
      };

      ws.onclose = (ev) => {
        if (socket === ws) socket = null;
        if (cancelled) return;

        if (ev.code === WS_AUTH_CLOSE_CODE) {
          cbRef.current.onStatus?.("closed");
          cbRef.current.onAuthError?.();
          return; // terminal - don't hammer with a bad token
        }

        if (downSince == null) downSince = Date.now();
        const downFor = Date.now() - downSince;
        // Briefly "reconnecting" (amber), then "closed" (red) on a sustained
        // outage - while still retrying in the background.
        cbRef.current.onStatus?.(downFor >= DOWN_GRACE_MS ? "closed" : "reconnecting");

        const delay = Math.min(BACKOFF_BASE_MS * 2 ** attempt, BACKOFF_MAX_MS);
        attempt += 1;
        timer = window.setTimeout(connect, delay);
      };

      ws.onerror = () => {
        // onclose will follow and drive reconnection.
        ws.close();
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (timer != null) {
        window.clearTimeout(timer);
        timer = null;
      }
      socket?.close();
      socket = null;
    };
  }, [url]);
}
