import { useTranslation } from "react-i18next";
import { AlertTriangle, Copy } from "lucide-react";
import type { ValidationFailure } from "../../lib/types";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";

type Props = {
  errors: ValidationFailure[];
  onSelectPath: (path: string) => void;
  variant?: "default" | "embedded";
};

export function ValidatorPanel({ errors, onSelectPath, variant = "default" }: Props) {
  const { t } = useTranslation();
  if (errors.length === 0) {
    return variant === "embedded" ? (
      <section className="flex h-full min-h-0 items-start bg-bg-surface px-4 py-3">
        <p className="rounded-lg border border-dashed border-border/50 bg-bg-app/40 p-3 text-sm leading-6 text-fg-muted">
          {t("validator.noIssues")}
        </p>
      </section>
    ) : null;
  }

  async function copy(text: string) {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text);
    }
  }

  return (
    <section
      className={
        variant === "embedded"
          ? "scroll-mask-y h-full min-h-0 overflow-y-auto bg-bg-surface px-4 py-3"
          : "border-t border-border/30 bg-bg-surface px-4 py-3"
      }
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-fg">{t("validator.title")}</h2>
        <Chip variant="failed">{t("validator.issueCount", { count: errors.length })}</Chip>
      </div>
      <div className="mt-3 grid gap-2">
        {errors.map((error, index) => {
          const location = error.location || "-";
          return (
            <article className="rounded-lg border border-destructive/30 bg-destructive/10 p-3" key={`${location}-${index}`}>
              <div className="flex items-start gap-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-destructive/15 text-destructive ring-1 ring-destructive/30">
                  <AlertTriangle aria-hidden className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-bg-app/60 px-2 py-1 text-xs font-medium text-fg ring-1 ring-destructive/25">
                      {error.bucket}
                    </span>
                    <Button
                      className="h-7 px-2 font-mono"
                      size="sm"
                      variant="ghost"
                      onClick={() => onSelectPath(location)}
                    >
                      {location}
                    </Button>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-fg">{friendlyMessage(error.detail)}</p>
                </div>
                <Button
                  aria-label={t("validator.copy")}
                  icon={<Copy aria-hidden className="h-4 w-4" />}
                  size="sm"
                  variant="ghost"
                  onClick={() => void copy(`${location}: ${error.detail}`)}
                />
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
