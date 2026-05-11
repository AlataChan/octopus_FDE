import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex min-w-6 items-center justify-center rounded-full bg-bg-muted px-2 py-0.5 text-xs font-semibold text-fg-muted ring-1 ring-border/50",
        className
      )}
      {...props}
    />
  );
}
