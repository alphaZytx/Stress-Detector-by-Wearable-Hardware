import { PageHeader } from "@/components/layout/PageHeader";
import { ConnectionPill } from "@/components/live/ConnectionPill";
import { GaugeRow } from "@/components/live/GaugeRow";
import { RawSensorStream } from "@/components/live/RawSensorStream";

/**
 * Sensor-only dashboard. It uses the main service's WebSocket, so the serial
 * device has one owner while both this page and stress inference see the same
 * live packets.
 */
export function Sensors() {
  return (
    <div className="flex h-full flex-col">
      <PageHeader
        eyebrow="Hardware"
        title="Live sensor data"
        subtitle="Unprocessed readings from the connected wearable"
        right={<ConnectionPill />}
      />

      <div className="flex-1 space-y-4 p-6">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-12">
          <GaugeRow forceAll />
        </div>

        <section className="surface-card rounded-2xl pt-5">
          <div className="px-5">
            <div className="eyebrow">Reading section</div>
            <h2 className="font-display text-sm font-semibold text-clinical-text">
              Live serial packets
            </h2>
            <p className="mt-1 text-xs text-clinical-muted">
              Object temperature and SpO2 are hidden whenever finger contact is not detected.
              Ambient temperature remains visible.
            </p>
          </div>
          <RawSensorStream frozen={false} snapshot={null} />
        </section>
      </div>
    </div>
  );
}
