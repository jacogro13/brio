from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from chatbot.domain.conversation.model import Attachment, Conversation, Message


class AbstractConversationRepository(ABC):
    @abstractmethod
    async def get(self, id: UUID, user_id: UUID) -> Conversation | None:
        """Scoped fetch — returns ``None`` when the conversation does not exist
        *or* belongs to another user (cross-user access reads as 404)."""
        ...

    @abstractmethod
    async def list(self, user_id: UUID) -> list[Conversation]: ...

    @abstractmethod
    async def add(self, conversation: Conversation) -> None: ...

    @abstractmethod
    async def claim_orphans(self, user_id: UUID) -> int:
        """Assign every ownerless (``user_id IS NULL``) conversation to
        ``user_id``. Used once, when the first user registers, to adopt legacy
        rows. Returns the number of conversations claimed."""
        ...

    @abstractmethod
    async def save_message(self, message: Message, conversation_id: UUID) -> None: ...

    @abstractmethod
    async def delete_messages(self, conversation_id: UUID, message_ids: list[UUID]) -> None: ...

    @abstractmethod
    async def update_title(self, conversation_id: UUID, title: str) -> None: ...

    @abstractmethod
    async def update_settings(self, conversation_id: UUID, updates: dict) -> None: ...

    @abstractmethod
    async def delete(self, id: UUID, user_id: UUID) -> None: ...

    @abstractmethod
    async def add_attachment(self, attachment: Attachment) -> None: ...

    @abstractmethod
    async def get_attachment(self, attachment_id: UUID) -> Attachment | None: ...

    @abstractmethod
    async def link_attachments(
        self, conversation_id: UUID, message_id: UUID, attachment_ids: list[UUID]
    ) -> list[Attachment]:
        """Attach the pending (``message_id IS NULL``) uploads with these ids to
        ``message_id``. Only attachments belonging to ``conversation_id`` are
        touched; returns the linked attachments (for history injection)."""
        ...
