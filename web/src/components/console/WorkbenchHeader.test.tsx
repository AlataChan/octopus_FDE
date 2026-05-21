import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import type { SessionDetail } from "../../lib/types";
import { WorkbenchHeader } from "./WorkbenchHeader";

afterEach(cleanup);

const session: SessionDetail = {
  actor_id: "single-user",
  artifacts: [],
  created_at: "2026-05-21T00:00:00Z",
  display_title: "Original title",
  latest_ir_json: null,
  latest_ir_sha256: null,
  llm_base_url: null,
  llm_key_version: null,
  llm_model: null,
  session_id: "session-1",
  state: "validated",
  title: null,
  updated_at: "2026-05-21T00:00:00Z"
};

function renderHeader(overrides: Partial<SessionDetail> = {}) {
  const onRename = vi.fn().mockResolvedValue(undefined);
  const onResetLayout = vi.fn();
  render(
    <MemoryRouter>
      <WorkbenchHeader
        session={{ ...session, ...overrides }}
        onRename={onRename}
        onResetLayout={onResetLayout}
      />
    </MemoryRouter>
  );
  return { onRename, onResetLayout };
}

describe("WorkbenchHeader", () => {
  it("saves an inline rename with Enter", async () => {
    const { onRename } = renderHeader();

    fireEvent.doubleClick(screen.getByText("Original title"));
    const input = screen.getByLabelText(/Session title|会话标题/i);
    fireEvent.change(input, { target: { value: " Renamed session " } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(onRename).toHaveBeenCalledWith("Renamed session"));
  });

  it("cancels inline rename with Escape", () => {
    const { onRename } = renderHeader();

    fireEvent.doubleClick(screen.getByText("Original title"));
    const input = screen.getByLabelText(/Session title|会话标题/i);
    fireEvent.change(input, { target: { value: "Discarded" } });
    fireEvent.keyDown(input, { key: "Escape" });

    expect(onRename).not.toHaveBeenCalled();
    expect(screen.getByText("Original title")).toBeInTheDocument();
  });

  it("rejects titles longer than 80 characters", () => {
    const { onRename } = renderHeader();

    fireEvent.doubleClick(screen.getByText("Original title"));
    const input = screen.getByLabelText(/Session title|会话标题/i);
    fireEvent.change(input, { target: { value: "x".repeat(81) } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onRename).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/80/);
  });

  it("keeps editing open when rename fails", async () => {
    const onRename = vi.fn().mockRejectedValue(new Error("failed"));
    render(
      <MemoryRouter>
        <WorkbenchHeader session={session} onRename={onRename} onResetLayout={vi.fn()} />
      </MemoryRouter>
    );

    fireEvent.doubleClick(screen.getByText("Original title"));
    const input = screen.getByLabelText(/Session title|会话标题/i);
    fireEvent.change(input, { target: { value: "Renamed session" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(await screen.findByRole("alert")).toHaveTextContent(/保存失败|Save failed/i);
    expect(screen.getByLabelText(/Session title|会话标题/i)).toBeInTheDocument();
  });
});
