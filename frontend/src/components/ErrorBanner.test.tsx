import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test } from "vitest";
import { FakeServer, apiError, json } from "../test/fakeServer";
import { renderApp } from "../test/render";

const CREATED = "2026-11-20T10:00:00Z";
const SERVER_ERROR_EN = "Server error. Please try again shortly.";
const NOT_FOUND_EN = "Conversation not found: it may have been deleted.";

function serverWithOneChat() {
  return new FakeServer()
    .on("GET /auth/me", json(200, { username: "alice", language: "en" }))
    .on("PATCH /auth/me", json(200, { username: "alice", language: "it" }))
    .on("GET /conversations/", json(200, [{ id: "c1", title: "Trip to Rome", created_at: CREATED }]));
}

async function rename(title: string) {
  fireEvent.click(await screen.findByTitle("Rename"));
  const input = screen.getByDisplayValue("Trip to Rome");
  fireEvent.change(input, { target: { value: title } });
  fireEvent.keyDown(input, { key: "Enter" });
}

async function deleteChat() {
  fireEvent.click(await screen.findByTitle("Delete"));
}

beforeEach(() => {
  localStorage.clear();
});

// No vitest globals, so testing-library does not unmount between tests itself.
afterEach(cleanup);

describe("error banner", () => {
  test.each([
    {
      action: "list load",
      server: () => serverWithOneChat().on("GET /conversations/", apiError(500, "internal_error")),
      act: async () => {},
      text: SERVER_ERROR_EN,
    },
    {
      action: "rename",
      server: () => serverWithOneChat().on("PATCH /conversations/c1", apiError(404, "conversation_not_found")),
      act: () => rename("New title"),
      text: NOT_FOUND_EN,
    },
    {
      action: "delete",
      server: () => serverWithOneChat().on("DELETE /conversations/c1", apiError(404, "conversation_not_found")),
      act: deleteChat,
      text: NOT_FOUND_EN,
    },
  ])("failed action shows its text in the banner ($action)", async ({ server, act, text }) => {
    renderApp(server());

    await act();

    expect((await screen.findByRole("alert")).textContent).toContain(text);
  });

  test("failed delete keeps the chat in the sidebar", async () => {
    const server = serverWithOneChat().on("DELETE /conversations/c1", apiError(404, "conversation_not_found"));
    renderApp(server);

    await deleteChat();

    await screen.findByRole("alert");
    expect(screen.getByText("Trip to Rome")).toBeDefined();
  });

  test("dismiss hides the banner", async () => {
    const server = serverWithOneChat().on("DELETE /conversations/c1", apiError(404, "conversation_not_found"));
    renderApp(server);
    await deleteChat();
    await screen.findByRole("alert");

    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));

    expect(screen.queryByRole("alert")).toBeNull();
  });

  test("banner text follows the ui language", async () => {
    const server = serverWithOneChat().on("GET /conversations/", apiError(500, "internal_error"));
    renderApp(server);
    await waitFor(async () => expect((await screen.findByRole("alert")).textContent).toContain(SERVER_ERROR_EN));

    fireEvent.click(screen.getByRole("button", { name: "IT" }));

    expect(screen.getByRole("alert").textContent).toContain("Errore del server. Riprova tra poco.");
  });
});
