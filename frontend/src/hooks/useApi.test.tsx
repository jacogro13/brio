import { render, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { describe, expect, test } from "vitest";
import { api } from "../api/client";
import { FakeServer, json } from "../test/fakeServer";
import { testClient } from "../test/render";
import { ApiProvider } from "./ApiProvider";
import { useApi, type ApiClient } from "./useApi";

/** Remembers the client `useApi()` gave the component that rendered it. */
class SeenClient {
  client: ApiClient | null = null;
  record = (client: ApiClient): void => {
    this.client = client;
  };
}

function Probe({ seen }: { seen: SeenClient }) {
  const client = useApi();
  useEffect(() => {
    seen.record(client);
  }, [seen, client]);
  return null;
}

describe("useApi", () => {
  test("returns the provided client", async () => {
    const server = new FakeServer().on("GET /auth/me", json(200, { username: "a", language: "en" }));
    const seen = new SeenClient();

    render(
      <ApiProvider client={testClient(server)}>
        <Probe seen={seen} />
      </ApiProvider>
    );
    await seen.client!.GET("/auth/me");

    await waitFor(() => expect(server.requestsTo("GET /auth/me")).toHaveLength(1));
  });

  test("defaults to the app client", () => {
    const seen = new SeenClient();

    render(<Probe seen={seen} />);

    expect(seen.client).toBe(api);
  });
});
