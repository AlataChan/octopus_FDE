import { fireEvent, render, screen } from "@testing-library/react";
import { useEffect, useState, type ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
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

vi.mock("../../hooks/useSession", () => ({
  useCompileSession: () => ({ isPending: false, mutate: vi.fn() }),
  useIRDiff: () => ({ data: null }),
  useMarkImported: () => ({ mutate: vi.fn(), variables: null }),
  useSession: () => ({
    bindings: { data: [] },
    ir: { data: { ir: null, validation_errors: [], validator_status: "draft" } },
    session: {
      data: {
        artifacts: [],
        llm_model: "test-model",
        state: "draft"
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
  downloadArtifact: vi.fn()
}));

let panelGroupMounts = 0;
let panelGroupUnmounts = 0;

describe("SessionDetailPage reset layout", () => {
  beforeEach(() => {
    panelGroupMounts = 0;
    panelGroupUnmounts = 0;
    localStorage.clear();
    localStorage.setItem(PANEL_STORAGE_KEY, "[30,40,30]");
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      addEventListener: vi.fn(),
      addListener: vi.fn(),
      dispatchEvent: vi.fn(),
      matches: query === "(min-width: 1280px)",
      media: query,
      onchange: null,
      removeEventListener: vi.fn(),
      removeListener: vi.fn()
    }));
  });

  it("clears saved panel layout and remounts the panel group", async () => {
    render(
      <MemoryRouter initialEntries={["/sessions/session-1"]}>
        <Routes>
          <Route element={<SessionDetailPage />} path="/sessions/:id" />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByTestId("panel-group")).toHaveTextContent("mount:1");

    fireEvent.click(screen.getByRole("button", { name: /重置布局|Reset layout/i }));

    expect(localStorage.getItem(PANEL_STORAGE_KEY)).toBeNull();
    expect(screen.getByTestId("panel-group")).toHaveTextContent("mount:2");
    expect(panelGroupUnmounts).toBe(1);
  });
});
