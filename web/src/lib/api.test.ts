import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "./api";

describe("apiFetch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("adds the actor header and includes cookies on backend requests", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json" },
        status: 200
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch<{ ok: boolean }>("/v1/health");

    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    const init = calls[0][1];
    const headers = init.headers as Headers;
    expect(headers.get("X-Actor-Id")).toBe("single-user");
    expect(init.credentials).toBe("include");
  });
});
