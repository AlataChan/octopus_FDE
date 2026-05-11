import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import { IRDiffView } from "./IRDiffView";

describe("IRDiffView", () => {
  it("renders a compact list of semantic changes", () => {
    render(
      <IRDiffView
        diff={{
          changes: [
            { kind: "added", node_id: "answer", scope: "node" },
            {
              fields: [{ after: 5, before: 20, path: "top_k" }],
              kind: "config-changed",
              node_id: "retrieve",
              scope: "node"
            }
          ],
          from: "turn-a",
          summary: { edges: 0, nodes: 2, total: 2 },
          to: "turn-b"
        }}
        onSelectPath={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /IR 变更/ }));

    expect(screen.getByText(/answer/)).toBeInTheDocument();
    expect(screen.getByText(/retrieve/)).toBeInTheDocument();
    expect(screen.getByText(/top_k/)).toBeInTheDocument();
  });
});

describe("ValidatorPanel", () => {
  it("calls back with the JSON path when a path is clicked", async () => {
    const onSelectPath = vi.fn();
    const { ValidatorPanel } = await import("./ValidatorPanel");
    render(
      <ValidatorPanel
        errors={[{ bucket: "schema", detail: "rationale is required", location: "nodes.1.rationale" }]}
        onSelectPath={onSelectPath}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /nodes\.1\.rationale/ }));

    expect(onSelectPath).toHaveBeenCalledWith("nodes.1.rationale");
  });
});
