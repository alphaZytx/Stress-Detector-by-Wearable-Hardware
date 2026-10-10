import { useEffect, useRef, useState } from "react";
import { ShieldCheck, TriangleAlert } from "lucide-react";
import { fmtPercent } from "@/lib/format";
import { stressLevel } from "@/design/tokens";
import { useLiveStore } from "@/stores/liveStore";

/**
 * Radial stress dial - the command-center centerpiece of the Live view.
 * A near-full-circle gauge whose arc length + color track P(stress). The center
 * reads the SMOOTHED label (raw flickers ~12%); the numeric P(stress) eases
 * toward its target via requestAnimationFrame so the arc glides on each 5s emit.
 * Glow intensifies as stress rises so baseline→stress is a visceral shift.
 */
const SWEEP = 280; // degrees of the visible arc
const SIZE = 260;
const STROKE = 18;

export function StressDial() {
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
      displayRef.current += diff * 0.12;
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

  const r = (SIZE - STROKE) / 2;
  const circ = 2 * Math.PI * r;
  const arc = circ * (SWEEP / 360);
  const gapRot = (360 - SWEEP) / 2 + 90; // center the gap at the bottom

  return (
    <div
      className="surface-raised relative flex flex-col items-center justify-center overflow-hidden p-6"
      role="status"
      aria-live="polite"
    >
      {/* top accent bar keyed to stress level */}
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-2 transition-colors duration-300"
        style={{ background: accent }}
      />

      <div className="eyebrow relative mb-2">Current state</div>

      <div className="relative grid place-items-center" style={{ width: SIZE, height: SIZE }}>
        <svg width={SIZE} height={SIZE} className="absolute" style={{ transform: `rotate(${gapRot}deg)` }}>
          {/* track */}
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={r}
            fill="none"
            stroke="var(--clinical-surface-2)"
            strokeWidth={STROKE}
            strokeLinecap="butt"
            strokeDasharray={`${arc} ${circ}`}
          />
          {/* value arc - flat, hard cap */}
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={r}
            fill="none"
            stroke={accent}
            strokeWidth={STROKE}
            strokeLinecap="butt"
            strokeDasharray={`${arc * display} ${circ}`}
            style={{ transition: "stroke 0.3s" }}
          />
        </svg>

        {/* center readout */}
        <div className="relative flex flex-col items-center text-center">
          <span
            className="mb-3 grid h-14 w-14 place-items-center rounded-none border-2 border-clinical-border text-white"
            style={{ background: accent }}
          >
            {isStress ? (
              <TriangleAlert className="h-7 w-7" aria-hidden />
            ) : (
              <ShieldCheck className="h-7 w-7" aria-hidden />
            )}
          </span>
          <div
            className="font-display text-2xl font-bold uppercase tracking-tight transition-colors duration-300"
            style={{ color: accent }}
          >
            {label}
          </div>
          <div className="eyebrow mt-2">P(stress)</div>
          <div className="tnum text-stat-lg font-bold leading-none text-clinical-text">
            {pred ? fmtPercent(display) : "-"}
          </div>
        </div>
      </div>

      {pred?.calibration_applied && (
        <div className="relative mt-4 inline-flex items-center gap-1 rounded-none border-2 border-clinical-border bg-clinical-accent px-3 py-1 text-xs font-bold uppercase tracking-wide text-white">
          calibrated
        </div>
      )}
    </div>
  );
}
