import { useEffect, useState } from "react";
import { useLanguage } from "../i18n";
import { THINKING_VERBS } from "../i18n/strings";

/** How long each rotating "still thinking" verb is shown, in ms. */
const VERB_INTERVAL_MS = 2500;

interface Props {
  thinking: string;
  /** True while the reply is still streaming (thinking or answer). */
  streaming?: boolean;
  /** True once the answer has begun — drives the "thinking…" shimmer label. */
  hasAnswer?: boolean;
}

/**
 * Collapsible reasoning panel shown above an assistant answer. Stays collapsed
 * by default — the reasoning is never shown until the user clicks the header to
 * reveal it, even while it is still streaming (a shimmer label signals activity).
 */
export function ThinkingBlock({ thinking, streaming = false, hasAnswer = false }: Props) {
  const { t, lang } = useLanguage();
  const [expanded, setExpanded] = useState(false);

  const toggle = () => setExpanded((e) => !e);

  const active = streaming && !hasAnswer;

  // While reasoning streams, cycle a whimsical verb (Claude-Code style) so the
  // wait feels less static.
  const verbs = THINKING_VERBS[lang];
  const [verbIndex, setVerbIndex] = useState(0);
  useEffect(() => {
    if (!active) return;
    const id = setInterval(
      () => setVerbIndex((i) => (i + 1) % verbs.length),
      VERB_INTERVAL_MS
    );
    return () => clearInterval(id);
  }, [active, verbs.length]);
  const activeLabel = `${verbs[verbIndex] ?? t("thinkingActive")}…`;

  return (
    <div
      style={{
        marginBottom: expanded ? 10 : 4,
        border: "1px solid var(--border)",
        borderRadius: 8,
        background: "var(--surface-hover)",
        overflow: "hidden",
      }}
    >
      <button
        onClick={toggle}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          width: "100%",
          padding: "5px 10px",
          border: "none",
          background: "transparent",
          color: "var(--text-muted)",
          cursor: "pointer",
          fontSize: 12,
          fontWeight: 600,
          textAlign: "left",
        }}
      >
        <span style={{ fontSize: 10 }}>{expanded ? "▾" : "▸"}</span>
        <span className={active ? "thinking-shimmer" : undefined}>
          {active ? activeLabel : t("thoughts")}
        </span>
      </button>
      {expanded && (
        <div
          style={{
            padding: "0 12px 8px 26px",
            color: "var(--text-muted)",
            fontSize: 13,
            lineHeight: 1.5,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            fontStyle: "italic",
          }}
        >
          {thinking}
        </div>
      )}
    </div>
  );
}
