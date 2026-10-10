import { useMemo } from "react";
import { Waves } from "lucide-react";
import { cssVar } from "@/design/tokens";
import { cn } from "@/lib/cn";
import { fmt } from "@/lib/format";
import { Card, CardHeader } from "@/components/primitives/Card";
import { useLiveStore } from "@/stores/liveStore";
import { Sparkline } from "./Sparkline";

/**
 * HRV proxy - hr_pnn_proxy from the latest feature emit, with a sparkline of the
 * last 12 emits (~1 minute at 5s stride).
 */
export function HrvPanel({ className }: { className?: string }) {
  const features = useLiveStore((s) => s.features);
  const latest = useLiveStore((s) => s.latestFeatures);

  const series = useMemo(
    () => features.slice(-12).map((f) => f.hr_pnn_proxy),
    [features],
  );
  const accent = cssVar("--clinical-accent") || "#2563eb";

  return (
    <Card className={cn("flex h-full flex-col pb-4", className)}>
      <CardHeader
        title="HRV proxy"
        subtitle="hr_pnn_proxy · last minute"
        right={<Waves className="h-4 w-4 text-clinical-muted" aria-hidden />}
      />
      <div className="px-4 pt-3">
        <div className="tnum text-3xl font-bold text-clinical-text">
          {latest ? fmt(latest.hr_pnn_proxy, 3) : "-"}
        </div>
        <p className="mt-1 text-xs text-clinical-muted">
          Higher values suggest more beat-to-beat variability (calmer state).
        </p>
      </div>
      <div className="mt-3 px-2">
        <Sparkline values={series} color={accent} height={48} />
      </div>
    </Card>
  );
}
