import { Card } from "@/components/primitives/Card";
import { cn } from "@/lib/cn";

export function SettingsSection({
  title,
  description,
  icon,
  prominent,
  compact,
  children,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  /** The most consequential setting on the screen - elevated surface + accent. */
  prominent?: boolean;
  /** A quiet, low-weight section (e.g. Account). */
  compact?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Card
      raised={prominent}
      className={cn(
        "relative overflow-hidden",
        prominent ? "p-6" : compact ? "p-4" : "p-5",
      )}
    >
      {prominent && (
        <span aria-hidden className="absolute inset-x-0 top-0 h-2 bg-clinical-accent" />
      )}
      <div className={cn("flex items-start gap-3", compact ? "mb-3" : "mb-4")}>
        {icon && (
          <span
            className={cn(
              "grid shrink-0 place-items-center rounded-none border-2 border-clinical-border bg-clinical-accent text-white",
              prominent ? "h-10 w-10" : "h-8 w-8",
            )}
          >
            {icon}
          </span>
        )}
        <div className="min-w-0">
          <h2
            className={cn(
              "font-semibold tracking-tight text-clinical-text",
              prominent ? "text-base" : "text-sm",
            )}
          >
            {title}
          </h2>
          {description && (
            <p className="mt-0.5 text-xs leading-relaxed text-clinical-faint">
              {description}
            </p>
          )}
        </div>
      </div>
      <div className="space-y-4">{children}</div>
    </Card>
  );
}
