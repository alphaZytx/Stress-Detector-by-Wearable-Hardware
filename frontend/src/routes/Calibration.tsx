import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  Droplets,
  HeartPulse,
  Sparkles,
  Thermometer,
  TriangleAlert,
} from "lucide-react";
import type { SensorSample } from "@/api/types";
import { Button } from "@/components/primitives/Button";
import { ProgressRing } from "@/components/wellness/ProgressRing";
import { AuroraBackground } from "@/components/decorative/AuroraBackground";
import { useSetCalibration } from "@/hooks/useSessions";
import { computeCalibration, type CalibrationResult } from "@/lib/calibration";
import { fmt, fmtBpm, fmtTemp } from "@/lib/format";
import { formatMmSs } from "@/lib/time";
import { useLiveStore } from "@/stores/liveStore";

type Step = "welcome" | "capture" | "confirm" | "success";
const DEFAULT_CAPTURE_S = 120;

function WellnessShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative min-h-full overflow-hidden">
      <AuroraBackground />
      <div className="relative z-10 mx-auto flex min-h-full max-w-xl flex-col items-center justify-center px-6 py-16 text-center animate-fade-in">
        {children}
      </div>
    </div>
  );
}

function MiniStat({
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
    <div className="surface-glass flex flex-col items-center gap-1.5 rounded-xl px-4 py-4">
      <span className="flex items-center gap-1.5 text-wellness-accent">
        {icon}
        <span className="eyebrow !text-wellness-faint">{label}</span>
      </span>
      <span className="tnum text-2xl font-bold text-wellness-text">
        {value}
        <span className="ml-0.5 text-xs font-normal text-wellness-faint">{unit}</span>
      </span>
    </div>
  );
}

export function Calibration() {
  const [params] = useSearchParams();
  // Dev/test-only fast capture so e2e doesn't wait 2 minutes; production uses 120s.
  const captureS =
    import.meta.env.DEV && params.get("dev_seconds")
      ? Math.max(2, Number(params.get("dev_seconds")))
      : DEFAULT_CAPTURE_S;

  const [step, setStep] = useState<Step>("welcome");
  const [remaining, setRemaining] = useState(captureS);
  const [result, setResult] = useState<CalibrationResult | null>(null);

  const latest = useLiveStore((s) => s.latestSample);
  const setCalibration = useSetCalibration();
  const qc = useQueryClient();

  const capturedRef = useRef<Map<number, SensorSample>>(new Map());

  // Collect unique samples while capturing.
  useEffect(() => {
    if (step !== "capture") return;
    const unsub = useLiveStore.subscribe((s) => {
      const sample = s.latestSample;
      if (sample) capturedRef.current.set(sample.timestamp_ms, sample);
    });
    return unsub;
  }, [step]);

  // Countdown.
  useEffect(() => {
    if (step !== "capture") return;
    const startedAt = Date.now();
    const id = window.setInterval(() => {
      const elapsed = (Date.now() - startedAt) / 1000;
      const left = Math.max(0, captureS - elapsed);
      setRemaining(left);
      if (left <= 0) {
        window.clearInterval(id);
        const samples = [...capturedRef.current.values()];
        setResult(computeCalibration(samples));
        setStep("confirm");
      }
    }, 250);
    return () => window.clearInterval(id);
  }, [step, captureS]);

  const begin = () => {
    capturedRef.current = new Map();
    setRemaining(captureS);
    setResult(null);
    setStep("capture");
  };

  const save = async () => {
    if (!result) return;
    await setCalibration.mutateAsync({
      hr_baseline: result.hr?.mean ?? null,
      gsr_baseline: result.gsr.mean,
      temp_baseline: result.temp?.mean ?? null,
      extra: {
        captured_seconds: captureS,
        hr_std: result.hr?.std ?? null,
        gsr_std: result.gsr.std,
        temp_std: result.temp?.std ?? null,
      },
    });
    await qc.invalidateQueries({ queryKey: ["calibration"] });
    setStep("success");
  };

  if (step === "welcome")
    return (
      <WellnessShell>
        <span
          className="mb-6 grid h-20 w-20 place-items-center rounded-none border-2 border-clinical-border bg-clinical-accent text-white shadow-md"
        >
          <Sparkles className="h-9 w-9" aria-hidden />
        </span>
        <div className="eyebrow mb-2 text-wellness-faint">Calibration</div>
        <h1 className="text-hero font-semibold text-wellness-text">
          Let’s learn your baseline
        </h1>
        <p className="mt-3 max-w-md leading-relaxed text-wellness-muted">
          We’ll watch your resting biosignals for {formatMmSs(captureS)} to learn your
          personal baseline. Please sit comfortably and breathe normally - don’t
          stress, exercise, or move much during this time.
        </p>
        <Button variant="wellness" size="lg" className="mt-8 px-8 shadow-glow" onClick={begin}>
          Begin
          <ArrowRight className="h-4 w-4" aria-hidden />
        </Button>
      </WellnessShell>
    );

  if (step === "capture")
    return (
      <WellnessShell>
        <div className="eyebrow mb-2 text-wellness-faint">Capturing baseline</div>
        <p className="mb-9 text-wellness-muted">
          Breathe normally. Stay relaxed and still.
        </p>
        <ProgressRing progress={(captureS - remaining) / captureS}>
          <div className="text-center">
            <div className="tnum text-stat-lg font-bold text-wellness-text">
              {formatMmSs(remaining)}
            </div>
            <div className="eyebrow mt-1 text-wellness-faint">remaining</div>
          </div>
        </ProgressRing>
        <div className="mt-10 grid grid-cols-3 gap-3">
          <MiniStat
            icon={<HeartPulse className="h-3.5 w-3.5" aria-hidden />}
            label="HR"
            value={fmtBpm(latest?.bpm)}
            unit="bpm"
          />
          <MiniStat
            icon={<Droplets className="h-3.5 w-3.5" aria-hidden />}
            label="GSR"
            value={fmt(latest?.gsr, 0)}
            unit=""
          />
          <MiniStat
            icon={<Thermometer className="h-3.5 w-3.5" aria-hidden />}
            label="Temp"
            value={fmtTemp(latest?.temp_c)}
            unit="°C"
          />
        </div>
      </WellnessShell>
    );

  if (step === "confirm" && result)
    return (
      <WellnessShell>
        <div className="eyebrow mb-2 text-wellness-faint">Result</div>
        <h1 className="text-hero font-semibold text-wellness-text">Your baseline</h1>
        <p className="mt-2 text-wellness-muted">
          Measured over {formatMmSs(captureS)} of rest.
        </p>

        {result.warnings.length > 0 && (
          <div className="mt-5 w-full rounded-lg border border-clinical-warning/30 bg-clinical-warning/10 p-4 text-left">
            <div className="mb-1 flex items-center gap-2 text-sm font-medium text-clinical-warning">
              <TriangleAlert className="h-4 w-4" aria-hidden />
              Capture quality issues
            </div>
            <ul className="list-disc pl-5 text-sm text-clinical-warning">
              {result.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-6 grid w-full grid-cols-3 gap-3">
          <MiniStat
            icon={<HeartPulse className="h-3.5 w-3.5" aria-hidden />}
            label="HR"
            value={result.hr ? `${result.hr.mean.toFixed(0)}±${result.hr.std.toFixed(0)}` : "-"}
            unit="bpm"
          />
          <MiniStat
            icon={<Droplets className="h-3.5 w-3.5" aria-hidden />}
            label="GSR"
            value={`${result.gsr.mean.toFixed(0)}±${result.gsr.std.toFixed(0)}`}
            unit=""
          />
          <MiniStat
            icon={<Thermometer className="h-3.5 w-3.5" aria-hidden />}
            label="Temp"
            value={result.temp ? `${result.temp.mean.toFixed(1)}±${result.temp.std.toFixed(1)}` : "-"}
            unit="°C"
          />
        </div>

        <div className="mt-8 flex gap-3">
          <Button variant="secondary" onClick={begin}>
            Try again
          </Button>
          <Button
            variant="wellness"
            onClick={save}
            loading={setCalibration.isPending}
            disabled={!result.ok && captureS >= DEFAULT_CAPTURE_S}
          >
            Save baseline
          </Button>
        </div>
      </WellnessShell>
    );

  return (
    <WellnessShell>
      <span className="mb-6 grid h-20 w-20 place-items-center rounded-none border-2 border-clinical-border bg-clinical-accent text-white shadow-md">
        <CheckCircle2 className="h-9 w-9" aria-hidden />
      </span>
      <div className="eyebrow mb-2 text-wellness-faint">All set</div>
      <h1 className="text-hero font-semibold text-wellness-text">Calibration saved</h1>
      <p className="mt-3 max-w-md leading-relaxed text-wellness-muted">
        Your personal baseline is now active. New recordings will interpret your
        biosignals relative to this resting state.
      </p>
      <Link to="/live" className="mt-8">
        <Button variant="wellness" size="lg">
          Back to live
          <ArrowRight className="h-4 w-4" aria-hidden />
        </Button>
      </Link>
    </WellnessShell>
  );
}
