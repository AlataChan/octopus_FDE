import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import SessionDetailPage from "../../pages/sessions/[id]";

const PANEL_STORAGE_KEY = "react-resizable-panels:fde-session-panels-v1";

vi.mock("react-resizable-panels", () => ({
  Panel: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  PanelGroup: ({ children }: { children: ReactNode }) => {
    const [mountId] = useState(() => {
      panelGroupMounts += 1;
      return panelGroupMounts;
    });

    useEffect(() => {
      return () => {
        panelGroupUnmounts += 1;
      };
    }, []);

    return <div data-testid="panel-group">mount:{mountId}{children}</div>;
  },
  PanelResizeHandle: ({
    "aria-label": ariaLabel,
    children
  }: {
    "aria-label"?: string;
    children?: ReactNode;
  }) => (
    <div aria-label={ariaLabel} role="separator">
      {children}
    </div>
  )
}));

vi.mock("../../components/console/IRColumn", () => ({
  IRColumn: ({
    selectedNodeId,
    onSelectedNodeIdChange
  }: {
    selectedNodeId: string | null;
    onSelectedNodeIdChange: (nodeId: string | null) => void;
  }) => (
    <div data-selected-node={selectedNodeId || ""} data-testid="mock-ir-column">
      <button type="button" onClick={() => onSelectedNodeIdChange("answer")}>
        select answer node
      </button>
    </div>
  )
}));

vi.mock("../../hooks/useSession", () => ({
  useCompileSession: () => ({ isPending: false, mutate: vi.fn() }),
  useIRDiff: () => ({ data: null }),
  useMarkImported: () => ({ mutate: vi.fn(), variables: null }),
  useSession: () => ({
    bindings: { data: [] },
    ir: { data: { ir: null, validation_errors: [], validator_status: "draft" } },
    session: {
      data: {
        artifacts: [
          {
            actor_id: "single-user",
            artifact_id: "artifact-1",
            artifact_kind: "yaml",
            artifact_name: "Knowledge Retrieval RAG.yaml",
            artifact_path: "/tmp/knowledge-retrieval-rag.yaml",
            artifact_size: 2048,
            binding_handle: "test",
            compile_warnings: [],
            created_at: "2026-05-21T00:00:00Z",
            mode: "chatflow",
            sha256: "abc1234567890def",
            session_id: "session-1",
            target: "hiagent",
            workflow_id: "workflow-1"
          },
          {
            actor_id: "single-user",
            artifact_id: "artifact-2",
            artifact_kind: "zip",
            artifact_name: "Knowledge Retrieval RAG.zip",
            artifact_path: "/tmp/knowledge-retrieval-rag.zip",
            artifact_size: 4096,
            binding_handle: "test",
            compile_warnings: [],
            created_at: "2026-05-21T00:01:00Z",
            mode: "chatflow",
            sha256: "def1234567890abc",
            session_id: "session-1",
            target: "hiagent",
            workflow_id: "workflow-2"
          }
        ],
        display_title: "Test session",
        llm_model: "test-model",
        session_id: "session-1",
        state: "compiled"
      }
    },
    turns: { data: [] },
    workflows: { data: [] }
  }),
  useSetLLMConfig: () => ({ isPending: false, mutate: vi.fn() })
}));

vi.mock("../../hooks/usePlannerTurn", () => ({
  usePlannerTurn: () => ({ isPending: false, mutate: vi.fn() })
}));

vi.mock("../../lib/api", () => ({
  createSession: vi.fn(),
  createSessionFromTemplate: vi.fn(),
  downloadArtifact: vi.fn(),
  listSessions: vi.fn().mockResolvedValue([]),
  renameSession: vi.fn()
}));

let panelGroupMounts = 0;
let panelGroupUnmounts = 0;

describe("SessionDetailPage reset layout", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    panelGroupMounts = 0;
    panelGroupUnmounts = 0;
    localStorage.clear();
    localStorage.setItem(PANEL_STORAGE_KEY, "[30,40,30]");
    stubViewportWidth(1280);
  });

  function renderPage() {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } }
    });
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/sessions/session-1"]}>
          <Routes>
            <Route element={<SessionDetailPage />} path="/sessions/:id" />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  function renderPageWithRouteSwitcher() {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } }
    });
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/sessions/session-1"]}>
          <Link to="/sessions/session-2">Switch session</Link>
          <Routes>
            <Route element={<SessionDetailPage />} path="/sessions/:id" />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  it("clears saved panel layout and remounts the panel group", async () => {
    renderPage();

    expect(screen.getByTestId("panel-group")).toHaveTextContent("mount:1");

    fireEvent.click(screen.getByRole("button", { name: /工作台操作|Workbench actions/i }));
    fireEvent.click(screen.getByRole("menuitem", { name: /重置布局|Reset layout/i }));

    expect(localStorage.getItem(PANEL_STORAGE_KEY)).toBeNull();
    expect(screen.getByTestId("panel-group")).toHaveTextContent("mount:2");
    expect(panelGroupUnmounts).toBe(1);
  });

  it("uses the resizable panel group at the lg breakpoint", () => {
    stubViewportWidth(1100);

    renderPage();

    expect(screen.getByTestId("panel-group")).toBeInTheDocument();
  });

  it("gives the compile pane height so compiled artifacts stay reachable", () => {
    renderPage();

    const compilePane = screen.getByTestId("context-compile-pane");
    expect(compilePane).toHaveClass("flex-1");
    expect(compilePane).toHaveClass("min-h-[360px]");
    expect(screen.getByText("Knowledge Retrieval RAG.yaml")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /下载|Download/i })).toHaveLength(2);
  });

  it("opens the mobile sidebar as a full-width sheet", () => {
    stubViewportWidth(800);

    renderPage();

    expect(screen.queryByTestId("sessions-sidebar")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /打开 Sessions 侧栏|Open sessions sidebar/i }));

    const sidebar = screen.getByTestId("sessions-sidebar");
    expect(sidebar).toHaveAttribute("data-collapsed", "false");
    expect(sidebar).toHaveClass("w-[220px]");
  });

  it("resets the selected flow node when switching sessions", () => {
    renderPageWithRouteSwitcher();

    fireEvent.click(screen.getByRole("button", { name: "select answer node" }));
    expect(screen.getByTestId("mock-ir-column")).toHaveAttribute("data-selected-node", "answer");

    fireEvent.click(screen.getByRole("link", { name: "Switch session" }));

    expect(screen.getByTestId("mock-ir-column")).toHaveAttribute("data-selected-node", "");
  });
});

function stubViewportWidth(width: number) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    addEventListener: vi.fn(),
    addListener: vi.fn(),
    dispatchEvent: vi.fn(),
    matches:
      query === "(min-width: 1280px)"
        ? width >= 1280
        : query === "(min-width: 1024px)"
          ? width >= 1024
          : false,
    media: query,
    onchange: null,
    removeEventListener: vi.fn(),
    removeListener: vi.fn()
  }));
}
