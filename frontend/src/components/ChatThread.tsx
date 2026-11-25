import { useEffect, useRef } from "react";
import type { Message } from "../hooks/useConversations";
import type { ToolEvent } from "./ToolActivity";
import { messageFor } from "../api/errors";
import type { StreamError } from "../hooks/useChatStream";
import { useLanguage } from "../i18n";
import { MessageBubble } from "./MessageBubble";

interface Props {
  conversationId: string;
  messages: Message[];
  streamingContent: string | null;
  streamingThinking: string | null;
  streamingToolEvents: ToolEvent[];
  isStreaming: boolean;
  onEdit: (messageId: string, content: string) => void;
  onRetry: () => void;
  /** The last stream's failure; shown only if it belongs to this conversation. */
  streamError?: StreamError | null;
  /** Gets a failed attachment download. */
  onDownloadError?: (error: unknown) => void;
}

export function ChatThread({
  conversationId,
  messages,
  streamingContent,
  streamingThinking,
  streamingToolEvents,
  isStreaming,
  onEdit,
  onRetry,
  onDownloadError,
  streamError = null,
}: Props) {
  const { t, lang } = useLanguage();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  if (messages.length === 0 && streamingContent === null) {
    return (
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--text-muted)",
          fontSize: 16,
        }}
      >
        {t("startConversation")}
      </div>
    );
  }

  const lastIndex = messages.length - 1;

  return (
    <div className="chat-thread" style={{ flex: 1, overflowY: "auto" }}>
      {messages.map((m, i) => (
        <MessageBubble
          key={m.id}
          conversationId={conversationId}
          message={m}
          thinking={m.thinking ?? null}
          toolEvents={m.tool_events ?? []}
          canEdit={m.role === "user" && !isStreaming}
          canRetry={m.role === "assistant" && i === lastIndex && !isStreaming}
          canCopy={m.role === "assistant"}
          onEdit={onEdit}
          onRetry={onRetry}
          onDownloadError={onDownloadError}
        />
      ))}
      {streamingContent !== null && (
        <MessageBubble
          conversationId={conversationId}
          message={{
            id: "__streaming__",
            role: "assistant",
            content: streamingContent,
            created_at: "",
            attachments: [],
          }}
          thinking={streamingThinking}
          toolEvents={streamingToolEvents}
          streaming
          canEdit={false}
          canRetry={false}
          canCopy={false}
          onEdit={onEdit}
          onRetry={onRetry}
        />
      )}
      {streamError && streamError.conversationId === conversationId && (
        <div role="alert" style={{ color: "var(--danger)", fontSize: 13, marginBottom: 12 }}>
          {messageFor[lang](streamError.error)}
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
