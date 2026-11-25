import type { ReactNode } from "react";
import { useT } from "../i18n";
import { LanguageSwitcher } from "./LanguageSwitcher";

interface Props {
  title: string;
  /** The ⚙ settings popover, when a persisted chat is open. */
  settings: ReactNode;
  /** Shown on desktop only. */
  username: string | null;
  mobile: boolean;
  onToggleSidebar: () => void;
  onLogout: () => void;
}

export function TopBar({ title, settings, username, mobile, onToggleSidebar, onLogout }: Props) {
  const t = useT();
  return (
    <div
      className="top-bar"
      style={{
        display: "flex",
        alignItems: "center",
        paddingLeft: 12,
        paddingRight: 12,
        minHeight: 48,
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
        flexShrink: 0,
        gap: 10,
      }}
    >
      <button
        onClick={onToggleSidebar}
        aria-label={t("toggleConversations")}
        style={{
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: "var(--text-muted)",
          fontSize: 20,
          padding: "4px 6px",
          lineHeight: 1,
        }}
      >
        ☰
      </button>
      <span
        style={{
          flex: 1,
          fontSize: 17,
          fontWeight: 600,
          fontFamily: "var(--font-serif)",
          color: "var(--text)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {title}
      </span>
      {settings}
      {!mobile && username && (
        <span
          style={{
            fontSize: 13,
            color: "var(--text-muted)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            maxWidth: 120,
          }}
          title={username}
        >
          {username}
        </span>
      )}
      <LanguageSwitcher />
      <button
        onClick={onLogout}
        title={t("logoutTitle")}
        style={{
          background: "transparent",
          border: "1px solid var(--border)",
          borderRadius: 6,
          cursor: "pointer",
          color: "var(--text-muted)",
          fontSize: 12,
          padding: "4px 8px",
          lineHeight: 1,
        }}
      >
        {t("logout")}
      </button>
    </div>
  );
}
