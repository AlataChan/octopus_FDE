import { useTranslation } from "react-i18next";
import type { ValidationFailure } from "../../lib/types";
import { toDisplayYaml } from "../../lib/yaml";

type Props = {
  errors: ValidationFailure[];
  ir: unknown | null;
  status: string;
};

export function IRView({ errors, ir, status }: Props) {
  const { t } = useTranslation();
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
      <pre className="flex-1 overflow-auto whitespace-pre-wrap p-4 font-mono text-xs leading-5">
        {ir ? toDisplayYaml(ir) : t("ir.empty")}
      </pre>
    </section>
  );
}
