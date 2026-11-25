# ADR-004: File attachments in Garage

**Status**: Accepted
**Date**: 2026-07-13

## Context

Phase 5 of the Claude.ai-like upgrade adds file uploads: a user attaches
text/code/markdown/PDF/image files to a conversation, and the model sees the
extracted text of the readable ones. Files can be large and binary, so they do
not belong in Postgres; the fleet already runs a shared, S3-compatible **Garage**
object store (managed by `Infrastructure/`, used by Blibiobot and Pasti), so
Chatbot reuses it rather than inventing new storage.

Two forces shaped the design:

- **Upload happens before the message is sent.** The composer lets you stage
  several files, edit the text, then send — so an attachment must exist
  (uploaded, text extracted) while still *pending*, unattached to any message.
- **The browser cannot reach Garage in production.** Garage is bound to
  `shared_network` / localhost on the mini-PC and is not LAN-exposed, so
  presigned URLs handed to the browser would be unreachable.

## Decision

**Two-step upload.** `POST /conversations/{id}/attachments` (multipart) uploads
the blob to Garage, extracts its text *immediately*, and persists an
`attachments` row with `message_id` NULL (pending) and `conversation_id` NOT
NULL. `SendMessageRequest.attachment_ids` then links the pending rows to the
user message at send time (`link_attachments` sets `message_id`, scoped to the
conversation so a foreign id is ignored).

**Storage is a port.** `domain/conversation/ports/attachment_storage.py`
(`upload_file` / `get_file` / `delete_prefix`); the Garage adapter
(`adapters/storage/garage/`) copies Blibiobot's shape verbatim — boto3 behind
`functools.partial` + `anyio.to_thread.run_sync` so no S3 call blocks the event
loop. Keys are `conversations/{cid}/{attachment_id}/{filename}`, so a
conversation's blobs share the `conversations/{cid}/` prefix and
`delete_conversation` wipes them with one best-effort `delete_prefix` after the
DB delete (attachment rows go via FK cascade; the DB is the source of truth, so a
storage error only warns). When `GARAGE_ENDPOINT` is unset the wiring falls back
to an in-memory `NullAttachmentStorage` (mirrors the LLM mock fallback), so local
dev and unit tests need no Garage.

**Extraction is a port too.** `text_extractor.py` +
`adapters/extraction/text_extraction.py`: text/code/markdown decoded as UTF-8
(latin-1 fallback), PDF via `pypdf`, images → `extracted_text` NULL (stored, but
flagged "not visible to the model"). It never raises — a failed parse returns
NULL — and truncates to `ATTACHMENT_MAX_EXTRACTED_CHARS` (40k) to bound the LLM
context. Uploads over `ATTACHMENT_MAX_BYTES` (10 MB) are rejected with 413.

**History injection is a pure function.** `_streaming.py::render_user_content`
inlines `[Attached file: {name}]\n{extracted_text}` after a user turn's text;
`build_history` applies it to every historical user message. The persisted
`Message.content` stays the raw user text — only the LLM history is augmented,
and `extracted_text` NULL attachments contribute a "no extractable text" note
rather than bytes.

**Downloads stream through the backend.** `GET
/conversations/{cid}/attachments/{id}` fetches from Garage and returns the bytes
with a `Content-Disposition` — no presigned URLs, so the browser only ever talks
to the api.

## Consequences

- New migration `0004`: `attachments(id, conversation_id FK cascade,
  message_id FK cascade NULL, filename, content_type, size, s3_key,
  extracted_text NULL, created_at)` + indexes on both FKs.
- In **dev/e2e** each app runs its own isolated Garage container (host port
  3907; e2e `!reset`s it); in **production** Chatbot uses the **shared** Garage
  (`shared_garage` on `shared_network`) reached via the `garage` service alias —
  never `shared_garage`, whose underscore breaks botocore endpoint validation.
  `chatbot` must be added to `GARAGE_BUCKETS` in Infrastructure's `.env` and
  `garage_init` re-run once before the first prod deploy.
- Images are stored but not model-visible; a future vision-model phase can start
  reading them without a schema change.
- Edit drops a message's attachments (FK cascade on the deleted user message);
  edit is text-only in this phase.
