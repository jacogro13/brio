import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import type { Message } from "../hooks/useConversations";
import { useT } from "../i18n";
import { copyText } from "../utils/clipboard";
import { ActionButton } from "./ActionButton";
import { AttachmentChips } from "./AttachmentChips";
import { CodeBlock } from "./CodeBlock";
import { ThinkingBlock } from "./ThinkingBlock";
import { ToolActivity, type ToolEvent } from "./ToolActivity";

/** One message: markdown for the assistant, plain text for the user, inline
 * editing, and the hover action row (edit / retry / copy). */
export function MessageBubble({
  conversationId,
  message,
  thinking = null,
  toolEvents = [],
  streaming = false,
  canEdit,
  canRetry,
  canCopy,
  onEdit,
  onRetry,
  onDownloadError,
}: {
  conversationId: string;
  message: Message;
  thinking?: string | null;
  toolEvents?: ToolEvent[];
  streaming?: boolean;
  canEdit: boolean;
  canRetry: boolean;
  canCopy: boolean;
  onEdit: (messageId: string, content: string) => void;
  onRetry: () => void;
  onDownloadError?: (error: unknown) => void;
}) {
  const t = useT();
  const isUser = message.role === "user";
  const [hovered, setHovered] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);
  const [copied, setCopied] = useState(false);

  const copyMessage = async () => {
    if (await copyText(message.content)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  const startEdit = () => {
    setDraft(message.content);
    setEditing(true);
  };

  const saveEdit = () => {
    const value = draft.trim();
    if (value) onEdit(message.id, value);
    setEditing(false);
  };

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: isUser ? "flex-end" : "flex-start",
        marginBottom: 12,
      }}
    >
      <div
        className={isUser ? "bubble bubble-user" : "bubble bubble-assistant"}
        style={{
          minWidth: editing ? "60%" : undefined,
          padding: "10px 14px",
          borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
          background: isUser ? "var(--accent)" : "var(--surface)",
          border: isUser ? "none" : "1px solid var(--border)",
          color: isUser ? "#fff" : "var(--text)",
          fontSize: 14,
          lineHeight: 1.6,
          wordBreak: "break-word",
        }}
      >
        {!editing && message.attachments && message.attachments.length > 0 && (
          <AttachmentChips
            conversationId={conversationId}
            attachments={message.attachments}
            onError={onDownloadError}
          />
        )}
        {editing ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <textarea
              value={draft}
              autoFocus
              rows={3}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  saveEdit();
                } else if (e.key === "Escape") {
                  setEditing(false);
                }
              }}
              style={{
                width: "100%",
                minWidth: 260,
                padding: "8px 10px",
                borderRadius: 8,
                border: "1px solid var(--accent)",
                background: "var(--surface)",
                color: "var(--text)",
                fontSize: 14,
                resize: "vertical",
                outline: "none",
                lineHeight: 1.4,
                fontFamily: "inherit",
              }}
            />
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <ActionButton label={t("cancel")} onClick={() => setEditing(false)} />
              <ActionButton label={t("saveAndSubmit")} onClick={saveEdit} primary />
            </div>
          </div>
        ) : isUser ? (
          <span style={{ whiteSpace: "pre-wrap" }}>{message.content}</span>
        ) : (
          <>
            <ToolActivity events={toolEvents} />
            {thinking && (
              <ThinkingBlock
                thinking={thinking}
                streaming={streaming}
                hasAnswer={message.content !== ""}
              />
            )}
            {streaming && message.content === "" && !thinking ? (
              <div className="dots" aria-label={t("thinkingActive")}>
                <span />
                <span />
                <span />
              </div>
            ) : (
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeHighlight, rehypeKatex]}
                components={{
                  a: ({ href, children }) => (
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  ),
                  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
                }}
              >
                {message.content}
              </ReactMarkdown>
            )}
          </>
        )}
        {streaming && message.content !== "" && (
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 14,
              background: "var(--accent)",
              marginLeft: 2,
              verticalAlign: "middle",
              animation: "blink 1s step-start infinite",
            }}
          />
        )}
      </div>

      {!editing && (canEdit || canRetry || canCopy) && (
        <div
          style={{
            display: "flex",
            gap: 6,
            marginTop: 4,
            height: 22,
            visibility: hovered ? "visible" : "hidden",
          }}
        >
          {canEdit && <ActionButton label={t("edit")} onClick={startEdit} />}
          {canRetry && <ActionButton label={t("retry")} onClick={onRetry} />}
          {canCopy && (
            <ActionButton
              label={copied ? t("copied") : t("copy")}
              onClick={copyMessage}
            />
          )}
        </div>
      )}
    </div>
  );
}
