import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { ArrowDownToLine, Circle, Copy, Eraser, Check } from "lucide-react";
import type { SensorSample } from "@/api/types";
import { cn } from "@/lib/cn";
import { useLiveStore } from "@/stores/liveStore";

/**
 * Raw sensor stream - rendered as a serial monitor, not a data table.
 *
 * These are the 1 Hz packets exactly as they arrive from the source, before any
 * windowing or feature extraction. Nothing is smoothed, resampled or rescaled;
 * a dropped PPG reading prints as `--`, not as an interpolated value, because
 * that is what the pipeline actually receives.
 *
 * WHY A CONSOLE AND NOT A TABLE: a table implies a settled dataset you scan at
 * leisure. This is a live wire. Lines print at the bottom and scroll up, the
 * newest flashes as it lands, the caret blinks while the port is open, and
 * scrolling up detaches the follow so you can read back without fighting the
 * stream - the behaviours anyone who has watched the Arduino IDE serial monitor
 * already knows. The panel's Freeze button is the monitor's pause.
 *
 * The console owns a fixed dark palette in BOTH themes. A serial monitor is a
 * terminal; re-tinting it for light mode would cost the thing that makes it
 * legible at a glance. It is a self-contained device surface, deliberately.
 *
 * The source is whatever `input.source` in config/service.yaml selects
 * (synthetic / csv_replay / serial / tcp) - this view is unaware of which.
 */

/** Console height, in printed lines. */
const HEIGHT_CHOICES = [12, 24, 40];
/** Dropout rate is only meaningful over a recent horizon, not the whole buffer. */
const DROPOUT_WINDOW = 60;
/** Cap the rendered scrollback; the store may hold far more than is readable. */
const MAX_SCROLLBACK = 400;
const LINE_H = 18; // px - must match leading-[18px] on the rows

/** Fixed terminal palette - intentionally theme-independent (see module note). */
const T = {
  bg: "#080b0d",
  chrome: "#0e1316",
  rule: "#1c2529",
  dim: "#4d5d63",
  text: "#c9d4d0",
  ts: "#5f7f8e",
  bpm: "#ff6b7a",
  gsr: "#62a0ff",
  temp: "#f0a43a",
  accent: "#3ecf8e",
  warn: "#f0a43a",
  ok: "#3ecf8e",
} as const;

type Format = "aligned" | "csv" | "json";

const FORMATS: { id: Format; label: string }[] = [
  { id: "aligned", label: "aligned" },
  { id: "csv", label: "csv" },
  { id: "json", label: "json" },
];

/** CSV column order, mirroring the service's SensorSample (see api/types.ts). */
const CSV_HEADER =
  "t,bpm,spo2,object_temp_c,ambient_temp_c,gsr,ir,finger_present";

function fmtStreamClock(ms: number): string {
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/** Fixed-width numeric field - alignment is what makes a console readable. */
function pad(
  value: number | null | undefined,
  decimals: number,
  width: number,
): string {
  const text =
    value == null || !Number.isFinite(value) ? "--" : value.toFixed(decimals);
  return text.padStart(width);
}

/** One packet as a plain-text line - also what the copy button writes out. */
function toText(s: SensorSample, format: Format): string {
  const t = fmtStreamClock(s.timestamp_ms);
  const visible =
    s.finger_present === false
      ? { ...s, temp_c: null, ambient_temp_c: null }
      : s;
  if (format === "json") return JSON.stringify(visible);
  if (format === "csv") {
    const n = (v: number | null | undefined, d: number) =>
      v == null || !Number.isFinite(v) ? "" : v.toFixed(d);
    return [
      t,
      s.finger_present === false ? "0" : n(s.bpm, 0),
      n(s.spo2, 1),
      n(visible.temp_c, 2),
      n(visible.ambient_temp_c, 2),
      n(s.gsr, 1),
      n(s.ir, 0),
      s.finger_present == null ? "" : String(s.finger_present),
    ].join(",");
  }
  const bpm = s.finger_present === false ? "0" : pad(s.bpm, 0, 1).trim();
  const spo2 = s.spo2 == null ? "--" : s.spo2.toFixed(1);
  const objectTemp = visible.temp_c == null ? "--" : visible.temp_c.toFixed(2);
  const ambientTemp =
    visible.ambient_temp_c == null ? "--" : visible.ambient_temp_c.toFixed(2);
  const gsr = Number.isFinite(s.gsr) ? s.gsr.toFixed(2) : "--";
  const ir = s.ir == null ? "--" : s.ir.toFixed(0);
  return (
    `BPM: ${bpm || "--"} | SPO2: ${spo2} | ObjTemp: ${objectTemp} | ` +
    `AmbTemp: ${ambientTemp} | GSR: ${gsr} | IR: ${ir}` +
    (s.finger_present === false
      ? " | No finger"
      : s.bpm == null
        ? " | [DROP]"
        : "")
  );
}

/** One printed line, colored per channel. */
function Line({
  sample,
  format,
  fresh,
  open,
  onToggle,
}: {
  sample: SensorSample;
  format: Format;
  fresh: boolean;
  open: boolean;
  onToggle: () => void;
}) {
  const dropped = sample.bpm == null;

  return (
    <>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-label={`Packet at ${fmtStreamClock(sample.timestamp_ms)}`}
        className={cn(
          "block w-full cursor-pointer whitespace-pre text-left leading-[18px] outline-none",
          "hover:bg-white/[0.04] focus-visible:bg-white/[0.07]",
          fresh && "animate-line-print",
          open && "bg-white/[0.06]",
        )}
        style={{ color: T.text }}
      >
        {format === "aligned" ? (
          <span style={{ color: dropped ? T.warn : T.text }}>
            {toText(sample, "aligned")}
          </span>
        ) : (
          <span style={{ color: dropped ? T.warn : T.text }}>
            {toText(sample, format)}
          </span>
        )}
      </button>

      {/* expanded packet - every field, nothing derived, printed in place */}
      {open && (
        <div
          className="whitespace-pre-wrap border-l-2 px-3 py-1 leading-[18px]"
          style={{ borderColor: T.rule, color: T.dim, background: "rgba(255,255,255,0.03)" }}
        >
          {JSON.stringify(
            sample.finger_present === false
              ? { ...sample, temp_c: null, ambient_temp_c: null }
              : sample,
            null,
            2,
          )}
        </div>
      )}
    </>
  );
}

export function RawSensorStream({
  frozen,
  snapshot,
}: {
  frozen: boolean;
  snapshot: SensorSample[] | null;
}) {
  const liveSamples = useLiveStore((s) => s.samples);
  const samples = frozen && snapshot ? snapshot : liveSamples;

  const [height, setHeight] = useState(24);
  const [format, setFormat] = useState<Format>("aligned");
  const [expandedTs, setExpandedTs] = useState<number | null>(null);
  /** Hide everything at or before this stream time - the monitor's Clear. */
  const [clearedThrough, setClearedThrough] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  /**
   * Follow the tail. On by default, like the Arduino monitor's Autoscroll box,
   * and surfaced as a real control rather than hidden state - scrolling up
   * turns it off so you can read back without fighting the stream.
   */
  const [autoscroll, setAutoscroll] = useState(true);

  const viewportRef = useRef<HTMLDivElement>(null);
  /** Set while we scroll programmatically, so our own scroll event - which
   *  lands after the DOM update - isn't mistaken for the reader scrolling. */
  const selfScrolling = useRef(false);

  const printed = useMemo(() => {
    const kept =
      clearedThrough == null
        ? samples
        : samples.filter((s) => s.timestamp_ms > clearedThrough);
    return kept.slice(-MAX_SCROLLBACK);
  }, [samples, clearedThrough]);

  const latest = samples.length ? samples[samples.length - 1] : null;
  const recent = samples.slice(-DROPOUT_WINDOW);
  // A null bpm is a real PPG dropout the validity gate counts - surface it
  // rather than hiding it, since >30% in a window suppresses the emit entirely.
  const dropouts = recent.filter((s) => s.bpm == null).length;
  const newestTs = printed.length ? printed[printed.length - 1].timestamp_ms : null;

  // Pin to the tail as lines print. Layout effect so the jump happens in the
  // same frame the line appears - otherwise the console visibly judders.
  //
  // Keyed on the newest packet's timestamp, NOT on printed.length: the
  // scrollback is capped, so once it fills, length stops changing and a
  // length-keyed effect would silently stop firing while packets kept printing.
  useLayoutEffect(() => {
    if (!autoscroll) return;
    const el = viewportRef.current;
    if (!el) return;
    selfScrolling.current = true;
    el.scrollTop = el.scrollHeight;
  }, [newestTs, autoscroll, format, height, expandedTs]);

  useEffect(() => {
    if (!copied) return;
    const id = window.setTimeout(() => setCopied(false), 1400);
    return () => window.clearTimeout(id);
  }, [copied]);

  const handleScroll = () => {
    const el = viewportRef.current;
    if (!el) return;
    if (selfScrolling.current) {
      // Our own pin-to-bottom, not the reader - consume it and keep following.
      selfScrolling.current = false;
      return;
    }
    // A slack of one line: a packet printing while pinned leaves us exactly one
    // line-height off the bottom, which must not read as "the reader left".
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= LINE_H + 6;
    setAutoscroll(atBottom);
  };

  const jumpToLatest = () => {
    const el = viewportRef.current;
    if (el) {
      selfScrolling.current = true;
      el.scrollTop = el.scrollHeight;
    }
    setAutoscroll(true);
  };

  const copyBuffer = async () => {
    const body = printed.map((s) => toText(s, format)).join("\n");
    const text = format === "csv" ? `${CSV_HEADER}\n${body}` : body;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      // Clipboard denied (insecure origin / permission) - the console is still
      // selectable text, so fail quiet rather than throwing up an error.
    }
  };

  return (
    <div className="mt-4 px-5 pb-5">
      <div
        className="overflow-hidden rounded-[2px] border-2"
        style={{ borderColor: T.rule, background: T.bg }}
      >
        {/* monitor chrome - port state left, output controls right */}
        <div
          className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b px-3 py-2 font-mono text-[11px]"
          style={{ borderColor: T.rule, background: T.chrome }}
        >
          <span className="inline-flex items-center gap-1.5" style={{ color: frozen ? T.warn : T.ok }}>
            <Circle
              className={cn("h-2 w-2 fill-current", !frozen && "animate-pulse-soft")}
              aria-hidden
            />
            {frozen ? "PAUSED" : "STREAMING"}
          </span>
          <span style={{ color: T.dim }}>1 Hz</span>
          <span style={{ color: T.dim }}>
            t={latest ? fmtStreamClock(latest.timestamp_ms) : "--:--"}
          </span>
          <span style={{ color: dropouts > 0 ? T.warn : T.dim }}>
            dropouts {dropouts}/{recent.length}
          </span>

          <div className="ml-auto flex flex-wrap items-center gap-1.5">
            <div
              role="group"
              aria-label="Output format"
              className="flex overflow-hidden rounded-[2px] border"
              style={{ borderColor: T.rule }}
            >
              {FORMATS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setFormat(f.id)}
                  aria-pressed={format === f.id}
                  className="cursor-pointer px-2 py-0.5 transition-colors"
                  style={{
                    background: format === f.id ? T.accent : "transparent",
                    color: format === f.id ? T.bg : T.dim,
                  }}
                >
                  {f.label}
                </button>
              ))}
            </div>

            <div
              role="group"
              aria-label="Console height in lines"
              className="flex overflow-hidden rounded-[2px] border"
              style={{ borderColor: T.rule }}
            >
              {HEIGHT_CHOICES.map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setHeight(n)}
                  aria-pressed={height === n}
                  className="cursor-pointer px-2 py-0.5 tabular-nums transition-colors"
                  style={{
                    background: height === n ? T.accent : "transparent",
                    color: height === n ? T.bg : T.dim,
                  }}
                >
                  {n}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={() => (autoscroll ? setAutoscroll(false) : jumpToLatest())}
              aria-pressed={autoscroll}
              title="Follow the newest line"
              className="inline-flex cursor-pointer items-center gap-1 rounded-[2px] border px-2 py-0.5 transition-colors"
              style={{
                borderColor: autoscroll ? T.accent : T.rule,
                background: autoscroll ? T.accent : "transparent",
                color: autoscroll ? T.bg : T.dim,
              }}
            >
              <ArrowDownToLine className="h-3 w-3" aria-hidden />
              autoscroll
            </button>

            <button
              type="button"
              onClick={copyBuffer}
              className="inline-flex cursor-pointer items-center gap-1 rounded-[2px] border px-2 py-0.5 transition-colors"
              style={{ borderColor: T.rule, color: copied ? T.ok : T.dim }}
            >
              {copied ? (
                <Check className="h-3 w-3" aria-hidden />
              ) : (
                <Copy className="h-3 w-3" aria-hidden />
              )}
              {copied ? "copied" : "copy"}
            </button>

            <button
              type="button"
              onClick={() => {
                setClearedThrough(latest?.timestamp_ms ?? null);
                setExpandedTs(null);
              }}
              className="inline-flex cursor-pointer items-center gap-1 rounded-[2px] border px-2 py-0.5 transition-colors"
              style={{ borderColor: T.rule, color: T.dim }}
            >
              <Eraser className="h-3 w-3" aria-hidden />
              clear
            </button>
          </div>
        </div>

        {/* the console */}
        <div className="relative">
          <div
            ref={viewportRef}
            onScroll={handleScroll}
            role="log"
            aria-live="off"
            aria-label="Raw sensor packet console"
            tabIndex={0}
            className="overflow-auto px-3 py-2 font-mono text-[11px] leading-[18px]"
            style={{ height: height * LINE_H + 16, color: T.text }}
          >
            {/* banner - printed once, like a monitor announcing the port */}
            <div style={{ color: T.dim }} className="whitespace-pre">
              {`# raw sensor stream · 1 Hz · unprocessed packets\n`}
              {format === "csv" ? `# ${CSV_HEADER}\n` : ""}
            </div>

            {printed.length === 0 ? (
              <div style={{ color: T.dim }}>
                {clearedThrough != null
                  ? "# cleared - waiting for the next packet…"
                  : "# waiting for the first sensor packet…"}
              </div>
            ) : (
              printed.map((s) => (
                <Line
                  key={s.timestamp_ms}
                  sample={s}
                  format={format}
                  fresh={!frozen && s.timestamp_ms === newestTs}
                  open={expandedTs === s.timestamp_ms}
                  onToggle={() =>
                    setExpandedTs(expandedTs === s.timestamp_ms ? null : s.timestamp_ms)
                  }
                />
              ))
            )}

            {/* caret - blinks only while the stream is actually running */}
            <div className="leading-[18px]" style={{ color: T.ok }}>
              <span aria-hidden>{"> "}</span>
              <span
                className={cn("inline-block", !frozen && "animate-caret-blink")}
                style={{ background: frozen ? "transparent" : T.ok, color: T.ok }}
                aria-hidden
              >
                {" "}
              </span>
            </div>
          </div>

          {/* follow is detached - offer the way back rather than yanking them */}
          {!autoscroll && (
            <button
              type="button"
              onClick={jumpToLatest}
              className="absolute bottom-2 right-3 inline-flex cursor-pointer items-center gap-1.5 rounded-[2px] border px-2 py-1 font-mono text-[11px] shadow-lg transition-colors"
              style={{ borderColor: T.accent, background: T.chrome, color: T.accent }}
            >
              <ArrowDownToLine className="h-3 w-3" aria-hidden />
              jump to latest
            </button>
          )}
        </div>
      </div>

    </div>
  );
}
