import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import {
  createSession,
  createSessionFromTemplate,
  deleteSession,
  listSessions
} from "../../lib/api";
import SessionListPage from "./list";

afterEach(cleanup);

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    createSession: vi.fn(),
    createSessionFromTemplate: vi.fn(),
    deleteSession: vi.fn(),
    listSessions: vi.fn()
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

function renderListPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SessionListPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("SessionListPage", () => {
  beforeEach(() => {
    vi.mocked(createSession).mockResolvedValue({ session_id: "new-session", state: "init" });
    vi.mocked(createSessionFromTemplate).mockResolvedValue({ session_id: "new-template", state: "validated" });
    vi.mocked(deleteSession).mockResolvedValue(undefined);
    vi.mocked(listSessions).mockResolvedValue(sessions);
  });

  it("deletes a session from the card actions after confirmation", async () => {
    renderListPage();
    await screen.findByText("Active session");

    fireEvent.click(screen.getAllByRole("button", { name: /Open session actions menu|打开 session 操作菜单/i })[0]);
    fireEvent.click(screen.getByRole("menuitem", { name: /Delete|删除/i }));

    expect(screen.getByRole("dialog")).toHaveTextContent(/Active session/);

    fireEvent.click(screen.getByRole("button", { name: /Delete session|确认删除/i }));

    await waitFor(() => expect(deleteSession).toHaveBeenCalledWith("session-active"));
  });
});
