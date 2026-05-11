import type { ReactNode } from "react";
import { CheckCircle2, Circle, Clock3, Download, FileCheck2, Loader2, XCircle } from "lucide-react";
import { cn } from "../../lib/cn";

export type ChipVariant =
  | "compiled"
  | "downloaded"
  | "draft"
  | "failed"
  | "init"
  | "llm_config_set"
  | "ok"
  | "running"
  | "succeeded"
  | "validated"
  | "warning";

const styles: Record<ChipVariant, string> = {
  compiled: "border-accent/35 bg-accent/10 text-green-200",
  downloaded: "border-sky-400/35 bg-sky-400/10 text-sky-200",
  draft: "border-slate-500/35 bg-slate-500/10 text-slate-200",
  failed: "border-destructive/40 bg-destructive/10 text-red-200",
  init: "border-slate-500/35 bg-slate-500/10 text-slate-200",
  llm_config_set: "border-cyan-400/35 bg-cyan-400/10 text-cyan-200",
  ok: "border-accent/35 bg-accent/10 text-green-200",
  running: "border-warning/40 bg-warning/10 text-amber-200",
  succeeded: "border-accent/35 bg-accent/10 text-green-200",
  validated: "border-emerald-400/35 bg-emerald-400/10 text-emerald-200",
  warning: "border-warning/40 bg-warning/10 text-amber-200"
};

export function Chip({
  children,
  className,
  pulse = false,
  variant = "draft"
}: {
  children: ReactNode;
  className?: string;
  pulse?: boolean;
  variant?: ChipVariant;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold",
        styles[variant],
        className
      )}
    >
      {pulse ? <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" /> : iconFor(variant)}
      {children}
    </span>
  );
}

function iconFor(variant: ChipVariant) {
  const className = "h-3.5 w-3.5";
  if (variant === "running") {
    return <Loader2 aria-hidden className={cn(className, "animate-spin")} />;
  }
  if (variant === "failed") {
    return <XCircle aria-hidden className={className} />;
  }
  if (variant === "compiled" || variant === "validated" || variant === "succeeded" || variant === "ok") {
    return <CheckCircle2 aria-hidden className={className} />;
  }
  if (variant === "downloaded") {
    return <Download aria-hidden className={className} />;
  }
  if (variant === "llm_config_set") {
    return <FileCheck2 aria-hidden className={className} />;
  }
  if (variant === "warning") {
    return <Clock3 aria-hidden className={className} />;
  }
  return <Circle aria-hidden className={className} />;
}
