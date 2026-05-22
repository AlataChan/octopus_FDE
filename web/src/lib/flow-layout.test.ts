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

  it("rejects malformed IR graphs with useful layout errors", () => {
    const cases = [
      {
        ir: {
          nodes: [
            { id: "start", type: "trigger", next: "answer" },
            { id: "answer", type: "llm", next: "start" }
          ]
        },
        message: "cycle"
      },
      {
        ir: {
          nodes: [{ id: "answer", type: "llm" }]
        },
        message: "trigger"
      },
      {
        ir: {
          nodes: [
            { id: "start", type: "trigger", next: "vision" },
            { id: "vision", type: "unsupported" }
          ]
        },
        message: "Unsupported"
      }
    ];

    for (const row of cases) {
      expect(() => irToFlowGraph(row.ir)).toThrow(FlowLayoutError);
      expect(() => irToFlowGraph(row.ir)).toThrow(row.message);
    }
  });
});
