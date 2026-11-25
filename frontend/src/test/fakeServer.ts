// A hand-written fake backend for component and hook tests: no network, no
// mocks. Routes are keyed "METHOD /path" (the path after the client's base URL,
// query string dropped). Each route answers with a queue of responses: one per
// call, the last one repeats.

const BASE = "http://test/api";

export type FakeResponse =
  | { kind: "json"; status: number; body: unknown }
  /** A complete SSE body: one `data:` frame per event. */
  | { kind: "sse"; events: object[] }
  /** Sends these SSE events, then keeps the body open until the request aborts. */
  | { kind: "sse-then-wait"; events: object[] }
  /** Never answers until the request aborts (no headers, no body). */
  | { kind: "wait" };

export function json(status: number, body: unknown): FakeResponse {
  return { kind: "json", status, body };
}

export function apiError(status: number, code: string): FakeResponse {
  return json(status, { code, message: code, field: null });
}

export function sse(...events: object[]): FakeResponse {
  return { kind: "sse", events };
}

function frames(events: object[]): Uint8Array {
  return new TextEncoder().encode(events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join(""));
}

function abortError(): DOMException {
  return new DOMException("The operation was aborted.", "AbortError");
}

export class FakeServer {
  readonly requests: Request[] = [];
  private readonly routes = new Map<string, FakeResponse[]>();

  /** Answer `key` ("GET /conversations/") with these responses, one per call. */
  on(key: string, ...responses: FakeResponse[]): this {
    this.routes.set(key, responses);
    return this;
  }

  /** Requests whose key matches, e.g. `requestsTo("PATCH /conversations/c1")`. */
  requestsTo(key: string): Request[] {
    return this.requests.filter((r) => keyOf(r) === key);
  }

  fetch = async (request: Request): Promise<Response> => {
    this.requests.push(request);
    const key = keyOf(request);
    const queue = this.routes.get(key);
    if (!queue || queue.length === 0) {
      return respond(json(404, { code: "not_found", message: `no fake route ${key}`, field: null }));
    }
    const next = queue.length > 1 ? queue.shift()! : queue[0];
    return respond(next, request.signal);
  };
}

function keyOf(request: Request): string {
  const url = new URL(request.url);
  const path = url.href.slice(BASE.length).split("?")[0];
  return `${request.method} ${path}`;
}

function respond(response: FakeResponse, signal?: AbortSignal): Promise<Response> {
  switch (response.kind) {
    case "json":
      return Promise.resolve(
        // A 204 must have no body.
        new Response(response.status === 204 ? null : JSON.stringify(response.body), {
          status: response.status,
          headers: { "Content-Type": "application/json" },
        })
      );
    case "sse":
      return Promise.resolve(sseResponse(frames(response.events), false, signal));
    case "sse-then-wait":
      return Promise.resolve(sseResponse(frames(response.events), true, signal));
    case "wait":
      return new Promise((_, reject) => {
        signal?.addEventListener("abort", () => reject(abortError()));
      });
  }
}

function sseResponse(chunk: Uint8Array, wait: boolean, signal?: AbortSignal): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(chunk);
      if (!wait) {
        controller.close();
        return;
      }
      // As a real fetch does: an abort mid-body fails the next read.
      signal?.addEventListener("abort", () => controller.error(abortError()));
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}
