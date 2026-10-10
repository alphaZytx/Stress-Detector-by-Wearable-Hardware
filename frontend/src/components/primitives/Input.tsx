import { forwardRef, useId } from "react";
import { cn } from "@/lib/cn";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, className, id, ...rest },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? autoId;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="font-mono text-xs font-semibold uppercase tracking-wide text-clinical-muted">
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        aria-invalid={!!error}
        className={cn(
          "h-11 rounded-none border-2 bg-clinical-surface px-3.5 text-sm text-clinical-text",
          "placeholder:text-clinical-faint",
          "transition-all duration-100",
          "focus:outline-none focus:shadow-card focus:-translate-x-[2px] focus:-translate-y-[2px]",
          error ? "border-clinical-danger" : "border-clinical-border",
          className,
        )}
        {...rest}
      />
      {error && (
        <span role="alert" className="text-xs text-clinical-danger">
          {error}
        </span>
      )}
    </div>
  );
});
