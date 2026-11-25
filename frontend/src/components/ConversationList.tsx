import { useState } from "react";
import { useT } from "../i18n";
import type { ConversationSummary } from "../hooks/useConversations";

interface Props {
  conversations: ConversationSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
}

export function ConversationList({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onRename,
}: Props) {
  const t = useT();
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const startRename = (c: ConversationSummary) => {
    setRenamingId(c.id);
    setDraft(c.title ?? "");
  };

  const commitRename = () => {
    const value = draft.trim();
    if (renamingId && value) onRename(renamingId, value);
    setRenamingId(null);
  };

  return (
    <div
      style={{
        width: 240,
        minWidth: 240,
        background: "var(--surface)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        borderRight: "1px solid var(--border)",
      }}
    >
      <div style={{ padding: "16px 12px 8px" }}>
        <button
          onClick={onNew}
          style={{
            width: "100%",
            padding: "8px 12px",
            background: "var(--surface-hover)",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: 14,
            fontWeight: 600,
          }}
        >
          {t("newChat")}
        </button>
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: "4px 8px" }}>
        {conversations.map((c) => (
          <div
            key={c.id}
            style={{
              display: "flex",
              alignItems: "center",
              borderRadius: 6,
              marginBottom: 2,
              background: c.id === activeId ? "var(--surface-hover)" : "transparent",
            }}
          >
            {renamingId === c.id ? (
              <input
                value={draft}
                autoFocus
                onChange={(e) => setDraft(e.target.value)}
                onBlur={commitRename}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    commitRename();
                  } else if (e.key === "Escape") {
                    setRenamingId(null);
                  }
                }}
                style={{
                  flex: 1,
                  padding: "7px 9px",
                  margin: "1px 2px",
                  borderRadius: 5,
                  border: "1px solid var(--accent)",
                  background: "var(--surface)",
                  color: "var(--text)",
                  fontSize: 13,
                  outline: "none",
                }}
              />
            ) : (
              <>
                <button
                  onClick={() => onSelect(c.id)}
                  style={{
                    flex: 1,
                    textAlign: "left",
                    padding: "8px 10px",
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    color: c.id === activeId ? "var(--text)" : "var(--text-muted)",
                    fontSize: 13,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {c.title ?? t("newConversation")}
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    startRename(c);
                  }}
                  title={t("rename")}
                  style={{
                    padding: "6px 4px",
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    color: "var(--text-muted)",
                    fontSize: 13,
                    flexShrink: 0,
                  }}
                >
                  ✎
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(c.id);
                  }}
                  title={t("delete")}
                  style={{
                    padding: "6px 8px",
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    color: "var(--text-muted)",
                    fontSize: 14,
                    flexShrink: 0,
                  }}
                >
                  ×
                </button>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
