import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { computeDiffSummary, FlowLayoutError, irToFlowGraph } from "./flow-layout";

const ir = {
  ir_version: "0.4",
  nodes: [
    { id: "start", type: "trigger", rationale: "Start" },
    { id: "retrieve", type: "retrieval", dataset: "product_kb", top_k: 5 },
    { id: "answer", type: "llm", model: "configured-planner-model" },
    { id: "out", type: "output" }
  ],
  edges: [
    { from: "start", to: "retrieve" },
    { from: "retrieve", to: "answer" },
    { from: "answer", to: "out" }
  ]
};

describe("flow-layout", () => {
  it("generates flow nodes and edges from IR", () => {
    const graph = irToFlowGraph(ir, {
      errors: [{ bucket: "typecheck", detail: "bad model", location: "nodes.answer.model" }],
      selectedNodeId: "answer"
    });

    expect(graph.nodes).toHaveLength(4);
    expect(graph.edges.map((edge) => `${edge.source}->${edge.target}`)).toEqual([
      "start->retrieve",
      "retrieve->answer",
      "answer->out"
    ]);
    const answer = graph.nodes.find((node) => node.id === "answer");
    expect(answer?.data.selected).toBe(true);
    expect(answer?.data.issueCount).toBe(1);
    expect(answer?.data.keyFields[0]).toEqual({
      label: "model",
      value: "configured-planner-model"
    });
  });

  it("computes node diff summaries", () => {
    const next = {
      ...ir,
      nodes: [
        { id: "start", type: "trigger", rationale: "Start" },
        { id: "answer", type: "llm", model: "new-model" },
        { id: "out", type: "output" },
        { id: "audit", type: "output" }
      ]
    };

    expect(computeDiffSummary(ir, next)).toEqual({
      added_node_ids: ["audit"],
      modified_node_ids: ["answer"],
      removed_node_ids: ["retrieve"]
    });
  });

  it("dedupes condition edges and preserves the best available labels", () => {
    const graph = irToFlowGraph({
      ir_version: "0.4",
      nodes: [
        { id: "start", type: "trigger" },
        {
          id: "route",
          type: "condition",
          branches: [{ when: "fail", next: "fail_out" }],
          default: "pass_out"
        },
        { id: "fail_out", type: "output" },
        { id: "pass_out", type: "output" }
      ],
      edges: [
        { from: "start", to: "route" },
        { from: "route", to: "fail_out", when: "explicit fail" },
        { from: "route", to: "pass_out" }
      ]
    });

    const routeEdges = graph.edges
      .filter((edge) => edge.source === "route")
      .map((edge) => ({
        label: edge.label,
        target: edge.target
      }));

    expect(routeEdges).toEqual([
      { label: "explicit fail", target: "fail_out" },
      { label: "default", target: "pass_out" }
    ]);
  });

  it("rejects malformed IR graphs loaded from the fixture file", () => {
    const fixturePath = resolve(__dirname, "../../tests/fixtures/malformed-ir.yaml");
    const raw = readFileSync(fixturePath, "utf-8");
    const cases = parseFixtureDocuments(raw);

    expect(cases).toHaveLength(3);

    for (const { name, ir: fixtureIr } of cases) {
      expect(
        () => irToFlowGraph(fixtureIr),
        `fixture "${name}" should throw FlowLayoutError`
      ).toThrow(FlowLayoutError);
    }
  });
});

function parseFixtureDocuments(raw: string): Array<{ name: string; ir: unknown }> {
  const chunks = raw.split(/^---$/m).filter((c) => c.trim());
  return chunks.map(parseOneFixture);
}

function parseOneFixture(chunk: string): { name: string; ir: unknown } {
  const lines = chunk.split("\n");
  const doc: Record<string, unknown> = {};
  const nodesList: Array<Record<string, unknown>> = [];
  const edgesList: Array<Record<string, unknown>> = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    const itemMatch = trimmed.match(/^-\s*\{(.+)\}$/);
    if (itemMatch) {
      const obj = parseInlineObject(itemMatch[1]);
      if (doc.nodes && !doc.edges) {
        nodesList.push(obj);
      } else {
        edgesList.push(obj);
      }
      continue;
    }

    const kvMatch = trimmed.match(/^(\w[\w_-]*):\s*(.*)$/);
    if (!kvMatch) continue;

    const [, key, rawValue] = kvMatch;
    const value = rawValue.replace(/#.*$/, "").trim();

    if (value) {
      doc[key] = parseScalarValue(value);
    } else {
      doc[key] = key === "nodes" ? nodesList : key === "edges" ? edgesList : null;
    }
  }

  return {
    name: String(doc.name || ""),
    ir: {
      nodes: doc.nodes || nodesList,
      ...(doc.edges || edgesList.length > 0 ? { edges: doc.edges || edgesList } : {})
    }
  };
}

function parseInlineObject(raw: string): Record<string, unknown> {
  const obj: Record<string, unknown> = {};
  const pairs = raw.match(/(\w[\w_-]*):\s*('[^']*'|"[^"]*"|[^,]+)/g);
  if (!pairs) return obj;

  for (const pair of pairs) {
    const colonIdx = pair.indexOf(":");
    const key = pair.slice(0, colonIdx).trim();
    const val = pair.slice(colonIdx + 1).trim().replace(/^["']|["']$/g, "");
    obj[key] = parseScalarValue(val);
  }
  return obj;
}

function parseScalarValue(value: string): string | number | boolean | null {
  if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value);
  if (value === "true") return true;
  if (value === "false") return false;
  if (value === "null" || value === "~") return null;
  return value;
}
