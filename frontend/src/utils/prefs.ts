// Composer capability toggles that persist across turns and conversations in
// localStorage. Thinking lives here (not just in MessageInput) so regenerate
// and edit can honour the user's current preference without the composer in
// scope. Mirrors the web-access toggle's sticky pattern.
const THINKING_KEY = "chatbot.thinking";

export function getThinkingPref(): boolean {
  return localStorage.getItem(THINKING_KEY) === "1";
}

export function setThinkingPref(on: boolean): void {
  localStorage.setItem(THINKING_KEY, on ? "1" : "0");
}
