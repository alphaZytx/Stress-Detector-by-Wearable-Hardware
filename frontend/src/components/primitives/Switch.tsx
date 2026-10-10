import * as RSwitch from "@radix-ui/react-switch";
import { cn } from "@/lib/cn";

export function Switch({
  checked,
  onCheckedChange,
  label,
  description,
  id,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
  description?: string;
  id?: string;
}) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-center justify-between gap-4">
      <span>
        <span className="block text-sm font-medium text-clinical-text">{label}</span>
        {description && (
          <span className="block text-xs text-clinical-muted">{description}</span>
        )}
      </span>
      <RSwitch.Root
        id={id}
        checked={checked}
        onCheckedChange={onCheckedChange}
        className={cn(
          "relative h-6 w-11 shrink-0 rounded-none border-2 border-clinical-border transition-colors duration-120 cursor-pointer",
          "data-[state=checked]:bg-clinical-accent data-[state=unchecked]:bg-clinical-surface-2",
        )}
      >
        <RSwitch.Thumb className="block h-4 w-4 translate-x-0.5 rounded-none border-2 border-clinical-border bg-white transition-transform duration-120 data-[state=checked]:translate-x-[22px]" />
      </RSwitch.Root>
    </label>
  );
}
