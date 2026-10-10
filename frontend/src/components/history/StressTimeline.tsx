import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import type { SessionLabel, SessionPredictionRow } from "@/api/types";
import { cssVar } from "@/design/tokens";

/**
 * Session stress timeline. X = seconds within the session, Y = P(stress) 0..1.
 * Filled area whose color shifts teal→amber→red with height (a vertical gradient
 * keyed to the value axis). Manual labels render as dashed vertical lines; the
 * draggable playhead is a solid accent line.
 */
export function StressTimeline({
  predictions,
  labels,
  startMs,
  playheadS,
  compact = false,
}: {
  predictions: SessionPredictionRow[];
  labels: SessionLabel[];
  startMs: number;
  playheadS: number;
  /** Shorter height + visible dots - used for sparse/short sessions. */
  compact?: boolean;
}) {
  const data = useMemo(
    () =>
      predictions.map((p) => ({
        t: Math.round((p.timestamp_ms - startMs) / 1000),
        p: p.p_stress,
      })),
    [predictions, startMs],
  );

  const teal = cssVar("--clinical-success") || "#0d9488";
  const amber = cssVar("--clinical-warning") || "#d97706";
  const red = cssVar("--clinical-danger") || "#dc2626";
  const accent = cssVar("--clinical-accent") || "#2563eb";
  const grid = cssVar("--clinical-border") || "#e2e8f0";
  const muted = cssVar("--clinical-muted") || "#475569";

  const maxT = data.length ? data[data.length - 1].t : 0;
  const sparse = data.length <= 12;

  return (
    <div className={compact ? "h-44 w-full" : "h-72 w-full"}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
          <defs>
            <linearGradient id="stressFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={red} stopOpacity={0.7} />
              <stop offset="35%" stopColor={amber} stopOpacity={0.5} />
              <stop offset="100%" stopColor={teal} stopOpacity={0.15} />
            </linearGradient>
            <linearGradient id="stressStroke" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={red} />
              <stop offset="50%" stopColor={amber} />
              <stop offset="100%" stopColor={teal} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={grid} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="t"
            type="number"
            domain={[0, maxT]}
            tick={{ fill: muted, fontSize: 11 }}
            tickFormatter={(v) => `${v}s`}
            stroke={grid}
          />
          <YAxis
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tickFormatter={(v) => `${Math.round(v * 100)}%`}
            tick={{ fill: muted, fontSize: 11 }}
            stroke={grid}
            width={44}
          />
          <ReferenceLine y={0.5} stroke={muted} strokeDasharray="4 4" />
          <Area
            type="monotone"
            dataKey="p"
            stroke="url(#stressStroke)"
            strokeWidth={2.5}
            fill="url(#stressFill)"
            isAnimationActive={false}
            dot={sparse ? { r: 3, fill: accent, strokeWidth: 0 } : false}
          />
          {labels.map((l, i) => (
            <ReferenceLine
              key={`${l.timestamp_ms}-${i}`}
              x={Math.round((l.timestamp_ms - startMs) / 1000)}
              stroke={accent}
              strokeDasharray="2 2"
              label={{ value: l.label, position: "top", fill: accent, fontSize: 10 }}
            />
          ))}
          <ReferenceLine x={Math.round(playheadS)} stroke={accent} strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
