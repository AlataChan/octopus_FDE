import { type KeyboardEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Copy, MoreVertical, Pencil, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { listSessions, renameSession } from "../../lib/api";
import { cn } from "../../lib/cn";
import type { SessionSummary } from "../../lib/types";
import { Button } from "../ui/Button";

const SIDEBAR_COLLAPSED_KEY = "fde-sessions-sidebar-collapsed-v1";

type Props = {
  currentSessionId?: string | null;
  defaultCollapsed?: boolean;
  forceExpanded?: boolean;
  onCreateSession: () => void;
};

export function SessionsSidebar({
  currentSessionId,
  defaultCollapsed = false,
  forceExpanded = false,
  onCreateSession
}: Props) {
  const { i18n, t } = useTranslation();
  const queryClient = useQueryClient();
  const [collapsed, setCollapsed] = useState(() => readCollapsed(defaultCollapsed));
  const [menuSessionId, setMenuSessionId] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [renameErrorSessionId, setRenameErrorSessionId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const isCollapsed = forceExpanded ? false : collapsed;
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: listSessions
  });
  const rename = useMutation({
    mutationFn: ({ sessionId, title }: { sessionId: string; title: string }) =>
      renameSession(sessionId, title),
    onSuccess: async (_row, variables) => {
      setEditingSessionId(null);
      setMenuSessionId(null);
      setRenameErrorSessionId(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["sessions"] }),
        queryClient.invalidateQueries({ queryKey: ["session", variables.sessionId] })
      ]);
    },
    onError: (_error, variables) => {
      setEditingSessionId(variables.sessionId);
      setRenameErrorSessionId(variables.sessionId);
    }
  });
  const sortedSessions = useMemo(
    () =>
      [...(sessions.data || [])].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      ),
    [sessions.data]
  );

  function toggleCollapsed() {
    if (forceExpanded) {
      return;
    }
    setCollapsed((value) => {
      const next = !value;
      try {
        window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
      } catch {
        // localStorage can be blocked in private or test contexts.
      }
      return next;
    });
  }

  function beginRename(session: SessionSummary) {
    setEditingSessionId(session.session_id);
    setDraftTitle(session.display_title || session.session_id.slice(0, 8));
    setRenameErrorSessionId(null);
    setMenuSessionId(null);
  }

  function saveRename(sessionId: string) {
    const title = draftTitle.trim();
    if (!title || title.length > 80) {
      setRenameErrorSessionId(sessionId);
      return;
    }
    setRenameErrorSessionId(null);
    rename.mutate({ sessionId, title });
  }

  function handleRenameKeyDown(event: KeyboardEvent<HTMLInputElement>, sessionId: string) {
    if (event.key === "Enter") {
      event.preventDefault();
      saveRename(sessionId);
    }
    if (event.key === "Escape") {
      event.preventDefault();
      setEditingSessionId(null);
      setRenameErrorSessionId(null);
      setDraftTitle("");
    }
  }

  function copySessionId(sessionId: string) {
    void navigator.clipboard?.writeText(sessionId);
    setMenuSessionId(null);
  }

  return (
    <aside
      className={cn(
        "flex h-full min-h-0 shrink-0 flex-col border-r border-border/40 bg-bg-muted/70 transition-[width] duration-200",
        isCollapsed ? "w-14" : "w-[220px]"
      )}
      data-collapsed={isCollapsed}
      data-testid="sessions-sidebar"
    >
      <div
        className={cn(
          "flex shrink-0 border-b border-border/30 p-2",
          isCollapsed ? "h-24 flex-col gap-2" : "h-12 items-center gap-2"
        )}
      >
        <Button
          aria-label={t("sessions.create")}
          className={cn("min-w-0", isCollapsed ? "h-8 w-10 px-0" : "flex-1")}
          icon={<Plus aria-hidden className="h-4 w-4" />}
          size="sm"
          variant="primary"
          onClick={onCreateSession}
        >
          {isCollapsed ? null : <span className="truncate">{t("sessions.create")}</span>}
        </Button>
        {forceExpanded ? null : (
          <Button
            aria-label={isCollapsed ? t("sidebar.expand") : t("sidebar.collapse")}
            className={cn("px-2", isCollapsed && "h-8 w-10")}
            icon={
              isCollapsed ? (
                <ChevronRight aria-hidden className="h-4 w-4" />
              ) : (
                <ChevronLeft aria-hidden className="h-4 w-4" />
              )
            }
            size="sm"
            variant="ghost"
            onClick={toggleCollapsed}
          />
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {sessions.isPending ? (
          <p className={cn("text-xs text-fg-muted", isCollapsed && "sr-only")}>
            {t("sessions.loading")}
          </p>
        ) : sessions.isError ? (
          <p className={cn("text-xs text-destructive", isCollapsed && "sr-only")}>
            {t("sessions.error")}
          </p>
        ) : sortedSessions.length === 0 ? (
          <p className={cn("text-xs text-fg-muted", isCollapsed && "sr-only")}>{t("sessions.empty")}</p>
        ) : (
          <div className="flex min-w-0 flex-col gap-1">
            {sortedSessions.map((session) => (
              <SessionSidebarItem
                collapsed={isCollapsed}
                current={session.session_id === currentSessionId}
                draftTitle={draftTitle}
                editing={editingSessionId === session.session_id}
                key={session.session_id}
                language={i18n.language}
                menuOpen={menuSessionId === session.session_id}
                renameError={renameErrorSessionId === session.session_id}
                renaming={rename.isPending}
                session={session}
                onBeginRename={beginRename}
                onCopy={copySessionId}
                onDraftTitleChange={(title) => {
                  setDraftTitle(title);
                  setRenameErrorSessionId(null);
                }}
                onMenuOpenChange={(open) => setMenuSessionId(open ? session.session_id : null)}
                onRenameKeyDown={handleRenameKeyDown}
              />
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}

function SessionSidebarItem({
  collapsed,
  current,
  draftTitle,
  editing,
  language,
  menuOpen,
  renameError,
  renaming,
  session,
  onBeginRename,
  onCopy,
  onDraftTitleChange,
  onMenuOpenChange,
  onRenameKeyDown
}: {
  collapsed: boolean;
  current: boolean;
  draftTitle: string;
  editing: boolean;
  language: string;
  menuOpen: boolean;
  renameError: boolean;
  renaming: boolean;
  session: SessionSummary;
  onBeginRename: (session: SessionSummary) => void;
  onCopy: (sessionId: string) => void;
  onDraftTitleChange: (title: string) => void;
  onMenuOpenChange: (open: boolean) => void;
  onRenameKeyDown: (event: KeyboardEvent<HTMLInputElement>, sessionId: string) => void;
}) {
  const { t } = useTranslation();
  const title = session.display_title || session.session_id.slice(0, 8);

  if (collapsed) {
    return (
      <Link
        aria-current={current ? "page" : undefined}
        aria-label={title}
        className={cn(
          "relative flex h-10 items-center justify-center rounded-lg text-fg-muted hover:bg-bg-app hover:text-fg",
          current && "bg-bg-app text-fg"
        )}
        data-testid={`session-item-${session.session_id}`}
        title={title}
        to={`/sessions/${session.session_id}`}
      >
        <span
          aria-hidden
          className={cn("absolute left-0 h-5 w-0.5 rounded-full", current ? "bg-ring" : "bg-transparent")}
        />
        <span className={cn("h-2.5 w-2.5 rounded-full", dotColor(session.state))} />
      </Link>
    );
  }

  return (
    <div
      aria-current={current ? "page" : undefined}
      className={cn(
        "group relative min-w-0 rounded-lg",
        current ? "bg-bg-app text-fg" : "text-fg-muted hover:bg-bg-app/70 hover:text-fg"
      )}
      data-testid={`session-item-${session.session_id}`}
    >
      {current ? <span aria-hidden className="absolute left-0 top-2 h-8 w-0.5 rounded-full bg-ring" /> : null}
      <div className="flex items-start gap-2 py-2 pl-3 pr-1.5">
        <span className={cn("mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full", dotColor(session.state))} />
        <div className="min-w-0 flex-1">
          {editing ? (
            <div className="grid gap-1">
              <input
                aria-label={t("sidebar.renameInput", { title })}
                autoFocus
                className="h-7 w-full rounded-md border border-border/60 bg-bg-app px-2 text-sm font-medium text-fg"
                disabled={renaming}
                maxLength={100}
                value={draftTitle}
                onChange={(event) => onDraftTitleChange(event.target.value)}
                onKeyDown={(event) => onRenameKeyDown(event, session.session_id)}
              />
              {renameError ? (
                <p className="text-xs text-destructive" role="alert">
                  {t("common.saveFailed")}
                </p>
              ) : null}
            </div>
          ) : (
            <Link
              className="block truncate text-sm font-medium"
              title={title}
              to={`/sessions/${session.session_id}`}
            >
              {title}
            </Link>
          )}
          <p className="mt-0.5 truncate text-xs text-fg-muted">
            {relativeTime(session.updated_at, language)}
          </p>
        </div>
        <div className="relative shrink-0">
          <button
            aria-expanded={menuOpen}
            aria-label={t("sidebar.itemActions", { title })}
            className="rounded-md p-1 text-fg-muted opacity-0 hover:bg-bg-muted hover:text-fg group-hover:opacity-100 focus:opacity-100"
            type="button"
            onClick={() => onMenuOpenChange(!menuOpen)}
          >
            <MoreVertical aria-hidden className="h-4 w-4" />
          </button>
          {menuOpen ? (
            <div
              className="absolute right-0 top-7 z-20 min-w-32 rounded-lg border border-border/50 bg-bg-surface p-1 shadow-glow"
              role="menu"
            >
              <button
                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-fg-muted hover:bg-bg-muted hover:text-fg"
                role="menuitem"
                type="button"
                onClick={() => onBeginRename(session)}
              >
                <Pencil aria-hidden className="h-4 w-4" />
                {t("sidebar.rename")}
              </button>
              <button
                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-fg-muted hover:bg-bg-muted hover:text-fg"
                role="menuitem"
                type="button"
                onClick={() => onCopy(session.session_id)}
              >
                <Copy aria-hidden className="h-4 w-4" />
                {t("sidebar.copyId")}
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function readCollapsed(defaultCollapsed: boolean) {
  try {
    const stored = window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
    return stored === null ? defaultCollapsed : stored === "true";
  } catch {
    return defaultCollapsed;
  }
}

function dotColor(state: string) {
  if (state === "downloaded" || state === "compiled" || state === "validated") {
    return "bg-accent";
  }
  if (state === "drafting") {
    return "bg-warning";
  }
  if (state === "llm_config_set") {
    return "bg-fg-muted";
  }
  return "bg-border";
}

function relativeTime(value: string, language: string): string {
  const deltaMs = Date.now() - new Date(value).getTime();
  const minutes = Math.max(0, Math.round(deltaMs / 60000));
  const formatter = new Intl.RelativeTimeFormat(language.startsWith("zh") ? "zh" : "en", {
    numeric: "auto"
  });
  if (minutes < 1) {
    return formatter.format(0, "minute");
  }
  if (minutes < 60) {
    return formatter.format(-minutes, "minute");
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return formatter.format(-hours, "hour");
  }
  return formatter.format(-Math.round(hours / 24), "day");
}
