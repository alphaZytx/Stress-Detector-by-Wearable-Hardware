/**
 * Shared visual primitives for the Explain page.
 *
 * Everything here is inline SVG or CSS - no chart library - because these are
 * bespoke explanatory diagrams (a kernel boundary, a forest of voting trees, a
 * neural net firing), not standard charts. Recharts is still used on the Live
 * page for the actual time-series plots.
 *
 * Colour follows the app's existing tokens so this page reads as part of the
 * product: success = calm/baseline, danger = stress, accent = "the pipeline".
 */

import type { ReactNode } from "react";

/** Blend calm→stress for a probability. Used everywhere a value is 0..1. */
export function stressColor(p: number): string {
  if (p >= 0.66) return "var(--clinical-danger)";
  if (p >= 0.4) return "var(--clinical-warning)";
  return "var(--clinical-success)";
}

export function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v));
}

/** One numbered stage of the pipeline. */
export function Stage({
  index,
  title,
  subtitle,
  children,
  active = false,
  wide = false,
}: {
  index: number;
  title: string;
  subtitle: string;
  children: ReactNode;
  active?: boolean;
  wide?: boolean;
}) {
  return (
    <section
      className={[
        "relative border-2 bg-clinical-surface p-5 transition-shadow duration-300",
        active
          ? "border-clinical-accent shadow-[0_0_0_4px_var(--clinical-accent-soft)]"
          : "border-clinical-border",
        wide ? "lg:col-span-2" : "",
      ].join(" ")}
    >
      <header className="mb-4 flex items-baseline gap-3">
        <span
          className={[
            "tnum grid h-7 w-7 shrink-0 place-items-center border-2 text-sm font-bold",
            active
              ? "border-clinical-accent bg-clinical-accent text-white"
              : "border-clinical-border bg-clinical-surface-2 text-clinical-text",
          ].join(" ")}
        >
          {index}
        </span>
        <div className="min-w-0">
          <h2 className="text-base font-bold leading-tight">{title}</h2>
          <p className="mt-0.5 text-xs leading-snug text-clinical-muted">
            {subtitle}
          </p>
        </div>
      </header>
      {children}
    </section>
  );
}

/**
 * Vertical connector between stages with particles flowing downward, so the
 * eye follows the direction data actually moves.
 */
export function Flow({ label, active = true }: { label: string; active?: boolean }) {
  return (
    <div className="relative flex h-14 items-center justify-center" aria-hidden>
      <svg width="100%" height="56" className="absolute inset-0">
        <line
          x1="50%"
          y1="0"
          x2="50%"
          y2="48"
          stroke="var(--clinical-border)"
          strokeWidth="2"
        />
        {/* Arrowhead at the BOTTOM: data flows downward through the page.
            Without this the bare line reads as an up-arrow against the
            downward particle motion. */}
        <polygon
          points="-6,-8 6,-8 0,2"
          fill="var(--clinical-border)"
          style={{ transform: "translate(50%, 54px)" }}
        />
        {active &&
          [0, 1, 2].map((i) => (
            <circle key={i} r="3.5" fill="var(--clinical-accent)">
              <animate
                attributeName="cy"
                from="0"
                to="56"
                dur="1.6s"
                begin={`${i * 0.53}s`}
                repeatCount="indefinite"
              />
              <animate
                attributeName="cx"
                values="50%;50%"
                dur="1.6s"
                begin={`${i * 0.53}s`}
                repeatCount="indefinite"
              />
              <animate
                attributeName="opacity"
                values="0;1;1;0"
                dur="1.6s"
                begin={`${i * 0.53}s`}
                repeatCount="indefinite"
              />
            </circle>
          ))}
      </svg>
      <span className="relative bg-clinical-bg px-2 text-[10px] font-semibold uppercase tracking-wider text-clinical-faint">
        {label}
      </span>
    </div>
  );
}

/** Small inline sparkline. `band` shades the 30 s window region. */
export function Spark({
  values,
  width = 200,
  height = 40,
  color = "var(--clinical-accent)",
  bandFrom,
}: {
  values: number[];
  width?: number;
  height?: number;
  color?: string;
  bandFrom?: number;
}) {
  const clean = values.filter((v) => Number.isFinite(v));
  if (clean.length < 2) {
    return (
      <div
        style={{ width, height }}
        className="grid place-items-center text-[10px] text-clinical-faint"
      >
        waiting for data…
      </div>
    );
  }
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const span = max - min || 1;
  const pts = clean.map((v, i) => {
    const x = (i / (clean.length - 1)) * width;
    const y = height - ((v - min) / span) * (height - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return (
    <svg width={width} height={height} className="overflow-visible">
      {bandFrom !== undefined && bandFrom < clean.length && (
        <rect
          x={(bandFrom / (clean.length - 1)) * width}
          y={0}
          width={width - (bandFrom / (clean.length - 1)) * width}
          height={height}
          fill="var(--clinical-accent-soft)"
        />
      )}
      <polyline
        points={pts.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle
        cx={(width * (clean.length - 1)) / (clean.length - 1)}
        cy={
          height - ((clean[clean.length - 1] - min) / span) * (height - 4) - 2
        }
        r="3"
        fill={color}
      />
    </svg>
  );
}

/** Horizontal 0..1 probability bar with a label and value. */
export function ProbBar({
  label,
  value,
  sublabel,
  emphasis = false,
}: {
  label: string;
  value: number;
  sublabel?: string;
  emphasis?: boolean;
}) {
  const pct = clamp01(value) * 100;
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span
          className={[
            "text-xs",
            emphasis ? "font-bold text-clinical-text" : "text-clinical-muted",
          ].join(" ")}
        >
          {label}
        </span>
        <span className="tnum text-xs font-semibold">{value.toFixed(3)}</span>
      </div>
      <div className="relative h-2.5 border-2 border-clinical-border bg-clinical-surface-2">
        <div
          className="absolute inset-y-0 left-0 transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%`, background: stressColor(value) }}
        />
        {/* decision threshold */}
        <div
          className="absolute inset-y-0 w-[2px] bg-clinical-border"
          style={{ left: "50%" }}
        />
      </div>
      {sublabel && (
        <p className="mt-1 text-[10px] leading-tight text-clinical-faint">
          {sublabel}
        </p>
      )}
    </div>
  );
}

/** A short explanatory note in the margin of a stage. */
export function Note({ children }: { children: ReactNode }) {
  return (
    <p className="mt-3 border-l-2 border-clinical-accent bg-clinical-accent-soft/40 py-1.5 pl-3 text-[11px] leading-snug text-clinical-muted">
      {children}
    </p>
  );
}
