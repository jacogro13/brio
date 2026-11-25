from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field, NonNegativeInt, PositiveInt, StringConstraints

from chatbot.domain.errors import Conflict, NotFound, PayloadTooLarge
from chatbot.domain.validated import Validated

Role = Literal["user", "assistant"]

Filename = Annotated[str, StringConstraints(min_length=1)]
"""Non-empty; kept as uploaded (not stripped), since the storage key embeds it."""

Temperature = Annotated[float, Field(ge=0, le=2)]
"""Sampling temperature override, as the settings popover allows (0–2)."""

MaxTokens = PositiveInt


class ConversationNotFound(NotFound):
    """No such conversation for this user (another user's reads as missing)."""

    code = "conversation_not_found"


class MessageNotFound(NotFound):
    code = "message_not_found"


class AttachmentNotFound(NotFound):
    code = "attachment_not_found"


class NothingToRegenerate(Conflict):
    """Regenerate needs a user message to answer again."""

    code = "nothing_to_regenerate"


class AttachmentTooLarge(PayloadTooLarge):
    code = "attachment_too_large"


@dataclass
class Attachment(Validated):
    """A file uploaded to a conversation and stored in object storage (Garage).

    Uploaded in a two-step flow: ``message_id`` is ``None`` while pending (after
    upload, before the message it belongs to is sent) and is set when the user
    message linking it is persisted. ``extracted_text`` holds the model-visible
    text lifted at upload time (``None`` for images and anything unextractable —
    the blob is still stored, just not shown to the LLM). ``s3_key`` is the
    object-storage key under the ``conversations/{cid}/{id}/`` prefix.
    """

    id: UUID
    conversation_id: UUID
    filename: Filename
    content_type: str
    size: NonNegativeInt
    s3_key: str
    created_at: datetime
    message_id: UUID | None = None
    extracted_text: str | None = None


@dataclass
class ToolResult(Validated):
    """One search hit shown under a tool chip."""

    title: str
    url: str


@dataclass
class ToolEvent(Validated):
    """One web-access tool call (Phase 6), persisted on the assistant message so
    the UI chips re-render on reload. ``query`` is set for ``web_search``,
    ``url`` for ``fetch_page``; ``ok``/``summary``/``results`` are missing when
    the reply was stopped before the tool finished."""

    id: int
    tool: str
    query: str | None = None
    url: str | None = None
    ok: bool | None = None
    summary: str | None = None
    results: list[ToolResult] | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ToolEvent:
        """Build from the stored/streamed JSON record (unknown keys ignored)."""
        results = data.get("results")
        return cls(
            id=data["id"],
            tool=data["tool"],
            query=data.get("query"),
            url=data.get("url"),
            ok=data.get("ok"),
            summary=data.get("summary"),
            results=(
                None
                if results is None
                else [ToolResult(title=r["title"], url=r["url"]) for r in results]
            ),
        )

    def to_json(self) -> dict[str, Any]:
        """The JSON record, without the keys that are not set (as stored today)."""
        data: dict[str, Any] = {"id": self.id, "tool": self.tool}
        for key in ("query", "url", "ok", "summary"):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        if self.results is not None:
            data["results"] = [{"title": r.title, "url": r.url} for r in self.results]
        return data


@dataclass
class Message(Validated):
    id: UUID
    role: Role
    content: str
    created_at: datetime
    thinking: str | None = None
    attachments: list[Attachment] = field(default_factory=list)
    # Web-access tool activity (Phase 6), assistant-only. One record per tool
    # call (``id``, ``tool``, ``query``/``url``, ``ok``, ``summary``, ``results``)
    # so the UI chips re-render on reload. ``None`` when no tools ran. Never
    # replayed to the LLM as history.
    tool_events: list[ToolEvent] | None = None


@dataclass
class Conversation(Validated):
    id: UUID
    title: str | None
    messages: list[Message]
    created_at: datetime
    # Owning user (Phase 7). ``None`` only for legacy rows created before
    # multiuser; the first registered user adopts them (``claim_orphans``).
    user_id: UUID | None = None
    # Per-conversation LLM overrides. ``None`` means "use the server default"
    # (never conflate with ``0`` / ``False``). Resolved at stream time.
    # (Thinking is a per-message toggle sent on each turn — not stored here.)
    temperature: Temperature | None = None
    max_tokens: MaxTokens | None = None
    system_prompt_override: str | None = None

    def add_message(self, message: Message) -> None:
        if self.title is None and message.role == "user":
            self.title = message.content[:60]
        self.messages.append(message)
