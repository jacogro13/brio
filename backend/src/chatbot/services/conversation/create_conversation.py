from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from chatbot.domain.conversation.model import Conversation
from chatbot.domain.conversation.ports.conversation_unit_of_work import (
    ConversationUnitOfWorkFactory,
)


class CreateConversationUseCase:
    def __init__(self, uow_factory: ConversationUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, user_id: UUID) -> Conversation:
        conversation = Conversation(
            id=uuid4(),
            title=None,
            messages=[],
            created_at=datetime.now(tz=UTC),
            user_id=user_id,
        )
        async with self._uow_factory() as uow:
            await uow.conversations.add(conversation)
        return conversation
