import { describe, expect, test } from "vitest";
import type { Lang } from "../i18n/strings";
import { ApiError } from "./client";
import { messageFor } from "./errors";
import { readEvents, type StreamEvent } from "./stream";

/** A response body that delivers the given text chunks, in order. */
function bodyOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

/** A body that sends one chunk, then fails the next read with `error`. */
function brokenBodyOf(chunk: string, error: unknown): ReadableStream<Uint8Array> {
  let sent = false;
  return new ReadableStream({
    pull(controller) {
      if (sent) {
        controller.error(error);
        return;
      }
      sent = true;
      controller.enqueue(new TextEncoder().encode(chunk));
    },
  });
}

function frame(event: object): string {
  return `data: ${JSON.stringify(event)}\n\n`;
}

async function collect(body: ReadableStream<Uint8Array>): Promise<StreamEvent[]> {
  const events: StreamEvent[] = [];
  for await (const event of readEvents(body)) events.push(event);
  return events;
}

async function streamError(body: ReadableStream<Uint8Array>): Promise<unknown> {
  try {
    await collect(body);
  } catch (error) {
    return error;
  }
  throw new Error("the stream did not throw");
}

describe("readEvents", () => {
  test("yields events in order", async () => {
    const body = bodyOf(
      frame({ type: "token", content: "Hi" }),
      frame({ type: "done", message_id: "m1" })
    );

    const events = await collect(body);

    expect(events).toEqual([
      { type: "token", content: "Hi" },
      { type: "done", message_id: "m1" },
    ]);
  });

  test("frame split across chunks is joined", async () => {
    const whole = frame({ type: "token", content: "split" });
    const body = bodyOf(whole.slice(0, 10), whole.slice(10));

    const events = await collect(body);

    expect(events).toEqual([{ type: "token", content: "split" }]);
  });

  test("non data lines are ignored", async () => {
    const body = bodyOf(": keep-alive\n\n", frame({ type: "token", content: "x" }));

    const events = await collect(body);

    expect(events).toEqual([{ type: "token", content: "x" }]);
  });

  test("error event throws ApiError with its code", async () => {
    const body = bodyOf(
      frame({ type: "token", content: "partial" }),
      frame({ type: "error", code: "conversation_not_found", message: "gone" })
    );

    const error = await streamError(body);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "conversation_not_found" });
  });

  test("error event without code is unknown", async () => {
    const body = bodyOf(frame({ type: "error", message: "boom" }));

    const error = await streamError(body);

    expect(error).toMatchObject({ code: "unknown" });
  });

  test.each(["en", "it", "de"] as Lang[])(
    "%s: stream error and http error with the same code give the same text",
    async (lang) => {
      const body = bodyOf(frame({ type: "error", code: "attachment_too_large", message: "x" }));
      const httpError = new ApiError(413, "attachment_too_large", null, "y", null);

      const streamed = await streamError(body);

      expect(messageFor[lang](streamed)).toBe(messageFor[lang](httpError));
    }
  );

  test("broken connection becomes network error", async () => {
    const body = brokenBodyOf(frame({ type: "token", content: "Hi" }), new TypeError("terminated"));

    const error = await streamError(body);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 0, code: "network_error" });
  });

  test("abort is rethrown as is", async () => {
    const abort = new DOMException("The operation was aborted.", "AbortError");
    const body = brokenBodyOf(frame({ type: "token", content: "Hi" }), abort);

    const error = await streamError(body);

    expect(error).toBe(abort);
  });
});
