from __future__ import annotations

from uuid import UUID

from chatbot.domain.conversation.model import Conversation, ConversationNotFound
from chatbot.domain.conversation.ports.conversation_unit_of_work import (
    ConversationUnitOfWorkFactory,
)


class GetConversationUseCase:
    def __init__(self, uow_factory: ConversationUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, conversation_id: UUID, user_id: UUID) -> Conversation:
        async with self._uow_factory() as uow:
            conv = await uow.conversations.get(conversation_id, user_id)
        if conv is None:
            raise ConversationNotFound(f"conversation {conversation_id} not found")
        return conv
