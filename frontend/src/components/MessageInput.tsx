import { useRef, useState } from "react";
import { messageFor } from "../api/errors";
import { useLanguage } from "../i18n";
import { useUploadAttachment, type Attachment } from "../hooks/useConversations";
import { ComposerToggles } from "./ComposerToggles";
import { PendingChips } from "./PendingChips";
import { getThinkingPref, setThinkingPref } from "../utils/prefs";

const WEB_ACCESS_KEY = "chatbot.webAccess";

interface Props {
  // `null` while the chat is still a draft (no row yet). The parent keys this
  // component by a stable threadKey — NOT the id — so promoting a draft to a
  // real conversation doesn't remount and wipe staged text/attachments.
  conversationId: string | null;
  onSend: (
    content: string,
    attachments: Attachment[],
    webAccess: boolean,
    thinking: boolean
  ) => void;
  onStop: () => void;
  isStreaming: boolean;
  /** Materialise a draft chat before uploading, returning its real id. */
  ensureConversation: () => Promise<string>;
}

export function MessageInput({
  conversationId,
  onSend,
  onStop,
  isStreaming,
  ensureConversation,
}: Props) {
  const { t, lang } = useLanguage();
  const { mutateAsync: uploadAttachment } = useUploadAttachment();
  const ref = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(0);
  // The last failed upload (or failed create of a draft's row); a failed file
  // is never staged. Cleared when files are picked again or a message is sent.
  const [uploadError, setUploadError] = useState<unknown>(null);
  // Web-access + thinking toggles are sticky across turns/conversations via
  // localStorage (thinking through the shared prefs helper so regenerate/edit
  // read the same value). Web access forces thinking off for the turn on the
  // backend, so it's visually disabled while web access is on.
  const [webAccess, setWebAccess] = useState(
    () => localStorage.getItem(WEB_ACCESS_KEY) === "1"
  );
  const [thinking, setThinking] = useState(() => getThinkingPref());

  const toggleWeb = () => {
    setWebAccess((on) => {
      const next = !on;
      localStorage.setItem(WEB_ACCESS_KEY, next ? "1" : "0");
      return next;
    });
  };

  const toggleThinking = () => {
    setThinking((on) => {
      const next = !on;
      setThinkingPref(next);
      return next;
    });
  };

  const submit = () => {
    if (isStreaming || uploading > 0) return;
    const value = ref.current?.value.trim() ?? "";
    if (!value && pending.length === 0) return;
    // Web access wins: the backend forces thinking off for a web turn.
    onSend(value, pending, webAccess, thinking && !webAccess);
    setUploadError(null);
    if (ref.current) {
      ref.current.value = "";
      ref.current.style.height = "auto"; // collapse the auto-grown textarea
    }
    setPending([]);
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const list = Array.from(files);
    setUploadError(null);
    // Uploading is the first action that needs a real row, so promote the draft.
    let id = conversationId;
    if (id === null) {
      try {
        id = await ensureConversation();
      } catch (error) {
        setUploadError(error);
        if (fileRef.current) fileRef.current.value = "";
        return;
      }
    }
    const target = id;
    setUploading((n) => n + list.length);
    await Promise.all(
      list.map(async (file) => {
        try {
          const attachment = await uploadAttachment({ conversationId: target, file });
          setPending((prev) => [...prev, attachment]);
        } catch (error) {
          setUploadError(error);
        } finally {
          setUploading((n) => n - 1);
        }
      })
    );
    if (fileRef.current) fileRef.current.value = "";
  };

  const removePending = (id: string) =>
    setPending((prev) => prev.filter((a) => a.id !== id));

  return (
    <div
      className="composer"
      style={{
        background: "var(--bg)",
        borderTop: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <PendingChips pending={pending} uploading={uploading} onRemove={removePending} />
      {uploadError != null && (
        <div role="alert" style={{ color: "var(--danger)", fontSize: 13 }}>
          {messageFor[lang](uploadError)}
        </div>
      )}

      <div style={pillStyle}>
        <input
          ref={fileRef}
          type="file"
          multiple
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
        <textarea
          ref={ref}
          rows={1}
          placeholder={t("messagePlaceholder")}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          onInput={(e) => {
            // Auto-grow up to ~6 lines, then scroll.
            const el = e.currentTarget;
            el.style.height = "auto";
            el.style.height = Math.min(el.scrollHeight, 160) + "px";
          }}
          style={{
            width: "100%",
            padding: "4px 6px",
            border: "none",
            background: "transparent",
            color: "var(--text)",
            fontSize: 16,
            resize: "none",
            outline: "none",
            lineHeight: 1.4,
            overflowY: "auto",
            fontFamily: "inherit",
          }}
        />
        <ComposerToggles
          webAccess={webAccess}
          thinking={thinking}
          isStreaming={isStreaming}
          onAttach={() => fileRef.current?.click()}
          onToggleWeb={toggleWeb}
          onToggleThinking={toggleThinking}
          onSend={submit}
          onStop={onStop}
        />
      </div>
    </div>
  );
}

// Unified composer pill: textarea on top, control row (📎 🌐 … Send) below.
const pillStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 4,
  padding: 8,
  border: "1px solid var(--border)",
  borderRadius: 16,
  background: "var(--surface)",
};
