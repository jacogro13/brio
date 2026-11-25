from __future__ import annotations

from uuid import UUID

from chatbot.domain.conversation.model import (
    Attachment,
    AttachmentNotFound,
    ConversationNotFound,
)
from chatbot.domain.conversation.ports.attachment_storage import AbstractAttachmentStorage
from chatbot.domain.conversation.ports.conversation_unit_of_work import (
    ConversationUnitOfWorkFactory,
)


class DownloadAttachmentUseCase:
    """Stream an attachment's bytes back through the backend (no presigned URLs —
    the browser can't reach Garage in prod). Raises ``AttachmentNotFound`` if the
    attachment doesn't exist or doesn't belong to the given conversation."""

    def __init__(
        self,
        uow_factory: ConversationUnitOfWorkFactory,
        storage: AbstractAttachmentStorage,
    ) -> None:
        self._uow_factory = uow_factory
        self._storage = storage

    async def execute(
        self, conversation_id: UUID, user_id: UUID, attachment_id: UUID
    ) -> tuple[Attachment, bytes]:
        async with self._uow_factory() as uow:
            # Ownership check: a scoped get returns None for another user's (or a
            # missing) conversation, so cross-user downloads read as 404.
            conv = await uow.conversations.get(conversation_id, user_id)
            if conv is None:
                raise ConversationNotFound(f"conversation {conversation_id} not found")
            attachment = await uow.conversations.get_attachment(attachment_id)
        if attachment is None or attachment.conversation_id != conversation_id:
            raise AttachmentNotFound(f"attachment {attachment_id} not found")
        data = await self._storage.get_file(attachment.s3_key)
        return attachment, data
