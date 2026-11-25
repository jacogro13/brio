import { useDownloadAttachment, type Attachment } from "../hooks/useConversations";
import { useT } from "../i18n";

/** A sent message's attachments; clicking one downloads it. */
export function AttachmentChips({
  conversationId,
  attachments,
  onError,
}: {
  conversationId: string;
  attachments: Attachment[];
  /** Gets a failed download (shown in the banner). */
  onError?: (error: unknown) => void;
}) {
  const t = useT();
  const downloadAttachment = useDownloadAttachment();
  // Download through the backend as a Blob (a plain <a href> can't carry the
  // Bearer header), then trigger a programmatic download from an object URL.
  const handleDownload = async (id: string, filename: string) => {
    try {
      const blob = await downloadAttachment(conversationId, id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      onError?.(error);
    }
  };

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
      {attachments.map((a) => (
        <button
          key={a.id}
          onClick={() => handleDownload(a.id, a.filename)}
          title={
            a.has_text
              ? t("downloadAttachment", { name: a.filename })
              : t("attachmentNoText", { name: a.filename })
          }
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 8px",
            borderRadius: 6,
            background: "var(--surface-hover)",
            border: "1px solid var(--border)",
            color: "var(--text)",
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          📄 {a.filename}
          {!a.has_text && (
            <span style={{ color: "var(--text-muted)", fontSize: 11 }}>{t("noText")}</span>
          )}
        </button>
      ))}
    </div>
  );
}
