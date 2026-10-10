import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { cssVar } from "@/design/tokens";
import { cn } from "@/lib/cn";
import { rollingMean } from "@/lib/smoothing";
import { Card, CardHeader } from "@/components/primitives/Card";
import { useLiveStore } from "@/stores/liveStore";
import { useSettingsStore } from "@/stores/settingsStore";

/**
 * Streaming BPM line over the last N seconds. animationDuration=0 keeps the line
 * smooth under 1 Hz updates (no per-point tween). X is seconds-ago (negative);
 * Y is fixed [40,160] so the trace doesn't rescale every frame.
 */
export function BpmChart({ className }: { className?: string }) {
  const samples = useLiveStore((s) => s.samples);
  const bufferSeconds = useSettingsStore((s) => s.bufferSeconds);

  const data = useMemo(() => {
    if (samples.length === 0) return [];
    const latestTs = samples[samples.length - 1].timestamp_ms;
    const bpm = rollingMean(
      samples.map((sample) => sample.bpm ?? sample.avg_bpm),
      5,
    );
    return samples
      .map((s, index) => ({
        t: Math.round((s.timestamp_ms - latestTs) / 1000),
        bpm: bpm[index],
      }))
      .filter((d) => d.t >= -bufferSeconds);
  }, [samples, bufferSeconds]);

  const accent = cssVar("--clinical-accent") || "#2563eb";
  const grid = cssVar("--clinical-border") || "#e2e8f0";
  const muted = cssVar("--clinical-muted") || "#475569";

  return (
    <Card
      className={cn(
        // This card shares auto-sized grid rows with the much taller stress
        // dial. Without an explicit minimum, flexbox is allowed to shrink the
        // ResponsiveContainer to a few pixels and the BPM trace appears as a
        // flat line along the top edge even though valid samples are present.
        "flex h-full min-h-[16rem] flex-col pb-4",
        className,
      )}
    >
      <CardHeader title="Heart rate" subtitle={`Last ${bufferSeconds}s · BPM`} />
      <div className="mt-2 min-h-[10rem] flex-1 px-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
            <CartesianGrid stroke={grid} strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              domain={[-bufferSeconds, 0]}
              tickCount={5}
              tick={{ fill: muted, fontSize: 11 }}
              tickFormatter={(v) => (v === 0 ? "now" : `${v}s`)}
              stroke={grid}
            />
            <YAxis
              domain={[40, 160]}
              ticks={[40, 70, 100, 130, 160]}
              tick={{ fill: muted, fontSize: 11 }}
              stroke={grid}
              width={36}
            />
            <Line
              type="monotone"
              dataKey="bpm"
              stroke={accent}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
