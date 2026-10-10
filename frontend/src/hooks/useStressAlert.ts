/**
 * Watches the smoothed stress probability and reports how long it has stayed
 * above the user's threshold. Used by the Live view toast (3.2) and the
 * breathing auto-trigger banner (3.5).
 *
 * Predictions arrive ~every 5s. "Elevated for >30s" therefore means several
 * consecutive elevated emits; we track the wall-clock time since elevation began
 * so the rule is robust to stride changes.
 */

import { useEffect, useRef, useState } from "react";
import { useLiveStore } from "@/stores/liveStore";
import { useSettingsStore } from "@/stores/settingsStore";

const SUSTAINED_MS = 30_000;

export function useStressAlert() {
  const latest = useLiveStore((s) => s.latestPrediction);
  const threshold = useSettingsStore((s) => s.stressThreshold);
  const elevatedSinceRef = useRef<number | null>(null);
  const [secondsElevated, setSecondsElevated] = useState(0);

  useEffect(() => {
    if (!latest) {
      elevatedSinceRef.current = null;
      setSecondsElevated(0);
      return;
    }
    // Use the SMOOTHED P(stress) (per spec): if smoothed_label is stress, the
    // smoothed_confidence IS P(stress); otherwise it's P(baseline).
    const smoothedPStress =
      latest.smoothed_label === "stress"
        ? latest.smoothed_confidence
        : 1 - latest.smoothed_confidence;
    const isElevated = smoothedPStress >= threshold;

    if (isElevated) {
      if (elevatedSinceRef.current == null) elevatedSinceRef.current = Date.now();
      setSecondsElevated((Date.now() - elevatedSinceRef.current) / 1000);
    } else {
      elevatedSinceRef.current = null;
      setSecondsElevated(0);
    }
  }, [latest, threshold]);

  return {
    secondsElevated,
    sustained: secondsElevated >= SUSTAINED_MS / 1000,
  };
}
