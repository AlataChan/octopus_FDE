import { useTranslation } from "react-i18next";
import type { ValidationFailure } from "../../lib/types";

type Props = {
  errors: ValidationFailure[];
  onSelectPath: (path: string) => void;
};

export function ValidatorPanel({ errors, onSelectPath }: Props) {
  const { t } = useTranslation();
  if (errors.length === 0) {
    return null;
  }

  async function copy(text: string) {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text);
    }
  }

  return (
    <section className="border-t border-slate-200 bg-white px-4 py-3">
      <h2 className="text-sm font-semibold text-slate-950">{t("validator.title")}</h2>
      <div className="mt-3 grid gap-2">
        {errors.map((error, index) => {
          const location = error.location || "-";
          return (
            <article className="rounded-md border border-rose-200 bg-rose-50 p-3" key={`${location}-${index}`}>
              <div className="flex items-start gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-rose-600 text-xs font-bold text-white">
                  !
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-white px-2 py-1 text-xs font-medium text-rose-700">
                      {error.bucket}
                    </span>
                    <button
                      className="font-mono text-xs text-slate-950 underline"
                      type="button"
                      onClick={() => onSelectPath(location)}
                    >
                      {location}
                    </button>
                  </div>
                  <p className="mt-2 text-sm text-slate-800">{friendlyMessage(error.detail)}</p>
                </div>
                <button
                  className="rounded-md border border-rose-200 bg-white px-2 py-1 text-xs font-medium text-rose-700"
                  type="button"
                  onClick={() => void copy(`${location}: ${error.detail}`)}
                >
                  {t("validator.copy")}
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function friendlyMessage(detail: string): string {
  return detail.replace(/^Value error, /, "");
}
