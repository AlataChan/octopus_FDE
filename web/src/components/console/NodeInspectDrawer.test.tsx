import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import { NodeInspectDrawer } from "./NodeInspectDrawer";

afterEach(cleanup);

const ir = {
  nodes: [
    { id: "start", type: "trigger", rationale: "Start", next: "answer" },
    { id: "answer", type: "llm", model: "configured-planner-model", next: "out" },
    { id: "out", type: "output" }
  ]
};

describe("NodeInspectDrawer", () => {
  it("renders fields and closes", () => {
    const onClose = vi.fn();
    render(
      <NodeInspectDrawer
        ir={ir}
        node={ir.nodes[1]}
        onClose={onClose}
        onShowIssues={vi.fn()}
        onShowYaml={vi.fn()}
      />
    );

    expect(screen.getByTestId("node-inspect-drawer")).toBeInTheDocument();
    expect(screen.getByText("configured-planner-model")).toBeInTheDocument();
    expect(screen.getByText(/start/)).toBeInTheDocument();
    expect(screen.getAllByText(/out/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /关闭|Close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("routes drawer actions to issues and YAML", () => {
    const onShowIssues = vi.fn();
    const onShowYaml = vi.fn();
    render(
      <NodeInspectDrawer
        ir={ir}
        node={ir.nodes[1]}
        onClose={vi.fn()}
        onShowIssues={onShowIssues}
        onShowYaml={onShowYaml}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /查看 Issues|View issues/i }));
    fireEvent.click(screen.getByRole("button", { name: /查看 YAML|View YAML/i }));

    expect(onShowIssues).toHaveBeenCalledWith("answer");
    expect(onShowYaml).toHaveBeenCalledWith("answer");
  });
});
