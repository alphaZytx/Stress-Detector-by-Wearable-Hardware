import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Wind, X } from "lucide-react";
import { Button } from "@/components/primitives/Button";
import { useStressAlert } from "@/hooks/useStressAlert";

/**
 * Non-blocking prompt: when smoothed stress stays elevated >30s, gently suggest
 * the breathing exercise. Wellness-toned (this is a care moment, not a metric).
 * Dismissible; re-arms only after stress subsides and rises again.
 */
export function StressAlertBanner() {
  const { sustained } = useStressAlert();
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(false);

  // Re-arm the banner once stress is no longer sustained.
  useEffect(() => {
    if (!sustained) setDismissed(false);
  }, [sustained]);

  if (!sustained || dismissed) return null;

  return (
    <div
      role="alert"
      className="surface-glass animate-fade-in flex items-center gap-3 rounded-2xl border-wellness-accent/30 px-4 py-3"
    >
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-wellness-accent/15 text-wellness-accent">
        <Wind className="h-5 w-5" aria-hidden />
      </span>
      <div className="flex-1">
        <p className="text-sm font-medium text-wellness-text">
          Stress has been elevated for a while.
        </p>
        <p className="text-xs text-wellness-muted">
          A short breathing exercise may help you settle.
        </p>
      </div>
      <Button variant="wellness" size="sm" onClick={() => navigate("/breathing")}>
        Try breathing
      </Button>
      <button
        aria-label="Dismiss"
        onClick={() => setDismissed(true)}
        className="grid h-7 w-7 place-items-center rounded-md text-wellness-muted transition-colors hover:bg-wellness-accent/10 cursor-pointer"
      >
        <X className="h-4 w-4" aria-hidden />
      </button>
    </div>
  );
}
