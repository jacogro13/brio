import { useT } from "../i18n";

interface Props {
  webAccess: boolean;
  thinking: boolean;
  isStreaming: boolean;
  onAttach: () => void;
  onToggleWeb: () => void;
  onToggleThinking: () => void;
  onSend: () => void;
  onStop: () => void;
}

/** The composer's control row: 📎 🌐 🧠, then Send (or Stop while streaming). */
export function ComposerToggles({
  webAccess,
  thinking,
  isStreaming,
  onAttach,
  onToggleWeb,
  onToggleThinking,
  onSend,
  onStop,
}: Props) {
  const t = useT();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      <button
        onClick={onAttach}
        aria-label={t("attachFiles")}
        title={t("attachFiles")}
        disabled={isStreaming}
        className="icon-btn"
      >
        📎
      </button>
      <button
        onClick={onToggleWeb}
        aria-label={t("toggleWebAccess")}
        aria-pressed={webAccess}
        title={webAccess ? t("webAccessOn") : t("webAccessOff")}
        className="icon-btn"
        style={
          webAccess
            ? { background: "var(--accent-soft)", color: "var(--accent)" }
            : undefined
        }
      >
        🌐
      </button>
      <button
        onClick={onToggleThinking}
        aria-label={t("toggleThinking")}
        aria-pressed={thinking && !webAccess}
        // Web access forces thinking off for the turn — reflect that.
        disabled={webAccess}
        title={
          webAccess
            ? t("thinkingWebAccessNote")
            : thinking
              ? t("thinkingOn")
              : t("thinkingOff")
        }
        className="icon-btn"
        style={
          thinking && !webAccess
            ? { background: "var(--accent-soft)", color: "var(--accent)" }
            : webAccess
              ? { opacity: 0.4 }
              : undefined
        }
      >
        🧠
      </button>
      <div style={{ flex: 1 }} />
      {isStreaming ? (
        <button onClick={onStop} style={{ ...sendStyle, background: "var(--danger)" }}>
          {t("stop")}
        </button>
      ) : (
        <button onClick={onSend} style={{ ...sendStyle, background: "var(--accent)" }}>
          {t("send")}
        </button>
      )}
    </div>
  );
}

const sendStyle: React.CSSProperties = {
  height: 34,
  padding: "6px 14px",
  color: "#fff",
  border: "none",
  borderRadius: 10,
  cursor: "pointer",
  fontSize: 14,
  fontWeight: 600,
};
