from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from chatbot.domain.conversation.model import (
    Attachment,
    AttachmentTooLarge,
    ConversationNotFound,
)
from chatbot.domain.conversation.ports.attachment_storage import AbstractAttachmentStorage
from chatbot.domain.conversation.ports.conversation_unit_of_work import (
    ConversationUnitOfWorkFactory,
)
from chatbot.domain.conversation.ports.text_extractor import AbstractTextExtractor


class UploadAttachmentUseCase:
    """Two-step upload, step 1: store the blob in object storage, extract its
    text, and persist a *pending* attachment row (``message_id`` NULL). It is
    linked to a message later, at send time (``SendMessageUseCase``)."""

    def __init__(
        self,
        uow_factory: ConversationUnitOfWorkFactory,
        storage: AbstractAttachmentStorage,
        extractor: AbstractTextExtractor,
        max_bytes: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._storage = storage
        self._extractor = extractor
        self._max_bytes = max_bytes

    async def execute(
        self,
        conversation_id: UUID,
        user_id: UUID,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> Attachment:
        if len(data) > self._max_bytes:
            raise AttachmentTooLarge(f"attachment exceeds {self._max_bytes} bytes", field="file")

        async with self._uow_factory() as uow:
            conv = await uow.conversations.get(conversation_id, user_id)
            if conv is None:
                raise ConversationNotFound(f"conversation {conversation_id} not found")

        attachment_id = uuid4()
        s3_key = f"conversations/{conversation_id}/{attachment_id}/{filename}"
        await self._storage.upload_file(s3_key, data, content_type)
        extracted_text = await self._extractor.extract(filename, content_type, data)

        attachment = Attachment(
            id=attachment_id,
            conversation_id=conversation_id,
            message_id=None,
            filename=filename,
            content_type=content_type,
            size=len(data),
            s3_key=s3_key,
            extracted_text=extracted_text,
            created_at=datetime.now(tz=UTC),
        )
        async with self._uow_factory() as uow:
            await uow.conversations.add_attachment(attachment)
        return attachment
