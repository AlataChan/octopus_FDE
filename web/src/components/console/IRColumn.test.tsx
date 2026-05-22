import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import { IRColumn } from "./IRColumn";

vi.mock("./FlowCanvas", () => ({
  FlowCanvas: ({
    selectedNodeId,
    onNodeSelect
  }: {
    selectedNodeId: string | null;
    onNodeSelect: (id: string) => void;
  }) => (
    <div data-selected-node={selectedNodeId || ""} data-testid="mock-flow-canvas">
      <button type="button" onClick={() => onNodeSelect("answer")}>
        select answer
      </button>
    </div>
  )
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

const error = {
  bucket: "typecheck",
  detail: "model is invalid",
  location: "nodes.answer.model"
};

function IRColumnHarness() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [highlightedPath, setHighlightedPath] = useState<string | null>(null);
  return (
    <IRColumn
      diff={null}
      errors={[error]}
      highlightedPath={highlightedPath}
      ir={ir}
      selectedNodeId={selectedNodeId}
      status="failed"
      onSelectedNodeIdChange={setSelectedNodeId}
      onSelectPath={setHighlightedPath}
    />
  );
}

describe("IRColumn", () => {
  it("switches between Flow, YAML, Issues, and Diff tabs", () => {
    render(<IRColumnHarness />);

    expect(screen.getByRole("tab", { name: /Flow/i })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: /YAML/i }));
    expect(screen.getByText(/Validator:/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: /问题|Issues/i }));
    expect(screen.getByText("model is invalid")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: /Diff/i }));
    expect(screen.getByText(/至少需要两个成功 turn|At least two successful turns/i)).toBeInTheDocument();
  });

  it("clicking an issue jumps back to Flow with the node selected", () => {
    render(<IRColumnHarness />);

    fireEvent.click(screen.getByRole("tab", { name: /问题|Issues/i }));
    fireEvent.click(screen.getByRole("button", { name: "nodes.answer.model" }));

    expect(screen.getByRole("tab", { name: /Flow/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("mock-flow-canvas")).toHaveAttribute("data-selected-node", "answer");
  });

  it("drawer YAML action highlights the selected node id line", () => {
    render(<IRColumnHarness />);

    fireEvent.click(screen.getByRole("button", { name: "select answer" }));
    fireEvent.click(screen.getByRole("button", { name: /查看 YAML|View YAML/i }));

    expect(screen.getByRole("tab", { name: /YAML/i })).toHaveAttribute("aria-selected", "true");
    const line = document.querySelector('[data-ir-node-id="answer"]');
    expect(line).toHaveClass("bg-warning/15");
  });
});
