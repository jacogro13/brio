from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import aclosing
from uuid import UUID

from chatbot.domain.conversation.model import ConversationNotFound, NothingToRegenerate
from chatbot.domain.conversation.ports.chat_llm import ChatLLM
from chatbot.domain.conversation.ports.conversation_unit_of_work import (
    ConversationUnitOfWorkFactory,
)
from chatbot.services.conversation._streaming import (
    build_history,
    error_event,
    resolve_chat_config,
    stream_and_persist,
)


class RegenerateMessageUseCase:
    def __init__(
        self,
        uow_factory: ConversationUnitOfWorkFactory,
        llm: ChatLLM,
        system_prompt: str,
        enable_thinking: bool = False,
    ) -> None:
        self._uow_factory = uow_factory
        self._llm = llm
        self._default_system_prompt = system_prompt
        self._default_enable_thinking = enable_thinking

    async def stream(
        self,
        conversation_id: UUID,
        user_id: UUID,
        enable_thinking: bool | None = None,
        language: str = "en",
    ) -> AsyncGenerator[dict]:
        # 1. Drop the trailing assistant message(s), rebuild history up to the
        #    last user turn. Delete by explicit id list (never `created_at >=`).
        async with self._uow_factory() as uow:
            conv = await uow.conversations.get(conversation_id, user_id)
            if conv is None:
                yield error_event(ConversationNotFound("conversation not found"))
                return
            messages = conv.messages
            cut = len(messages)
            while cut > 0 and messages[cut - 1].role == "assistant":
                cut -= 1
            remaining = messages[:cut]
            if not remaining:
                yield error_event(NothingToRegenerate("nothing to regenerate"))
                return
            trailing_ids = [m.id for m in messages[cut:]]
            await uow.conversations.delete_messages(conversation_id, trailing_ids)
            history = build_history(remaining)
            system_prompt, params = resolve_chat_config(
                conv,
                self._default_system_prompt,
                self._default_enable_thinking,
                enable_thinking,
                language,
            )

        # 2. Stream tokens + persist the new assistant reply (aclosing → the
        #    finally-persist survives a client disconnect mid-stream).
        async with aclosing(
            stream_and_persist(
                self._uow_factory,
                self._llm,
                system_prompt,
                params,
                conversation_id,
                history,
            )
        ) as events:
            async for event in events:
                yield event
