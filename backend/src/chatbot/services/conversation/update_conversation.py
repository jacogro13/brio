from __future__ import annotations

from uuid import UUID

from chatbot.domain.conversation.model import Conversation, ConversationNotFound
from chatbot.domain.conversation.ports.conversation_unit_of_work import (
    ConversationUnitOfWorkFactory,
)

# Fields a client may set via a partial update. ``title`` is folded in here so
# rename and the per-conversation settings share one use case and one route.
_ALLOWED_FIELDS = frozenset(
    {
        "title",
        "temperature",
        "max_tokens",
        "system_prompt_override",
    }
)


class UpdateConversationUseCase:
    """Partial update of a conversation's title and per-conversation settings.

    ``updates`` carries only the explicitly-provided keys (the router derives it
    from the request with ``exclude_unset``); an explicit ``None`` resets that
    setting to the server default. Unknown keys are ignored.
    """

    def __init__(self, uow_factory: ConversationUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, conversation_id: UUID, user_id: UUID, updates: dict) -> Conversation:
        clean = {k: v for k, v in updates.items() if k in _ALLOWED_FIELDS}
        async with self._uow_factory() as uow:
            conv = await uow.conversations.get(conversation_id, user_id)
            if conv is None:
                raise ConversationNotFound(f"conversation {conversation_id} not found")
            await uow.conversations.update_settings(conversation_id, clean)
            for key, value in clean.items():
                setattr(conv, key, value)
            return conv
