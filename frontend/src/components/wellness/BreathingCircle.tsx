import { useEffect, useRef, useState } from "react";
import type { BreathingPattern } from "@/lib/breathing";

/**
 * Animated breathing guide - brutalist edition. A single thick-bordered disc
 * scales between MIN and MAX with the breath; the phase label sits in the centre.
 * Timing is driven by requestAnimationFrame + CSS transforms (NOT keyframes) so
 * phase durations are exact and we can report cycle/phase progress. Respects
 * prefers-reduced-motion (the global rule freezes transitions; rAF still advances
 * phases so guidance + cycle counting stay correct).
 */
export function BreathingCircle({
  pattern,
  running,
  onCycleComplete,
}: {
  pattern: BreathingPattern;
  running: boolean;
  onCycleComplete: (completed: number) => void;
}) {
  const circleRef = useRef<HTMLDivElement>(null);
  const [label, setLabel] = useState(pattern.phases[0].label);

  const MIN = 0.55;
  const MAX = 1;

  useEffect(() => {
    if (!running) return;

    const phases = pattern.phases;
    let phaseIdx = 0;
    let phaseStart = performance.now();
    let prevScale = MIN;
    let cyclesDone = 0;
    setLabel(phases[0].label);

    const mapTarget = (t: number) => MIN + (MAX - MIN) * t;
    const scaleFor = (target: number, progress: number) =>
      prevScale + (mapTarget(target) - prevScale) * progress;

    let raf = 0;
    const tick = (now: number) => {
      const phase = phases[phaseIdx];
      const elapsed = (now - phaseStart) / 1000;
      const progress = Math.min(elapsed / phase.seconds, 1);
      const scale = scaleFor(phase.target, progress);

      const el = circleRef.current;
      if (el) el.style.transform = `scale(${scale.toFixed(4)})`;

      if (progress >= 1) {
        prevScale = mapTarget(phase.target);
        phaseIdx += 1;
        if (phaseIdx >= phases.length) {
          phaseIdx = 0;
          cyclesDone += 1;
          onCycleComplete(cyclesDone);
        }
        phaseStart = now;
        setLabel(phases[phaseIdx].label);
      }
      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [running, pattern, onCycleComplete]);

  return (
    <div className="relative grid h-[24rem] w-[24rem] place-items-center" aria-live="polite">
      {/* static reference ring at full size so growth is legible */}
      <div
        aria-hidden
        className="absolute h-72 w-72 rounded-full border-2 border-dashed border-clinical-border opacity-40"
      />
      {/* the breathing disc */}
      <div
        ref={circleRef}
        className="relative grid h-72 w-72 place-items-center rounded-full border-[6px] border-clinical-border bg-clinical-accent shadow-float"
        style={{ transform: "scale(0.55)", willChange: "transform" }}
      >
        <span className="font-display text-xl font-bold uppercase tracking-wide text-white">
          {label}
        </span>
      </div>
    </div>
  );
}
