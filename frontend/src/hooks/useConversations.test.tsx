import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import { FakeServer, apiError, json } from "../test/fakeServer";
import { providersFor, testQueryClient } from "../test/render";
import {
  conversationKey,
  useConversation,
  useConversationList,
  useDeleteConversation,
  useRenameConversation,
  useUpdateSettings,
  type Conversation,
} from "./useConversations";

const CREATED = "2026-11-20T10:00:00Z";

function summary(id: string, title: string) {
  return { id, title, created_at: CREATED };
}

function conversation(id: string, title: string): Conversation {
  return {
    ...summary(id, title),
    temperature: null,
    max_tokens: null,
    system_prompt_override: null,
    messages: [
      { id: "m1", role: "user", content: "hello", created_at: CREATED, attachments: [] },
    ],
  };
}

/** Renders the list plus one write hook on the same query client. */
function renderWith<T>(server: FakeServer, useWrite: () => T) {
  return renderHook(() => ({ list: useConversationList(), write: useWrite() }), {
    wrapper: providersFor(server),
  });
}

function titles(list: { data?: { title: string | null }[] }) {
  return list.data?.map((c) => c.title);
}

describe("conversation hooks", () => {
  test("rename refreshes the list with the server title", async () => {
    const server = new FakeServer()
      .on("GET /conversations/", json(200, [summary("c1", "Old")]), json(200, [summary("c1", "New")]))
      .on("PATCH /conversations/c1", json(200, conversation("c1", "New")));
    const { result } = renderWith(server, useRenameConversation);
    await waitFor(() => expect(titles(result.current.list)).toEqual(["Old"]));

    await act(() => result.current.write.mutateAsync({ id: "c1", title: "New" }));

    await waitFor(() => expect(titles(result.current.list)).toEqual(["New"]));
  });

  test("failed rename leaves the list unchanged", async () => {
    const server = new FakeServer()
      .on("GET /conversations/", json(200, [summary("c1", "Old")]))
      .on("PATCH /conversations/c1", apiError(404, "conversation_not_found"));
    const { result } = renderWith(server, useRenameConversation);
    await waitFor(() => expect(titles(result.current.list)).toEqual(["Old"]));

    await act(() =>
      result.current.write.mutateAsync({ id: "c1", title: "New" }).catch(() => undefined)
    );

    await waitFor(() => expect(result.current.write.isError).toBe(true));
    expect(titles(result.current.list)).toEqual(["Old"]);
    expect(server.requestsTo("GET /conversations/")).toHaveLength(1);
  });

  test("delete removes the chat from the list", async () => {
    const server = new FakeServer()
      .on("GET /conversations/", json(200, [summary("c1", "A"), summary("c2", "B")]), json(200, [summary("c2", "B")]))
      .on("DELETE /conversations/c1", json(204, null));
    const { result } = renderWith(server, useDeleteConversation);
    await waitFor(() => expect(titles(result.current.list)).toEqual(["A", "B"]));

    await act(() => result.current.write.mutateAsync("c1"));

    await waitFor(() => expect(titles(result.current.list)).toEqual(["B"]));
  });

  test("failed delete keeps the chat", async () => {
    const server = new FakeServer()
      .on("GET /conversations/", json(200, [summary("c1", "A")]))
      .on("DELETE /conversations/c1", apiError(404, "conversation_not_found"));
    const { result } = renderWith(server, useDeleteConversation);
    await waitFor(() => expect(titles(result.current.list)).toEqual(["A"]));

    await act(() => result.current.write.mutateAsync("c1").catch(() => undefined));

    await waitFor(() => expect(result.current.write.isError).toBe(true));
    expect(titles(result.current.list)).toEqual(["A"]);
  });

  test("settings update keeps the messages", async () => {
    const updated = { ...conversation("c1", "A"), temperature: 0.5, messages: [] };
    const server = new FakeServer()
      .on("GET /conversations/c1", json(200, conversation("c1", "A")))
      .on("PATCH /conversations/c1", json(200, updated));
    const queryClient = testQueryClient();
    const { result } = renderHook(
      () => ({ open: useConversation("c1"), write: useUpdateSettings() }),
      { wrapper: providersFor(server, queryClient) }
    );
    await waitFor(() => expect(result.current.open.data).toBeDefined());

    await act(() =>
      result.current.write.mutateAsync({
        id: "c1",
        settings: { temperature: 0.5, max_tokens: null, system_prompt_override: null },
      })
    );

    const cached = queryClient.getQueryData<Conversation>(conversationKey("c1"));
    expect(cached?.temperature).toBe(0.5);
    expect(cached?.messages.map((m) => m.content)).toEqual(["hello"]);
  });
});
