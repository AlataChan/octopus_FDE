import { useTranslation } from "react-i18next";
import type { ValidationFailure } from "../../lib/types";
import { toDisplayYaml } from "../../lib/yaml";

type Props = {
  errors: ValidationFailure[];
  highlightedPath?: string | null;
  ir: unknown | null;
  status: string;
};

export function IRView({ errors, highlightedPath, ir, status }: Props) {
  const { t } = useTranslation();
  const text = ir ? toDisplayYaml(ir) : t("ir.empty");
  const lines = text.split("\n");
  const highlightKey = highlightedPath ? highlightedPath.split(".").at(-1)?.replace(/\[\d+\]/g, "") : null;
  return (
    <section className="flex min-h-[480px] flex-col bg-slate-950 text-slate-50">
      <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold">{t("ir.title")}</h2>
          <p className="mt-1 text-xs text-slate-400">{t("ir.status", { status })}</p>
        </div>
        <span className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-300">
          {errors.length ? t("ir.errors", { count: errors.length }) : t("ir.valid")}
        </span>
      </div>
      {highlightedPath ? (
        <div className="border-b border-amber-300/20 bg-amber-300/10 px-4 py-2 text-xs text-amber-100">
          {t("ir.highlightedPath", { path: highlightedPath })}
        </div>
      ) : null}
      <pre className="flex-1 overflow-auto p-4 font-mono text-xs leading-5">
        {lines.map((line, index) => {
          const isHighlighted =
            Boolean(highlightKey) && line.trimStart().startsWith(`${highlightKey}:`);
          return (
            <span
              className={isHighlighted ? "block bg-amber-300/20 text-amber-50" : "block"}
              key={`${index}-${line}`}
            >
              {line || " "}
            </span>
          );
        })}
      </pre>
    </section>
  );
}
