// UI string catalog. Keep in sync with the backend's supported languages
// (services/conversation/language.py). English is the default and fallback;
// `t()` falls back to the English string for any key missing in it/de.
//
// Values may contain `{name}` placeholders, filled by `t(key, { name })`.

export type Lang = "en" | "it" | "de";

export const LANGUAGES: readonly Lang[] = ["en", "it", "de"] as const;

/** Short label shown in the switcher for each language. */
export const LANGUAGE_LABELS: Record<Lang, string> = {
  en: "EN",
  it: "IT",
  de: "DE",
};

const en = {
  // App shell / top bar
  appName: "Brio",
  toggleConversations: "Toggle conversations",
  logout: "Logout",
  logoutTitle: "Log out",
  greetingTitle: "Hi, I'm Brio — how can I help?",
  greetingSubtitle: "Type a message below to start a new chat.",
  selectLanguage: "Language",
  dismiss: "Dismiss",

  // Auth — tab labels are nouns, distinct from the submit-button verbs below
  // (avoids an ambiguous accessible name between the "Login" tab and "Log in").
  tabLogin: "Login",
  tabRegister: "Register",
  username: "Username",
  password: "Password",
  logIn: "Log in",
  createAccount: "Create account",
  registrationFailed: "Registration failed",
  loginFailed: "Invalid username or password",

  // Conversation list
  newChat: "+ New chat",
  newConversation: "New conversation",
  rename: "Rename",
  delete: "Delete",

  // Composer
  messagePlaceholder: "Type a message…",
  attachFiles: "Attach files",
  toggleWebAccess: "Toggle web access",
  webAccessOn: "Web access: on",
  webAccessOff: "Web access: off",
  toggleThinking: "Toggle thinking",
  thinkingOn: "Thinking: on",
  thinkingOff: "Thinking: off",
  thinkingWebAccessNote: "Thinking is off while web access is on",
  uploading: "Uploading…",
  noText: "· no text",
  attachmentNoTextPending: "Stored, but not visible to the model yet",
  removeAttachment: "Remove {name}",
  send: "Send",
  stop: "■ Stop",

  // Conversation settings
  conversationSettings: "Conversation settings",
  resetToDefaults: "Reset to defaults",
  temperature: "Temperature",
  temperatureDefault: "(default)",
  maxTokens: "Max tokens",
  defaultPlaceholder: "default",
  systemPromptOverride: "System prompt override",
  systemPromptPlaceholder: "Leave empty to use the server default",
  save: "Save",

  // Chat thread
  startConversation: "Start a conversation",
  cancel: "Cancel",
  saveAndSubmit: "Save & submit",
  edit: "Edit",
  retry: "Retry",
  copy: "Copy",
  copied: "Copied ✓",
  downloadAttachment: "Download {name}",
  attachmentNoText: "{name} — stored, but not visible to the model",

  // Thinking block
  thinkingActive: "Thinking…",
  thoughts: "Thoughts",

  // Tool activity
  searching: "Searching: {query}",
  reading: "Reading {host}",
  tool: "Tool",
};

/** The set of translatable keys — every language must be a subset of these. */
export type StringKey = keyof typeof en;

const it: Partial<Record<StringKey, string>> = {
  toggleConversations: "Mostra/nascondi conversazioni",
  logout: "Esci",
  logoutTitle: "Esci",
  greetingTitle: "Ciao, sono Brio — come posso aiutarti?",
  greetingSubtitle: "Scrivi un messaggio qui sotto per iniziare una nuova chat.",
  selectLanguage: "Lingua",
  dismiss: "Chiudi",

  tabLogin: "Accedi",
  tabRegister: "Registrati",
  username: "Nome utente",
  password: "Password",
  logIn: "Accedi",
  createAccount: "Crea account",
  registrationFailed: "Registrazione non riuscita",
  loginFailed: "Nome utente o password non validi",

  newChat: "+ Nuova chat",
  newConversation: "Nuova conversazione",
  rename: "Rinomina",
  delete: "Elimina",

  messagePlaceholder: "Scrivi un messaggio…",
  attachFiles: "Allega file",
  toggleWebAccess: "Attiva/disattiva accesso web",
  webAccessOn: "Accesso web: attivo",
  webAccessOff: "Accesso web: disattivo",
  toggleThinking: "Attiva/disattiva ragionamento",
  thinkingOn: "Ragionamento: attivo",
  thinkingOff: "Ragionamento: disattivo",
  thinkingWebAccessNote:
    "Il ragionamento è disattivato quando l'accesso web è attivo",
  uploading: "Caricamento…",
  noText: "· nessun testo",
  attachmentNoTextPending: "Salvato, ma non ancora visibile al modello",
  removeAttachment: "Rimuovi {name}",
  send: "Invia",
  stop: "■ Ferma",

  conversationSettings: "Impostazioni conversazione",
  resetToDefaults: "Ripristina predefiniti",
  temperature: "Temperatura",
  temperatureDefault: "(predefinita)",
  maxTokens: "Token massimi",
  defaultPlaceholder: "predefinito",
  systemPromptOverride: "Prompt di sistema personalizzato",
  systemPromptPlaceholder: "Lascia vuoto per usare il valore predefinito del server",
  save: "Salva",

  startConversation: "Inizia una conversazione",
  cancel: "Annulla",
  saveAndSubmit: "Salva e invia",
  edit: "Modifica",
  retry: "Riprova",
  copy: "Copia",
  copied: "Copiato ✓",
  downloadAttachment: "Scarica {name}",
  attachmentNoText: "{name} — salvato, ma non visibile al modello",

  thinkingActive: "Sto ragionando…",
  thoughts: "Ragionamento",

  searching: "Ricerca: {query}",
  reading: "Lettura di {host}",
  tool: "Strumento",
};

const de: Partial<Record<StringKey, string>> = {
  toggleConversations: "Unterhaltungen ein-/ausblenden",
  logout: "Abmelden",
  logoutTitle: "Abmelden",
  greetingTitle: "Hi, ich bin Brio — wie kann ich dir helfen?",
  greetingSubtitle: "Schreibe unten eine Nachricht, um einen neuen Chat zu starten.",
  selectLanguage: "Sprache",
  dismiss: "Schließen",

  tabLogin: "Anmelden",
  tabRegister: "Registrieren",
  username: "Benutzername",
  password: "Passwort",
  logIn: "Anmelden",
  createAccount: "Konto erstellen",
  registrationFailed: "Registrierung fehlgeschlagen",
  loginFailed: "Ungültiger Benutzername oder Passwort",

  newChat: "+ Neuer Chat",
  newConversation: "Neue Unterhaltung",
  rename: "Umbenennen",
  delete: "Löschen",

  messagePlaceholder: "Schreibe eine Nachricht…",
  attachFiles: "Dateien anhängen",
  toggleWebAccess: "Webzugriff ein-/ausschalten",
  webAccessOn: "Webzugriff: an",
  webAccessOff: "Webzugriff: aus",
  toggleThinking: "Denken ein-/ausschalten",
  thinkingOn: "Denken: an",
  thinkingOff: "Denken: aus",
  thinkingWebAccessNote: "Denken ist aus, solange der Webzugriff aktiv ist",
  uploading: "Wird hochgeladen…",
  noText: "· kein Text",
  attachmentNoTextPending: "Gespeichert, aber für das Modell noch nicht sichtbar",
  removeAttachment: "{name} entfernen",
  send: "Senden",
  stop: "■ Stopp",

  conversationSettings: "Unterhaltungseinstellungen",
  resetToDefaults: "Auf Standard zurücksetzen",
  temperature: "Temperatur",
  temperatureDefault: "(Standard)",
  maxTokens: "Max. Tokens",
  defaultPlaceholder: "Standard",
  systemPromptOverride: "System-Prompt überschreiben",
  systemPromptPlaceholder: "Leer lassen, um den Server-Standard zu verwenden",
  save: "Speichern",

  startConversation: "Beginne eine Unterhaltung",
  cancel: "Abbrechen",
  saveAndSubmit: "Speichern & senden",
  edit: "Bearbeiten",
  retry: "Wiederholen",
  copy: "Kopieren",
  copied: "Kopiert ✓",
  downloadAttachment: "{name} herunterladen",
  attachmentNoText: "{name} — gespeichert, aber für das Modell nicht sichtbar",

  thinkingActive: "Denke nach…",
  thoughts: "Gedanken",

  searching: "Suche: {query}",
  reading: "Lese {host}",
  tool: "Werkzeug",
};

export const translations: Record<Lang, Partial<Record<StringKey, string>>> = {
  en,
  it,
  de,
};

/**
 * Whimsical "still thinking" verbs cycled while reasoning streams (Claude-Code
 * style) so the wait feels less static. The first entry matches `thinkingActive`
 * and is the fallback if the list is somehow empty. Ellipsis is added by the UI.
 */
export const THINKING_VERBS: Record<Lang, readonly string[]> = {
  en: [
    "Thinking",
    "Pondering",
    "Musing",
    "Ruminating",
    "Noodling",
    "Percolating",
    "Mulling",
    "Cogitating",
    "Contemplating",
    "Deliberating",
  ],
  it: [
    "Sto ragionando",
    "Rifletto",
    "Pondero",
    "Medito",
    "Elaboro",
    "Ci penso su",
    "Considero",
    "Rimugino",
  ],
  de: [
    "Denke nach",
    "Überlege",
    "Grüble",
    "Sinniere",
    "Erwäge",
    "Knoble",
    "Reflektiere",
    "Tüftle",
  ],
};

/** Fill `{name}` placeholders from `vars`; unknown placeholders are left as-is. */
export function interpolate(
  template: string,
  vars?: Record<string, string | number>
): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m));
}

/** Resolve a key for a language, falling back to English then the key itself. */
export function translate(
  lang: Lang,
  key: StringKey,
  vars?: Record<string, string | number>
): string {
  const template = translations[lang][key] ?? translations.en[key] ?? key;
  return interpolate(template, vars);
}
