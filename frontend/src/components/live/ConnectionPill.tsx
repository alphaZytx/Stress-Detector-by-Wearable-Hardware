import { Activity, Plug, RefreshCw, WifiOff } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatClock } from "@/lib/time";
import type { ConnectionStatus } from "@/stores/liveStore";
import { useLiveStore } from "@/stores/liveStore";

const CONFIG: Record<
  ConnectionStatus,
  { label: string; cls: string; Icon: typeof Plug }
> = {
  open: {
    label: "Connected",
    cls: "bg-clinical-success/12 text-clinical-success border-clinical-success/30",
    Icon: Plug,
  },
  connecting: {
    label: "Connecting…",
    cls: "bg-clinical-warning/12 text-clinical-warning border-clinical-warning/30",
    Icon: RefreshCw,
  },
  reconnecting: {
    label: "Reconnecting…",
    cls: "bg-clinical-warning/12 text-clinical-warning border-clinical-warning/30",
    Icon: RefreshCw,
  },
  closed: {
    label: "Disconnected",
    cls: "bg-clinical-danger/12 text-clinical-danger border-clinical-danger/30",
    Icon: WifiOff,
  },
  demo: {
    label: "Demo mode",
    cls: "bg-clinical-accent/12 text-clinical-accent border-clinical-accent/30",
    Icon: Activity,
  },
};

export function ConnectionPill() {
  const status = useLiveStore((s) => s.status);
  const lastMessageMs = useLiveStore((s) => s.lastMessageMs);
  const { label, cls, Icon } = CONFIG[status];
  const spinning = status === "connecting" || status === "reconnecting";

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-none border-2 px-3 py-1.5 text-xs font-bold uppercase tracking-wide",
        cls,
      )}
      role="status"
      aria-live="polite"
    >
      <Icon className={cn("h-3.5 w-3.5", spinning && "animate-spin")} aria-hidden />
      <span>{label}</span>
      {status === "closed" && lastMessageMs && (
        <span className="text-clinical-muted">· last {formatClock(lastMessageMs)}</span>
      )}
    </div>
  );
}
