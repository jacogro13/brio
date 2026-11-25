from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import aclosing
from datetime import UTC, datetime
from uuid import UUID, uuid4

from chatbot.domain.conversation.model import ConversationNotFound, Message, MessageNotFound
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


class EditMessageUseCase:
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
        message_id: UUID,
        new_content: str,
        enable_thinking: bool | None = None,
        language: str = "en",
    ) -> AsyncGenerator[dict]:
        # 1. Delete the target user message + everything after it, save the
        #    edited user message, rebuild history. Delete by explicit id list.
        async with self._uow_factory() as uow:
            conv = await uow.conversations.get(conversation_id, user_id)
            if conv is None:
                yield error_event(ConversationNotFound("conversation not found"))
                return
            messages = conv.messages
            idx = next((i for i, m in enumerate(messages) if m.id == message_id), None)
            if idx is None or messages[idx].role != "user":
                yield error_event(MessageNotFound("message not found"))
                return
            to_delete = [m.id for m in messages[idx:]]
            await uow.conversations.delete_messages(conversation_id, to_delete)
            new_user_msg = Message(
                id=uuid4(),
                role="user",
                content=new_content,
                created_at=datetime.now(tz=UTC),
            )
            await uow.conversations.save_message(new_user_msg, conversation_id)
            history = build_history(messages[:idx]) + [{"role": "user", "content": new_content}]
            system_prompt, params = resolve_chat_config(
                conv,
                self._default_system_prompt,
                self._default_enable_thinking,
                enable_thinking,
                language,
            )

        # 2. Stream tokens + persist the assistant reply (aclosing → the
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
