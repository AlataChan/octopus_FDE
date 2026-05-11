import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "../../lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost";
type ButtonSize = "sm" | "md" | "lg";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: ReactNode;
  loading?: boolean;
  size?: ButtonSize;
  variant?: ButtonVariant;
};

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-slate-950 shadow-[0_0_24px_rgba(34,197,94,0.18)] hover:bg-green-400 disabled:bg-slate-700 disabled:text-slate-400",
  secondary:
    "bg-bg-muted text-fg ring-1 ring-border/60 hover:bg-slate-700 disabled:bg-bg-muted/60 disabled:text-slate-500",
  ghost: "bg-transparent text-fg-muted hover:bg-bg-muted hover:text-fg disabled:text-slate-600"
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-8 gap-1.5 px-3 text-xs",
  md: "h-10 gap-2 px-4 text-sm",
  lg: "h-11 gap-2.5 px-5 text-sm"
};

export function Button({
  children,
  className,
  disabled,
  icon,
  loading = false,
  size = "md",
  type = "button",
  variant = "secondary",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-lg font-semibold tracking-[0.01em]",
        "transition duration-150 active:translate-y-px disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className
      )}
      disabled={disabled || loading}
      type={type}
      {...props}
    >
      {loading ? <Loader2 aria-hidden className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}
