import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type NodeMouseHandler,
  type NodeTypes
} from "@xyflow/react";
import { useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { CompileWarning, ValidationFailure } from "../../lib/types";
import {
  FlowLayoutError,
  irToFlowGraph,
  type FlowDiffSummary,
  type LoomIR
} from "../../lib/flow-layout";
import { FlowErrorPanel } from "./FlowErrorPanel";
import { FlowNode } from "./FlowNode";

type Props = {
  diffSummary?: FlowDiffSummary | null;
  errors?: ValidationFailure[];
  ir: LoomIR | null;
  onNodeSelect: (id: string) => void;
  onShowIssues?: (nodeId: string) => void;
  onSwitchToYaml?: () => void;
  selectedNodeId: string | null;
  warnings?: CompileWarning[];
};

const nodeTypes: NodeTypes = { flowNode: FlowNode };

export function FlowCanvas(props: Props) {
  return (
    <ReactFlowProvider>
      <FlowCanvasInner {...props} />
    </ReactFlowProvider>
  );
}

function FlowCanvasInner({
  diffSummary,
  errors = [],
  ir,
  onNodeSelect,
  onShowIssues,
  onSwitchToYaml = () => {},
  selectedNodeId,
  warnings = []
}: Props) {
  const { t } = useTranslation();
  const { fitView } = useReactFlow();
  const result = useMemo(() => {
    if (!ir) {
      return { graph: null };
    }
    try {
      return {
        graph: irToFlowGraph(ir, {
          diffSummary,
          errors,
          onShowIssues,
          selectedNodeId,
          warnings
        })
      };
    } catch (error) {
      const layoutError = error instanceof FlowLayoutError ? error : null;
      return {
        error,
        parsedCount: layoutError?.parsedCount ?? 0,
        totalCount: layoutError?.totalCount ?? 0
      };
    }
  }, [diffSummary, errors, ir, onShowIssues, selectedNodeId, warnings]);

  useEffect(() => {
    if (!selectedNodeId || !result.graph) {
      return;
    }
    window.requestAnimationFrame(() => {
      void fitView({
        duration: prefersReducedMotion() ? 0 : 240,
        nodes: [{ id: selectedNodeId }],
        padding: 0.45
      });
    });
  }, [fitView, result.graph, selectedNodeId]);

  if (!ir) {
    return (
      <section className="flex h-full min-h-0 items-center justify-center bg-bg-app/70 p-4">
        <p className="rounded-lg border border-dashed border-border/50 bg-bg-surface/70 p-4 text-sm text-fg-muted">
          {t("flow.empty")}
        </p>
      </section>
    );
  }

  if ("error" in result) {
    return (
      <FlowErrorPanel
        error={result.error}
        parsedCount={result.parsedCount}
        totalCount={result.totalCount}
        onSwitchToYaml={onSwitchToYaml}
      />
    );
  }

  const graph = result.graph;
  const changeCount = diffSummary
    ? diffSummary.added_node_ids.length +
      diffSummary.removed_node_ids.length +
      (diffSummary.modified_node_ids || []).length
    : 0;

  const handleNodeClick: NodeMouseHandler = (_event, node) => {
    onNodeSelect(node.id);
  };

  return (
    <section className="relative h-full min-h-0 overflow-hidden bg-bg-app/60" data-flow-canvas>
      {diffSummary ? (
        <div className="absolute left-3 top-3 z-10 rounded-full border border-border/50 bg-bg-surface/90 px-3 py-1 text-xs font-medium text-fg-muted shadow-glow">
          {t("flow.diffSummary", {
            added: diffSummary.added_node_ids.length,
            changed: changeCount,
            removed: diffSummary.removed_node_ids.length
          })}
        </div>
      ) : null}
      <ReactFlow
        fitView
        fitViewOptions={{ padding: 0.2 }}
        edges={graph?.edges || []}
        elementsSelectable
        nodes={graph?.nodes || []}
        nodesConnectable={false}
        nodesDraggable={false}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
      >
        <Background color="rgb(var(--border) / 0.35)" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </section>
  );
}

function prefersReducedMotion() {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}
