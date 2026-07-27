import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { FlowNodeData } from "../../lib/flow-layout";
import "../../lib/i18n";
import { FlowNode } from "./FlowNode";

vi.mock("@xyflow/react", () => ({
  Handle: () => <span data-testid="flow-handle" />,
  Position: { Left: "left", Right: "right" }
}));

afterEach(cleanup);

function nodeData(overrides: Partial<FlowNodeData> = {}): FlowNodeData {
  return {
    errors: [],
    id: "start",
    issueCount: 0,
    keyFields: [],
    nodeType: "trigger",
    rawNode: { id: "start", type: "trigger" },
    selected: false,
    warningCount: 0,
    warnings: [],
    ...overrides
  };
}

type FlowNodeProps = Parameters<typeof FlowNode>[0];

function nodeProps(data: FlowNodeData): FlowNodeProps {
  return {
    data,
    deletable: true,
    draggable: true,
    dragging: false,
    id: data.id,
    isConnectable: true,
    positionAbsoluteX: 0,
    positionAbsoluteY: 0,
    selectable: true,
    selected: data.selected,
    type: "flowNode",
    zIndex: 0
  };
}

describe("FlowNode", () => {
  it("renders with the node id and type label", () => {
    render(<FlowNode {...nodeProps(nodeData({ id: "retrieve", nodeType: "retrieval" }))} />);

    expect(screen.getByText("retrieve")).toBeInTheDocument();
    expect(screen.getByText("retrieval")).toBeInTheDocument();
  });

  it("shows issues badge when issueCount is greater than zero", () => {
    render(
      <FlowNode
        {...nodeProps(
          nodeData({
            id: "bad-node",
            issueCount: 3,
            nodeType: "llm"
          })
        )}
      />
    );

    expect(screen.getByText(/3.*问题|3.*issues/i)).toBeInTheDocument();
  });

  it("shows warnings badge when warningCount is greater than zero", () => {
    render(
      <FlowNode
        {...nodeProps(
          nodeData({
            id: "warn-node",
            nodeType: "llm",
            warningCount: 2
          })
        )}
      />
    );

    expect(screen.getByText(/2.*警告|2.*warnings/i)).toBeInTheDocument();
  });

  it("displays key fields for an llm node", () => {
    render(
      <FlowNode
        {...nodeProps(
          nodeData({
            id: "llm-1",
            keyFields: [
              { label: "model", value: "gpt-4" },
              { label: "temp", value: "0.7" }
            ],
            nodeType: "llm"
          })
        )}
      />
    );

    expect(screen.getByText("model")).toBeInTheDocument();
    expect(screen.getByText("gpt-4")).toBeInTheDocument();
    expect(screen.getByText("temp")).toBeInTheDocument();
    expect(screen.getByText("0.7")).toBeInTheDocument();
  });

  it("displays rationale when no key fields are present", () => {
    render(
      <FlowNode
        {...nodeProps(
          nodeData({
            id: "trigger",
            nodeType: "trigger",
            rationale: "Entry point for the workflow"
          })
        )}
      />
    );

    expect(screen.getByText("Entry point for the workflow")).toBeInTheDocument();
  });

  it("shows no-issues label when issueCount is zero", () => {
    render(<FlowNode {...nodeProps(nodeData())} />);

    expect(screen.getByText(/无问题|No issues/i)).toBeInTheDocument();
  });

  it("applies selected styling when selected is true", () => {
    const { container } = render(
      <FlowNode {...nodeProps(nodeData({ selected: true }))} />
    );

    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("ring-2");
  });

  it("applies added diff status styling", () => {
    const { container } = render(
      <FlowNode {...nodeProps(nodeData({ diffStatus: "added" }))} />
    );

    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("bg-accent/5");
  });

  it("applies removed diff status styling", () => {
    const { container } = render(
      <FlowNode {...nodeProps(nodeData({ diffStatus: "removed" }))} />
    );

    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("bg-destructive/5");
  });

  it("applies modified diff status styling", () => {
    const { container } = render(
      <FlowNode {...nodeProps(nodeData({ diffStatus: "modified" }))} />
    );

    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("bg-warning/5");
  });

  it("calls onShowIssues when the issues button is clicked", () => {
    const onShowIssues = vi.fn();
    render(
      <FlowNode
        {...nodeProps(
          nodeData({
            id: "node-1",
            issueCount: 1,
            onShowIssues
          })
        )}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /1.*问题|1.*issue/i }));
    expect(onShowIssues).toHaveBeenCalledWith("node-1");
  });
});
