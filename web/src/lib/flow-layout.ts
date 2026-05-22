import dagre from "dagre";
import type { Edge, Node } from "@xyflow/react";
import type { CompileWarning, ValidationFailure } from "./types";

const NODE_WIDTH = 220;
const NODE_HEIGHT = 104;
const VALID_NODE_TYPES = new Set([
  "trigger",
  "llm",
  "retrieval",
  "http",
  "code",
  "condition",
  "loop",
  "parallel",
  "agent",
  "output"
]);

export type LoomIRNode = {
  id: string;
  type: string;
  rationale?: string;
  next?: string;
  default?: string;
  branches?: unknown;
  [key: string]: unknown;
};

export type LoomIREdge = {
  from: string;
  to: string;
  label?: string;
};

type EdgeCandidate = LoomIREdge & {
  sourceKind: "explicit" | "implicit";
};

export type LoomIR = {
  nodes: LoomIRNode[];
  edges?: LoomIREdge[];
  [key: string]: unknown;
};

export type FlowDiffSummary = {
  added_node_ids: string[];
  removed_node_ids: string[];
  modified_node_ids?: string[];
};

export type FlowNodeData = {
  [key: string]: unknown;
  diffStatus?: "added" | "modified" | "removed";
  errors: ValidationFailure[];
  id: string;
  issueCount: number;
  keyFields: Array<{ label: string; value: string }>;
  nodeType: string;
  onShowIssues?: (nodeId: string) => void;
  rationale?: string;
  rawNode: LoomIRNode;
  selected: boolean;
  warningCount: number;
  warnings: CompileWarning[];
};

export type FlowEdgeData = {
  label?: string;
};

export type FlowNodeModel = Node<FlowNodeData, "flowNode">;

export type FlowGraph = {
  edges: Array<Edge<FlowEdgeData>>;
  nodes: FlowNodeModel[];
};

export type IrToFlowGraphOptions = {
  diffSummary?: FlowDiffSummary | null;
  errors?: ValidationFailure[];
  onShowIssues?: (nodeId: string) => void;
  selectedNodeId?: string | null;
  warnings?: CompileWarning[];
};

export class FlowLayoutError extends Error {
  parsedCount: number;
  totalCount: number;

  constructor(message: string, parsedCount: number, totalCount: number) {
    super(message);
    this.name = "FlowLayoutError";
    this.parsedCount = parsedCount;
    this.totalCount = totalCount;
  }
}

export function irToFlowGraph(ir: unknown, options: IrToFlowGraphOptions = {}): FlowGraph {
  const normalized = normalizeIr(ir);
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: "LR", nodesep: 60, ranksep: 80 });

  const seen = new Set<string>();
  let parsedCount = 0;
  for (const node of normalized.nodes) {
    if (!node.id || typeof node.id !== "string") {
      throw new FlowLayoutError("IR node is missing a string id.", parsedCount, normalized.nodes.length);
    }
    if (seen.has(node.id)) {
      throw new FlowLayoutError(`Duplicate IR node id: ${node.id}`, parsedCount, normalized.nodes.length);
    }
    if (!VALID_NODE_TYPES.has(node.type)) {
      throw new FlowLayoutError(`Unsupported IR node type: ${node.type}`, parsedCount, normalized.nodes.length);
    }
    seen.add(node.id);
    graph.setNode(node.id, { height: NODE_HEIGHT, width: NODE_WIDTH });
    parsedCount += 1;
  }

  if (!normalized.nodes.some((node) => node.type === "trigger")) {
    throw new FlowLayoutError("IR must include a trigger node before it can be visualized.", parsedCount, normalized.nodes.length);
  }

  const edges = collectEdges(normalized);
  for (const edge of edges) {
    if (!seen.has(edge.from) || !seen.has(edge.to)) {
      throw new FlowLayoutError(`IR edge references an unknown node: ${edge.from} -> ${edge.to}`, parsedCount, normalized.nodes.length);
    }
  }
  assertAcyclic(edges, parsedCount, normalized.nodes.length);

  for (const edge of edges) {
    graph.setEdge(edge.from, edge.to);
  }

  dagre.layout(graph);

  return {
    edges: edges.map((edge) => ({
      data: { label: edge.label },
      id: `${edge.from}->${edge.to}${edge.label ? `:${edge.label}` : ""}`,
      label: edge.label,
      source: edge.from,
      target: edge.to,
      type: "smoothstep"
    })),
    nodes: normalized.nodes.map((node) => {
      const positioned = graph.node(node.id) as { x: number; y: number } | undefined;
      const errors = (options.errors || []).filter((error) =>
        errorBelongsToNode(error, node.id, normalized.nodes)
      );
      const warnings = (options.warnings || []).filter((warning) => warning.node_id === node.id);
      return {
        data: {
          diffStatus: diffStatusForNode(node.id, options.diffSummary),
          errors,
          id: node.id,
          issueCount: errors.length,
          keyFields: keyFieldsForNode(node),
          nodeType: node.type,
          onShowIssues: options.onShowIssues,
          rationale: typeof node.rationale === "string" ? node.rationale : undefined,
          rawNode: node,
          selected: node.id === options.selectedNodeId,
          warningCount: warnings.length,
          warnings
        },
        id: node.id,
        position: {
          x: (positioned?.x ?? 0) - NODE_WIDTH / 2,
          y: (positioned?.y ?? 0) - NODE_HEIGHT / 2
        },
        type: "flowNode"
      };
    })
  };
}

export function computeDiffSummary(beforeIr: unknown, afterIr: unknown): FlowDiffSummary {
  const before = beforeIr ? normalizeIr(beforeIr) : { nodes: [] };
  const after = afterIr ? normalizeIr(afterIr) : { nodes: [] };
  const beforeById = new Map(before.nodes.map((node) => [node.id, node]));
  const afterById = new Map(after.nodes.map((node) => [node.id, node]));
  const added_node_ids = after.nodes
    .filter((node) => !beforeById.has(node.id))
    .map((node) => node.id);
  const removed_node_ids = before.nodes
    .filter((node) => !afterById.has(node.id))
    .map((node) => node.id);
  const modified_node_ids = after.nodes
    .filter((node) => {
      const previous = beforeById.get(node.id);
      return previous ? stableStringify(previous) !== stableStringify(node) : false;
    })
    .map((node) => node.id);

  return { added_node_ids, modified_node_ids, removed_node_ids };
}

export function getNodeReferences(ir: unknown, nodeId: string): { incoming: string[]; outgoing: string[] } {
  const normalized = normalizeIr(ir);
  const edges = collectEdges(normalized);
  return {
    incoming: edges.filter((edge) => edge.to === nodeId).map((edge) => edge.from),
    outgoing: edges.filter((edge) => edge.from === nodeId).map((edge) => edge.to)
  };
}

export function findNodeById(ir: unknown, nodeId: string | null): LoomIRNode | null {
  if (!nodeId) {
    return null;
  }
  try {
    return normalizeIr(ir).nodes.find((node) => node.id === nodeId) || null;
  } catch {
    return null;
  }
}

export function nodeIdFromPath(path: string | null | undefined, ir: unknown): string | null {
  if (!path) {
    return null;
  }
  const normalized = safeNormalizeIr(ir);
  const nodeIds = new Set(normalized?.nodes.map((node) => node.id) || []);

  const dotted = path.match(/(?:^|\.)nodes\.([A-Za-z0-9_-]+)/)?.[1];
  if (dotted && nodeIds.has(dotted)) {
    return dotted;
  }

  const indexed = path.match(/nodes\[(\d+)\]/)?.[1];
  if (indexed && normalized) {
    return normalized.nodes[Number(indexed)]?.id || null;
  }

  return Array.from(nodeIds).find((id) => path.includes(id)) || null;
}

function normalizeIr(ir: unknown): LoomIR {
  if (!ir || typeof ir !== "object") {
    throw new FlowLayoutError("IR is empty or not an object.", 0, 0);
  }
  const candidate = ir as { nodes?: unknown; edges?: unknown };
  if (!Array.isArray(candidate.nodes)) {
    throw new FlowLayoutError("IR must contain a nodes array.", 0, 0);
  }
  return {
    ...(ir as Record<string, unknown>),
    edges: Array.isArray(candidate.edges)
      ? candidate.edges.map(normalizeEdge).filter((edge): edge is LoomIREdge => Boolean(edge))
      : undefined,
    nodes: candidate.nodes.map(normalizeNode)
  };
}

function safeNormalizeIr(ir: unknown): LoomIR | null {
  try {
    return normalizeIr(ir);
  } catch {
    return null;
  }
}

function normalizeNode(node: unknown): LoomIRNode {
  if (!node || typeof node !== "object") {
    return { id: "", type: "" };
  }
  const row = node as Record<string, unknown>;
  return {
    ...row,
    id: typeof row.id === "string" ? row.id : "",
    type: typeof row.type === "string" ? row.type : ""
  };
}

function normalizeEdge(edge: unknown): LoomIREdge | null {
  if (!edge || typeof edge !== "object") {
    return null;
  }
  const row = edge as Record<string, unknown>;
  if (typeof row.from !== "string" || typeof row.to !== "string") {
    return null;
  }
  const label =
    typeof row.when === "string"
      ? row.when
      : typeof row.label === "string"
        ? row.label
        : undefined;
  return {
    from: row.from,
    label,
    to: row.to
  };
}

function collectEdges(ir: LoomIR): LoomIREdge[] {
  const explicit: EdgeCandidate[] = (ir.edges ?? []).map((edge) => ({
    ...edge,
    sourceKind: "explicit"
  }));
  const implicit: EdgeCandidate[] = ir.nodes.flatMap((node) => {
    const rows: EdgeCandidate[] = [];
    if (typeof node.next === "string") {
      rows.push({ from: node.id, sourceKind: "implicit", to: node.next });
    }
    if (typeof node.default === "string") {
      rows.push({ from: node.id, label: "default", sourceKind: "implicit", to: node.default });
    }
    for (const target of branchTargets(node.branches)) {
      rows.push({ from: node.id, label: target.label, sourceKind: "implicit", to: target.to });
    }
    return rows;
  });

  const byEndpoints = new Map<string, EdgeCandidate>();
  for (const edge of [...explicit, ...implicit]) {
    const key = `${edge.from}->${edge.to}`;
    const current = byEndpoints.get(key);
    if (!current || shouldReplaceEdge(current, edge)) {
      byEndpoints.set(key, edge);
    }
  }
  return Array.from(byEndpoints.values()).map((edge) => ({
    from: edge.from,
    label: edge.label,
    to: edge.to
  }));
}

function shouldReplaceEdge(current: EdgeCandidate, candidate: EdgeCandidate): boolean {
  if (candidate.sourceKind === "explicit" && candidate.label) {
    return true;
  }
  if (current.sourceKind === "explicit" && current.label) {
    return false;
  }
  if (!current.label && candidate.label) {
    return true;
  }
  return false;
}

function branchTargets(branches: unknown): Array<{ label?: string; to: string }> {
  if (!branches) {
    return [];
  }
  if (Array.isArray(branches)) {
    return branches.flatMap((branch, index) => {
      if (branch && typeof branch === "object") {
        const row = branch as Record<string, unknown>;
        return typeof row.next === "string"
          ? [{ label: typeof row.when === "string" ? row.when : `branch ${index + 1}`, to: row.next }]
          : [];
      }
      return typeof branch === "string" ? [{ label: `branch ${index + 1}`, to: branch }] : [];
    });
  }
  if (typeof branches === "object") {
    return Object.entries(branches as Record<string, unknown>).flatMap(([label, value]) => {
      if (typeof value === "string") {
        return [{ label, to: value }];
      }
      if (Array.isArray(value)) {
        return [];
      }
      if (value && typeof value === "object" && typeof (value as Record<string, unknown>).next === "string") {
        return [{ label, to: (value as Record<string, string>).next }];
      }
      return [];
    });
  }
  return [];
}

function assertAcyclic(edges: LoomIREdge[], parsedCount: number, totalCount: number) {
  const outgoing = new Map<string, string[]>();
  for (const edge of edges) {
    outgoing.set(edge.from, [...(outgoing.get(edge.from) || []), edge.to]);
  }

  const visiting = new Set<string>();
  const visited = new Set<string>();

  function visit(nodeId: string): boolean {
    if (visiting.has(nodeId)) {
      return false;
    }
    if (visited.has(nodeId)) {
      return true;
    }
    visiting.add(nodeId);
    for (const next of outgoing.get(nodeId) || []) {
      if (!visit(next)) {
        return false;
      }
    }
    visiting.delete(nodeId);
    visited.add(nodeId);
    return true;
  }

  for (const nodeId of outgoing.keys()) {
    if (!visit(nodeId)) {
      throw new FlowLayoutError("IR graph contains a cycle and cannot be auto-laid out safely.", parsedCount, totalCount);
    }
  }
}

function errorBelongsToNode(error: ValidationFailure, nodeId: string, nodes: LoomIRNode[]) {
  const location = error.location || "";
  const exact = nodeIdFromPath(location, { nodes });
  return exact === nodeId;
}

function diffStatusForNode(nodeId: string, diffSummary?: FlowDiffSummary | null) {
  if (!diffSummary) {
    return undefined;
  }
  if (diffSummary.added_node_ids.includes(nodeId)) {
    return "added";
  }
  if (diffSummary.removed_node_ids.includes(nodeId)) {
    return "removed";
  }
  if ((diffSummary.modified_node_ids || []).includes(nodeId)) {
    return "modified";
  }
  return undefined;
}

function keyFieldsForNode(node: LoomIRNode): Array<{ label: string; value: string }> {
  if (node.type === "llm") {
    return compactFields([["model", node.model], ["temp", node.temperature]]);
  }
  if (node.type === "retrieval") {
    return compactFields([["mode", node.mode || node.dataset], ["top_k", node.top_k]]);
  }
  if (node.type === "http") {
    return compactFields([["method", node.method], ["url", node.url]]);
  }
  if (node.type === "code") {
    return compactFields([["language", node.language]]);
  }
  if (node.type === "condition") {
    return [{ label: "branches", value: String(branchTargets(node.branches).length) }];
  }
  return [];
}

function compactFields(rows: Array<[string, unknown]>): Array<{ label: string; value: string }> {
  return rows
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .slice(0, 2)
    .map(([label, value]) => ({ label, value: String(value) }));
}

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, row]) => `${JSON.stringify(key)}:${stableStringify(row)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}
