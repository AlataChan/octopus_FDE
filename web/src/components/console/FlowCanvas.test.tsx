import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ComponentType, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import { FlowCanvas } from "./FlowCanvas";

vi.mock("@xyflow/react", () => ({
  Background: () => <div data-testid="flow-background" />,
  Controls: () => <div data-testid="flow-controls" />,
  Handle: () => <span data-testid="flow-handle" />,
  Position: { Left: "left", Right: "right" },
  ReactFlowProvider: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  ReactFlow: ({
    edges,
    nodeTypes,
    nodes,
    onNodeClick
  }: {
    edges: Array<{ id: string; source: string; target: string }>;
    nodeTypes: Record<string, ComponentType<{ data: unknown }>>;
    nodes: Array<{ data: unknown; id: string; type?: string }>;
    onNodeClick?: (event: unknown, node: { id: string }) => void;
  }) => (
    <div data-testid="react-flow">
      {nodes.map((node) => {
        const NodeComponent = nodeTypes[node.type || "flowNode"];
        return (
          <div
            data-testid={`mock-flow-node-${node.id}`}
            key={node.id}
            role="button"
            tabIndex={0}
            onClick={(event) => onNodeClick?.(event, node)}
          >
            <NodeComponent data={node.data} />
          </div>
        );
      })}
      {edges.map((edge) => (
        <span data-testid="mock-flow-edge" key={edge.id}>
          {edge.source}-&gt;{edge.target}
        </span>
      ))}
    </div>
  ),
  useReactFlow: () => ({ fitView: vi.fn() })
}));

afterEach(cleanup);

const ir = {
  nodes: [
    { id: "start", type: "trigger", rationale: "Start" },
    { id: "answer", type: "llm", model: "configured-planner-model" },
    { id: "out", type: "output" }
  ],
  edges: [
    { from: "start", to: "answer" },
    { from: "answer", to: "out" }
  ]
};

describe("FlowCanvas", () => {
  it("renders nodes and edges", () => {
    render(<FlowCanvas ir={ir} selectedNodeId={null} onNodeSelect={vi.fn()} />);

    expect(screen.getByTestId("mock-flow-node-start")).toBeInTheDocument();
    expect(screen.getByTestId("mock-flow-node-answer")).toBeInTheDocument();
    expect(screen.getAllByTestId("mock-flow-edge")).toHaveLength(2);
  });

  it("clicking a node selects it", () => {
    const onNodeSelect = vi.fn();
    render(<FlowCanvas ir={ir} selectedNodeId={null} onNodeSelect={onNodeSelect} />);

    fireEvent.click(screen.getByTestId("mock-flow-node-answer"));

    expect(onNodeSelect).toHaveBeenCalledWith("answer");
  });
});
