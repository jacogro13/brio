import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, test } from "vitest";
import { FakeServer, apiError, json, sse, type FakeResponse } from "../test/fakeServer";
import { renderApp } from "../test/render";

const CREATED = "2026-11-20T10:00:00Z";
const SUMMARY = { id: "c1", title: null, created_at: CREATED };

function saved(...contents: string[]) {
  return {
    ...SUMMARY,
    title: "Small talk",
    messages: contents.map((content, i) => ({
      id: `m${i}`,
      role: i % 2 === 0 ? "user" : "assistant",
      content,
      created_at: CREATED,
      attachments: [],
    })),
  };
}

/** A draft-chat server: creating the conversation answers `c1`. */
function draftServer() {
  return new FakeServer()
    .on("GET /auth/me", json(200, { username: "alice", language: "en" }))
    .on("GET /conversations/", json(200, []))
    .on("POST /conversations/", json(201, SUMMARY))
    .on("GET /conversations/c1", json(200, saved("hello")));
}

function typeAndSend(text: string) {
  fireEvent.change(screen.getByRole("textbox"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
}

beforeAll(() => {
  // jsdom has no layout engine; ChatThread auto-scrolls to a bottom ref.
  Element.prototype.scrollIntoView = () => {};
});

beforeEach(() => {
  localStorage.clear();
});

// No vitest globals, so testing-library does not unmount between tests itself.
afterEach(cleanup);

describe("stream errors", () => {
  test("stream error event shows its text under the thread", async () => {
    const server = draftServer().on(
      "POST /conversations/c1/messages",
      sse({ type: "token", content: "par" }, { type: "error", code: "nothing_to_regenerate", message: "x" })
    );
    renderApp(server);

    typeAndSend("hello");

    expect((await screen.findByRole("alert")).textContent).toBe("There is no reply to regenerate.");
  });

  test.each<{ when: string; response: FakeResponse; ready: (server: FakeServer) => Promise<unknown> }>([
    {
      when: "after the first token",
      response: { kind: "sse-then-wait", events: [{ type: "token", content: "Partial reply" }] },
      ready: () => screen.findByText("Partial reply"),
    },
    {
      when: "before any response",
      response: { kind: "wait" },
      // The send request is in flight, with no answer yet.
      ready: (server) =>
        waitFor(() => expect(server.requestsTo("POST /conversations/c1/messages")).toHaveLength(1)),
    },
  ])("stopped stream shows no error ($when)", async ({ response, ready }) => {
    const server = draftServer().on("POST /conversations/c1/messages", response);
    renderApp(server);
    typeAndSend("hello");
    await ready(server);

    fireEvent.click(screen.getByRole("button", { name: "■ Stop" }));

    await screen.findByRole("button", { name: "Send" });
    await waitFor(() => expect(server.requestsTo("GET /conversations/c1")).toHaveLength(1));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  test("next send clears the stream error", async () => {
    const server = draftServer().on(
      "POST /conversations/c1/messages",
      sse({ type: "error", code: "nothing_to_regenerate", message: "x" }),
      sse({ type: "token", content: "Fine now" }, { type: "done", message_id: "m3" })
    );
    renderApp(server);
    typeAndSend("hello");
    await screen.findByRole("alert");

    typeAndSend("again");

    await waitFor(() => expect(server.requestsTo("POST /conversations/c1/messages")).toHaveLength(2));
    await screen.findByRole("button", { name: "Send" });
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("upload errors", () => {
  test("failed upload shows its text and stages no chip", async () => {
    const server = draftServer().on(
      "POST /conversations/c1/attachments",
      apiError(413, "attachment_too_large")
    );
    const { container } = renderApp(server);
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;

    fireEvent.change(input, { target: { files: [new File(["x"], "big.txt", { type: "text/plain" })] } });

    expect((await screen.findByRole("alert")).textContent).toBe("The file is too large.");
    expect(screen.queryByText(/big\.txt/)).toBeNull();
  });
});

