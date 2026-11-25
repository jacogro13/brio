/** A small text button in a message's action row or edit form. */
export function ActionButton({
  label,
  onClick,
  primary = false,
}: {
  label: string;
  onClick: () => void;
  primary?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "3px 10px",
        fontSize: 12,
        fontWeight: 600,
        borderRadius: 6,
        border: primary ? "none" : "1px solid var(--border)",
        cursor: "pointer",
        background: primary ? "var(--accent)" : "var(--surface)",
        color: primary ? "#fff" : "var(--text)",
      }}
    >
      {label}
    </button>
  );
}
