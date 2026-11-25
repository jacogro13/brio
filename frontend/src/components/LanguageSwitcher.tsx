import { LANGUAGES, LANGUAGE_LABELS, useLanguage } from "../i18n";

/** Compact EN · IT · DE selector. Used in the top bar (signed in) and on the
 * auth page (before sign-in — changes stay local until an account exists). */
export function LanguageSwitcher() {
  const { lang, setLanguage, t } = useLanguage();
  return (
    <div
      role="group"
      aria-label={t("selectLanguage")}
      style={{ display: "flex", gap: 2, flexShrink: 0 }}
    >
      {LANGUAGES.map((l) => {
        const active = l === lang;
        return (
          <button
            key={l}
            type="button"
            onClick={() => setLanguage(l)}
            aria-pressed={active}
            style={{
              padding: "3px 6px",
              borderRadius: 5,
              border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
              background: active ? "var(--accent)" : "transparent",
              color: active ? "#fff" : "var(--text-muted)",
              cursor: "pointer",
              fontSize: 11,
              fontWeight: 600,
              lineHeight: 1,
            }}
          >
            {LANGUAGE_LABELS[l]}
          </button>
        );
      })}
    </div>
  );
}
