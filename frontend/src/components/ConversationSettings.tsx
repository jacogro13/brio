import { useEffect, useRef, useState } from "react";
import { useT } from "../i18n";
import type { Conversation, ConversationSettings as Settings } from "../hooks/useConversations";

interface Props {
  conversation: Conversation;
  onUpdate: (patch: Settings) => void;
}

// `null` overrides render as empty inputs — an empty field means "use the
// server default", never `0` / `false` (so we never use `||`).
function numToInput(v: number | null | undefined): string {
  return v === null || v === undefined ? "" : String(v);
}

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 12,
  fontWeight: 600,
  color: "var(--text-muted)",
  marginBottom: 4,
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "7px 9px",
  borderRadius: 6,
  border: "1px solid var(--border)",
  background: "var(--surface)",
  color: "var(--text)",
  fontSize: 13,
  outline: "none",
  boxSizing: "border-box",
};

export function ConversationSettings({ conversation, onUpdate }: Props) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [temperature, setTemperature] = useState("");
  const [maxTokens, setMaxTokens] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);

  // Seed the draft from the conversation each time the popover opens, so it
  // always reflects the persisted overrides (and edits are discardable).
  const openPopover = () => {
    setTemperature(numToInput(conversation.temperature));
    setMaxTokens(numToInput(conversation.max_tokens));
    setSystemPrompt(conversation.system_prompt_override ?? "");
    setOpen(true);
  };

  useEffect(() => {
    if (!open) return;
    const onClickOutside = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  const buildPatch = (): Settings => ({
    temperature: temperature.trim() === "" ? null : Number(temperature),
    max_tokens: maxTokens.trim() === "" ? null : Number(maxTokens),
    system_prompt_override:
      systemPrompt.trim() === "" ? null : systemPrompt,
  });

  const save = () => {
    onUpdate(buildPatch());
    setOpen(false);
  };

  const resetToDefaults = () => {
    setTemperature("");
    setMaxTokens("");
    setSystemPrompt("");
  };

  return (
    <div ref={rootRef} style={{ position: "relative", flexShrink: 0 }}>
      <button
        onClick={() => (open ? setOpen(false) : openPopover())}
        aria-label={t("conversationSettings")}
        title={t("conversationSettings")}
        style={{
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: open ? "var(--text)" : "var(--text-muted)",
          fontSize: 18,
          padding: "4px 6px",
          lineHeight: 1,
        }}
      >
        ⚙
      </button>

      {open && (
        <div
          style={{
            position: "absolute",
            top: 36,
            right: 0,
            width: 300,
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            boxShadow: "0 8px 24px rgba(45, 32, 19, 0.15)",
            padding: 14,
            zIndex: 200,
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}
        >
          <div
            style={{
              fontSize: 13,
              fontWeight: 700,
              color: "var(--text)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            {t("conversationSettings")}
            <button
              onClick={resetToDefaults}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--text-muted)",
                cursor: "pointer",
                fontSize: 11,
                padding: 0,
              }}
            >
              {t("resetToDefaults")}
            </button>
          </div>

          <div>
            <label style={labelStyle}>
              {t("temperature")}{" "}
              <span style={{ fontWeight: 400, color: "var(--text-muted)" }}>
                {temperature.trim() === "" ? t("temperatureDefault") : temperature}
              </span>
            </label>
            <input
              type="range"
              min={0}
              max={2}
              step={0.1}
              value={temperature === "" ? 0.7 : Number(temperature)}
              onChange={(e) => setTemperature(e.target.value)}
              style={{ width: "100%", accentColor: "var(--accent)" }}
            />
          </div>

          <div>
            <label style={labelStyle}>{t("maxTokens")}</label>
            <input
              type="number"
              min={1}
              placeholder={t("defaultPlaceholder")}
              value={maxTokens}
              onChange={(e) => setMaxTokens(e.target.value)}
              style={inputStyle}
            />
          </div>

          <div>
            <label style={labelStyle}>{t("systemPromptOverride")}</label>
            <textarea
              rows={3}
              placeholder={t("systemPromptPlaceholder")}
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              style={{ ...inputStyle, resize: "vertical", lineHeight: 1.4 }}
            />
          </div>

          <button
            onClick={save}
            style={{
              padding: "8px 12px",
              background: "var(--accent)",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {t("save")}
          </button>
        </div>
      )}
    </div>
  );
}
