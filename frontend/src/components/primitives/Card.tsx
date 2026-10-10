import { cn } from "@/lib/cn";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Wellness surface treatment (frosted glass on aurora) vs clinical soft-UI. */
  wellness?: boolean;
  /** The single elevated "hero" card per screen - stronger surface + shadow. */
  raised?: boolean;
}

export function Card({ className, wellness, raised, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-2xl",
        wellness
          ? "surface-glass"
          : raised
            ? "surface-raised"
            : "surface-card",
        className,
      )}
      {...rest}
    />
  );
}

export function CardHeader({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3 px-5 pt-5">
      <div>
        <h3 className="font-display text-sm font-semibold tracking-tight text-clinical-text">
          {title}
        </h3>
        {subtitle && (
          <p className="mt-0.5 text-xs text-clinical-faint">{subtitle}</p>
        )}
      </div>
      {right}
    </div>
  );
}
