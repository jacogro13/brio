// Conversations: the list, one conversation, and the writes that change them
// (Blueprint v2, F2). Components use these hooks and never call `api`.
//
// Query keys: `conversationsKey` (the sidebar list) and `conversationKey(id)`
// (one conversation with its messages). Detail queries never refetch on their
// own (`staleTime: Infinity`, no refetch on focus): the streaming hook writes
// optimistic messages into that cache entry, and a background refetch would
// wipe them mid-stream. Opening a chat and the end of a stream refresh it.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import type { components } from "../api/schema";
import type { ToolEvent } from "../components/ToolActivity";
import { useApi } from "./useApi";

type Schemas = components["schemas"];
type ConversationResponse = Schemas["ConversationResponse"];
type ConversationUpdate = Schemas["UpdateConversationRequest"];

// Backend shapes, from the generated schema (F1).
export type Attachment = Schemas["AttachmentResponse"];
export type ConversationSummary = Schemas["ConversationSummaryResponse"];
export type Message = Omit<Schemas["MessageResponse"], "tool_events"> & {
  tool_events?: ToolEvent[] | null;
};
export type Conversation = Omit<ConversationResponse, "messages"> & { messages: Message[] };
/** Per-conversation LLM overrides. `null` means "use the server default" —
 * never conflate with `0` / `false`. */
export type ConversationSettings = Required<Omit<ConversationUpdate, "title">>;

/** `tool_events` is `list[dict]` in the backend, so it's generated as
 * `Record<string, unknown>[]`; its real shape is the SSE `tool_start`/`tool_end`
 * events folded together (ADR-005). The one cast to `ToolEvent[]` is here. */
export function toConversation(conversation: ConversationResponse): Conversation {
  return {
    ...conversation,
    messages: conversation.messages.map((message) => ({
      ...message,
      tool_events: message.tool_events as ToolEvent[] | null | undefined,
    })),
  };
}

export const conversationsKey = ["conversations"] as const;

export function conversationKey(id: string) {
  return ["conversation", id] as const;
}

/** Detail-query options shared by `useConversation` and an explicit fetch. */
export function conversationQuery(api: ReturnType<typeof useApi>, id: string) {
  return {
    queryKey: conversationKey(id),
    queryFn: async (): Promise<Conversation> => {
      const { data } = await api.GET("/conversations/{conversation_id}", {
        params: { path: { conversation_id: id } },
      });
      return toConversation(data!);
    },
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  };
}

export function useConversationList() {
  const api = useApi();
  return useQuery({
    queryKey: conversationsKey,
    queryFn: async () => (await api.GET("/conversations/")).data ?? [],
  });
}

/** The conversation `id`, or nothing for a draft (`null`). */
export function useConversation(id: string | null) {
  const api = useApi();
  return useQuery({
    ...conversationQuery(api, id ?? ""),
    enabled: id !== null,
  });
}

export function useCreateConversation() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => (await api.POST("/conversations/")).data!,
    onSuccess: () => qc.invalidateQueries({ queryKey: conversationsKey }),
  });
}

/** PATCH a conversation: send only the keys to change; `null` resets a setting. */
function usePatchConversation() {
  const api = useApi();
  return async ({ id, patch }: { id: string; patch: ConversationUpdate }) => {
    const { data } = await api.PATCH("/conversations/{conversation_id}", {
      params: { path: { conversation_id: id } },
      body: patch,
    });
    return toConversation(data!);
  };
}

export function useRenameConversation() {
  const patch = usePatchConversation();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => patch({ id, patch: { title } }),
    onSuccess: (updated) => {
      qc.setQueryData<Conversation>(conversationKey(updated.id), (prev) =>
        prev ? { ...prev, title: updated.title } : prev
      );
      return qc.invalidateQueries({ queryKey: conversationsKey });
    },
  });
}

export function useDeleteConversation() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.DELETE("/conversations/{conversation_id}", {
        params: { path: { conversation_id: id } },
      });
    },
    onSuccess: (_data, id) => {
      qc.removeQueries({ queryKey: conversationKey(id) });
      return qc.invalidateQueries({ queryKey: conversationsKey });
    },
  });
}

export function useUpdateSettings() {
  const patch = usePatchConversation();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, settings }: { id: string; settings: ConversationSettings }) =>
      patch({ id, patch: settings }),
    // Merge only the settings back in: the cached messages may hold optimistic ones.
    onSuccess: (updated) => {
      qc.setQueryData<Conversation>(conversationKey(updated.id), (prev) =>
        prev
          ? {
              ...prev,
              temperature: updated.temperature,
              max_tokens: updated.max_tokens,
              system_prompt_override: updated.system_prompt_override,
            }
          : prev
      );
    },
  });
}

/** Upload a file to a conversation; returns the pending attachment, whose `id`
 * goes in the next message's `attachment_ids`. The conversation id is a
 * variable, not a hook argument: a draft gets its id only after the file is
 * picked (`ensureConversation`). */
export function useUploadAttachment() {
  const api = useApi();
  return useMutation({
    mutationFn: async ({ conversationId, file }: { conversationId: string; file: File }) => {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.POST("/conversations/{conversation_id}/attachments", {
        params: { path: { conversation_id: conversationId } },
        // The generated body type says `file: string`; the real body is the FormData.
        body: { file: "" },
        bodySerializer: () => form,
      });
      return data!;
    },
  });
}

/** A function that downloads an attachment as a Blob. Downloads go through the
 * backend (the browser can't reach Garage in prod), fetched so the Bearer
 * header rides along (an `<a href>` can't carry it). */
export function useDownloadAttachment() {
  const api = useApi();
  return useCallback(
    async (conversationId: string, attachmentId: string): Promise<Blob> => {
      const { data } = await api.GET("/conversations/{conversation_id}/attachments/{attachment_id}", {
        params: { path: { conversation_id: conversationId, attachment_id: attachmentId } },
        parseAs: "blob",
      });
      return data!;
    },
    [api]
  );
}
