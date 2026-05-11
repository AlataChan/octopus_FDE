import type { InputHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  error?: boolean;
};

export function Input({ className, error = false, ...props }: InputProps) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-lg border bg-bg-app/60 px-3 text-sm text-fg placeholder:text-fg-muted/70",
        "shadow-[inset_0_1px_2px_rgb(0_0_0/0.08)] outline-none transition",
        error
          ? "border-destructive/70 focus:border-destructive"
          : "border-border/70 focus:border-accent/70",
        className
      )}
      {...props}
    />
  );
}
