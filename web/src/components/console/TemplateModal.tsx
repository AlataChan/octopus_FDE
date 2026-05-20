import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FilePlus2, LayoutTemplate } from "lucide-react";
import { useTranslation } from "react-i18next";
import { listTemplates } from "../../lib/api";
import type { TemplateSummary } from "../../lib/types";
import { Button } from "../ui/Button";
import { CardBody, CardHeader } from "../ui/Card";
import { Chip } from "../ui/Chip";
import { Modal } from "../ui/Modal";

const DEFAULT_TEMPLATE_SCOPE = "ecommerce/kb";
const tabs = ["blank", "template"] as const;
type TabId = (typeof tabs)[number];

type Props = {
  creatingBlank: boolean;
  creatingTemplateId: string | null;
  open: boolean;
  onCreateBlank: () => void;
  onCreateTemplate: (templateId: string) => void;
  onOpenChange: (open: boolean) => void;
};

export function TemplateModal({
  creatingBlank,
  creatingTemplateId,
  open,
  onCreateBlank,
  onCreateTemplate,
  onOpenChange
}: Props) {
  const { i18n, t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TabId>("blank");
  const templates = useQuery({
    enabled: open,
    queryKey: ["templates", DEFAULT_TEMPLATE_SCOPE],
    queryFn: () => listTemplates({ scope: DEFAULT_TEMPLATE_SCOPE })
  });
  const locale = i18n.language.startsWith("zh") ? "zh" : "en";

  if (!open) {
    return null;
  }

  function renderTab(tab: TabId) {
    const selected = activeTab === tab;
    return (
      <button
        aria-controls={`template-modal-panel-${tab}`}
        aria-selected={selected}
        className={
          selected
            ? "inline-flex h-8 items-center rounded-lg bg-bg-app/60 px-3 text-xs font-semibold text-fg ring-1 ring-accent/30"
            : "inline-flex h-8 items-center rounded-lg px-3 text-xs font-semibold text-fg-muted hover:bg-bg-muted hover:text-fg"
        }
        id={`template-modal-tab-${tab}`}
        key={tab}
        role="tab"
        type="button"
        onClick={() => setActiveTab(tab)}
      >
        {t(`template.tab.${tab}`)}
      </button>
    );
  }

  return (
    <Modal labelledBy="template-modal-title" open={open} onOpenChange={onOpenChange}>
      <CardHeader
        subtitle={t("template.subtitle")}
        title={<span id="template-modal-title">{t("template.title")}</span>}
      />
      <div
        aria-label={t("template.title")}
        className="flex gap-1 border-b border-border/30 px-3 py-2"
        role="tablist"
      >
        {tabs.map((tab) => renderTab(tab))}
      </div>
      <CardBody className="max-h-[68vh] overflow-y-auto">
        <div
          aria-labelledby={`template-modal-tab-${activeTab}`}
          id={`template-modal-panel-${activeTab}`}
          role="tabpanel"
        >
          {activeTab === "blank" ? (
            <div className="grid gap-5">
              <div className="rounded-lg border border-border/40 bg-bg-app/45 p-4">
                <div className="flex items-center gap-2">
                  <FilePlus2 aria-hidden className="h-4 w-4 text-accent" />
                  <h3 className="text-sm font-semibold text-fg">{t("template.blankTitle")}</h3>
                </div>
                <p className="mt-2 text-sm leading-6 text-fg-muted">{t("template.blankDescription")}</p>
              </div>
              <Button
                className="w-full"
                loading={creatingBlank}
                type="button"
                variant="primary"
                onClick={onCreateBlank}
              >
                {creatingBlank ? t("sessions.creating") : t("template.createBlank")}
              </Button>
            </div>
          ) : (
            <TemplateGrid
              creatingTemplateId={creatingTemplateId}
              isError={templates.isError}
              isPending={templates.isPending}
              locale={locale}
              templates={templates.data || []}
              onCreateTemplate={onCreateTemplate}
            />
          )}
        </div>
      </CardBody>
    </Modal>
  );
}

function TemplateGrid({
  creatingTemplateId,
  isError,
  isPending,
  locale,
  templates,
  onCreateTemplate
}: {
  creatingTemplateId: string | null;
  isError: boolean;
  isPending: boolean;
  locale: "zh" | "en";
  templates: TemplateSummary[];
  onCreateTemplate: (templateId: string) => void;
}) {
  const { t } = useTranslation();

  if (isPending) {
    return <p className="text-sm text-fg-muted">{t("template.loading")}</p>;
  }
  if (isError) {
    return <p className="text-sm text-destructive">{t("template.error")}</p>;
  }
  if (templates.length === 0) {
    return <p className="text-sm text-fg-muted">{t("template.empty")}</p>;
  }

  return (
    <div className="grid gap-3">
      {templates.map((template) => {
        const isCreating = creatingTemplateId === template.id;
        return (
          <button
            className="rounded-lg border border-border/40 bg-bg-app/45 p-4 text-left outline-none transition hover:border-accent/45 hover:bg-bg-muted focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-70"
            disabled={Boolean(creatingTemplateId)}
            key={template.id}
            type="button"
            onClick={() => onCreateTemplate(template.id)}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <LayoutTemplate aria-hidden className="h-4 w-4 shrink-0 text-accent" />
                  <h3 className="truncate text-sm font-semibold text-fg">{template.name[locale]}</h3>
                </div>
                <p className="mt-2 line-clamp-2 text-sm leading-6 text-fg-muted">
                  {template.description[locale]}
                </p>
              </div>
              {isCreating ? <Chip variant="running">{t("sessions.creating")}</Chip> : null}
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {template.tags.map((tag) => (
                <span
                  className="rounded-full bg-bg-muted px-2 py-0.5 text-[11px] font-medium text-fg-muted ring-1 ring-border/40"
                  key={tag}
                >
                  {tag}
                </span>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {template.compile_targets.map((target) => (
                <Chip className="px-2 py-0.5 text-[11px]" key={target} variant="draft">
                  {target}
                </Chip>
              ))}
            </div>
          </button>
        );
      })}
    </div>
  );
}
