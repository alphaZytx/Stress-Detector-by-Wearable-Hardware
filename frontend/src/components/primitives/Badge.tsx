import { cn } from "@/lib/cn";

type Tone = "neutral" | "success" | "warning" | "danger" | "accent";

const TONE: Record<Tone, string> = {
  neutral: "bg-clinical-surface-2 text-clinical-text border-clinical-border",
  success: "bg-clinical-success text-white border-clinical-border",
  warning: "bg-clinical-warning text-white border-clinical-border",
  danger: "bg-clinical-danger text-white border-clinical-border",
  accent: "bg-clinical-accent text-white border-clinical-border",
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-none border-2 px-2 py-0.5 text-xs font-bold uppercase tracking-wide",
        TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
