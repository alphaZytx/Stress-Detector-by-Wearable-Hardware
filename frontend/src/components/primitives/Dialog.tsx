import * as RDialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  className,
}: DialogProps) {
  return (
    <RDialog.Root open={open} onOpenChange={onOpenChange}>
      <RDialog.Portal>
        <RDialog.Overlay className="fixed inset-0 z-40 bg-black/60 data-[state=open]:animate-fade-in" />
        <RDialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 w-[min(420px,calc(100vw-2rem))]",
            "-translate-x-1/2 -translate-y-1/2 rounded-none border-2 border-clinical-border bg-clinical-surface p-6 shadow-float",
            "data-[state=open]:animate-fade-in",
            className,
          )}
        >
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <RDialog.Title className="font-display text-base font-semibold text-clinical-text">
                {title}
              </RDialog.Title>
              {description && (
                <RDialog.Description className="mt-1 text-sm text-clinical-muted">
                  {description}
                </RDialog.Description>
              )}
            </div>
            <RDialog.Close
              aria-label="Close"
              className="grid h-7 w-7 place-items-center rounded-md text-clinical-muted transition-colors hover:bg-clinical-surface-2 hover:text-clinical-text cursor-pointer"
            >
              <X className="h-4 w-4" aria-hidden />
            </RDialog.Close>
          </div>
          {children}
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  );
}
