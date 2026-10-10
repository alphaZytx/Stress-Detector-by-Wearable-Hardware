import { forwardRef } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "wellness";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

// Bordered variants share the brutalist press: hard shadow that snaps shut when
// you click (translate into the shadow). `ghost` is the only flat/borderless one.
const PRESS =
  "border-2 border-clinical-border shadow-card hover:-translate-x-[2px] hover:-translate-y-[2px] hover:shadow-md active:translate-x-0 active:translate-y-0 active:shadow-none";

const VARIANT: Record<Variant, string> = {
  primary: `bg-clinical-accent text-white ${PRESS}`,
  secondary: `bg-clinical-surface text-clinical-text ${PRESS}`,
  ghost: "text-clinical-text border-2 border-transparent hover:bg-clinical-surface-2",
  danger: `bg-clinical-danger text-white ${PRESS}`,
  wellness: `bg-clinical-accent text-white ${PRESS}`,
};

const SIZE: Record<Size, string> = {
  sm: "h-9 px-4 text-xs",
  md: "h-11 px-5 text-sm",
  lg: "h-12 px-7 text-base",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "primary", size = "md", loading, disabled, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-none font-semibold uppercase tracking-wide",
        "transition-all duration-100 cursor-pointer",
        "disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none disabled:translate-x-0 disabled:translate-y-0",
        VARIANT[variant],
        SIZE[size],
        className,
      )}
      {...rest}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
});
