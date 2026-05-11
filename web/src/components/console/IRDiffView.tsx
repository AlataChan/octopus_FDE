import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { IRDiffChange, IRDiffResponse } from "../../lib/types";

type Props = {
  diff: IRDiffResponse | null;
  onSelectPath: (path: string) => void;
};

export function IRDiffView({ diff, onSelectPath }: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const hasChanges = Boolean(diff && diff.summary.total > 0);

  return (
    <section className="border-t border-slate-200 bg-white">
      <button
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-slate-950"
        type="button"
        onClick={() => setOpen((value) => !value)}
      >
        <span>{t("diff.title")}</span>
        <span className="text-xs font-normal text-slate-500">
          {diff ? t("diff.count", { count: diff.summary.total }) : t("diff.needTurns")}
        </span>
      </button>
      {open ? (
        <div className="space-y-2 border-t border-slate-200 px-4 py-3">
          {!diff ? (
            <p className="text-sm text-slate-500">{t("diff.empty")}</p>
          ) : !hasChanges ? (
            <p className="text-sm text-slate-500">{t("diff.noChanges")}</p>
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
      <article className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
        <span className="font-semibold text-slate-900">{t(`diff.kind.${change.kind}`)}</span>
        <span className="ml-2 font-mono text-xs text-slate-600">
          {change.from} → {change.to}
        </span>
      </article>
    );
  }
  if (change.kind === "config-changed") {
    return (
      <article className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
        <div>
          <span className="font-semibold text-slate-900">{t("diff.kind.config-changed")}</span>
          <span className="ml-2 font-mono text-xs text-slate-600">{change.node_id}</span>
        </div>
        <ul className="mt-2 space-y-1">
          {change.fields.map((field) => (
            <li className="text-xs text-slate-600" key={field.path}>
              <button
                className="font-mono text-slate-900 underline"
                type="button"
                onClick={() => onSelectPath(`nodes.${change.node_id}.${field.path}`)}
              >
                {field.path}
              </button>
              <span className="ml-2">
                {JSON.stringify(field.before)} → {JSON.stringify(field.after)}
              </span>
            </li>
          ))}
        </ul>
      </article>
    );
  }
  return (
    <article className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
      <span className="font-semibold text-slate-900">{t(`diff.kind.${change.kind}`)}</span>
      <span className="ml-2 font-mono text-xs text-slate-600">{change.node_id}</span>
    </article>
  );
}
