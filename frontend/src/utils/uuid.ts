// crypto.randomUUID() is only available in secure contexts (HTTPS / localhost),
// so it throws when the frontend is opened from a LAN IP over plain HTTP.
export function uuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return (
    Math.random().toString(36).slice(2) +
    Math.random().toString(36).slice(2) +
    Date.now().toString(36)
  );
}
