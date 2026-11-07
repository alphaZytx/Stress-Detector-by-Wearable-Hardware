import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Droplets, HeartPulse, Tag, Thermometer } from "lucide-react";
import { sessionApi } from "@/api/session";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/primitives/Badge";
import { Button } from "@/components/primitives/Button";
import { Card } from "@/components/primitives/Card";
import { Dialog } from "@/components/primitives/Dialog";
import { Input } from "@/components/primitives/Input";
import { StressTimeline } from "@/components/history/StressTimeline";
import { useSessionDetail } from "@/hooks/useSessions";
import { fmt, fmtBpm, fmtPercent, fmtTemp } from "@/lib/format";
import { dominantStress, sessionAverages } from "@/lib/sessionStats";
import { formatDateTime, formatDuration } from "@/lib/time";

function StatCard({
  icon,
  label,
  value,
  unit,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  unit: string;
}) {
  return (
    <Card className="flex flex-col gap-2 p-5">
      <span className="flex items-center gap-2">
        <span className="grid h-7 w-7 place-items-center rounded-none border-2 border-clinical-border bg-clinical-accent text-white">
          {icon}
        </span>
        <span className="eyebrow">{label}</span>
      </span>
      <div className="flex items-baseline gap-1">
        <span className="tnum text-stat-lg font-bold leading-none text-clinical-text">
          {value}
        </span>
        <span className="text-xs text-clinical-faint">{unit}</span>
      </div>
    </Card>
  );
}

function MetaChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-clinical-border bg-clinical-surface-2 px-3 py-1.5">
      <span className="eyebrow !tracking-normal mr-1.5">{label}</span>
      <span className="tnum text-sm font-semibold text-clinical-text">{value}</span>
    </div>
  );
}

export function SessionDetail() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data, isLoading, error } = useSessionDetail(sessionId);

  const [playheadS, setPlayheadS] = useState(0);
  const [annotateOpen, setAnnotateOpen] = useState(false);
  const [annotation, setAnnotation] = useState("");
  const [saving, setSaving] = useState(false);

  // Samples/predictions carry STREAM-relative timestamps (ms since the source
  // started), NOT offsets from started_at_ms. Anchor the timeline to the first
  // recorded sample so 0s = session start.
  const baseMs = useMemo(() => {
    if (!data) return 0;
    return data.samples[0]?.timestamp_ms ?? data.predictions[0]?.timestamp_ms ?? 0;
  }, [data]);

  const durationS = useMemo(() => {
    if (!data || data.samples.length === 0) return 0;
    const last = data.samples[data.samples.length - 1].timestamp_ms;
    return Math.max(0, Math.round((last - baseMs) / 1000));
  }, [data, baseMs]);

  const averages = useMemo(
    () => (data ? sessionAverages(data.samples) : { hr: null, gsr: null, temp: null }),
    [data],
  );

  // Sample + prediction nearest the playhead.
  const atPlayhead = useMemo(() => {
    if (!data) return { sample: null, pStress: null as number | null };
    const targetMs = baseMs + playheadS * 1000;
    const nearest = <T extends { timestamp_ms: number }>(arr: T[]): T | null =>
      arr.length === 0
        ? null
        : arr.reduce((best, x) =>
            Math.abs(x.timestamp_ms - targetMs) <
            Math.abs(best.timestamp_ms - targetMs)
              ? x
              : best,
          );
    const sample = nearest(data.samples);
    const pred = nearest(data.predictions);
    return { sample, pStress: pred ? pred.p_stress : null };
  }, [data, baseMs, playheadS]);

  const saveAnnotation = async () => {
    if (!sessionId || !annotation.trim()) return;
    setSaving(true);
    try {
      await sessionApi.label(
        baseMs + Math.round(playheadS) * 1000,
        annotation.trim(),
        sessionId,
      );
      await qc.invalidateQueries({ queryKey: ["session", sessionId] });
      setAnnotateOpen(false);
      setAnnotation("");
    } finally {
      setSaving(false);
    }
  };

  const isShort = !!data && data.predictions.length < 8;
  const dom = data ? dominantStress(data.predictions) : null;

  const averagesBlock = data && (
    <div className="grid grid-cols-3 gap-3 lg:grid-cols-1">
      <StatCard
        icon={<HeartPulse className="h-4 w-4" aria-hidden />}
        label="Mean HR"
        value={fmtBpm(averages.hr)}
        unit="bpm"
      />
      <StatCard
        icon={<Droplets className="h-4 w-4" aria-hidden />}
        label="Mean GSR"
        value={fmt(averages.gsr, 0)}
        unit="µS-adc"
      />
      <StatCard
        icon={<Thermometer className="h-4 w-4" aria-hidden />}
        label="Mean temp"
        value={fmtTemp(averages.temp)}
        unit="°F"
      />
    </div>
  );

  const timelineBlock = data && (
    <Card className="p-5">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-clinical-text">
            Stress timeline
          </h3>
          {isShort && (
            <p className="mt-0.5 text-xs text-clinical-faint">
              Short session - {data.predictions.length}{" "}
              {data.predictions.length === 1 ? "reading" : "readings"} shown as points.
            </p>
          )}
        </div>
        <Button size="sm" variant="secondary" onClick={() => setAnnotateOpen(true)}>
          <Tag className="h-4 w-4" aria-hidden />
          Add annotation
        </Button>
      </div>
      <StressTimeline
        predictions={data.predictions}
        labels={data.labels}
        startMs={baseMs}
        playheadS={playheadS}
        compact={isShort}
      />

      {/* Scrubber */}
      <div className="mt-4 rounded-lg bg-clinical-surface-2 p-3">
        <label
          htmlFor="scrub"
          className="mb-2 block eyebrow"
        >
          Playhead · {playheadS}s
        </label>
        <input
          id="scrub"
          type="range"
          min={0}
          max={durationS}
          value={playheadS}
          onChange={(e) => setPlayheadS(Number(e.target.value))}
          className="w-full cursor-pointer accent-clinical-accent"
          aria-label="Timeline playhead"
        />
        <div className="mt-3 grid grid-cols-4 gap-2 text-center">
          {[
            { l: "HR", v: fmtBpm(atPlayhead.sample?.bpm), u: "bpm" },
            { l: "GSR", v: fmt(atPlayhead.sample?.gsr, 0), u: "" },
            { l: "Temp", v: fmtTemp(atPlayhead.sample?.temp_c), u: "°F" },
            {
              l: "P(stress)",
              v: atPlayhead.pStress != null ? fmtPercent(atPlayhead.pStress) : "-",
              u: "",
            },
          ].map((x) => (
            <div key={x.l}>
              <div className="eyebrow !tracking-normal">{x.l}</div>
              <div className="tnum text-sm font-semibold text-clinical-text">
                {x.v}
                {x.u && <span className="ml-0.5 text-xs text-clinical-faint">{x.u}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        eyebrow="Session"
        title={data?.user_label || "Session"}
        subtitle={data ? formatDateTime(data.started_at_ms) : "Loading…"}
        right={
          <Button variant="secondary" size="sm" onClick={() => navigate("/history")}>
            <ArrowLeft className="h-4 w-4" aria-hidden />
            Back
          </Button>
        }
      />

      <div className="flex-1 space-y-5 p-6">
        {isLoading && <p className="text-sm text-clinical-muted">Loading session…</p>}
        {error && <p className="text-sm text-clinical-danger">Failed to load session.</p>}

        {data && (
          <>
            {/* Metadata chips + dominant badge */}
            <div className="flex flex-wrap items-center gap-2">
              <MetaChip
                label="Duration"
                value={formatDuration(data.started_at_ms, data.ended_at_ms)}
              />
              <MetaChip label="Samples" value={String(data.samples.length)} />
              <MetaChip label="Predictions" value={String(data.predictions.length)} />
              {dom && dom.level !== "none" && (
                <Badge tone={dom.level === "stress" ? "danger" : "success"}>
                  {dom.level === "stress"
                    ? `mostly stress · ${fmtPercent(dom.stressFraction)}`
                    : `mostly baseline · ${fmtPercent(1 - dom.stressFraction)}`}
                </Badge>
              )}
              {data.notes && (
                <span className="text-sm text-clinical-faint">· {data.notes}</span>
              )}
            </div>

            {/* Timeline-led bento: the scrubable timeline is the feature; the
                session averages sit in a side column. On short sessions the
                averages lead (the timeline has little to show), so they appear
                first in source order on mobile. */}
            <div className="grid gap-5 lg:grid-cols-3">
              <div className={isShort ? "order-2 lg:order-1 lg:col-span-2" : "lg:col-span-2"}>
                {timelineBlock}
              </div>
              <div className={isShort ? "order-1 lg:order-2" : ""}>{averagesBlock}</div>
            </div>
          </>
        )}
      </div>

      <Dialog
        open={annotateOpen}
        onOpenChange={setAnnotateOpen}
        title="Add annotation"
        description={`Marks the timeline at ${playheadS}s (drag the playhead to reposition).`}
      >
        <div className="flex flex-col gap-4">
          <Input
            label="Label"
            placeholder="e.g. felt anxious"
            value={annotation}
            onChange={(e) => setAnnotation(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setAnnotateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={saveAnnotation} loading={saving} disabled={!annotation.trim()}>
              Save annotation
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
