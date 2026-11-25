import { QueryClient } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import { FakeServer, apiError } from "../test/fakeServer";
import { providersFor } from "../test/render";
import { useActiveConversation } from "./useActiveConversation";

/** The app's own defaults (main.tsx): reads retry once, writes never. */
function appQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: 1 }, mutations: { retry: false } },
  });
}

describe("useActiveConversation", () => {
  test("failed open sends one request", async () => {
    const server = new FakeServer().on("GET /conversations/c2", apiError(502, "internal_error"));
    const { result } = renderHook(useActiveConversation, {
      wrapper: providersFor(server, appQueryClient()),
    });

    let failed: unknown = null;
    await act(() => result.current.select("c2").catch((error) => (failed = error)));

    expect(failed).toMatchObject({ code: "internal_error" });
    expect(server.requestsTo("GET /conversations/c2")).toHaveLength(1);
    expect(result.current.activeId).toBeNull();
  });
});
