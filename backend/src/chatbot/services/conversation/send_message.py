from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import aclosing
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from chatbot.domain.conversation.model import ConversationNotFound, Message
from chatbot.domain.conversation.ports.chat_llm import ChatLLM
from chatbot.domain.conversation.ports.conversation_unit_of_work import (
    ConversationUnitOfWorkFactory,
)
from chatbot.domain.conversation.ports.web_tools import PageFetcher, WebSearch
from chatbot.services.conversation._streaming import (
    build_history,
    error_event,
    render_user_content,
    resolve_chat_config,
    stream_and_persist,
)
from chatbot.services.conversation.tool_loop import WebTools


class SendMessageUseCase:
    def __init__(
        self,
        uow_factory: ConversationUnitOfWorkFactory,
        llm: ChatLLM,
        system_prompt: str,
        enable_thinking: bool = False,
        web_search: WebSearch | None = None,
        page_fetcher: PageFetcher | None = None,
        web_tool_max_iterations: int = 4,
        web_search_max_results: int = 5,
    ) -> None:
        self._uow_factory = uow_factory
        self._llm = llm
        self._default_system_prompt = system_prompt
        self._default_enable_thinking = enable_thinking
        self._web_search = web_search
        self._page_fetcher = page_fetcher
        self._web_tool_max_iterations = web_tool_max_iterations
        self._web_search_max_results = web_search_max_results

    async def stream(
        self,
        conversation_id: UUID,
        user_id: UUID,
        user_content: str,
        attachment_ids: list[UUID] | None = None,
        web_access: bool = False,
        enable_thinking: bool | None = None,
        language: str = "en",
    ) -> AsyncGenerator[dict]:
        # 1. Persist user message and collect history for the LLM
        user_msg = Message(
            id=uuid4(),
            role="user",
            content=user_content,
            created_at=datetime.now(tz=UTC),
        )
        async with self._uow_factory() as uow:
            conv = await uow.conversations.get(conversation_id, user_id)
            if conv is None:
                yield error_event(ConversationNotFound("conversation not found"))
                return
            if conv.title is None:
                await uow.conversations.update_title(conversation_id, user_content[:60])
            await uow.conversations.save_message(user_msg, conversation_id)
            # Link any pending uploads to this user message; the returned
            # attachments carry the extracted text inlined into the LLM turn.
            linked = await uow.conversations.link_attachments(
                conversation_id, user_msg.id, attachment_ids or []
            )
            history = build_history(conv.messages) + [
                {"role": "user", "content": render_user_content(user_content, linked)}
            ]
            system_prompt, params = resolve_chat_config(
                conv,
                self._default_system_prompt,
                self._default_enable_thinking,
                enable_thinking,
                language,
            )

        # Web access: assemble the tool bundle and force thinking OFF for the
        # loop (Gemma 4 otherwise routes the tool_call block into reasoning_content
        # where the scanner can't see it). Falls back to a plain stream when the
        # tools aren't wired.
        web_tools = None
        if web_access and self._web_search is not None and self._page_fetcher is not None:
            params = replace(params, enable_thinking=False)
            web_tools = WebTools(
                search=self._web_search,
                fetcher=self._page_fetcher,
                max_iterations=self._web_tool_max_iterations,
                search_max_results=self._web_search_max_results,
            )

        # 2. Stream tokens + persist the assistant reply. `aclosing` ensures the
        #    inner generator's finally-persist runs if the client disconnects
        #    (this generator gets aclose()d mid-stream).
        async with aclosing(
            stream_and_persist(
                self._uow_factory,
                self._llm,
                system_prompt,
                params,
                conversation_id,
                history,
                web_tools=web_tools,
            )
        ) as events:
            async for event in events:
                yield event
