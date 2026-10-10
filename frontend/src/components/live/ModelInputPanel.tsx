import { useMemo, useState } from "react";
import {
  Activity,
  Binary,
  ChevronRight,
  Cpu,
  Pause,
  Play,
  Radio,
  SquareStack,
} from "lucide-react";
import type { FeatureVector, SensorSample } from "@/api/types";
import { cssVar } from "@/design/tokens";
import { cn } from "@/lib/cn";
import { fmtPercent } from "@/lib/format";
import {
  FEATURE_GROUPS,
  FEATURE_META,
  type FeatureGroupId,
  type FeatureMeta,
} from "@/lib/featureMeta";
import { baseProbabilities, isEnsemble, modelLabel } from "@/lib/modelMeta";
import { Card } from "@/components/primitives/Card";
import { MiniSpark } from "./MiniSpark";
import { RawSensorStream } from "./RawSensorStream";
import { useLiveStore } from "@/stores/liveStore";

/**
 * The input inspector - two views of what goes INTO the classifier, switchable
 * from the panel header.
 *
 *   "Model input" (default) - the derived side. A pipeline strip (raw 1 Hz
 *      stream → 30 s rolling window with a live stride countdown → the
 *      18-feature vector → the configured classifier's P(stress)), then, when an
 *      ensemble is serving, each base model's P(stress); then a grid of all 18 features
 *      grouped by sensor family, each with its value, change since the previous
 *      emit, a sparkline, and where it sits in its recent range.
 *
 *   "Raw sensors" - the underived side, rendered by RawSensorStream: the 1 Hz
 *      packets as they arrive, before any windowing or feature extraction.
 *
 * The two are the same data at different stages, which is the point of letting
 * the user flip between them. Freeze holds BOTH streams, so switching mode while
 * frozen keeps showing the same instant.
 *
 * DELIBERATELY NOT SHOWN: per-feature "importance" or "contribution" bars.
 * The RBF-kernel SVM has no per-feature attribution at all, and the tree models
 * and the MLP each define it differently - faking one number (e.g. from |z|)
 * would be inventing an explanation no model produced. The per-base-model
 * probabilities ARE shown, because those are values the models actually output.
 * Everything here is measured: values, movement, and recent range.
 *
 * Window/stride mirror config/default.yaml (window_s: 30, stride_s: 5).
 */

const WINDOW_S = 30;
const STRIDE_S = 5;

type SortMode = "canonical" | "change";
/** Which half of the pipeline the panel is showing. */
type PanelMode = "model" | "raw";

function formatValue(value: number | undefined, meta: FeatureMeta): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return value.toFixed(meta.decimals);
}

function FeatureRow({
  meta,
  series,
  color,
  expanded,
  onToggle,
}: {
  meta: FeatureMeta;
  series: number[];
  color: string;
  expanded: boolean;
  onToggle: () => void;
}) {
  const value = series.length ? series[series.length - 1] : undefined;
  const prev = series.length > 1 ? series[series.length - 2] : undefined;
  const delta = value != null && prev != null ? value - prev : null;

  const min = series.length ? Math.min(...series) : 0;
  const max = series.length ? Math.max(...series) : 0;
  const span = max - min;
  // Where the current value sits inside its own recent range (0–100%).
  const position = span > 0 && value != null ? ((value - min) / span) * 100 : 50;

  // Windows overlap 25 of 30 seconds, so consecutive emits move very little.
  // Anything below the column's own display resolution would render as a
  // meaningless "+0.0", so show the unit instead of a fake zero.
  const resolution = 0.5 * 10 ** -meta.decimals;
  const showDelta = delta != null && Math.abs(delta) >= resolution;
  // "Meaningful" change is relative to the feature's own recent spread, so a
  // 0.001 move in temp_slope reads as significant while 0.1 bpm does not.
  const moved = showDelta && span > 0 && Math.abs(delta) > span * 0.02;

  return (
    <div className="border-t border-clinical-border/60 first:border-t-0">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="group flex w-full items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-clinical-surface-2/60 cursor-pointer"
      >
        <span className="min-w-0 flex-1">
          <span className="block truncate font-mono text-[11px] text-clinical-faint">
            {meta.key}
          </span>
          <span className="block truncate text-xs text-clinical-muted">{meta.label}</span>
        </span>

        <span className="w-16 shrink-0">
          <MiniSpark values={series.slice(-16)} color={color} />
        </span>

        <span className="shrink-0 text-right">
          <span className="tnum block text-sm font-semibold text-clinical-text">
            {formatValue(value, meta)}
          </span>
          <span
            className={cn(
              "tnum block text-[10px]",
              moved && delta != null && delta > 0
                ? "text-clinical-warning"
                : moved && delta != null && delta < 0
                  ? "text-clinical-accent"
                  : "text-clinical-faint",
            )}
          >
            {showDelta && delta != null
              ? `${delta >= 0 ? "+" : ""}${delta.toFixed(meta.decimals)}`
              : meta.unit || "·"}
          </span>
        </span>

        <ChevronRight
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-clinical-faint transition-transform",
            expanded && "rotate-90",
          )}
          aria-hidden
        />
      </button>

      {expanded && (
        <div className="space-y-2 bg-clinical-surface-2/40 px-3 pb-3 pt-1">
          <p className="text-xs leading-relaxed text-clinical-muted">
            {meta.description}
          </p>
          {/* Position of the current value within its recent range. */}
          <div className="h-1.5 w-full rounded-full bg-clinical-surface-2">
            <div
              className="h-full rounded-full transition-all duration-300"
              style={{
                width: `${Math.max(2, Math.min(100, position))}%`,
                background: color,
              }}
            />
          </div>
          <div className="flex justify-between font-mono text-[10px] text-clinical-faint">
            <span>min {formatValue(min, meta)}</span>
            <span>
              {meta.unit ? `${meta.unit} · ` : ""}
              {series.length} emits
            </span>
            <span>max {formatValue(max, meta)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function Stage({
  icon,
  label,
  value,
  detail,
  active,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail?: string;
  active?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex-1 rounded-xl border border-clinical-border bg-clinical-surface-2/40 p-3 transition-colors",
        active && "border-clinical-accent/50",
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "grid h-6 w-6 shrink-0 place-items-center rounded-lg",
            active
              ? "bg-clinical-accent text-white"
              : "bg-clinical-surface-2 text-clinical-muted",
          )}
        >
          {icon}
        </span>
        <span className="eyebrow truncate">{label}</span>
      </div>
      <div className="tnum mt-2 text-lg font-bold leading-none text-clinical-text">
        {value}
      </div>
      {detail && <div className="mt-1 text-[11px] text-clinical-faint">{detail}</div>}
      {children}
    </div>
  );
}

function Arrow() {
  return (
    <ChevronRight
      className="hidden h-4 w-4 shrink-0 self-center text-clinical-faint lg:block"
      aria-hidden
    />
  );
}

export function ModelInputPanel({ className }: { className?: string }) {
  const features = useLiveStore((s) => s.features);
  const samples = useLiveStore((s) => s.samples);
  const latestSample = useLiveStore((s) => s.latestSample);
  const latestFeatureTs = useLiveStore((s) => s.latestFeatureTs);
  const emitCount = useLiveStore((s) => s.emitCount);
  const prediction = useLiveStore((s) => s.latestPrediction);

  const [mode, setMode] = useState<PanelMode>("model");
  const [group, setGroup] = useState<FeatureGroupId | "all">("all");
  const [sort, setSort] = useState<SortMode>("canonical");
  const [frozen, setFrozen] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  // Snapshot taken when the user freezes, so values stop moving while reading.
  const [snapshot, setSnapshot] = useState<FeatureVector[] | null>(null);
  // Freezing must hold BOTH streams: the user can switch modes while frozen.
  const [sampleSnapshot, setSampleSnapshot] = useState<SensorSample[] | null>(null);

  const live = frozen && snapshot ? snapshot : features;
  // null unless an ensemble is serving; drives the Base models block below.
  const basePredictions = baseProbabilities(prediction);

  const seriesByKey = useMemo(() => {
    const out = {} as Record<keyof FeatureVector, number[]>;
    for (const meta of FEATURE_META) {
      out[meta.key] = live
        .map((f) => f[meta.key])
        .filter((v): v is number => typeof v === "number" && Number.isFinite(v));
    }
    return out;
  }, [live]);

  const colorByGroup = useMemo(() => {
    const fallback: Record<FeatureGroupId, string> = {
      hr: "#f2686f",
      gsr: "#5b8cff",
      temp: "#f0a43a",
    };
    return Object.fromEntries(
      FEATURE_GROUPS.map((g) => [g.id, cssVar(g.colorVar) || fallback[g.id]]),
    ) as Record<FeatureGroupId, string>;
  }, []);

  // --- pipeline strip state -------------------------------------------------
  // Stream time, not wall clock: at 5x replay one stride is ~1 real second.
  const streamMs = latestSample?.timestamp_ms ?? 0;
  const warmup = latestFeatureTs == null;
  const strideProgress = warmup
    ? Math.min(1, samples.length / WINDOW_S)
    : Math.min(1, Math.max(0, (streamMs - latestFeatureTs) / (STRIDE_S * 1000)));
  const secondsToEmit = warmup
    ? Math.max(0, WINDOW_S - samples.length)
    : Math.max(0, STRIDE_S - Math.round((streamMs - latestFeatureTs) / 1000));

  const hasFeatures = live.length > 0;

  const visible = useMemo(() => {
    const pool =
      group === "all" ? FEATURE_META : FEATURE_META.filter((m) => m.group === group);
    if (sort === "canonical") return pool;
    // "Most movement" - rank by change since the previous emit, scaled by each
    // feature's own recent spread so units don't dominate the ordering.
    return [...pool].sort((a, b) => {
      const score = (m: FeatureMeta) => {
        const s = seriesByKey[m.key] ?? [];
        if (s.length < 2) return 0;
        const span = Math.max(...s) - Math.min(...s) || 1;
        return Math.abs(s[s.length - 1] - s[s.length - 2]) / span;
      };
      return score(b) - score(a);
    });
  }, [group, sort, seriesByKey]);

  const toggleFreeze = () => {
    if (frozen) {
      setSnapshot(null);
      setSampleSnapshot(null);
      setFrozen(false);
    } else {
      setSnapshot(features);
      setSampleSnapshot(samples);
      setFrozen(true);
    }
  };

  return (
    <Card className={cn("rounded-2xl", className)}>
      {/* header */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 pt-5">
        <div>
          <div className="eyebrow">
            {mode === "model" ? "Model input" : "Raw sensors"}
          </div>
          <h3 className="font-display text-sm font-semibold tracking-tight text-clinical-text">
            {mode === "model" ? "What the model sees" : "What the sensors send"}
          </h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div
            role="group"
            aria-label="Input view mode"
            className="inline-flex overflow-hidden rounded-lg border border-clinical-border"
          >
            <ModeButton
              active={mode === "model"}
              onClick={() => setMode("model")}
              icon={<Binary className="h-3 w-3" aria-hidden />}
            >
              Model input
            </ModeButton>
            <ModeButton
              active={mode === "raw"}
              onClick={() => setMode("raw")}
              icon={<Radio className="h-3 w-3" aria-hidden />}
            >
              Raw sensors
            </ModeButton>
          </div>
          <span className="font-mono text-[11px] text-clinical-faint">
            {mode === "model"
              ? hasFeatures
                ? `emit #${emitCount} · ${live.length} buffered`
                : "waiting…"
              : `${samples.length} packets · 1 Hz`}
          </span>
          <button
            type="button"
            onClick={toggleFreeze}
            aria-pressed={frozen}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg border border-clinical-border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide transition-colors cursor-pointer",
              frozen
                ? "bg-clinical-accent text-white"
                : "text-clinical-muted hover:text-clinical-text",
            )}
          >
            {frozen ? (
              <Play className="h-3 w-3" aria-hidden />
            ) : (
              <Pause className="h-3 w-3" aria-hidden />
            )}
            {frozen ? "Resume" : "Freeze"}
          </button>
        </div>
      </div>

      {mode === "raw" ? (
        <RawSensorStream frozen={frozen} snapshot={sampleSnapshot} />
      ) : (
        <>
      {/* pipeline strip */}
      <div className="mt-4 flex flex-col gap-2 px-5 lg:flex-row lg:items-stretch">
        <Stage
          icon={<Radio className="h-3.5 w-3.5" aria-hidden />}
          label="Sensor stream"
          value="1 Hz"
          detail={`${samples.length} samples buffered`}
          active={latestSample != null}
        />
        <Arrow />
        <Stage
          icon={<SquareStack className="h-3.5 w-3.5" aria-hidden />}
          label="Rolling window"
          value={`${WINDOW_S}s`}
          detail={
            warmup
              ? `filling - ${secondsToEmit}s to first emit`
              : `next emit in ~${secondsToEmit}s · stride ${STRIDE_S}s`
          }
          active={!warmup}
        >
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-clinical-surface-2">
            <div
              className="h-full rounded-full bg-clinical-accent transition-all duration-500 ease-linear"
              style={{ width: `${Math.round(strideProgress * 100)}%` }}
            />
          </div>
        </Stage>
        <Arrow />
        <Stage
          icon={<Binary className="h-3.5 w-3.5" aria-hidden />}
          label="Feature vector"
          value="22"
          detail="standardised, then fed to the model"
          active={hasFeatures}
        />
        <Arrow />
        {/* raw_proba.stress is exactly what StressDial displays - the two must
            never disagree. smoothed_confidence is confidence in the LABEL, a
            different quantity, and showing it here read as a contradiction. */}
        <Stage
          icon={<Cpu className="h-3.5 w-3.5" aria-hidden />}
          label={modelLabel(prediction?.model_type)}
          value={prediction ? fmtPercent(prediction.raw_proba.stress) : "-"}
          detail={
            prediction
              ? `P(stress) · smoothed: ${prediction.smoothed_label}`
              : "no prediction yet"
          }
          active={prediction != null}
        />
      </div>

      {/* Ensemble diagnostics. Rendered only when an ensemble is serving and
          the backend actually sent per-base-model probabilities - a single
          model sends none, and this whole block disappears. */}
      {basePredictions && (
        <div className="mt-3 px-5">
          <div className="rounded-xl border border-clinical-border bg-clinical-surface-2/40 p-3">
            <div className="flex items-center gap-2">
              <SquareStack className="h-3.5 w-3.5 text-clinical-muted" aria-hidden />
              <span className="text-[11px] font-medium uppercase tracking-wide text-clinical-muted">
                Base models
              </span>
              <span className="text-[11px] text-clinical-faint">
                P(stress) before {isEnsemble(prediction?.model_type) ? "combination" : "smoothing"}
              </span>
            </div>
            <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
              {basePredictions.map((base) => (
                <div key={base.key} className="min-w-0">
                  <dt className="truncate text-[11px] text-clinical-muted">{base.label}</dt>
                  <dd className="font-mono text-sm text-clinical-text">
                    {fmtPercent(base.value)}
                  </dd>
                  <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-clinical-surface-2">
                    <div
                      className="h-full rounded-full bg-clinical-accent"
                      style={{ width: `${Math.round(base.value * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </dl>
          </div>
        </div>
      )}

      {/* controls */}
      <div className="mt-4 flex flex-wrap items-center gap-2 px-5">
        <div className="flex flex-wrap gap-1">
          <FilterChip active={group === "all"} onClick={() => setGroup("all")}>
            All 22
          </FilterChip>
          {FEATURE_GROUPS.map((g) => (
            <FilterChip
              key={g.id}
              active={group === g.id}
              onClick={() => setGroup(g.id)}
              dot={colorByGroup[g.id]}
            >
              {g.label}
            </FilterChip>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-1">
          <span className="eyebrow">Sort</span>
          <FilterChip active={sort === "canonical"} onClick={() => setSort("canonical")}>
            Model order
          </FilterChip>
          <FilterChip active={sort === "change"} onClick={() => setSort("change")}>
            Most movement
          </FilterChip>
        </div>
      </div>

      {/* feature grid */}
      {!hasFeatures ? (
        <div className="flex items-center gap-3 px-5 py-8 text-sm text-clinical-muted">
          <Activity className="h-4 w-4 animate-pulse-soft text-clinical-faint" aria-hidden />
          Waiting for the first feature emit - the window needs {WINDOW_S}s of samples.
        </div>
      ) : sort === "change" ? (
        <div className="mt-3 grid grid-cols-1 gap-x-4 px-5 pb-5 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((meta) => (
            <FeatureRow
              key={meta.key}
              meta={meta}
              series={seriesByKey[meta.key] ?? []}
              color={colorByGroup[meta.group]}
              expanded={expanded === meta.key}
              onToggle={() => setExpanded(expanded === meta.key ? null : meta.key)}
            />
          ))}
        </div>
      ) : (
        <div className="mt-3 grid grid-cols-1 gap-4 px-5 pb-5 md:grid-cols-2 xl:grid-cols-4">
          {FEATURE_GROUPS.filter((g) => group === "all" || group === g.id).map((g) => {
            const rows = visible.filter((m) => m.group === g.id);
            if (!rows.length) return null;
            return (
              <div
                key={g.id}
                className="overflow-hidden rounded-xl border border-clinical-border"
              >
                <div className="flex items-center gap-2 bg-clinical-surface-2/50 px-3 py-2">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: colorByGroup[g.id] }}
                    aria-hidden
                  />
                  <span className="eyebrow">{g.label}</span>
                  <span className="ml-auto font-mono text-[10px] text-clinical-faint">
                    {rows.length}
                  </span>
                </div>
                {rows.map((meta) => (
                  <FeatureRow
                    key={meta.key}
                    meta={meta}
                    series={seriesByKey[meta.key] ?? []}
                    color={colorByGroup[g.id]}
                    expanded={expanded === meta.key}
                    onToggle={() => setExpanded(expanded === meta.key ? null : meta.key)}
                  />
                ))}
              </div>
            );
          })}
        </div>
      )}

        </>
      )}

      <p className="border-t border-clinical-border px-5 py-3 text-[11px] leading-relaxed text-clinical-faint">
        {mode === "model" ? (
          <>
            These are the exact 22 values sent to the classifier, recomputed every{" "}
            {STRIDE_S}s over the last {WINDOW_S}s. Movement and range are measured
            from the stream - no per-feature importance is shown, because the
            models in the ensemble do not agree on one (the RBF-kernel SVM exposes
            none at all).
          </>
        ) : (
          <>
            Unprocessed 1 Hz packets exactly as the service receives them - no
            smoothing, no resampling, no rescaling. Dropped PPG readings print as{" "}
            <span className="font-mono">--</span> rather than interpolated values.
            Click any line for the full packet. The source is whatever{" "}
            <span className="font-mono">input.source</span> selects in
            config/service.yaml.
          </>
        )}
      </p>
    </Card>
  );
}

function ModeButton({
  active,
  onClick,
  icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide transition-colors cursor-pointer",
        active
          ? "bg-clinical-accent text-white"
          : "text-clinical-muted hover:text-clinical-text",
      )}
    >
      {icon}
      {children}
    </button>
  );
}

function FilterChip({
  active,
  onClick,
  dot,
  children,
}: {
  active: boolean;
  onClick: () => void;
  dot?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide transition-colors cursor-pointer",
        active
          ? "border-clinical-accent bg-clinical-accent text-white"
          : "border-clinical-border text-clinical-muted hover:text-clinical-text",
      )}
    >
      {dot && !active && (
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: dot }} aria-hidden />
      )}
      {children}
    </button>
  );
}
