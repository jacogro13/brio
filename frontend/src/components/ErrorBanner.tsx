import { messageFor } from "../api/errors";
import { useLanguage } from "../i18n";

interface Props {
  /** The caught error itself: its text follows the UI language. */
  error: unknown;
  onDismiss: () => void;
}

/** A failed action's text at the top of the chat area, until dismissed or
 * replaced by a newer error. */
export function ErrorBanner({ error, onDismiss }: Props) {
  const { t, lang } = useLanguage();
  return (
    <div
      role="alert"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        margin: "8px 12px 0",
        padding: "8px 12px",
        borderRadius: 8,
        border: "1px solid var(--danger)",
        background: "var(--accent-soft)",
        color: "var(--danger)",
        fontSize: 13,
        flexShrink: 0,
      }}
    >
      <span style={{ flex: 1 }}>{messageFor[lang](error)}</span>
      <button
        onClick={onDismiss}
        aria-label={t("dismiss")}
        style={{
          background: "transparent",
          border: "none",
          color: "var(--danger)",
          cursor: "pointer",
          fontSize: 16,
          lineHeight: 1,
          padding: 0,
        }}
      >
        ×
      </button>
    </div>
  );
}
