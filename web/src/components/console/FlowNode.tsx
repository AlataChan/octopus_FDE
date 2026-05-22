import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import {
  Bot,
  Brain,
  CheckCircle2,
  Code2,
  Database,
  GitBranch,
  Globe2,
  Play,
  Repeat,
  Split,
  TerminalSquare
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "../../lib/cn";
import type { FlowNodeData } from "../../lib/flow-layout";

type AppFlowNode = Node<FlowNodeData, "flowNode">;

export function FlowNode({ data }: NodeProps<AppFlowNode>) {
  const { t } = useTranslation();
  const Icon = iconForType(data.nodeType);
  const status = data.issueCount > 0 ? "failed" : data.warningCount > 0 ? "warning" : "ok";

  return (
    <div
      className={cn(
        "relative w-[220px] rounded-lg border bg-bg-surface px-3 py-2 text-left shadow-glow transition-colors",
        data.selected ? "border-accent ring-2 ring-accent/25" : "border-border/50",
        data.diffStatus === "added" && "bg-accent/5",
        data.diffStatus === "removed" && "bg-destructive/5",
        data.diffStatus === "modified" && "bg-warning/5"
      )}
      data-testid={`flow-node-${data.id}`}
    >
      <Handle
        className="!h-2.5 !w-2.5 !border-border !bg-bg-surface"
        position={Position.Left}
        type="target"
      />
      <Handle
        className="!h-2.5 !w-2.5 !border-border !bg-accent"
        position={Position.Right}
        type="source"
      />
      <div className="flex min-w-0 items-center gap-2">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-bg-app text-fg-muted ring-1 ring-border/40">
          <Icon aria-hidden className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-xs font-semibold text-fg">{data.id}</p>
          <p className="truncate text-[11px] uppercase tracking-wide text-fg-muted">{data.nodeType}</p>
        </div>
        <span
          aria-label={t(`flow.status.${status}`)}
          className={cn(
            "h-2.5 w-2.5 shrink-0 rounded-full",
            status === "failed" && "bg-destructive",
            status === "warning" && "bg-warning",
            status === "ok" && "bg-accent"
          )}
          title={t(`flow.status.${status}`)}
        />
      </div>
      {data.keyFields.length ? (
        <dl className="mt-2 grid gap-1">
          {data.keyFields.map((field) => (
            <div className="flex min-w-0 gap-2 text-[11px]" key={field.label}>
              <dt className="shrink-0 text-fg-muted">{field.label}</dt>
              <dd className="truncate font-medium text-fg">{field.value}</dd>
            </div>
          ))}
        </dl>
      ) : data.rationale ? (
        <p className="mt-2 line-clamp-2 text-[11px] leading-4 text-fg-muted">{data.rationale}</p>
      ) : null}
      <div className="mt-2 flex items-center justify-between gap-2">
        <button
          className={cn(
            "rounded-full px-2 py-1 text-[10px] font-semibold ring-1",
            data.issueCount > 0
              ? "bg-destructive/10 text-destructive ring-destructive/25"
              : "bg-bg-app text-fg-muted ring-border/50"
          )}
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            data.onShowIssues?.(data.id);
          }}
        >
          {data.issueCount > 0
            ? t("flow.nodeIssues", { count: data.issueCount })
            : t("flow.nodeNoIssues")}
        </button>
        {data.warningCount > 0 ? (
          <span className="rounded-full bg-warning/10 px-2 py-1 text-[10px] font-semibold text-warning ring-1 ring-warning/25">
            {t("flow.nodeWarnings", { count: data.warningCount })}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function iconForType(type: string) {
  if (type === "trigger") {
    return Play;
  }
  if (type === "llm") {
    return Brain;
  }
  if (type === "retrieval") {
    return Database;
  }
  if (type === "http") {
    return Globe2;
  }
  if (type === "code") {
    return Code2;
  }
  if (type === "condition") {
    return GitBranch;
  }
  if (type === "loop") {
    return Repeat;
  }
  if (type === "parallel") {
    return Split;
  }
  if (type === "agent") {
    return Bot;
  }
  if (type === "output") {
    return CheckCircle2;
  }
  return TerminalSquare;
}
