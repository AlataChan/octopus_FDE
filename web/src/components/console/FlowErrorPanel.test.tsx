import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import { FlowErrorPanel } from "./FlowErrorPanel";

afterEach(cleanup);

describe("FlowErrorPanel", () => {
  it("shows the rendering error and lets the user open YAML without auto-switching", () => {
    const onSwitchToYaml = vi.fn();
    render(
      <FlowErrorPanel
        error={new Error("IR graph contains a cycle and cannot be auto-laid out safely.")}
        parsedCount={2}
        totalCount={3}
        onSwitchToYaml={onSwitchToYaml}
      />
    );

    expect(screen.getByText(/Flow 无法渲染|Flow could not be rendered/i)).toBeInTheDocument();
    expect(screen.getByText(/2\/3/)).toBeInTheDocument();
    expect(onSwitchToYaml).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /打开 YAML|Open YAML/i }));
    expect(onSwitchToYaml).toHaveBeenCalledTimes(1);
  });
});
