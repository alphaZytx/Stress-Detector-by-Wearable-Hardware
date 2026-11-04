import { useEffect, useRef, useState } from "react";
import { ShieldCheck, TriangleAlert } from "lucide-react";
import { cn } from "@/lib/cn";
import { fmtPercent } from "@/lib/format";
import { stressLevel } from "@/design/tokens";
import { useLiveStore } from "@/stores/liveStore";

/**
 * Headline stress strip. Shows the SMOOTHED label prominently (raw label flickers
 * ~12%). P(stress) is interpolated toward its target with requestAnimationFrame
 * so the bar + color glide rather than jump on each 5s emit. The whole panel
 * gains depth + a pulsing glow as stress rises, so baseline→stress reads as a
 * visceral shift, not just a color swap.
 */
export function StressIndicator() {
  const pred = useLiveStore((s) => s.latestPrediction);
  const target = pred ? pred.raw_proba.stress : 0;

  const [display, setDisplay] = useState(0);
  const displayRef = useRef(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const animate = () => {
      const diff = target - displayRef.current;
      if (Math.abs(diff) < 0.002) {
        displayRef.current = target;
        setDisplay(target);
        rafRef.current = null;
        return;
      }
      displayRef.current += diff * 0.12; // ease toward target
      setDisplay(displayRef.current);
      rafRef.current = requestAnimationFrame(animate);
    };
    if (rafRef.current == null) rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [target]);

  const level = stressLevel(display);
  const isStress = pred?.smoothed_label === "stress";
  const label = pred ? pred.smoothed_label.toUpperCase() : "-";

  const ACCENT: Record<string, string> = {
    calm: "var(--clinical-success)",
    moderate: "var(--clinical-warning)",
    high: "var(--clinical-danger)",
  };
  const accent = ACCENT[level];
  // Gradient/glow intensity tracks P(stress) - 0.04 at rest → ~0.22 at peak.
  const intensity = 0.04 + display * 0.2;

  return (
    <div
      className="relative overflow-hidden rounded-2xl border p-6 backdrop-blur-2xl transition-colors duration-500"
      style={{
        borderColor: `color-mix(in srgb, ${accent} 38%, transparent)`,
        background: `
          radial-gradient(130% 160% at 6% 0%, color-mix(in srgb, ${accent} ${intensity * 100}%, transparent), transparent 60%),
          var(--clinical-surface-raised)`,
        boxShadow: `var(--shadow-lg), var(--glass-highlight), 0 0 ${10 + display * 60}px -10px ${accent}`,
      }}
      role="status"
      aria-live="polite"
    >
      {/* Pulsing glow wash when stress is elevated. */}
      {level === "high" && (
        <div
          aria-hidden
          className="pointer-events-none absolute -right-10 -top-16 h-56 w-56 rounded-full blur-3xl animate-pulse-soft"
          style={{ background: `radial-gradient(circle, ${accent} 0%, transparent 70%)`, opacity: 0.5 }}
        />
      )}

      <div className="relative flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <span
            className="grid h-16 w-16 place-items-center rounded-2xl text-white transition-all duration-500"
            style={{
              background: `linear-gradient(135deg, color-mix(in srgb, ${accent} 80%, white) 0%, ${accent} 100%)`,
              boxShadow: `0 8px 24px -6px ${accent}, var(--ring-highlight)`,
            }}
          >
            {isStress ? (
              <TriangleAlert className="h-8 w-8" aria-hidden />
            ) : (
              <ShieldCheck className="h-8 w-8" aria-hidden />
            )}
          </span>
          <div>
            <div className="eyebrow">Current state</div>
            <div
              className="font-display text-stat font-bold tracking-tight transition-colors duration-500"
              style={{ color: accent }}
            >
              {label}
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="eyebrow">P(stress)</div>
          <div className="tnum text-stat-lg font-extrabold text-clinical-text">
            {pred ? fmtPercent(display, 1) : "-"}
          </div>
          {pred?.calibration_applied && (
            <div className="mt-1 inline-flex items-center gap-1 rounded-full bg-clinical-accent-soft px-2 py-0.5 text-xs font-medium text-clinical-accent">
              calibrated
            </div>
          )}
        </div>
      </div>

      {/* Confidence bar */}
      <div className="relative mt-6">
        <div className="h-3 w-full overflow-hidden rounded-full bg-clinical-surface-2 shadow-[inset_0_1px_2px_rgba(0,0,0,0.12)]">
          <div
            className={cn("h-full rounded-full transition-[width] duration-300")}
            style={{
              width: `${Math.round(display * 100)}%`,
              background: `linear-gradient(90deg, color-mix(in srgb, ${accent} 60%, transparent), ${accent})`,
              boxShadow: `0 0 12px ${accent}`,
            }}
          />
        </div>
        <div className="mt-1.5 flex justify-between">
          <span className="eyebrow !tracking-normal">Baseline</span>
          <span className="eyebrow !tracking-normal">Stress</span>
        </div>
      </div>
    </div>
  );
}
