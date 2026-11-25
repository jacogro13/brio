import type { Attachment } from "../hooks/useConversations";
import { useT } from "../i18n";

interface Props {
  pending: Attachment[];
  /** How many uploads are still running. */
  uploading: number;
  onRemove: (id: string) => void;
}

/** Uploaded files staged for the next message, plus "uploading…". */
export function PendingChips({ pending, uploading, onRemove }: Props) {
  const t = useT();
  if (pending.length === 0 && uploading === 0) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {pending.map((a) => (
        <span
          key={a.id}
          title={a.has_text ? undefined : t("attachmentNoTextPending")}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 8px",
            borderRadius: 6,
            background: "var(--surface)",
            border: "1px solid var(--border)",
            color: "var(--text)",
            fontSize: 12,
          }}
        >
          📄 {a.filename}
          {!a.has_text && (
            <span style={{ color: "var(--text-muted)", fontSize: 11 }}>
              {t("noText")}
            </span>
          )}
          <button
            onClick={() => onRemove(a.id)}
            aria-label={t("removeAttachment", { name: a.filename })}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
              fontSize: 14,
              lineHeight: 1,
              padding: 0,
            }}
          >
            ×
          </button>
        </span>
      ))}
      {uploading > 0 && (
        <span style={{ color: "var(--text-muted)", fontSize: 12, alignSelf: "center" }}>
          {t("uploading")}
        </span>
      )}
    </div>
  );
}
