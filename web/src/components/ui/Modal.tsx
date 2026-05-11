import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";
import { Button } from "./Button";
import { Card } from "./Card";

type ModalProps = {
  children: ReactNode;
  labelledBy?: string;
  onOpenChange?: (open: boolean) => void;
  open: boolean;
};

export function Modal({ children, labelledBy, onOpenChange, open }: ModalProps) {
  useEffect(() => {
    if (!open) {
      return;
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onOpenChange?.(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onOpenChange, open]);

  if (!open) {
    return null;
  }

  return (
    <div
      aria-labelledby={labelledBy}
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
      role="dialog"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onOpenChange?.(false);
        }
      }}
    >
      <Card className="relative w-full max-w-lg">
        {onOpenChange ? (
          <Button
            aria-label="Close modal"
            className="absolute right-3 top-3"
            size="sm"
            variant="ghost"
            icon={<X aria-hidden className="h-4 w-4" />}
            onClick={() => onOpenChange(false)}
          />
        ) : null}
        {children}
      </Card>
    </div>
  );
}
