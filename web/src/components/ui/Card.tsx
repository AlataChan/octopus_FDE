import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cn("rounded-lg bg-bg-surface ring-1 ring-border/40 shadow-glow", className)}
      {...props}
    />
  );
}

type CardHeaderProps = Omit<HTMLAttributes<HTMLDivElement>, "title"> & {
  action?: ReactNode;
  subtitle?: ReactNode;
  title?: ReactNode;
};

export function CardHeader({
  action,
  children,
  className,
  subtitle,
  title
}: CardHeaderProps) {
  return (
    <div
      className={cn(
        "flex min-h-14 items-start justify-between gap-3 border-b border-border/30 px-4 py-2.5",
        className
      )}
    >
      <div className="min-w-0">
        {title ? <h2 className="truncate text-sm font-semibold text-fg">{title}</h2> : null}
        {subtitle ? <p className="mt-1 text-xs leading-5 text-fg-muted">{subtitle}</p> : null}
        {children}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4", className)} {...props} />;
}
