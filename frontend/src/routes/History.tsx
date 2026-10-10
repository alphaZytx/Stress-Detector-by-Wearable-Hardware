import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Clock,
  Download,
  FileJson,
  FileSpreadsheet,
  Inbox,
  MoreVertical,
  StickyNote,
  Trash2,
  Waves,
} from "lucide-react";
import type { SessionSummary } from "@/api/types";
import { downloadSessionExport } from "@/api/session";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/primitives/Badge";
import { Button } from "@/components/primitives/Button";
import { Card } from "@/components/primitives/Card";
import { Dialog } from "@/components/primitives/Dialog";
import { DropdownItem, DropdownMenu } from "@/components/primitives/DropdownMenu";
import { useDeleteSession, useSessions } from "@/hooks/useSessions";
import { formatDateTime, formatDuration } from "@/lib/time";
import { fmtPercent } from "@/lib/format";

/** Per-card dominant-state badge, driven by the server-computed summary fields
 * (no per-session export fetch). */
function StressBadge({
  state,
  pct,
}: {
  state: SessionSummary["dominant_state"];
  pct: number;
}) {
  if (state === null) return <Badge tone="neutral">no data</Badge>;
  return state === "stress" ? (
    <Badge tone="danger">stress {fmtPercent(pct)}</Badge>
  ) : (
    <Badge tone="success">baseline {fmtPercent(pct)}</Badge>
  );
}

function SessionCard({
  session,
  onOpen,
  onDelete,
}: {
  session: SessionSummary;
  onOpen: () => void;
  onDelete: () => void;
}) {
  return (
    <Card
      data-session-card
      onClick={onOpen}
      className="group relative flex cursor-pointer flex-col gap-4 p-5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate font-display text-base font-semibold tracking-tight text-clinical-text">
            {session.user_label || "Untitled session"}
          </div>
          <div className="mt-0.5 text-xs text-clinical-faint">
            {formatDateTime(session.started_at_ms)}
          </div>
        </div>
        <div onClick={(e) => e.stopPropagation()}>
          <DropdownMenu
            trigger={
              <button
                aria-label="Session actions"
                className="grid h-8 w-8 place-items-center rounded-lg text-clinical-muted transition-colors hover:bg-clinical-surface-2 hover:text-clinical-text cursor-pointer"
              >
                <MoreVertical className="h-4 w-4" aria-hidden />
              </button>
            }
          >
            <DropdownItem onSelect={() => downloadSessionExport(session.session_id, "json")}>
              <FileJson className="h-4 w-4" aria-hidden /> Export JSON
            </DropdownItem>
            <DropdownItem onSelect={() => downloadSessionExport(session.session_id, "csv")}>
              <FileSpreadsheet className="h-4 w-4" aria-hidden /> Export CSV
            </DropdownItem>
            <DropdownItem danger onSelect={onDelete}>
              <Trash2 className="h-4 w-4" aria-hidden /> Delete
            </DropdownItem>
          </DropdownMenu>
        </div>
      </div>

      <StressBadge state={session.dominant_state} pct={session.dominant_state_pct} />

      <div className="mt-auto flex flex-col gap-2 border-t border-clinical-border pt-3 text-sm">
        <div className="flex items-center gap-2 text-clinical-muted">
          <Clock className="h-3.5 w-3.5 shrink-0 text-clinical-faint" aria-hidden />
          <span className="tnum">{formatDuration(session.started_at_ms, session.ended_at_ms)}</span>
        </div>
        <div className="flex items-center gap-2 text-clinical-faint">
          <StickyNote className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className="truncate">{session.notes || "No notes"}</span>
        </div>
      </div>
    </Card>
  );
}

export function History() {
  const navigate = useNavigate();
  const { data: sessions, isLoading, error } = useSessions();
  const del = useDeleteSession();
  const [toDelete, setToDelete] = useState<SessionSummary | null>(null);

  return (
    <div className="flex h-full flex-col">
      <PageHeader eyebrow="Sessions" title="History" subtitle="Past recording sessions" />

      <div className="flex-1 p-6">
        {isLoading && <p className="text-sm text-clinical-muted">Loading sessions…</p>}
        {error && (
          <p className="text-sm text-clinical-danger">Failed to load sessions.</p>
        )}
        {sessions && sessions.length === 0 && (
          <div className="surface-card grid place-items-center rounded-2xl px-6 py-16 text-center">
            <span className="mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-clinical-accent-soft text-clinical-accent">
              <Inbox className="h-7 w-7" aria-hidden />
            </span>
            <h3 className="font-display text-base font-semibold text-clinical-text">No sessions yet</h3>
            <p className="mt-1 max-w-sm text-sm text-clinical-faint">
              Record your biosignals from the Live view and they’ll appear here with a
              stress timeline you can scrub and annotate.
            </p>
            <Link to="/live" className="mt-5">
              <Button>
                <Waves className="h-4 w-4" aria-hidden />
                Go to Live
              </Button>
            </Link>
          </div>
        )}

        {sessions && sessions.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {sessions.map((s) => (
              <SessionCard
                key={s.session_id}
                session={s}
                onOpen={() => navigate(`/history/${s.session_id}`)}
                onDelete={() => setToDelete(s)}
              />
            ))}
          </div>
        )}
      </div>

      <Dialog
        open={!!toDelete}
        onOpenChange={(o) => !o && setToDelete(null)}
        title="Delete session?"
        description="This permanently removes the session and all its samples, predictions, and annotations."
      >
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2 text-sm text-clinical-muted">
            <Download className="h-4 w-4" aria-hidden />
            Tip: export it first if you might need it.
          </span>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setToDelete(null)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            loading={del.isPending}
            onClick={async () => {
              if (toDelete) await del.mutateAsync(toDelete.session_id);
              setToDelete(null);
            }}
          >
            Delete
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
