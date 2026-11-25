import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import { readEvents, type StreamEvent } from "../api/stream";
import type { ToolEvent } from "../components/ToolActivity";
import { getThinkingPref } from "../utils/prefs";
import { uuid } from "../utils/uuid";
import { useApi } from "./useApi";
import {
  conversationKey,
  conversationsKey,
  type Attachment,
  type Conversation,
  type Message,
} from "./useConversations";

export interface StreamError {
  conversationId: string;
  error: unknown;
}

interface Args {
  /** The open conversation, or `null` for a draft. */
  activeId: string | null;
  /** Materialise a draft chat into a real conversation, returning its id.
   * A no-op returning the existing id when already persisted. */
  ensureConversation: () => Promise<string>;
  /** Gets a failure that isn't the stream's own: creating the row on first send. */
  onError: (error: unknown) => void;
}

/** Start a streaming call (HTTP failures throw `ApiError` like any call), then
 * read its SSE events. */
async function* streamOf(
  start: () => Promise<{ data?: ReadableStream<Uint8Array> | null }>
): AsyncGenerator<StreamEvent> {
  const { data } = await start();
  yield* readEvents(data!);
}

function userMessage(content: string, attachments: Attachment[]): Message {
  return { id: uuid(), role: "user", content, created_at: new Date().toISOString(), attachments };
}

/**
 * Streaming state machine for a conversation: send / regenerate / edit + stop.
 *
 * Optimistic messages (the user's turn, the truncation of edit/regenerate) go
 * into the conversation's query-cache entry. Stop is a client-side abort — the
 * backend's `finally`-UoW persists any partial reply. After every stream
 * (normal end or abort) the conversation is refetched so optimistic fake-UUID
 * messages are replaced with real ids (needed for edit/regenerate), and the
 * list is refreshed to pick up the auto-title.
 */
export function useChatStream({ activeId, ensureConversation, onError }: Args) {
  const api = useApi();
  const qc = useQueryClient();
  const [streaming, setStreaming] = useState<string | null>(null);
  const [streamingThinking, setStreamingThinking] = useState<string | null>(null);
  const [streamingToolEvents, setStreamingToolEvents] = useState<ToolEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  // The last stream's failure, and the conversation it belongs to.
  const [streamError, setStreamError] = useState<StreamError | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const updateMessages = useCallback(
    (id: string, change: (messages: Message[]) => Message[]) => {
      qc.setQueryData<Conversation>(conversationKey(id), (prev) =>
        prev ? { ...prev, messages: change(prev.messages) } : prev
      );
    },
    [qc]
  );

  const runStream = useCallback(
    async (
      conversationId: string,
      makeStream: (signal: AbortSignal) => AsyncGenerator<StreamEvent>
    ) => {
      setIsStreaming(true);
      setStreamError(null);
      setStreaming("");
      setStreamingThinking(null);
      setStreamingToolEvents([]);
      const controller = new AbortController();
      abortRef.current = controller;

      let accumulated = "";
      let thinking = "";
      const toolEvents: ToolEvent[] = [];
      const upsertTool = (id: number, patch: Partial<ToolEvent>) => {
        const i = toolEvents.findIndex((t) => t.id === id);
        if (i === -1) toolEvents.push({ id, tool: "", ...patch });
        else toolEvents[i] = { ...toolEvents[i], ...patch };
        setStreamingToolEvents([...toolEvents]);
      };
      try {
        for await (const event of makeStream(controller.signal)) {
          if (event.type === "token") {
            accumulated += event.content;
            setStreaming(accumulated);
          } else if (event.type === "thinking") {
            thinking += event.content;
            setStreamingThinking(thinking);
          } else if (event.type === "tool_start") {
            upsertTool(event.id, {
              tool: event.tool,
              query: event.query,
              url: event.url,
            });
          } else if (event.type === "tool_end") {
            upsertTool(event.id, {
              tool: event.tool,
              ok: event.ok,
              summary: event.summary,
              results: event.results,
            });
          } else if (event.type === "done") {
            break;
          }
        }
      } catch (error) {
        // Stop aborts our own signal: not a failure. The error's type can't
        // tell: an abort before the response arrives is an
        // ApiError("network_error") from client.ts, one mid-body a DOMException.
        if (!controller.signal.aborted) setStreamError({ conversationId, error });
      } finally {
        abortRef.current = null;
        setStreaming(null);
        setStreamingThinking(null);
        setStreamingToolEvents([]);
        setIsStreaming(false);
        // refetchQueries never throws: a failed refresh leaves the cache as it is.
        await qc.refetchQueries({ queryKey: conversationKey(conversationId) });
        qc.invalidateQueries({ queryKey: conversationsKey });
      }
    },
    [qc]
  );

  const send = useCallback(
    async (content: string, attachments: Attachment[] = [], webAccess = false, thinking = false) => {
      if (isStreaming) return;
      // A draft chat has no row yet — create it now and use the returned id.
      let conversationId = activeId;
      if (conversationId === null) {
        try {
          conversationId = await ensureConversation();
        } catch (error) {
          onError(error);
          return;
        }
      }
      const id = conversationId;
      updateMessages(id, (messages) => [...messages, userMessage(content, attachments)]);
      await runStream(id, (signal) =>
        streamOf(() =>
          api.POST("/conversations/{conversation_id}/messages", {
            params: { path: { conversation_id: id } },
            body: {
              content,
              attachment_ids: attachments.map((a) => a.id),
              web_access: webAccess,
              enable_thinking: thinking,
            },
            parseAs: "stream",
            signal,
          })
        )
      );
    },
    [activeId, api, isStreaming, runStream, updateMessages, ensureConversation, onError]
  );

  const regenerate = useCallback(async () => {
    if (activeId === null || isStreaming) return;
    const conversationId = activeId;
    // Drop the trailing assistant message(s) so the stream buffer replaces them.
    updateMessages(conversationId, (prev) => {
      const messages = [...prev];
      while (messages.length && messages[messages.length - 1].role === "assistant") {
        messages.pop();
      }
      return messages;
    });
    await runStream(conversationId, (signal) =>
      streamOf(() =>
        api.POST("/conversations/{conversation_id}/messages/regenerate", {
          params: { path: { conversation_id: conversationId } },
          body: { enable_thinking: getThinkingPref() },
          parseAs: "stream",
          signal,
        })
      )
    );
  }, [activeId, api, isStreaming, runStream, updateMessages]);

  const edit = useCallback(
    async (messageId: string, content: string) => {
      if (activeId === null || isStreaming) return;
      const conversationId = activeId;
      // Truncate at the edited message and append the new text optimistically.
      updateMessages(conversationId, (messages) => {
        const idx = messages.findIndex((m) => m.id === messageId);
        if (idx === -1) return messages;
        return [...messages.slice(0, idx), userMessage(content, [])];
      });
      await runStream(conversationId, (signal) =>
        streamOf(() =>
          api.POST("/conversations/{conversation_id}/messages/{message_id}/edit", {
            params: { path: { conversation_id: conversationId, message_id: messageId } },
            body: { content, enable_thinking: getThinkingPref() },
            parseAs: "stream",
            signal,
          })
        )
      );
    },
    [activeId, api, isStreaming, runStream, updateMessages]
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return {
    streaming,
    streamingThinking,
    streamingToolEvents,
    isStreaming,
    streamError,
    send,
    regenerate,
    edit,
    stop,
  };
}
