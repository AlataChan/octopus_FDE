import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Route, Routes } from "react-router-dom";
import { getHealth } from "./lib/api";
import { useActor } from "./lib/useActor";
import SessionDetailPage from "./pages/sessions/[id]";
import SessionListPage from "./pages/sessions/list";

export default function App() {
  const { t, i18n } = useTranslation();
  const actor = useActor();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: getHealth
  });

  const nextLanguage = i18n.language === "zh" ? "en" : "zh";

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-sm font-semibold text-slate-950">{t("app.title")}</h1>
            <p className="text-xs text-slate-500">{t("app.subtitle")}</p>
          </div>
          <span className="hidden rounded bg-slate-100 px-2 py-1 text-xs text-slate-600 sm:inline">
            {health.isPending
              ? t("health.loading")
              : health.isError
                ? t("health.error")
                : JSON.stringify(health.data)}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden text-xs text-slate-500 sm:inline">
            {actor.id} / {actor.role}
          </span>
          <button
            className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
            type="button"
            onClick={() => void i18n.changeLanguage(nextLanguage)}
          >
            {t("language.switch")}
          </button>
        </div>
      </header>
      <Routes>
        <Route element={<SessionListPage />} path="/" />
        <Route element={<SessionDetailPage />} path="/sessions/:id" />
      </Routes>
    </main>
  );
}
