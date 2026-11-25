import { useT } from "../i18n";

/** Shown instead of the thread for a draft or empty chat. */
export function Greeting() {
  const t = useT();
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        color: "var(--text-muted)",
        textAlign: "center",
        padding: 24,
        gap: 8,
      }}
    >
      <div style={{ fontSize: 28 }}>💬</div>
      <div
        style={{
          fontSize: 26,
          fontWeight: 600,
          fontFamily: "var(--font-serif)",
          color: "var(--text)",
        }}
      >
        {t("greetingTitle")}
      </div>
      <div style={{ fontSize: 14, color: "var(--text-muted)" }}>{t("greetingSubtitle")}</div>
    </div>
  );
}
