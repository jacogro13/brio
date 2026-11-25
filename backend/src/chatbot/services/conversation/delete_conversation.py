from __future__ import annotations

import logging
from uuid import UUID

from chatbot.domain.conversation.ports.attachment_storage import AbstractAttachmentStorage
from chatbot.domain.conversation.ports.conversation_unit_of_work import (
    ConversationUnitOfWorkFactory,
)

logger = logging.getLogger(__name__)


class DeleteConversationUseCase:
    def __init__(
        self,
        uow_factory: ConversationUnitOfWorkFactory,
        storage: AbstractAttachmentStorage,
    ) -> None:
        self._uow_factory = uow_factory
        self._storage = storage

    async def execute(self, conversation_id: UUID, user_id: UUID) -> None:
        async with self._uow_factory() as uow:
            await uow.conversations.delete(conversation_id, user_id)
        # Best-effort: attachment rows are already gone (FK cascade); wipe the
        # conversation's blobs from object storage. A storage error must not fail
        # the delete — the DB is the source of truth.
        try:
            await self._storage.delete_prefix(f"conversations/{conversation_id}/")
        except Exception:
            logger.warning(
                "Failed to delete storage blobs for conversation %s",
                conversation_id,
                exc_info=True,
            )
