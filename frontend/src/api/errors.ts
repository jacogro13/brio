// Chatbot's error codes → text, one table per UI language (Blueprint v2, F3).
// Components show `messageFor[lang](error)` and never look at status codes or
// message text.
//
// Deviation from §4b (codes become Italian text): Chatbot's UI is EN/IT/DE
// (ADR-007), so `en` and `de` override every common code of the canonical
// (Italian) table, and `it` adds only Chatbot's own codes. An unknown code still
// gives the canonical Italian fallback in every language (spec 005).

import type { Lang } from "../i18n/strings";
import { makeMessageFor, type MessageTable } from "./messages";

const en: MessageTable = {
  // Common codes (the canonical table is Italian).
  network_error: "Can't reach the server. Check your connection and try again.",
  internal_error: "Server error. Please try again shortly.",
  not_found: "Not found: it may have been deleted. Reload the page.",
  conflict: "This can't be done right now.",
  invalid_input: "Invalid data.",
  // Chatbot's codes.
  invalid_credentials: "Invalid username or password.",
  username_taken: "This username is already taken.",
  http_429: "Too many login attempts. Wait a minute and try again.",
  invalid_token: "Your session is no longer valid. Please log in again.",
  token_expired: "Your session has expired. Please log in again.",
  conversation_not_found: "Conversation not found: it may have been deleted.",
  message_not_found: "Message not found: it may have been deleted.",
  nothing_to_regenerate: "There is no reply to regenerate.",
  attachment_too_large: "The file is too large.",
  attachment_not_found: "Attachment not found.",
};

const it: MessageTable = {
  invalid_credentials: "Nome utente o password non validi.",
  username_taken: "Questo nome utente è già in uso.",
  http_429: "Troppi tentativi di accesso. Attendi un minuto e riprova.",
  invalid_token: "La sessione non è più valida. Accedi di nuovo.",
  token_expired: "La sessione è scaduta. Accedi di nuovo.",
  conversation_not_found: "Conversazione non trovata: forse è stata eliminata.",
  message_not_found: "Messaggio non trovato: forse è stato eliminato.",
  nothing_to_regenerate: "Non c'è nessuna risposta da rigenerare.",
  attachment_too_large: "Il file è troppo grande.",
  attachment_not_found: "Allegato non trovato.",
};

const de: MessageTable = {
  // Common codes (the canonical table is Italian).
  network_error: "Server nicht erreichbar. Prüfe die Verbindung und versuche es erneut.",
  internal_error: "Serverfehler. Bitte versuche es gleich noch einmal.",
  not_found: "Nicht gefunden: vielleicht wurde es gelöscht. Lade die Seite neu.",
  conflict: "Das ist im Moment nicht möglich.",
  invalid_input: "Ungültige Daten.",
  // Chatbot's codes.
  invalid_credentials: "Ungültiger Benutzername oder ungültiges Passwort.",
  username_taken: "Dieser Benutzername ist bereits vergeben.",
  http_429: "Zu viele Anmeldeversuche. Warte eine Minute und versuche es erneut.",
  invalid_token: "Die Sitzung ist nicht mehr gültig. Bitte melde dich erneut an.",
  token_expired: "Die Sitzung ist abgelaufen. Bitte melde dich erneut an.",
  conversation_not_found: "Unterhaltung nicht gefunden: vielleicht wurde sie gelöscht.",
  message_not_found: "Nachricht nicht gefunden: vielleicht wurde sie gelöscht.",
  nothing_to_regenerate: "Es gibt keine Antwort zum Neugenerieren.",
  attachment_too_large: "Die Datei ist zu groß.",
  attachment_not_found: "Anhang nicht gefunden.",
};

export const messageFor: Record<Lang, (error: unknown) => string> = {
  en: makeMessageFor(en),
  it: makeMessageFor(it),
  de: makeMessageFor(de),
};
