import { useTranslation } from "react-i18next";
import type { ValidationFailure } from "../../lib/types";
import { toDisplayYaml } from "../../lib/yaml";
import { Badge } from "../ui/Badge";
import { Chip } from "../ui/Chip";

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
  const pathParts = highlightedPath ? highlightedPath.split(".") : [];
  const highlightKey = pathParts.length ? pathParts[pathParts.length - 1].replace(/\[\d+\]/g, "") : null;
  return (
    <section className="flex min-h-[520px] flex-col bg-bg-app/75 text-fg">
      <div className="flex items-center justify-between gap-3 border-b border-border/30 px-4 py-3">
        <p className="text-xs text-fg-muted">{t("ir.status", { status })}</p>
        <Chip variant={errors.length ? "failed" : "ok"}>
          {errors.length ? t("ir.errors", { count: errors.length }) : t("ir.valid")}
        </Chip>
      </div>
      {highlightedPath ? (
        <div className="border-b border-warning/20 bg-warning/10 px-4 py-2 text-xs text-fg">
          {t("ir.highlightedPath", { path: highlightedPath })}
        </div>
      ) : null}
      <pre className="flex-1 overflow-auto p-0 font-mono text-xs leading-5">
        {lines.map((line, index) => {
          const isHighlighted =
            Boolean(highlightKey) && line.trimStart().startsWith(`${highlightKey}:`);
          return (
            <span
              className={
                isHighlighted
                  ? "grid grid-cols-[3rem_1fr] bg-warning/15 text-fg"
                  : "grid grid-cols-[3rem_1fr]"
              }
              key={`${index}-${line}`}
            >
              <Badge className="mr-3 justify-end rounded-none border-0 bg-transparent pr-3 font-mono text-[10px] text-fg-muted ring-0">
                {index + 1}
              </Badge>
              <span className="min-w-0 border-l border-border/40 px-3 py-0.5">{line || " "}</span>
            </span>
          );
        })}
      </pre>
    </section>
  );
}
