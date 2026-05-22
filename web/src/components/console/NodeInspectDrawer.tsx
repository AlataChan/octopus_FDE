import { X } from "lucide-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  getNodeReferences,
  type LoomIR,
  type LoomIRNode
} from "../../lib/flow-layout";
import { Button } from "../ui/Button";

type Props = {
  ir: LoomIR | null;
  node: LoomIRNode | null;
  onClose: () => void;
  onShowIssues: (nodeId: string) => void;
  onShowYaml: (nodeId: string) => void;
};

export function NodeInspectDrawer({
  ir,
  node,
  onClose,
  onShowIssues,
  onShowYaml
}: Props) {
  const { t } = useTranslation();
  const references = useMemo(
    () => (ir && node ? getNodeReferences(ir, node.id) : { incoming: [], outgoing: [] }),
    [ir, node]
  );

  if (!node) {
    return null;
  }

  const fields = Object.entries(node).filter(([key]) => key !== "id" && key !== "type");

  return (
    <aside
      aria-label={t("flow.drawerTitle", { id: node.id })}
      className="absolute inset-y-0 right-0 z-20 flex w-80 max-w-[85%] flex-col border-l border-border/50 bg-bg-surface shadow-glow"
      data-testid="node-inspect-drawer"
    >
      <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border/30 px-4 py-3">
        <div className="min-w-0">
          <h3 className="truncate font-mono text-sm font-semibold text-fg">{node.id}</h3>
          <p className="mt-1 text-xs uppercase tracking-wide text-fg-muted">{node.type}</p>
        </div>
        <Button
          aria-label={t("flow.closeDrawer")}
          icon={<X aria-hidden className="h-4 w-4" />}
          size="sm"
          variant="ghost"
          onClick={onClose}
        />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        <section>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-fg-muted">
            {t("flow.fields")}
          </h4>
          <dl className="mt-2 grid gap-2">
            {fields.map(([key, value]) => (
              <div className="rounded-lg border border-border/40 bg-bg-app/45 p-2" key={key}>
                <dt className="font-mono text-[11px] font-semibold text-fg-muted">{key}</dt>
                <dd className="mt-1 break-words font-mono text-xs leading-5 text-fg">
                  {formatField(value)}
                </dd>
              </div>
            ))}
          </dl>
        </section>
        <section className="mt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-fg-muted">
            {t("flow.references")}
          </h4>
          <div className="mt-2 grid gap-2 text-xs text-fg-muted">
            <p>
              <span className="font-semibold text-fg">{t("flow.incoming")}: </span>
              {references.incoming.length ? references.incoming.join(", ") : t("flow.none")}
            </p>
            <p>
              <span className="font-semibold text-fg">{t("flow.outgoing")}: </span>
              {references.outgoing.length ? references.outgoing.join(", ") : t("flow.none")}
            </p>
          </div>
        </section>
      </div>
      <div className="grid shrink-0 grid-cols-2 gap-2 border-t border-border/30 p-3">
        <Button size="sm" variant="secondary" onClick={() => onShowIssues(node.id)}>
          {t("flow.viewIssues")}
        </Button>
        <Button size="sm" variant="secondary" onClick={() => onShowYaml(node.id)}>
          {t("flow.viewYaml")}
        </Button>
      </div>
    </aside>
  );
}

function formatField(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value, null, 2);
}
