from __future__ import annotations

from uuid import UUID

from chatbot.domain.conversation.model import Conversation
from chatbot.domain.conversation.ports.conversation_unit_of_work import (
    ConversationUnitOfWorkFactory,
)


class ListConversationsUseCase:
    def __init__(self, uow_factory: ConversationUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, user_id: UUID) -> list[Conversation]:
        async with self._uow_factory() as uow:
            return await uow.conversations.list(user_id)
