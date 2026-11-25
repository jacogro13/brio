import { useState } from "react";
import { useT } from "../i18n";
import type { StringKey } from "../i18n/strings";

/** One web-access tool call (Phase 6): search or page fetch. Frontend-only
 * shape (the backend stores `tool_events` as untyped JSON). Persisted on the
 * assistant message so the activity chips re-render on reload. */
export interface ToolEvent {
  id: number;
  tool: string;
  query?: string;
  url?: string;
  ok?: boolean;
  summary?: string;
  results?: { title: string; url: string }[];
}

type TFunc = (key: StringKey, vars?: Record<string, string | number>) => string;

/** Collapsed web-access activity chips shown above an assistant answer. Renders
 * both live (from the stream) and persisted (`message.tool_events`) events —
 * identical shape, so the display doesn't change on reload. */
export function ToolActivity({ events }: { events: ToolEvent[] }) {
  if (!events || events.length === 0) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 8 }}>
      {events.map((e) => (
        <ToolChip key={e.id} event={e} />
      ))}
    </div>
  );
}

function label(event: ToolEvent, t: TFunc): string {
  if (event.tool === "web_search") return t("searching", { query: event.query ?? "" });
  if (event.tool === "fetch_page") {
    let host = event.url ?? "";
    try {
      host = new URL(event.url ?? "").hostname;
    } catch {
      /* keep raw */
    }
    return t("reading", { host });
  }
  return event.tool || t("tool");
}

function ToolChip({ event }: { event: ToolEvent }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const running = event.ok === undefined;
  const failed = event.ok === false;
  const hasResults = (event.results?.length ?? 0) > 0;

  const icon = running ? "⏳" : failed ? "⚠️" : event.tool === "fetch_page" ? "📄" : "🔎";

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        background: "var(--surface-hover)",
        borderRadius: 8,
        padding: "6px 10px",
        fontSize: 12,
        color: "var(--text)",
      }}
    >
      <button
        onClick={() => hasResults && setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          width: "100%",
          background: "transparent",
          border: "none",
          color: "inherit",
          cursor: hasResults ? "pointer" : "default",
          padding: 0,
          fontSize: 12,
          textAlign: "left",
        }}
      >
        <span>{icon}</span>
        <span style={{ flex: 1, wordBreak: "break-word" }}>{label(event, t)}</span>
        {event.summary && !running && (
          <span style={{ color: "var(--text-muted)" }}>{event.summary}</span>
        )}
        {hasResults && <span style={{ color: "var(--text-muted)" }}>{open ? "▾" : "▸"}</span>}
      </button>
      {open && hasResults && (
        <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
          {event.results!.map((r, i) => (
            <li key={i} style={{ marginBottom: 2 }}>
              <a
                href={r.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: "var(--accent)" }}
              >
                {r.title || r.url}
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
