import { Loader2, SatelliteDish } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { BpmChart } from "@/components/live/BpmChart";
import { ConnectionPill } from "@/components/live/ConnectionPill";
import { GaugeRow } from "@/components/live/GaugeRow";
import { HrvPanel } from "@/components/live/HrvPanel";
import { ModelInputPanel } from "@/components/live/ModelInputPanel";
import { SessionControls } from "@/components/live/SessionControls";
import { StressAlertBanner } from "@/components/live/StressAlertBanner";
import { StressDial } from "@/components/live/StressDial";
import { useLiveStore } from "@/stores/liveStore";

/**
 * Live monitoring - a bento command center. A radial stress dial anchors the
 * grid; the heart-rate waveform, HRV proxy, and per-sensor vital tiles fill the
 * remaining cells. Tiles re-flow responsively (12-col → 2-col).
 */
export function Live() {
  const status = useLiveStore((s) => s.status);
  const hasData = useLiveStore((s) => s.latestSample != null);
  const awaitingData = !hasData && status !== "open" && status !== "demo";

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        eyebrow="Monitoring"
        title="Live monitoring"
        subtitle="Real-time biosignals and stress level"
        right={<ConnectionPill />}
      />

      <div className="flex-1 space-y-4 p-6">
        {awaitingData && (
          <div className="surface-card flex items-center gap-3 rounded-2xl px-5 py-4">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-clinical-accent-soft text-clinical-accent">
              <SatelliteDish className="h-5 w-5" aria-hidden />
            </span>
            <div className="flex-1">
              <div className="text-sm font-medium text-clinical-text">
                Waiting for your device…
              </div>
              <div className="text-xs text-clinical-faint">
                Connecting to the live sensor stream. Data will appear automatically.
              </div>
            </div>
            <Loader2 className="h-4 w-4 animate-spin text-clinical-faint" aria-hidden />
          </div>
        )}

        <StressAlertBanner />

        {/* Bento grid: dial hero (tall) + waveform + HRV + 3 sensor tiles. */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-12 lg:[grid-auto-flow:row_dense]">
          <div className="col-span-2 lg:col-span-5 lg:row-span-2 lg:[&>*]:h-full">
            <StressDial />
          </div>
          <BpmChart className="col-span-2 lg:col-span-7" />
          <HrvPanel className="col-span-2 lg:col-span-7" />
          <GaugeRow />
        </div>

        <SessionControls />

        {/* The model's-eye view: pipeline strip + the live 18-feature vector. */}
        <ModelInputPanel />
      </div>
    </div>
  );
}
