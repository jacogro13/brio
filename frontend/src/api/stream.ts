// The SSE stream reader (ADR-003). SSE isn't in OpenAPI, so `StreamEvent` is a
// frontend-only type. A stream `error` event becomes an `ApiError` with its
// `code`, so it gets the same text from `messageFor` as the HTTP error with
// that code.
import { ApiError } from "./client";

export type StreamEvent =
  | { type: "token"; content: string }
  | { type: "thinking"; content: string }
  | {
      type: "tool_start";
      id: number;
      tool: string;
      query?: string;
      url?: string;
    }
  | {
      type: "tool_end";
      id: number;
      tool: string;
      ok: boolean;
      summary: string;
      results: { title: string; url: string }[];
    }
  | { type: "done"; message_id: string | null }
  | { type: "error"; code?: string; message: string };

/** Yield each `data: {json}` frame of an SSE body; throw on an `error` event.
 * A connection that breaks mid-body becomes `ApiError(0, "network_error")`, as
 * a failed request does; an abort (stop) is rethrown as it is. */
export async function* readEvents(
  body: ReadableStream<Uint8Array>
): AsyncGenerator<StreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await read(reader);
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const frames = buf.split("\n\n");
    buf = frames.pop() ?? "";
    for (const frame of frames) {
      if (!frame.startsWith("data: ")) continue;
      const event = JSON.parse(frame.slice(6)) as StreamEvent;
      if (event.type === "error") {
        throw new ApiError(200, event.code ?? "unknown", null, event.message, null);
      }
      yield event;
    }
  }
}

async function read(reader: ReadableStreamDefaultReader<Uint8Array>) {
  try {
    return await reader.read();
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "network_error", null, String(error), null);
  }
}
