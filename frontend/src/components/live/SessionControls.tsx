import { useState } from "react";
import { Circle, Square } from "lucide-react";
import { Button } from "@/components/primitives/Button";
import { Dialog } from "@/components/primitives/Dialog";
import { Input } from "@/components/primitives/Input";
import { useRecording } from "@/hooks/useRecording";
import { formatElapsed } from "@/lib/time";
import { useLiveStore } from "@/stores/liveStore";

export function SessionControls() {
  const status = useLiveStore((s) => s.status);
  const { isRecording, elapsedMs, busy, start, stop } = useRecording();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");

  const isDemo = status === "demo";
  const disconnected = status !== "open" && !isDemo;
  const startDisabled = isDemo || disconnected || busy;

  const confirmStart = async () => {
    await start(label.trim() || undefined, notes.trim() || undefined);
    setDialogOpen(false);
    setLabel("");
    setNotes("");
  };

  return (
    <div className="surface-card flex items-center justify-between gap-4 rounded-2xl px-5 py-3.5">
      <div className="flex items-center gap-3">
        {isRecording ? (
          <span className="flex items-center gap-2 text-sm font-medium text-clinical-danger">
            <Circle className="h-3 w-3 animate-pulse-soft fill-current" aria-hidden />
            Recording · {formatElapsed(elapsedMs)}
          </span>
        ) : (
          <span className="text-sm text-clinical-muted">
            {isDemo
              ? "Recording is disabled in demo mode"
              : disconnected
                ? "Connect to start recording"
                : "Not recording"}
          </span>
        )}
      </div>

      {isRecording ? (
        <Button variant="danger" onClick={stop} loading={busy}>
          <Square className="h-4 w-4" aria-hidden />
          Stop recording
        </Button>
      ) : (
        <span title={isDemo ? "Disabled in demo mode" : undefined}>
          <Button
            variant="primary"
            disabled={startDisabled}
            onClick={() => setDialogOpen(true)}
          >
            <Circle className="h-4 w-4" aria-hidden />
            Start recording
          </Button>
        </span>
      )}

      <Dialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        title="Start a recording"
        description="Optionally label this session so you can find it later."
      >
        <div className="flex flex-col gap-4">
          <Input
            label="Label (optional)"
            placeholder="e.g. Morning baseline"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
          <Input
            label="Notes (optional)"
            placeholder="Context for this session"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <div className="mt-1 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={confirmStart} loading={busy}>
              Start
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
