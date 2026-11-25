import { useState } from "react";
import { messageFor } from "../api/errors";
import { useLogin, useRegister } from "../hooks/useAuth";
import { useLanguage } from "../i18n";
import { LanguageSwitcher } from "./LanguageSwitcher";

type Tab = "login" | "register";

/** Login / register gate. On success it stores the JWT and calls
 * `onAuthenticated`. Registration is open (self-service); after a successful
 * register it logs the new user straight in. */
export function AuthPage({ onAuthenticated }: { onAuthenticated: () => void }) {
  const { t, lang } = useLanguage();
  const [tab, setTab] = useState<Tab>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  // The caught error itself, not its text: the text follows a language switch.
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const { mutateAsync: login } = useLogin();
  const { mutateAsync: register } = useRegister();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      if (tab === "register") {
        await register({ username, password, language: lang });
      }
      await login({ username, password });
      onAuthenticated();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="app-shell"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg)",
        color: "var(--text)",
        fontFamily: "var(--font-sans)",
      }}
    >
      <form
        onSubmit={submit}
        style={{
          width: 320,
          padding: 28,
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <h1
          style={{
            margin: 0,
            fontSize: 26,
            fontFamily: "var(--font-serif)",
            fontWeight: 600,
            textAlign: "center",
          }}
        >
          {t("appName")}
        </h1>

        <div style={{ display: "flex", justifyContent: "center" }}>
          <LanguageSwitcher />
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          {(["login", "register"] as Tab[]).map((tabValue) => (
            <button
              key={tabValue}
              type="button"
              onClick={() => {
                setTab(tabValue);
                setError(null);
              }}
              style={{
                flex: 1,
                padding: "8px 0",
                borderRadius: 8,
                border: `1px solid ${tab === tabValue ? "var(--accent)" : "var(--border)"}`,
                background: tab === tabValue ? "var(--accent)" : "transparent",
                color: tab === tabValue ? "#fff" : "var(--text)",
                cursor: "pointer",
                fontSize: 14,
              }}
            >
              {tabValue === "login" ? t("tabLogin") : t("tabRegister")}
            </button>
          ))}
        </div>

        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
          {t("username")}
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
            style={inputStyle}
          />
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
          {t("password")}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={tab === "login" ? "current-password" : "new-password"}
            required
            style={inputStyle}
          />
        </label>

        {error != null && (
          <div style={{ color: "var(--danger)", fontSize: 13 }}>{messageFor[lang](error)}</div>
        )}

        <button
          type="submit"
          disabled={busy}
          style={{
            padding: "10px 0",
            borderRadius: 8,
            border: "none",
            background: "var(--accent)",
            color: "#fff",
            fontSize: 15,
            fontWeight: 600,
            cursor: busy ? "default" : "pointer",
            opacity: busy ? 0.6 : 1,
          }}
        >
          {busy ? "…" : tab === "login" ? t("logIn") : t("createAccount")}
        </button>
      </form>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: "8px 10px",
  borderRadius: 8,
  border: "1px solid var(--border)",
  background: "var(--surface)",
  color: "var(--text)",
  // 16px — iOS Safari auto-zooms on focusing any input with font-size < 16px.
  fontSize: 16,
  outline: "none",
};
