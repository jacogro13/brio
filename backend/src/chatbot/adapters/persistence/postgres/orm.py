"""Imperative (classical) mapping of the domain entities onto tables.

The domain classes stay plain dataclasses; `start_mappers()` instruments them
once per process (FastAPI `lifespan`, the CLI, tests). Repositories then load
and save the entities themselves — there are no separate ORM model classes.

Relationships are `lazy="raise"`: every query says what it loads
(`selectinload` / `noload`), so a forgotten load fails loudly in tests instead
of as an async `MissingGreenlet` in production.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Dialect,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Uuid,
)
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.orm import QueryableAttribute, registry, relationship
from sqlalchemy.types import TypeDecorator

from chatbot.domain.conversation.model import Attachment, Conversation, Message, ToolEvent
from chatbot.domain.user.model import User

mapper_registry = registry()
metadata = mapper_registry.metadata


class ToolEventList(TypeDecorator[list[ToolEvent]]):
    """`list[ToolEvent]` stored as the JSONB array of records it always was."""

    impl = JSONB
    cache_ok = True

    def process_bind_param(
        self, value: list[ToolEvent] | None, dialect: Dialect
    ) -> list[dict[str, Any]] | None:
        if value is None:
            return None
        return [event.to_json() for event in value]

    def process_result_value(
        self, value: list[dict[str, Any]] | None, dialect: Dialect
    ) -> list[ToolEvent] | None:
        if value is None:
            return None
        return [ToolEvent.from_json(record) for record in value]


users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("username", String, unique=True, nullable=False, index=True),
    Column("hashed_password", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    # UI + assistant reply language ('en' | 'it' | 'de'); server default 'en'.
    Column("language", String, nullable=False, server_default="en"),
)

conversations = Table(
    "conversations",
    metadata,
    Column("id", Uuid, primary_key=True),
    # Owning user — nullable for legacy rows adopted at first register.
    Column(
        "user_id",
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    ),
    Column("title", String, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    # Per-conversation LLM overrides — NULL = use the server default.
    Column("temperature", Float, nullable=True),
    Column("max_tokens", Integer, nullable=True),
    Column("system_prompt_override", String, nullable=True),
)

messages = Table(
    "messages",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "conversation_id",
        Uuid,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("role", String, nullable=False),
    Column("content", String, nullable=False),
    Column("thinking", String, nullable=True),
    # Web-access tool activity — list of per-call records; NULL if none.
    Column("tool_events", ToolEventList, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

attachments = Table(
    "attachments",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "conversation_id",
        Uuid,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    # NULL while the upload is pending (uploaded but not yet sent with a message).
    Column(
        "message_id",
        Uuid,
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    ),
    Column("filename", String, nullable=False),
    Column("content_type", String, nullable=False),
    Column("size", BigInteger, nullable=False),
    Column("s3_key", String, nullable=False),
    Column("extracted_text", String, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def start_mappers() -> None:
    """Map the domain classes onto the tables. Idempotent — safe to re-call."""
    try:
        sa_inspect(User)
        return
    except NoInspectionAvailable:
        pass

    mapper_registry.map_imperatively(User, users)
    mapper_registry.map_imperatively(Attachment, attachments)
    mapper_registry.map_imperatively(
        Message,
        messages,
        properties={
            # `Message` doesn't know its conversation; the repository sets this
            # private attribute before adding it (`Validated` ignores `_` names).
            "_conversation_id": messages.c.conversation_id,
            "attachments": relationship(
                Attachment,
                order_by=attachments.c.created_at,
                lazy="raise",
                passive_deletes=True,
            ),
        },
    )
    mapper_registry.map_imperatively(
        Conversation,
        conversations,
        properties={
            "messages": relationship(
                Message,
                order_by=messages.c.created_at,
                lazy="raise",
                passive_deletes=True,
            ),
        },
    )


def mapped_attribute(cls: type, name: str) -> QueryableAttribute[Any]:
    """The instrumented attribute for a mapped field, typed for loader options
    (the dataclass annotations make `Conversation.messages` look like a list)."""
    return sa_inspect(cls).attrs[name].class_attribute


def set_conversation_id(message: Message, conversation_id: UUID) -> None:
    """Set the FK `Message` doesn't model, through the mapped `_conversation_id`."""
    mapped_attribute(Message, "_conversation_id").__set__(message, conversation_id)
