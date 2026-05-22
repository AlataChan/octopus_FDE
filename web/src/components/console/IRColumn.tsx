import { type KeyboardEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { CompileWarning, IRDiffResponse, ValidationFailure } from "../../lib/types";
import {
  findNodeById,
  nodeIdFromPath,
  type FlowDiffSummary,
  type LoomIR
} from "../../lib/flow-layout";
import { Card, CardHeader } from "../ui/Card";
import { Chip } from "../ui/Chip";
import { FlowCanvas } from "./FlowCanvas";
import { IRDiffView } from "./IRDiffView";
import { IRView } from "./IRView";
import { NodeInspectDrawer } from "./NodeInspectDrawer";
import { ValidatorPanel } from "./ValidatorPanel";

type Props = {
  compileWarningCount?: number;
  compileWarnings?: CompileWarning[];
  diffSummary?: FlowDiffSummary | null;
  diff: IRDiffResponse | null;
  errors: ValidationFailure[];
  highlightedPath?: string | null;
  ir: unknown | null;
  onSelectedNodeIdChange: (nodeId: string | null) => void;
  onSelectPath: (path: string) => void;
  resetKey?: string;
  selectedNodeId: string | null;
  status: string;
};

const tabs = ["flow", "yaml", "issues", "diff"] as const;
type TabId = (typeof tabs)[number];

export function IRColumn({
  compileWarningCount = 0,
  compileWarnings = [],
  diffSummary = null,
  diff,
  errors,
  highlightedPath,
  ir,
  onSelectedNodeIdChange,
  onSelectPath,
  resetKey,
  selectedNodeId,
  status
}: Props) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TabId>("flow");
  const flowIr = isLoomIR(ir) ? ir : null;
  const selectedNode = findNodeById(flowIr, selectedNodeId);

  useEffect(() => {
    setActiveTab("flow");
  }, [resetKey]);

  function tabId(tab: TabId) {
    return `ir-tab-${tab}`;
  }

  function panelId(tab: TabId) {
    return `ir-tabpanel-${tab}`;
  }

  function handleSelectPath(path: string) {
    onSelectPath(path);
    setActiveTab("yaml");

    if (typeof window === "undefined" || !window.requestAnimationFrame) {
      return;
    }

    window.requestAnimationFrame(() => {
      const key = path.split(".").pop()?.replace(/\[\d+\]/g, "");
      if (!key) {
        return;
      }

      const root = document.querySelector("[data-ir-root]");
      if (!root) {
        return;
      }

      const target = Array.from(root.querySelectorAll("[data-ir-line]")).find((element) => {
        const pathKey = element.getAttribute("data-ir-path");
        return pathKey === key || (element.textContent || "").trimStart().startsWith(`${key}:`);
      });

      if (target && "scrollIntoView" in target) {
        const motionOk =
          typeof window.matchMedia !== "function" ||
          !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        (target as HTMLElement).scrollIntoView({
          behavior: motionOk ? "smooth" : "auto",
          block: "center"
        });
      }
    });
  }

  function handleIssueSelectPath(path: string) {
    onSelectPath(path);
    const nodeId = nodeIdFromPath(path, flowIr);
    if (nodeId) {
      onSelectedNodeIdChange(nodeId);
      setActiveTab("flow");
      return;
    }
    setActiveTab("yaml");
  }

  function handleShowYaml(nodeId: string) {
    onSelectedNodeIdChange(nodeId);
    onSelectPath(`nodes.${nodeId}`);
    setActiveTab("yaml");
  }

  function handleShowIssues(nodeId: string) {
    onSelectedNodeIdChange(nodeId);
    setActiveTab("issues");
  }

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, tab: TabId) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
      return;
    }

    event.preventDefault();
    const direction = event.key === "ArrowRight" ? 1 : -1;
    const currentIndex = tabs.indexOf(tab);
    const nextIndex = (currentIndex + direction + tabs.length) % tabs.length;
    document.getElementById(tabId(tabs[nextIndex]))?.focus();
  }

  function renderTab(tab: TabId) {
    const selected = activeTab === tab;
    const label = t(`ir.tab.${tab}`);

    return (
      <button
        aria-controls={panelId(tab)}
        aria-selected={selected}
        className={
          selected
            ? "inline-flex h-8 items-center gap-1.5 rounded-lg bg-bg-app/60 px-3 text-xs font-semibold text-fg ring-1 ring-accent/30"
            : "inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-fg-muted hover:bg-bg-muted hover:text-fg"
        }
        id={tabId(tab)}
        key={tab}
        role="tab"
        tabIndex={selected ? 0 : -1}
        type="button"
        onClick={() => setActiveTab(tab)}
        onKeyDown={(event) => handleTabKeyDown(event, tab)}
      >
        <span>{label}</span>
        {tab === "issues" ? (
          <span
            className={
              errors.length > 0
                ? "rounded-full bg-destructive/15 px-1.5 py-0.5 text-[10px] leading-none text-destructive ring-1 ring-destructive/25"
                : "rounded-full bg-bg-muted px-1.5 py-0.5 text-[10px] leading-none text-fg-muted ring-1 ring-border/50"
            }
          >
            {errors.length}
          </span>
        ) : null}
      </button>
    );
  }

  return (
    <Card className="flex h-full min-h-0 min-w-0 flex-col">
      <CardHeader
        action={
          <div className="flex flex-wrap justify-end gap-2">
            <Chip variant={errors.length ? "failed" : ir ? "ok" : "draft"}>
              {errors.length
                ? t("validator.issueCount", { count: errors.length })
                : ir
                  ? t("validator.ok")
                  : t("session.noIr")}
            </Chip>
            {compileWarningCount > 0 ? (
              <Chip variant="warning">{t("compile.warningCount", { count: compileWarningCount })}</Chip>
            ) : null}
          </div>
        }
        subtitle={t("ir.panelSubtitle")}
        title={t("ir.panelTitle")}
      />
      <div
        aria-label={t("ir.panelTitle")}
        className="flex shrink-0 gap-1 border-b border-border/30 px-2 py-1.5"
        role="tablist"
      >
        {tabs.map((tab) => renderTab(tab))}
      </div>
      <div
        aria-labelledby={tabId(activeTab)}
        className="relative min-h-0 flex-1 overflow-hidden"
        id={panelId(activeTab)}
        role="tabpanel"
        tabIndex={0}
      >
        {activeTab === "flow" ? (
          <>
            <FlowCanvas
              diffSummary={diffSummary}
              errors={errors}
              ir={flowIr}
              selectedNodeId={selectedNodeId}
              warnings={compileWarnings}
              onNodeSelect={onSelectedNodeIdChange}
              onShowIssues={handleShowIssues}
              onSwitchToYaml={() => setActiveTab("yaml")}
            />
            <NodeInspectDrawer
              ir={flowIr}
              node={selectedNode}
              onClose={() => onSelectedNodeIdChange(null)}
              onShowIssues={handleShowIssues}
              onShowYaml={handleShowYaml}
            />
          </>
        ) : activeTab === "yaml" ? (
          <IRView errors={errors} highlightedPath={highlightedPath} ir={ir} status={status} />
        ) : activeTab === "issues" ? (
          <ValidatorPanel errors={errors} variant="embedded" onSelectPath={handleIssueSelectPath} />
        ) : (
          <IRDiffView diff={diff} mode="embedded" onSelectPath={handleSelectPath} />
        )}
      </div>
    </Card>
  );
}

function isLoomIR(ir: unknown): ir is LoomIR {
  return Boolean(ir && typeof ir === "object" && Array.isArray((ir as { nodes?: unknown }).nodes));
}
