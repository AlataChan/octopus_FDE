import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import "../lib/i18n";
import LoginPage from "./LoginPage";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("LoginPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("submits username and password to the auth endpoint", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(JSON.stringify({ username: "admin", expires_at: null }), {
        headers: { "Content-Type": "application/json" },
        status: 200
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    fireEvent.change(screen.getByLabelText(/Username|用户名/i), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText(/Password|密码/i), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: /Sign in|登录/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/v1/auth/login");
    expect(init.credentials).toBe("include");
    expect(JSON.parse(String(init.body))).toEqual({ username: "admin", password: "secret" });
  });
});
