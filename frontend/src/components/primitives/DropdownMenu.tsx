import * as RDropdown from "@radix-ui/react-dropdown-menu";
import { cn } from "@/lib/cn";

export function DropdownMenu({
  trigger,
  children,
  align = "end",
}: {
  trigger: React.ReactNode;
  children: React.ReactNode;
  align?: "start" | "center" | "end";
}) {
  return (
    <RDropdown.Root>
      <RDropdown.Trigger asChild>{trigger}</RDropdown.Trigger>
      <RDropdown.Portal>
        <RDropdown.Content
          align={align}
          sideOffset={6}
          className={cn(
            "z-50 min-w-[170px] rounded-none border-2 border-clinical-border bg-clinical-surface p-1.5 shadow-md",
            "data-[state=open]:animate-fade-in",
          )}
        >
          {children}
        </RDropdown.Content>
      </RDropdown.Portal>
    </RDropdown.Root>
  );
}

export function DropdownItem({
  onSelect,
  children,
  danger,
}: {
  onSelect: () => void;
  children: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <RDropdown.Item
      onSelect={onSelect}
      className={cn(
        "flex cursor-pointer items-center gap-2 rounded-none px-2.5 py-2 text-sm font-medium outline-none",
        "transition-colors data-[highlighted]:bg-clinical-accent data-[highlighted]:text-white",
        danger ? "text-clinical-danger data-[highlighted]:bg-clinical-danger" : "text-clinical-text",
      )}
    >
      {children}
    </RDropdown.Item>
  );
}
