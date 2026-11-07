import { useMemo } from "react";
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Droplets,
  HeartPulse,
  ScanLine,
  Thermometer,
  Wind,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { cssVar } from "@/design/tokens";
import { fmt, fmtBpm, fmtTemp, trend } from "@/lib/format";
import { smoothedLatest } from "@/lib/smoothing";
import { Card } from "@/components/primitives/Card";
import { useLiveStore } from "@/stores/liveStore";
import { useSettingsStore } from "@/stores/settingsStore";
import { Sparkline } from "./Sparkline";

function TrendArrow({ dir }: { dir: "up" | "down" | "flat" }) {
  const Icon = dir === "up" ? ArrowUpRight : dir === "down" ? ArrowDownRight : ArrowRight;
  const color =
    dir === "up"
      ? "text-clinical-warning"
      : dir === "down"
        ? "text-clinical-success"
        : "text-clinical-muted";
  return <Icon className={cn("h-4 w-4", color)} aria-label={`trend ${dir}`} />;
}

function GaugeCard({
  icon,
  label,
  value,
  unit,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  unit?: string;
  children?: React.ReactNode;
}) {
  return (
    <Card className="group col-span-1 flex flex-col gap-3 p-5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md lg:col-span-3">
      <div className="flex items-center gap-2">
        <span className="grid h-7 w-7 place-items-center rounded-none border-2 border-clinical-border bg-clinical-accent text-white">
          {icon}
        </span>
        <span className="eyebrow">{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className="tnum text-stat font-bold leading-none text-clinical-text">
          {value}
        </span>
        {unit && <span className="text-xs text-clinical-faint">{unit}</span>}
      </div>
      {children}
    </Card>
  );
}

/** Window of recent samples for trend/sparkline. */
function useRecent(seconds: number) {
  const samples = useLiveStore((s) => s.samples);
  return useMemo(() => samples.slice(-seconds), [samples, seconds]);
}

export function GaugeRow({ forceAll = false }: { forceAll?: boolean }) {
  const sensors = useSettingsStore((s) => s.sensors);
  const recent30 = useRecent(30);
  const recent60 = useRecent(60);

  const teal = cssVar("--clinical-success") || "#0d9488";
  const accent = cssVar("--clinical-accent") || "#2563eb";

  const hrTrend = trend(
    recent30.map((s) => s.bpm).filter((b): b is number => b != null),
  );
  const tempTrend = trend(
    recent30.map((s) => s.temp_c).filter((t): t is number => t != null && t > 0),
    0.1,
  );
  const gsrSeries = recent60.map((s) => s.gsr);
  const recentVitals = recent30.slice(-5);
  const displayBpm = smoothedLatest(
    recentVitals.map((sample) => sample.bpm ?? sample.avg_bpm),
  );
  const displayGsr = smoothedLatest(recentVitals.map((sample) => sample.gsr));
  const displayTemp = smoothedLatest(recentVitals.map((sample) => sample.temp_c));
  const latest = recentVitals[recentVitals.length - 1];
  const contactValid = latest?.finger_present !== false;

  const cards: React.ReactNode[] = [];

  if (forceAll || sensors.hr)
    cards.push(
      <GaugeCard
        key="hr"
        icon={<HeartPulse className="h-3.5 w-3.5" aria-hidden />}
        label="Heart rate"
        value={contactValid ? fmtBpm(displayBpm) : "0"}
        unit="bpm"
      >
        <div className="flex items-center gap-1 text-xs text-clinical-muted">
          <TrendArrow dir={hrTrend} /> 30s
        </div>
      </GaugeCard>,
    );

  if (forceAll || sensors.gsr)
    cards.push(
      <GaugeCard
        key="gsr"
        icon={<Droplets className="h-3.5 w-3.5" aria-hidden />}
        label="GSR"
        value={fmt(displayGsr, 0)}
        unit="µS-adc"
      >
        <Sparkline values={gsrSeries} color={teal} />
      </GaugeCard>,
    );

  if (forceAll || sensors.temp)
    cards.push(
      <GaugeCard
        key="temp"
        icon={<Thermometer className="h-3.5 w-3.5" aria-hidden />}
        label="Body temperature"
        value={fmtTemp(contactValid ? displayTemp : null)}
        unit="°F"
      >
        <div className="flex items-center gap-1 text-xs text-clinical-muted">
          <TrendArrow dir={tempTrend} /> 30s
        </div>
      </GaugeCard>,
    );

  cards.push(
    <GaugeCard
      key="spo2"
      icon={<Wind className="h-3.5 w-3.5" aria-hidden />}
      label="SpO2"
      value={fmt(latest?.spo2, 1)}
      unit="%"
    >
      <div className="text-xs text-clinical-muted">Live sensor value · not a model input</div>
    </GaugeCard>,
  );

  cards.push(
    <GaugeCard
      key="ambient-temp"
      icon={<Thermometer className="h-3.5 w-3.5" aria-hidden />}
      label="Surrounding temperature"
      value={fmtTemp(latest?.ambient_temp_c)}
      unit="°F"
    />,
  );

  cards.push(
    <GaugeCard
      key="ir"
      icon={<ScanLine className="h-3.5 w-3.5" aria-hidden />}
      label="PPG infrared"
      value={fmt(latest?.ir, 0)}
    />,
  );

  cards.push(
    <GaugeCard
      key="contact"
      icon={<ScanLine className="h-3.5 w-3.5" aria-hidden />}
      label="Finger contact"
      value={latest?.finger_present == null ? "—" : latest.finger_present ? "Present" : "Not detected"}
    >
      {latest?.finger_present === false && (
        <div className="text-xs font-medium text-clinical-warning">Stress prediction paused</div>
      )}
    </GaugeCard>,
  );

  // Use accent ref to avoid unused var when no sparkline-accent card present.
  void accent;

  // Returns a fragment so each tile sits directly in the parent bento grid.
  return <>{cards}</>;
}
