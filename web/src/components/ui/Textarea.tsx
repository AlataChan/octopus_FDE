import type { TextareaHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  error?: boolean;
};

export function Textarea({ className, error = false, ...props }: TextareaProps) {
  return (
    <textarea
      className={cn(
        "w-full rounded-lg border bg-bg-app/60 px-3 py-2 text-sm text-fg placeholder:text-fg-muted/70",
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
