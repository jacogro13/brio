// Which conversation is open. A draft (the homepage, "+ New chat", after
// deleting the open chat) is just `activeId === null`: no row and no messages
// until the first send or upload calls `ensureConversation()`.
//
// The open conversation's data lives in the query cache under
// `conversationKey(activeId)` (read it with `useConversation`).
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import { useApi } from "./useApi";
import {
  conversationKey,
  conversationQuery,
  useCreateConversation,
  type Conversation,
} from "./useConversations";

export function useActiveConversation() {
  const api = useApi();
  const qc = useQueryClient();
  const { mutateAsync: createConversation } = useCreateConversation();
  const [activeId, setActiveIdState] = useState<string | null>(null);
  // Stable remount key for MessageInput: bumped on select/new/delete, NOT on
  // draft→real promotion, so staged text/attachments survive promotion.
  const [threadKey, setThreadKey] = useState(0);
  // The id callbacks read after an await, when the render's value may be stale.
  const activeIdRef = useRef<string | null>(null);
  // De-dupes concurrent promotion (e.g. multiple files picked at once).
  const creatingRef = useRef<Promise<string> | null>(null);

  const setActiveId = useCallback((id: string | null) => {
    activeIdRef.current = id;
    setActiveIdState(id);
  }, []);

  /** Open a conversation, fresh from the server. If loading fails it throws,
   * and the chat on screen stays as it was. No retry: the user clicked and is
   * waiting, so a failure shows at once (`fetchQuery` would otherwise inherit
   * the app-wide `retry: 1`). */
  const select = useCallback(
    async (id: string) => {
      await qc.fetchQuery({ ...conversationQuery(api, id), staleTime: 0, retry: false });
      setActiveId(id);
      setThreadKey((k) => k + 1);
    },
    [api, qc, setActiveId]
  );

  /** Start a fresh draft (no request: the row is created on first send/upload). */
  const startNew = useCallback(() => {
    setActiveId(null);
    setThreadKey((k) => k + 1);
  }, [setActiveId]);

  /** After a delete: if it was the open chat, land on a fresh draft. */
  const forget = useCallback(
    (id: string) => {
      if (activeIdRef.current === id) startNew();
    },
    [startNew]
  );

  /** The open chat's id, creating the row first if it's still a draft. Callers
   * use the returned id, never state read back. The new conversation is put in
   * the cache (no messages) so the thread renders at once. */
  const ensureConversation = useCallback(async (): Promise<string> => {
    if (activeIdRef.current !== null) return activeIdRef.current;
    if (creatingRef.current) return creatingRef.current;
    const promise = (async () => {
      const summary = await createConversation();
      qc.setQueryData<Conversation>(conversationKey(summary.id), { ...summary, messages: [] });
      // Promote only if the user is still on the draft.
      if (activeIdRef.current === null) setActiveId(summary.id);
      return summary.id;
    })();
    creatingRef.current = promise;
    try {
      return await promise;
    } finally {
      creatingRef.current = null;
    }
  }, [createConversation, qc, setActiveId]);

  return { activeId, threadKey, select, startNew, forget, ensureConversation };
}
