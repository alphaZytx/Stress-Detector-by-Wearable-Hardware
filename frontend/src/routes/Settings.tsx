import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Download,
  Gauge,
  Info,
  PlayCircle,
  SlidersHorizontal,
  Target,
  User,
} from "lucide-react";
import { downloadAllSessions } from "@/api/session";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/primitives/Badge";
import { Button } from "@/components/primitives/Button";
import { Slider } from "@/components/primitives/Slider";
import { Switch } from "@/components/primitives/Switch";
import { SettingsSection } from "@/components/settings/SettingsSection";
import { useAuth } from "@/hooks/useAuth";
import { useCalibration, useClearCalibration } from "@/hooks/useSessions";
import { fmt, fmtBpm, fmtPercent, fmtTemp } from "@/lib/format";
import { formatDateTime } from "@/lib/time";
import { modelLabel } from "@/lib/modelMeta";
import { useLiveStore } from "@/stores/liveStore";
import type { SensorVisibility } from "@/stores/settingsStore";
import { useSettingsStore } from "@/stores/settingsStore";

// Shown only until the first prediction arrives and names the live model.
const MODEL_FALLBACK = "svm (baseline)";
const FEATURE_COUNT = 18;

const SENSOR_LABELS: Record<keyof SensorVisibility, string> = {
  hr: "Heart rate",
  gsr: "GSR",
  temp: "Temperature",
};

/** Settings - a two-column control surface. The consequential Calibration panel
 * spans the top; the rest tile into a masonry grid. */
export function Settings() {
  const { user, logout } = useAuth();
  const { data: calibration } = useCalibration();
  // The served classifier is a backend config choice, so read it off the
  // stream rather than hard-coding an artifact name that can drift.
  const servedModel = useLiveStore((s) => s.latestPrediction?.model_type);
  const clearCalibration = useClearCalibration();

  const {
    useCalibration: useCal,
    setUseCalibration: setUseCal,
    sensors,
    setSensor,
    stressThreshold,
    setStressThreshold,
    demoMode,
    setDemoMode,
  } = useSettingsStore();

  const [exporting, setExporting] = useState(false);
  const exportAll = async () => {
    setExporting(true);
    try {
      await downloadAllSessions();
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <PageHeader eyebrow="Configuration" title="Settings" subtitle="Account, calibration, preferences" />

      <div className="flex-1 p-6">
        <div className="mx-auto grid max-w-5xl gap-4 lg:grid-cols-2">
          {/* Calibration - hero, full width. */}
          <div className="lg:col-span-2">
            <SettingsSection
              title="Calibration"
              prominent
              icon={<Target className="h-5 w-5" aria-hidden />}
              description="Personalises inference by subtracting your resting baseline. Heuristic - may help or hurt; toggle per session."
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {calibration?.calibrated ? (
                    <Badge tone="success">Calibrated</Badge>
                  ) : (
                    <Badge tone="neutral">Not calibrated</Badge>
                  )}
                  {calibration?.calibrated && calibration.captured_at_ms && (
                    <span className="text-xs text-clinical-muted">
                      {formatDateTime(calibration.captured_at_ms)}
                    </span>
                  )}
                </div>
                <Link to="/calibration">
                  <Button variant="secondary" size="sm">
                    <Target className="h-4 w-4" aria-hidden />
                    {calibration?.calibrated ? "Re-calibrate" : "Calibrate"}
                  </Button>
                </Link>
              </div>

              {calibration?.calibrated && (
                <div className="grid grid-cols-3 gap-3 rounded-xl bg-clinical-surface-2 p-3 text-center">
                  <div>
                    <div className="text-xs text-clinical-muted">HR</div>
                    <div className="tnum text-sm font-semibold text-clinical-text">
                      {fmtBpm(calibration.hr_baseline)} bpm
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-clinical-muted">GSR</div>
                    <div className="tnum text-sm font-semibold text-clinical-text">
                      {fmt(calibration.gsr_baseline, 0)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-clinical-muted">Temp</div>
                    <div className="tnum text-sm font-semibold text-clinical-text">
                      {fmtTemp(calibration.temp_baseline)} °C
                    </div>
                  </div>
                </div>
              )}

              <Switch
                id="use-calibration"
                label="Apply calibration to new sessions"
                description="When on, recordings interpret signals relative to your baseline."
                checked={useCal}
                onCheckedChange={setUseCal}
              />

              {calibration?.calibrated && (
                <Button
                  variant="ghost"
                  size="sm"
                  loading={clearCalibration.isPending}
                  onClick={() => clearCalibration.mutate()}
                  className="text-clinical-danger"
                >
                  Clear calibration
                </Button>
              )}
            </SettingsSection>
          </div>

          <SettingsSection title="Account" compact icon={<User className="h-4 w-4" aria-hidden />}>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-clinical-text">
                  {user?.display_name || "-"}
                </div>
                <div className="text-xs text-clinical-faint">{user?.email}</div>
              </div>
              <Button variant="secondary" size="sm" onClick={logout}>
                Log out
              </Button>
            </div>
          </SettingsSection>

          <SettingsSection
            title="Stress sensitivity"
            icon={<Gauge className="h-4 w-4" aria-hidden />}
            description="P(stress) threshold for the breathing auto-trigger prompt."
          >
            <div className="flex items-center gap-4">
              <Slider
                value={stressThreshold}
                min={0.5}
                max={0.95}
                step={0.05}
                label="Stress threshold"
                onValueChange={setStressThreshold}
              />
              <span className="tnum w-12 text-right text-sm font-semibold text-clinical-text">
                {fmtPercent(stressThreshold)}
              </span>
            </div>
          </SettingsSection>

          <SettingsSection
            title="Live view preferences"
            icon={<SlidersHorizontal className="h-4 w-4" aria-hidden />}
            description="Choose which sensor gauges to display on the Live view."
          >
            {(Object.keys(SENSOR_LABELS) as (keyof SensorVisibility)[]).map((key) => (
              <Switch
                key={key}
                id={`sensor-${key}`}
                label={SENSOR_LABELS[key]}
                checked={sensors[key]}
                onCheckedChange={(on) => setSensor(key, on)}
              />
            ))}
          </SettingsSection>

          <SettingsSection
            title="Demo mode"
            icon={<PlayCircle className="h-4 w-4" aria-hidden />}
            description="Replay a canned baseline→stress→recovery session instead of the live stream - useful for demos without the wearable. Recording is disabled in demo mode."
          >
            <Switch
              id="demo-mode"
              label="Enable demo mode"
              description={demoMode ? "Replaying the canned session." : "Off - using the live stream."}
              checked={demoMode}
              onCheckedChange={setDemoMode}
            />
          </SettingsSection>

          <SettingsSection
            title="Data export"
            compact
            icon={<Download className="h-4 w-4" aria-hidden />}
            description="Download every session as a ZIP of JSON files."
          >
            <Button variant="secondary" loading={exporting} onClick={exportAll}>
              <Download className="h-4 w-4" aria-hidden />
              Export all sessions (ZIP)
            </Button>
          </SettingsSection>

          <SettingsSection title="About" compact icon={<Info className="h-4 w-4" aria-hidden />}>
            <dl className="grid grid-cols-2 gap-y-2 text-sm">
              <dt className="text-clinical-muted">Version</dt>
              <dd className="text-right text-clinical-text">0.1.0 (Phase 3)</dd>
              <dt className="text-clinical-muted">Model</dt>
              <dd className="text-right text-clinical-text">
                {servedModel ? modelLabel(servedModel) : MODEL_FALLBACK}
              </dd>
              <dt className="text-clinical-muted">Features</dt>
              <dd className="text-right text-clinical-text">{FEATURE_COUNT}</dd>
            </dl>
          </SettingsSection>
        </div>
      </div>
    </div>
  );
}
