import { cn } from "@/lib/cn";

/**
 * Brutalist backdrop - a flat engineering-grid plane (no gradients, no blur).
 * Decorative only: aria-hidden, pointer-events-none, behind content.
 * Kept under the original name so existing imports don't change.
 */
export function AuroraBackground({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
      style={{ background: "var(--wellness-bg-grad), var(--wellness-bg)" }}
    />
  );
}
