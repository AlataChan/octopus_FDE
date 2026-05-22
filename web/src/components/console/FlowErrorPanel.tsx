import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "../ui/Button";

type Props = {
  error: unknown;
  onSwitchToYaml: () => void;
  parsedCount?: number;
  totalCount?: number;
};

export function FlowErrorPanel({
  error,
  onSwitchToYaml,
  parsedCount = 0,
  totalCount = 0
}: Props) {
  const { t } = useTranslation();
  const summary = error instanceof Error ? error.message : String(error);

  return (
    <section className="flex h-full min-h-0 items-start bg-bg-surface p-4">
      <div className="max-w-xl rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm">
        <div className="flex items-start gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-destructive/15 text-destructive ring-1 ring-destructive/30">
            <AlertTriangle aria-hidden className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <h3 className="font-semibold text-fg">{t("flow.errorTitle")}</h3>
            <p className="mt-2 max-w-full break-words font-mono text-xs leading-5 text-fg-muted">
              {summary.slice(0, 200)}
            </p>
            <p className="mt-2 text-xs text-fg-muted">
              {t("flow.parseProgress", { parsed: parsedCount, total: totalCount })}
            </p>
            <Button className="mt-3" size="sm" variant="secondary" onClick={onSwitchToYaml}>
              {t("flow.openYaml")}
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
