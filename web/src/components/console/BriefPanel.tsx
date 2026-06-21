import { CheckCircle2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { WorkflowBriefSnapshot } from "../../lib/types";
import { Button } from "../ui/Button";

type Props = {
  brief?: WorkflowBriefSnapshot | null;
  disabled?: boolean;
  onConfirm: () => void;
  variant: "brief_review" | "design_preview";
};

const sectionKeys = [
  "intent_clarifications",
  "trigger",
  "data_sources",
  "credentials",
  "approval_points",
  "success_criteria",
  "compliance_boundary",
  "business_rules",
  "risks"
] as const;

export function BriefPanel({
  brief,
  disabled = false,
  onConfirm,
  variant
}: Props) {
  const { t } = useTranslation();
  const sections = sectionKeys.map((key) => ({ key, values: normalizeValue(brief?.[key]) }));

  return (
    <div className="rounded-lg bg-bg-app/60 p-3 text-sm leading-6 text-fg ring-1 ring-accent/20">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase text-fg-muted">
            {t(`brief.${variant}.eyebrow`)}
          </div>
          <h3 className="mt-1 text-sm font-semibold text-fg">{t(`brief.${variant}.title`)}</h3>
          <p className="mt-1 text-xs leading-5 text-fg-muted">{t("brief.subtitle")}</p>
        </div>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {sections.map(({ key, values }) => (
          <section
            key={key}
            className={
              key === "trigger" || key === "compliance_boundary"
                ? "rounded-lg border border-border/50 bg-bg-surface/70 p-3 sm:col-span-2"
                : "rounded-lg border border-border/50 bg-bg-surface/70 p-3"
            }
          >
            <h4 className="text-xs font-semibold uppercase text-fg-muted">{t(`brief.field.${key}`)}</h4>
            {values.length ? (
              <ul className="mt-2 space-y-1.5">
                {values.map((value, index) => (
                  <li key={`${key}-${index}`} className="text-sm leading-5 text-fg">
                    {value}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-fg-muted">{t("brief.emptyField")}</p>
            )}
          </section>
        ))}
      </div>
      <div className="mt-3 flex justify-end">
        <Button
          disabled={disabled}
          icon={<CheckCircle2 aria-hidden className="h-4 w-4" />}
          size="sm"
          type="button"
          variant="primary"
          onClick={onConfirm}
        >
          {t("brief.confirm")}
        </Button>
      </div>
    </div>
  );
}

function normalizeValue(value: unknown): string[] {
  if (value == null || value === "") {
    return [];
  }
  if (Array.isArray(value)) {
    return value.flatMap((item) => normalizeValue(item));
  }
  if (typeof value === "object") {
    return normalizeObject(value as Record<string, unknown>);
  }
  return [String(value)];
}

function normalizeObject(value: Record<string, unknown>): string[] {
  if ("handle" in value) {
    const handle = normalizeValue(value.handle).join(", ");
    const kind = normalizeValue(value.kind).join(", ");
    return [kind ? `${handle} (${kind})` : handle].filter(Boolean);
  }
  if ("mode" in value) {
    const mode = normalizeValue(value.mode).join(", ");
    const rest = Object.entries(value)
      .filter(([key]) => key !== "mode")
      .flatMap(([key, item]) => formatObjectEntry(key, item));
    return [mode, ...rest].filter(Boolean);
  }
  return Object.entries(value).flatMap(([key, item]) => formatObjectEntry(key, item));
}

function formatObjectEntry(key: string, value: unknown): string[] {
  const normalized = normalizeValue(value);
  if (!normalized.length) {
    return [];
  }
  return [`${humanizeKey(key)}: ${normalized.join(", ")}`];
}

function humanizeKey(key: string): string {
  return key.replace(/_/g, " ");
}
