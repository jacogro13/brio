import { describe, expect, test } from "vitest";
import type { Lang } from "../i18n/strings";
import { ApiError } from "./client";
import { messageFor } from "./errors";
import { FALLBACK_MESSAGE } from "./messages";

const LANGS: Lang[] = ["en", "it", "de"];

function apiError(code: string, message = "server text"): ApiError {
  return new ApiError(400, code, null, message, null);
}

describe("messageFor", () => {
  test.each([
    ["en", "invalid_credentials", "Invalid username or password."],
    ["en", "username_taken", "This username is already taken."],
    ["en", "attachment_too_large", "The file is too large."],
    ["en", "network_error", "Can't reach the server. Check your connection and try again."],
    ["it", "invalid_credentials", "Nome utente o password non validi."],
    ["it", "username_taken", "Questo nome utente è già in uso."],
    ["it", "attachment_too_large", "Il file è troppo grande."],
    ["it", "network_error", "Server non raggiungibile. Controlla la connessione e riprova."],
    ["de", "invalid_credentials", "Ungültiger Benutzername oder ungültiges Passwort."],
    ["de", "username_taken", "Dieser Benutzername ist bereits vergeben."],
    ["de", "attachment_too_large", "Die Datei ist zu groß."],
    ["de", "network_error", "Server nicht erreichbar. Prüfe die Verbindung und versuche es erneut."],
  ] as const)("%s: %s gives that language's text", (lang, code, expected) => {
    const error = apiError(code);

    const text = messageFor[lang](error);

    expect(text).toBe(expected);
  });

  test.each(LANGS)("%s: unknown code gives the fallback", (lang) => {
    const error = apiError("something_new");

    const text = messageFor[lang](error);

    expect(text).toBe(FALLBACK_MESSAGE);
  });

  test.each(LANGS)("%s: never shows the backend message", (lang) => {
    const error = apiError("something_new", "Secret server detail");

    const text = messageFor[lang](error);

    expect(text).not.toContain("Secret server detail");
  });

  test("english invalid_credentials keeps the wording e2e matches", () => {
    const error = apiError("invalid_credentials");

    const text = messageFor.en(error);

    expect(text).toMatch(/invalid username or password/i);
  });
});
