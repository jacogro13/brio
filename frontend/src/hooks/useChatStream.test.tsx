import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, test } from "vitest";
import { FakeServer, json, sse } from "../test/fakeServer";
import { renderApp } from "../test/render";

const CREATED = "2026-11-20T10:00:00Z";

beforeAll(() => {
  // jsdom has no layout engine; ChatThread auto-scrolls to a bottom ref.
  Element.prototype.scrollIntoView = () => {};
});

beforeEach(() => {
  localStorage.clear();
});

function typeAndSend(text: string) {
  fireEvent.change(screen.getByRole("textbox"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
}

describe("useChatStream", () => {
  test("send shows the user message then the saved reply", async () => {
    const summary = { id: "c1", title: null, created_at: CREATED };
    const saved = {
      ...summary,
      title: "Small talk",
      messages: [
        { id: "m1", role: "user", content: "hello", created_at: CREATED, attachments: [] },
        { id: "m2", role: "assistant", content: "Hi there!", created_at: CREATED, attachments: [] },
      ],
    };
    const server = new FakeServer()
      .on("GET /auth/me", json(200, { username: "alice", language: "en" }))
      .on("GET /conversations/", json(200, []))
      .on("POST /conversations/", json(201, summary))
      .on(
        "POST /conversations/c1/messages",
        sse({ type: "token", content: "Hi" }, { type: "token", content: " there!" }, { type: "done", message_id: "m2" })
      )
      .on("GET /conversations/c1", json(200, saved));
    renderApp(server);

    typeAndSend("hello");

    expect(await screen.findByText("hello")).toBeDefined();
    expect(await screen.findByText("Hi there!")).toBeDefined();
    await waitFor(() => expect(server.requestsTo("GET /conversations/c1")).toHaveLength(1));
    expect(screen.getByRole("button", { name: "Send" })).toBeDefined();
  });
});
