import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import { listSessions, renameSession } from "../../lib/api";
import { SessionsSidebar } from "./SessionsSidebar";

afterEach(cleanup);

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    listSessions: vi.fn(),
    renameSession: vi.fn()
  };
});

const sessions = [
  {
    created_at: "2026-05-21T05:00:00Z",
    display_title: "Active session",
    latest_ir_sha256: "abc",
    session_id: "session-active",
    state: "validated",
    updated_at: "2026-05-21T05:00:00Z"
  },
  {
    created_at: "2026-05-21T04:00:00Z",
    display_title: "Other session",
    latest_ir_sha256: null,
    session_id: "session-other",
    state: "init",
    updated_at: "2026-05-21T04:00:00Z"
  }
];

function renderSidebar() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  const onCreateSession = vi.fn();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SessionsSidebar currentSessionId="session-active" onCreateSession={onCreateSession} />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return { onCreateSession };
}

describe("SessionsSidebar", () => {
  beforeEach(() => {
    vi.mocked(listSessions).mockResolvedValue(sessions);
    vi.mocked(renameSession).mockResolvedValue({
      ...sessions[0],
      actor_id: "single-user",
      artifacts: [],
      display_title: "Renamed",
      latest_ir_json: null,
      llm_base_url: null,
      llm_key_version: null,
      llm_model: null,
      title: "Renamed"
    });
    localStorage.clear();
  });

  it("renders sessions and highlights the active item", async () => {
    renderSidebar();

    expect(await screen.findByText("Active session")).toBeInTheDocument();
    expect(screen.getByTestId("session-item-session-active")).toHaveAttribute("aria-current", "page");
  });

  it("persists collapsed state when toggled", async () => {
    renderSidebar();
    await screen.findByText("Active session");

    fireEvent.click(screen.getByRole("button", { name: /Collapse sidebar|折叠侧栏/i }));

    expect(screen.getByTestId("sessions-sidebar")).toHaveAttribute("data-collapsed", "true");
    expect(localStorage.getItem("fde-sessions-sidebar-collapsed-v1")).toBe("true");
  });

  it("opens the item menu and renames a session", async () => {
    renderSidebar();
    await screen.findByText("Active session");

    fireEvent.click(screen.getByRole("button", { name: /Actions for Active session|Active session 的操作/i }));
    expect(screen.getByRole("menu")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("menuitem", { name: /Rename|重命名/i }));
    const input = screen.getByLabelText(/Rename Active session|重命名 Active session/i);
    fireEvent.change(input, { target: { value: " Renamed " } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(renameSession).toHaveBeenCalledWith("session-active", "Renamed"));
  });

  it("keeps the inline editor open when rename fails", async () => {
    vi.mocked(renameSession).mockRejectedValueOnce(new Error("failed"));
    renderSidebar();
    await screen.findByText("Active session");

    fireEvent.click(screen.getByRole("button", { name: /Actions for Active session|Active session 的操作/i }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Rename|重命名/i }));
    const input = screen.getByLabelText(/Rename Active session|重命名 Active session/i);
    fireEvent.change(input, { target: { value: "Renamed" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(await screen.findByRole("alert")).toHaveTextContent(/保存失败|Save failed/i);
    expect(screen.getByLabelText(/Rename Active session|重命名 Active session/i)).toBeInTheDocument();
  });
});
