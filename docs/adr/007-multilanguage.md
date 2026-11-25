# ADR-007: Per-user multilanguage (EN / IT / DE)

**Status**: Accepted
**Date**: 2026-07-15

## Context

The app shipped English-only UI text and an English default system prompt, but
its users are Italian- and German-speaking. "Multilanguage" has two independent
dimensions: the **UI chrome** (buttons, labels, placeholders) and the
**assistant's reply language**. Multiuser auth (ADR-006) already gives us a
natural place to hang a per-account preference, so the choice can follow a person
across devices rather than living only in one browser.

## Decision

**One per-user language preference (`users.language` ∈ {`en`,`it`,`de`}, default
`en`) drives both the UI and the assistant.** English is the fallback everywhere.

- **Assistant language is a system-prompt directive, resolved per request.**
  `services/conversation/language.py::apply_language` appends a short instruction
  (`it` → "Rispondi sempre in italiano.", `de` → "Antworte immer auf Deutsch.",
  `en` → nothing) to the resolved prompt inside `resolve_chat_config`. It is
  appended **after** any per-conversation `system_prompt_override`, so a custom
  persona still wins on tone while the language is honored. The API resolves the
  acting user's language via a `get_current_language` dependency (loads it fresh
  from the DB, since the JWT is not re-minted on change) and threads it into the
  send/regenerate/edit use cases. The CLI reads `CHATBOT_LANGUAGE` (default `en`).

- **Profile endpoints are the source of truth.** `GET /auth/me` returns
  `{username, language}`; `PATCH /auth/me {language}` validates against the
  `Literal["en","it","de"]` (automatic 422) and persists. `POST /auth/register`
  accepts an optional `language` so a new account adopts the browser-detected
  language chosen on the auth page.

- **Frontend i18n is a tiny homegrown layer, no new dependency.** A typed string
  catalog (`i18n/strings.ts`, EN/IT/DE with `{name}` interpolation and English
  fallback) plus a `LanguageProvider` + `useT()` hook. Initial language:
  localStorage cache → `navigator.language` → `en`; after auth, `GET /auth/me`
  overrides it (`syncLanguage`, no re-persist). A user change updates the UI,
  caches locally, and — when signed in — `PATCH`es the server.

## Consequences

- A missing key in `it`/`de` silently falls back to English, so the app is never
  broken by an untranslated string; new UI strings only *need* an English entry.
- Errors are shown from their stable `code`, never from the server's text
  (work item 005): `frontend/src/api/errors.ts` builds one `messageFor` per
  language (EN/IT/DE) on the canonical `makeMessageFor`. An unknown code gives
  the canonical Italian fallback in every language, and upload/download/stream
  failures are only logged, not shown yet (006).
- e2e users default to English, so the existing black-box specs keep asserting
  English text; `i18n.spec.ts` covers the switch + server persistence.
