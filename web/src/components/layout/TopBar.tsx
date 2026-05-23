import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Languages, LogOut, Moon, ShieldCheck, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTheme } from "../../hooks/useTheme";
import { useAuth } from "../../hooks/useAuth";
import { getHealth, logout } from "../../lib/api";
import { useActor } from "../../lib/useActor";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";

export function TopBar() {
  const { i18n, t } = useTranslation();
  const actor = useActor();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isDark, toggleTheme } = useTheme();
  const auth = useAuth({ enabled: location.pathname !== "/login" });
  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: ["auth", "me"] });
      navigate("/login", { replace: true });
    }
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: getHealth
  });
  const nextLanguage = i18n.language === "zh" ? "en" : "zh";
  const sessionId = location.pathname.startsWith("/sessions/")
    ? location.pathname.split("/")[2]
    : null;

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border/40 bg-bg-muted/95 px-4 backdrop-blur">
      <div className="flex min-w-0 items-center gap-4">
        <Link
          aria-label={t("app.title")}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-sm font-black tracking-tight text-primary dark:text-bg-app shadow-[0_0_28px_rgb(var(--accent)/0.22)]"
          to="/"
        >
          FDE
        </Link>
        <nav aria-label={t("topbar.breadcrumb")} className="min-w-0">
          <ol className="flex min-w-0 items-center gap-2 text-sm">
            <li>
              <Link className="font-medium text-fg-muted hover:text-fg" to="/">
                {t("topbar.sessions")}
              </Link>
            </li>
            {sessionId ? (
              <>
                <li className="text-fg-muted/60">/</li>
                <li className="min-w-0 truncate font-mono text-xs text-fg">{sessionId.slice(0, 8)}</li>
              </>
            ) : null}
          </ol>
        </nav>
        <Chip variant={health.isError ? "failed" : health.isPending ? "running" : "ok"} pulse={health.isPending}>
          {health.isPending ? t("health.loading") : health.isError ? t("health.error") : t("health.ok")}
        </Chip>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span className="hidden items-center gap-1.5 rounded-full border border-border/50 bg-bg-app/50 px-3 py-1.5 text-xs font-medium text-fg-muted sm:inline-flex">
          <ShieldCheck aria-hidden className="h-3.5 w-3.5 text-accent" />
          {auth.data?.username || actor.id} / {actor.role}
        </span>
        {auth.data ? (
          <Button
            aria-label={t("auth.logout")}
            icon={<LogOut aria-hidden className="h-4 w-4" />}
            loading={logoutMutation.isPending}
            size="sm"
            variant="ghost"
            onClick={() => logoutMutation.mutate()}
          >
            <span className="hidden sm:inline">{t("auth.logout")}</span>
          </Button>
        ) : null}
        <Button
          aria-label={t("language.switch")}
          icon={<Languages aria-hidden className="h-4 w-4" />}
          size="sm"
          variant="ghost"
          onClick={() => void i18n.changeLanguage(nextLanguage)}
        >
          <span className="hidden sm:inline">{t("language.short")}</span>
        </Button>
        <Button
          aria-label={isDark ? t("theme.aria.switch_to_light") : t("theme.aria.switch_to_dark")}
          icon={
            isDark ? (
              <Sun aria-hidden className="h-4 w-4" />
            ) : (
              <Moon aria-hidden className="h-4 w-4" />
            )
          }
          size="sm"
          variant="ghost"
          onClick={toggleTheme}
        >
          <span className="hidden sm:inline">
            {isDark ? t("theme.toggle.light") : t("theme.toggle.dark")}
          </span>
        </Button>
        <Activity aria-hidden className="hidden h-4 w-4 text-accent/70 md:block" />
      </div>
    </header>
  );
}
