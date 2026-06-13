import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../../lib/i18n";
import { TopBar } from "./TopBar";

function renderTopBar() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/sessions"]}>
        <TopBar />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("TopBar", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("uses the Octopus FDE brand mark for home navigation", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/v1/auth/me")) {
          return new Response(JSON.stringify({ username: "admin", expires_at: null }), {
            headers: { "Content-Type": "application/json" },
            status: 200
          });
        }
        return new Response(JSON.stringify({ ok: true }), {
          headers: { "Content-Type": "application/json" },
          status: 200
        });
      })
    );

    renderTopBar();

    const logo = screen.getByRole("img", { name: /Octopus FDE logo/i });
    expect(logo).toHaveAttribute("src", "/brand/octopus-praser-icon-1024.png");
    expect(screen.getByRole("link", { name: /Octopus FDE Console/i })).toHaveAttribute("href", "/");
  });
});
