import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { getHealth } from "./lib/api";
import { useActor } from "./lib/useActor";

export default function App() {
  const { t, i18n } = useTranslation();
  const actor = useActor();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: getHealth
  });

  const nextLanguage = i18n.language === "zh" ? "en" : "zh";

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-10">
      <section className="mx-auto max-w-3xl rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-8 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-slate-500">{t("app.subtitle")}</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-normal text-slate-950">
              {t("app.title")}
            </h1>
          </div>
          <button
            className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
            type="button"
            onClick={() => void i18n.changeLanguage(nextLanguage)}
          >
            {t("language.switch")}
          </button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-md border border-slate-200 p-4">
            <h2 className="text-sm font-semibold text-slate-900">{t("health.title")}</h2>
            <p className="mt-2 text-sm text-slate-600">
              {health.isPending
                ? t("health.loading")
                : health.isError
                  ? t("health.error")
                  : JSON.stringify(health.data)}
            </p>
          </div>

          <div className="rounded-md border border-slate-200 p-4">
            <h2 className="text-sm font-semibold text-slate-900">{t("actor.title")}</h2>
            <p className="mt-2 text-sm text-slate-600">
              {actor.id} / {actor.role}
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
