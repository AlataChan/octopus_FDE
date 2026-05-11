import { useState } from "react";
import { ChevronDown, Minus, Plus, RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { IRDiffChange, IRDiffResponse } from "../../lib/types";
import { Button } from "../ui/Button";

type Props = {
  diff: IRDiffResponse | null;
  onSelectPath: (path: string) => void;
};

export function IRDiffView({ diff, onSelectPath }: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const hasChanges = Boolean(diff && diff.summary.total > 0);

  return (
    <section className="border-t border-border/30 bg-bg-surface">
      <button
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-fg"
        type="button"
        onClick={() => setOpen((value) => !value)}
      >
        <span>{t("diff.title")}</span>
        <span className="inline-flex items-center gap-2 text-xs font-normal text-fg-muted">
          {diff ? t("diff.count", { count: diff.summary.total }) : t("diff.needTurns")}
          <ChevronDown
            aria-hidden
            className={open ? "h-4 w-4 rotate-180 transition" : "h-4 w-4 transition"}
          />
        </span>
      </button>
      {open ? (
        <div className="space-y-2 border-t border-border/30 px-4 py-3">
          {!diff ? (
            <p className="text-sm text-fg-muted">{t("diff.empty")}</p>
          ) : !hasChanges ? (
            <p className="text-sm text-fg-muted">{t("diff.noChanges")}</p>
          ) : (
            diff.changes.map((change, index) => (
              <ChangeRow change={change} key={index} onSelectPath={onSelectPath} />
            ))
          )}
        </div>
      ) : null}
    </section>
  );
}

function ChangeRow({
  change,
  onSelectPath
}: {
  change: IRDiffChange;
  onSelectPath: (path: string) => void;
}) {
  const { t } = useTranslation();
  if (change.scope === "edge") {
    return (
      <article className="rounded-lg border border-border/50 bg-bg-app/40 px-3 py-2 text-sm">
        <KindIcon kind={change.kind} />
        <span className="ml-2 font-semibold text-fg">{t(`diff.kind.${change.kind}`)}</span>
        <span className="ml-2 font-mono text-xs text-fg-muted">
          {change.from} → {change.to}
        </span>
      </article>
    );
  }
  if (change.kind === "config-changed") {
    return (
      <article className="rounded-lg border border-warning/25 bg-warning/5 px-3 py-2 text-sm">
        <div>
          <KindIcon kind={change.kind} />
          <span className="ml-2 font-semibold text-fg">{t("diff.kind.config-changed")}</span>
          <span className="ml-2 font-mono text-xs text-fg-muted">{change.node_id}</span>
        </div>
        <ul className="mt-2 space-y-1">
          {change.fields.map((field) => (
            <li className="flex flex-wrap items-center gap-2 text-xs text-fg-muted" key={field.path}>
              <Button
                className="h-7 px-2 font-mono"
                size="sm"
                variant="ghost"
                onClick={() => onSelectPath(`nodes.${change.node_id}.${field.path}`)}
              >
                {field.path}
              </Button>
              <span>
                {JSON.stringify(field.before)} → {JSON.stringify(field.after)}
              </span>
            </li>
          ))}
        </ul>
      </article>
    );
  }
  return (
    <article className="rounded-lg border border-border/50 bg-bg-app/40 px-3 py-2 text-sm">
      <KindIcon kind={change.kind} />
      <span className="ml-2 font-semibold text-fg">{t(`diff.kind.${change.kind}`)}</span>
      <span className="ml-2 font-mono text-xs text-fg-muted">{change.node_id}</span>
    </article>
  );
}

function KindIcon({ kind }: { kind: IRDiffChange["kind"] }) {
  const className = "inline h-4 w-4 align-[-3px]";
  if (kind === "added") {
    return <Plus aria-hidden className={`${className} text-accent`} />;
  }
  if (kind === "removed") {
    return <Minus aria-hidden className={`${className} text-destructive`} />;
  }
  return <RefreshCw aria-hidden className={`${className} text-warning`} />;
}
