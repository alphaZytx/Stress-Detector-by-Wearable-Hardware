import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowDownRight, ArrowRight, HeartPulse, RotateCcw } from "lucide-react";
import { cssVar } from "@/design/tokens";
import { Button } from "@/components/primitives/Button";
import { BreathingCircle } from "@/components/wellness/BreathingCircle";
import { AuroraBackground } from "@/components/decorative/AuroraBackground";
import { CYCLE_OPTIONS, PATTERNS, patternById } from "@/lib/breathing";
import { cn } from "@/lib/cn";
import { fmtBpm } from "@/lib/format";
import { useLiveStore } from "@/stores/liveStore";

type Mode = "setup" | "running" | "done";

/** Small inline glyph that visualises a pattern's rhythm as concentric rings. */
function PatternGlyph({ count, active }: { count: number; active: boolean }) {
  const stroke = active ? "var(--wellness-accent)" : "var(--wellness-faint)";
  return (
    <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
      {Array.from({ length: count }).map((_, i) => (
        <circle
          key={i}
          cx="16"
          cy="16"
          r={5 + i * 4.5}
          fill="none"
          stroke={stroke}
          strokeWidth={active ? 1.6 : 1.2}
          opacity={1 - i * 0.22}
        />
      ))}
    </svg>
  );
}

export function Breathing() {
  const [patternId, setPatternId] = useState("box");
  const [cycleTarget, setCycleTarget] = useState<number>(5);
  const [mode, setMode] = useState<Mode>("setup");
  const [completed, setCompleted] = useState(0);

  const latest = useLiveStore((s) => s.latestSample);
  const hrSeriesRef = useRef<{ t: number; bpm: number }[]>([]);
  const [hrSeries, setHrSeries] = useState<{ t: number; bpm: number }[]>([]);
  const startTimeRef = useRef(0);

  const pattern = patternById(patternId);
  const connected =
    useLiveStore((s) => s.status) === "open" ||
    useLiveStore.getState().status === "demo";

  // Collect HR while running.
  useEffect(() => {
    if (mode !== "running") return;
    if (latest?.bpm != null) {
      hrSeriesRef.current.push({
        t: Math.round((Date.now() - startTimeRef.current) / 1000),
        bpm: latest.bpm,
      });
    }
  }, [latest, mode]);

  const begin = () => {
    hrSeriesRef.current = [];
    startTimeRef.current = Date.now();
    setCompleted(0);
    setMode("running");
  };

  const finish = useCallback(() => {
    setHrSeries(hrSeriesRef.current.slice());
    setMode("done");
  }, []);

  const handleCycle = useCallback(
    (done: number) => {
      setCompleted(done);
      if (cycleTarget > 0 && done >= cycleTarget) finish();
    },
    [cycleTarget, finish],
  );

  // ---------------- RUNNING ----------------
  if (mode === "running") {
    return (
      <div className="relative min-h-full overflow-hidden">
        <AuroraBackground />
        <div className="relative z-10 mx-auto flex min-h-full max-w-xl flex-col items-center justify-center px-6 py-12">
          <div className="eyebrow mb-1 text-wellness-faint">
            {pattern.name}
          </div>
          <div className="mb-6 text-sm text-wellness-muted">
            {cycleTarget > 0
              ? `cycle ${Math.min(completed + 1, cycleTarget)} of ${cycleTarget}`
              : `cycle ${completed + 1}`}
          </div>

          <BreathingCircle pattern={pattern} running onCycleComplete={handleCycle} />

          {connected && latest?.bpm != null && (
            <div className="mt-8 inline-flex items-center gap-2 rounded-none border-2 border-clinical-border bg-clinical-surface px-4 py-2 text-sm text-clinical-muted shadow-card">
              <HeartPulse className="h-4 w-4 text-clinical-accent" aria-hidden />
              <span className="tnum text-base font-semibold text-wellness-text">
                {fmtBpm(latest.bpm)}
              </span>
              <span className="text-wellness-faint">bpm</span>
            </div>
          )}

          <button
            onClick={finish}
            className="mt-8 text-sm font-medium text-wellness-muted underline-offset-4 transition-colors hover:text-wellness-text hover:underline cursor-pointer"
          >
            End session
          </button>
        </div>
      </div>
    );
  }

  // ---------------- DONE ----------------
  if (mode === "done") {
    const first = hrSeries.find((p) => p.bpm != null)?.bpm ?? null;
    const last = [...hrSeries].reverse().find((p) => p.bpm != null)?.bpm ?? null;
    const delta = first != null && last != null ? last - first : null;
    const accent = cssVar("--wellness-accent") || "#0891b2";
    const muted = cssVar("--wellness-muted") || "#0e7490";
    return (
      <div className="relative min-h-full overflow-hidden">
        <AuroraBackground />
        <div className="relative z-10 mx-auto flex min-h-full max-w-lg flex-col items-center justify-center px-6 py-16 text-center animate-fade-in-slow">
          <div className="surface-glass w-full rounded-2xl p-8">
            <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-none border-2 border-clinical-border bg-clinical-accent text-white shadow-card">
              <svg viewBox="0 0 24 24" className="h-7 w-7" fill="none" aria-hidden>
                <path
                  d="M5 12.5l4 4 10-10"
                  stroke="currentColor"
                  strokeWidth="2.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <h1 className="text-hero font-semibold text-wellness-text">
              Session complete
            </h1>
            <p className="mt-2 text-wellness-muted">
              {completed} {completed === 1 ? "cycle" : "cycles"} of {pattern.name}{" "}
              breathing.
            </p>

            {first != null && last != null ? (
              <div className="mt-7 flex items-end justify-center gap-5">
                <div className="text-center">
                  <div className="eyebrow text-wellness-faint">Start</div>
                  <div className="tnum text-stat font-bold text-wellness-text">
                    {fmtBpm(first)}
                  </div>
                </div>
                <ArrowRight className="mb-3 h-5 w-5 text-wellness-faint" aria-hidden />
                <div className="text-center">
                  <div className="eyebrow text-wellness-faint">End</div>
                  <div className="tnum text-stat font-bold text-wellness-accent">
                    {fmtBpm(last)}
                  </div>
                </div>
                {delta != null && (
                  <div
                    className={cn(
                      "mb-2 inline-flex items-center gap-1 rounded-none border-2 border-clinical-border px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-white",
                      delta <= 0 ? "bg-clinical-success" : "bg-clinical-warning",
                    )}
                  >
                    {delta <= 0 && <ArrowDownRight className="h-3.5 w-3.5" aria-hidden />}
                    {delta > 0 ? "+" : ""}
                    {delta} bpm
                  </div>
                )}
              </div>
            ) : (
              <p className="mt-5 text-sm text-wellness-faint">
                No heart-rate data was available during this session.
              </p>
            )}

            {hrSeries.length > 1 && (
              <div className="mt-7 h-36 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={hrSeries} margin={{ top: 6, right: 6, bottom: 0, left: -18 }}>
                    <defs>
                      <linearGradient id="breathHr" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={accent} stopOpacity={0.35} />
                        <stop offset="100%" stopColor={accent} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="t" tick={{ fill: muted, fontSize: 10 }} tickFormatter={(v) => `${v}s`} stroke="transparent" />
                    <YAxis domain={["dataMin - 4", "dataMax + 4"]} tick={{ fill: muted, fontSize: 10 }} width={30} stroke="transparent" />
                    <Area type="monotone" dataKey="bpm" stroke={accent} strokeWidth={2.5} fill="url(#breathHr)" dot={false} isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          <div className="mt-7 flex gap-3">
            <Button variant="secondary" onClick={() => setMode("setup")}>
              <RotateCcw className="h-4 w-4" aria-hidden />
              New session
            </Button>
            <Link to="/live">
              <Button variant="wellness">
                Back to live
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ---------------- SETUP ----------------
  return (
    <div className="relative min-h-full overflow-hidden">
      <AuroraBackground />
      <div className="relative z-10 mx-auto flex min-h-full max-w-lg flex-col items-center justify-center px-6 py-16 text-center animate-fade-in">
        <div className="eyebrow mb-2 text-wellness-faint">Breathe</div>
        <h1 className="text-hero font-semibold text-wellness-text">
          Breathing exercise
        </h1>
        <p className="mt-2 max-w-sm text-wellness-muted">
          Choose a pattern and let the circle guide your breath.
        </p>

        <div className="mt-9 w-full text-left">
          <div className="eyebrow mb-3 text-wellness-faint">Pattern</div>
          <div className="grid grid-cols-3 gap-3">
            {PATTERNS.map((p) => {
              const active = patternId === p.id;
              return (
                <button
                  key={p.id}
                  onClick={() => setPatternId(p.id)}
                  className={cn(
                    "group rounded-none border-2 p-4 text-left transition-all duration-100 cursor-pointer",
                    active
                      ? "-translate-x-[2px] -translate-y-[2px] border-clinical-accent bg-clinical-surface shadow-card"
                      : "border-clinical-border bg-clinical-surface hover:-translate-x-[2px] hover:-translate-y-[2px] hover:shadow-card",
                  )}
                >
                  <PatternGlyph count={p.phases.length} active={active} />
                  <div className="mt-3 text-sm font-semibold text-wellness-text">
                    {p.name}
                  </div>
                  <div className="mt-1 text-xs leading-snug text-wellness-faint">
                    {p.description}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-7 w-full text-left">
          <div className="eyebrow mb-3 text-wellness-faint">Cycles</div>
          <div className="flex gap-2">
            {CYCLE_OPTIONS.map((c) => (
              <button
                key={c}
                onClick={() => setCycleTarget(c)}
                className={cn(
                  "flex-1 rounded-none border-2 py-2.5 text-sm font-bold uppercase tracking-wide transition-all duration-100 cursor-pointer",
                  cycleTarget === c
                    ? "border-clinical-border bg-clinical-accent text-white shadow-card"
                    : "border-clinical-border bg-clinical-surface text-clinical-muted hover:-translate-x-[2px] hover:-translate-y-[2px] hover:shadow-card",
                )}
              >
                {c === 0 ? "Until I stop" : c}
              </button>
            ))}
          </div>
        </div>

        <Button variant="wellness" size="lg" className="mt-9 px-8 shadow-glow" onClick={begin}>
          Start breathing
          <ArrowRight className="h-4 w-4" aria-hidden />
        </Button>
      </div>
    </div>
  );
}
