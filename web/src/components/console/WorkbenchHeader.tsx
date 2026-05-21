import { type KeyboardEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ArrowLeft, Languages, MoreVertical, RotateCcw, Settings } from "lucide-react";
import { Button } from "../ui/Button";
import { Chip, type ChipVariant } from "../ui/Chip";
import type { SessionDetail } from "../../lib/types";

type Props = {
  onRename: (title: string) => Promise<unknown> | unknown;
  onResetLayout: () => void;
  session?: SessionDetail | null;
};

export function WorkbenchHeader({ onRename, onResetLayout, session }: Props) {
  const { i18n, t } = useTranslation();
  const [isEditing, setIsEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const title = session?.display_title || session?.session_id || t("session.loading");
  const nextLanguage = i18n.language === "zh" ? "en" : "zh";

  function beginEdit() {
    setDraftTitle(title);
    setError(null);
    setIsEditing(true);
  }

  async function saveTitle() {
    const nextTitle = draftTitle.trim();
    if (!nextTitle || nextTitle.length > 80) {
      setError(t("workbench.titleError"));
      return;
    }
    try {
      await onRename(nextTitle);
      setIsEditing(false);
      setError(null);
    } catch {
      setError(t("common.saveFailed"));
    }
  }

  function cancelEdit() {
    setIsEditing(false);
    setDraftTitle("");
    setError(null);
  }

  function handleTitleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      void saveTitle();
    }
    if (event.key === "Escape") {
      event.preventDefault();
      cancelEdit();
    }
  }

  return (
    <header className="flex min-h-12 items-center gap-3 border-b border-border/30 bg-bg-surface/90 px-3 backdrop-blur">
      <Link className="hidden shrink-0 sm:inline-flex" to="/sessions">
        <Button
          icon={<ArrowLeft aria-hidden className="h-4 w-4" />}
          size="sm"
          variant="ghost"
        >
          {t("workbench.sessionsLink")}
        </Button>
      </Link>
      <div className="min-w-0 flex-1">
        {isEditing ? (
          <div className="grid gap-1">
            <input
              aria-label={t("workbench.titleInput")}
              autoFocus
              className="h-8 w-full rounded-md border border-border/60 bg-bg-app px-2 text-sm font-semibold text-fg outline-none focus-visible:ring-2 focus-visible:ring-ring"
              maxLength={100}
              value={draftTitle}
              onBlur={() => void saveTitle()}
              onChange={(event) => {
                setDraftTitle(event.target.value);
                setError(null);
              }}
              onKeyDown={handleTitleKeyDown}
            />
            {error ? (
              <p className="text-xs text-destructive" role="alert">
                {error}
              </p>
            ) : null}
          </div>
        ) : (
          <button
            className="block max-w-full truncate text-left text-sm font-semibold text-fg hover:text-accent"
            title={title}
            type="button"
            onDoubleClick={beginEdit}
          >
            {title}
          </button>
        )}
      </div>
      <div className="relative flex shrink-0 items-center gap-2">
        <Chip className="hidden sm:inline-flex" variant={chipForState(session?.state || "init")}>
          {session?.state || t("session.loading")}
        </Chip>
        <Button
          aria-expanded={menuOpen}
          aria-label={t("workbench.more")}
          icon={<MoreVertical aria-hidden className="h-4 w-4" />}
          size="sm"
          variant="ghost"
          onClick={() => setMenuOpen((open) => !open)}
        />
        {menuOpen ? (
          <div
            className="absolute right-20 top-10 z-20 min-w-40 rounded-lg border border-border/50 bg-bg-surface p-1 shadow-glow"
            role="menu"
          >
            <button
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-fg-muted hover:bg-bg-muted hover:text-fg"
              role="menuitem"
              type="button"
              onClick={() => {
                setMenuOpen(false);
                onResetLayout();
              }}
            >
              <RotateCcw aria-hidden className="h-4 w-4" />
              {t("layout.reset")}
            </button>
          </div>
        ) : null}
        <Button
          aria-label={t("language.switch")}
          icon={<Languages aria-hidden className="h-4 w-4" />}
          size="sm"
          variant="ghost"
          onClick={() => void i18n.changeLanguage(nextLanguage)}
        >
          <span className="hidden lg:inline">{t("language.short")}</span>
        </Button>
        <Link to="/settings">
          <Button
            aria-label={t("workbench.settings")}
            icon={<Settings aria-hidden className="h-4 w-4" />}
            size="sm"
            variant="ghost"
          />
        </Link>
      </div>
    </header>
  );
}

function chipForState(state: string): ChipVariant {
  if (state === "downloaded") {
    return "downloaded";
  }
  if (state === "compiled") {
    return "compiled";
  }
  if (state === "validated") {
    return "validated";
  }
  if (state === "drafting") {
    return "running";
  }
  if (state === "llm_config_set") {
    return "llm_config_set";
  }
  return "init";
}
