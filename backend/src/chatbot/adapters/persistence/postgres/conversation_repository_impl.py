from __future__ import annotations

from uuid import UUID

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

from chatbot.adapters.persistence.postgres.orm import (
    attachments,
    conversations,
    mapped_attribute,
    messages,
    set_conversation_id,
)
from chatbot.domain.conversation.model import Attachment, Conversation, Message
from chatbot.domain.conversation.ports.conversation_repository import AbstractConversationRepository


class PostgresConversationRepository(AbstractConversationRepository):
    """Loads and saves the mapped domain entities themselves (see `orm.py`).

    Relationships are `lazy="raise"`, so every read states what it loads.
    Reads use `populate_existing` so an entity already in the session is
    refreshed from the database rather than returned stale. Bulk deletes and
    `claim_orphans` are single Core statements on the tables.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: UUID, user_id: UUID) -> Conversation | None:
        result = await self._session.execute(
            select(Conversation)
            .where(conversations.c.id == id, conversations.c.user_id == user_id)
            .options(
                selectinload(mapped_attribute(Conversation, "messages")).selectinload(
                    mapped_attribute(Message, "attachments")
                )
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list(self, user_id: UUID) -> list[Conversation]:
        result = await self._session.execute(
            select(Conversation)
            .where(conversations.c.user_id == user_id)
            .order_by(conversations.c.created_at.desc())
            .options(noload(mapped_attribute(Conversation, "messages")))
            .execution_options(populate_existing=True)
        )
        return list(result.scalars())

    async def add(self, conversation: Conversation) -> None:
        self._session.add(conversation)
        await self._session.flush()

    async def claim_orphans(self, user_id: UUID) -> int:
        result = await self._session.execute(
            update(conversations).where(conversations.c.user_id.is_(None)).values(user_id=user_id)
        )
        await self._session.flush()
        assert isinstance(result, CursorResult)  # an UPDATE always returns one
        return result.rowcount or 0

    async def delete(self, id: UUID, user_id: UUID) -> None:
        await self._session.execute(
            delete(conversations).where(
                conversations.c.id == id,
                conversations.c.user_id == user_id,
            )
        )
        await self._session.flush()

    async def save_message(self, message: Message, conversation_id: UUID) -> None:
        # `Message` doesn't know its conversation; the mapping keeps the FK on
        # a private attribute (see `orm.start_mappers`).
        set_conversation_id(message, conversation_id)
        self._session.add(message)
        await self._session.flush()

    async def delete_messages(self, conversation_id: UUID, message_ids: list[UUID]) -> None:
        if not message_ids:
            return
        await self._session.execute(
            delete(messages).where(
                messages.c.conversation_id == conversation_id,
                messages.c.id.in_(message_ids),
            )
        )
        await self._session.flush()

    async def update_title(self, conversation_id: UUID, title: str) -> None:
        conversation = await self._session.get(Conversation, conversation_id)
        if conversation:
            conversation.title = title
            await self._session.flush()

    async def update_settings(self, conversation_id: UUID, updates: dict) -> None:
        if not updates:
            return
        conversation = await self._session.get(Conversation, conversation_id)
        if conversation:
            # Only the explicitly-provided keys are set; an explicit ``None``
            # resets that override back to the server default.
            for key, value in updates.items():
                setattr(conversation, key, value)
            await self._session.flush()

    async def add_attachment(self, attachment: Attachment) -> None:
        self._session.add(attachment)
        await self._session.flush()

    async def get_attachment(self, attachment_id: UUID) -> Attachment | None:
        result = await self._session.execute(
            select(Attachment)
            .where(attachments.c.id == attachment_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def link_attachments(
        self, conversation_id: UUID, message_id: UUID, attachment_ids: list[UUID]
    ) -> list[Attachment]:
        if not attachment_ids:
            return []
        result = await self._session.execute(
            select(Attachment).where(
                attachments.c.conversation_id == conversation_id,
                attachments.c.message_id.is_(None),
                attachments.c.id.in_(attachment_ids),
            )
        )
        linked = list(result.scalars())
        for attachment in linked:
            attachment.message_id = message_id
        await self._session.flush()
        return linked
