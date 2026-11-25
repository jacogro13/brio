import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { FakeServer, json } from "./test/fakeServer";
import { renderApp } from "./test/render";

beforeEach(() => {
  localStorage.clear();
});

describe("App", () => {
  test("lists conversations from the server", async () => {
    const server = new FakeServer()
      .on("GET /auth/me", json(200, { username: "alice", language: "en" }))
      .on("GET /conversations/", json(200, [{ id: "c1", title: "Trip to Rome", created_at: "2026-11-20T10:00:00Z" }]));

    renderApp(server);

    expect(await screen.findByText("Trip to Rome")).toBeDefined();
  });
});
