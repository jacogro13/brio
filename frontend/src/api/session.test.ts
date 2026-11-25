import { beforeEach, describe, expect, test } from "vitest";
import { ApiError, createApiClient } from "./client";
import { getUsername, makeAuthMiddleware, setToken } from "./session";

/** Answers every request with one canned response and remembers what it got. */
class FakeServer {
  requests: Request[] = [];
  private readonly status: number;
  private readonly body: unknown;

  constructor(status: number, body: unknown) {
    this.status = status;
    this.body = body;
  }

  fetch = async (request: Request): Promise<Response> => {
    this.requests.push(request);
    return new Response(JSON.stringify(this.body), {
      status: this.status,
      headers: { "Content-Type": "application/json" },
    });
  };
}

class CountingRejected {
  calls = 0;
  onRejected = (): void => {
    this.calls += 1;
  };
}

function clientFor(server: FakeServer, rejected: CountingRejected) {
  const client = createApiClient({ baseUrl: "http://test/api", fetch: server.fetch });
  client.use(makeAuthMiddleware(rejected.onRejected));
  return client;
}

function fakeJwt(payload: object): string {
  return `header.${btoa(JSON.stringify(payload))}.signature`;
}

beforeEach(() => {
  localStorage.clear();
});

describe("auth middleware", () => {
  test("token is sent as bearer", async () => {
    setToken("abc");
    const server = new FakeServer(200, { username: "alice", language: "en" });
    const client = clientFor(server, new CountingRejected());

    await client.GET("/auth/me");

    expect(server.requests[0].headers.get("Authorization")).toBe("Bearer abc");
  });

  test.each([401, 403])("rejected token (%i) calls onRejected", async (status) => {
    setToken("stale");
    const server = new FakeServer(status, { code: "invalid_token", message: "x", field: null });
    const rejected = new CountingRejected();
    const client = clientFor(server, rejected);

    await expect(client.GET("/auth/me")).rejects.toBeInstanceOf(ApiError);

    expect(rejected.calls).toBe(1);
  });

  test("401 without a token does not call onRejected and reaches the caller", async () => {
    const server = new FakeServer(401, {
      code: "invalid_credentials",
      message: "Invalid username or password",
      field: null,
    });
    const rejected = new CountingRejected();
    const client = clientFor(server, rejected);

    const result = client.POST("/auth/login", { body: { username: "a", password: "wrong" } });

    await expect(result).rejects.toMatchObject({ code: "invalid_credentials" });
    expect(rejected.calls).toBe(0);
  });
});

describe("getUsername", () => {
  test("reads the username claim", () => {
    setToken(fakeJwt({ username: "alice" }));

    const username = getUsername();

    expect(username).toBe("alice");
  });

  test("returns null for a garbage token", () => {
    setToken("not-a-jwt");

    const username = getUsername();

    expect(username).toBeNull();
  });
});
