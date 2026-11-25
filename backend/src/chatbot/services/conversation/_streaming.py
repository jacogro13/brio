from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

from chatbot.domain.conversation.model import Attachment, Conversation, Message, ToolEvent
from chatbot.domain.conversation.ports.chat_llm import ChatLLM, ChatParams
from chatbot.domain.conversation.ports.conversation_unit_of_work import (
    ConversationUnitOfWorkFactory,
)
from chatbot.domain.errors import DomainError
from chatbot.services.conversation.language import apply_language
from chatbot.services.conversation.tool_loop import WebTools, run_tool_loop


def error_event(error: DomainError) -> dict:
    """The stream's ``error`` event for an expected failure: its stable ``code``
    (as in HTTP error bodies) plus the English ``message``."""
    return {"type": "error", "code": error.code, "message": error.message}


def render_user_content(content: str, attachments: list[Attachment]) -> str:
    """Inline a user turn's attachments into the text the LLM sees.

    Each attachment appends an ``[Attached file: {name}]`` block — its extracted
    text when available, or a note that it isn't model-visible (images). Pure
    function: the persisted ``Message.content`` stays the raw user text; only the
    LLM history is augmented."""
    if not attachments:
        return content
    parts = [content] if content else []
    for a in attachments:
        if a.extracted_text:
            parts.append(f"[Attached file: {a.filename}]\n{a.extracted_text}")
        else:
            parts.append(
                f"[Attached file: {a.filename}] (no extractable text — not visible to the model)"
            )
    return "\n\n".join(parts)


def build_history(messages: list[Message]) -> list[dict]:
    """Build the LLM message history from stored messages, inlining each user
    turn's attachments (pure). Assistant ``thinking`` is never replayed."""
    return [
        {
            "role": m.role,
            "content": (
                render_user_content(m.content, m.attachments) if m.role == "user" else m.content
            ),
        }
        for m in messages
    ]


def resolve_chat_config(
    conv: Conversation,
    default_system_prompt: str,
    default_enable_thinking: bool,
    enable_thinking: bool | None = None,
    language: str = "en",
) -> tuple[str, ChatParams]:
    """Resolve a conversation's per-conversation overrides against the server
    defaults. The ``system_prompt_override`` / ``temperature`` / ``max_tokens``
    overrides live on the conversation (``None`` → default; ``temperature`` /
    ``max_tokens`` stay ``None`` so the adapter omits them). ``enable_thinking``
    is a **per-turn** value (the composer toggle, like web access): ``None``
    falls back to the server default. Never conflate a ``None`` override with
    ``0`` / ``False``. ``language`` appends the user's reply-language directive
    to the resolved prompt (no-op for ``en``)."""
    system_prompt = (
        conv.system_prompt_override
        if conv.system_prompt_override is not None
        else default_system_prompt
    )
    system_prompt = apply_language(system_prompt, language)
    resolved_thinking = enable_thinking if enable_thinking is not None else default_enable_thinking
    params = ChatParams(
        temperature=conv.temperature,
        max_tokens=conv.max_tokens,
        enable_thinking=resolved_thinking,
    )
    return system_prompt, params


def _events_source(
    llm: ChatLLM,
    system_prompt: str,
    params: ChatParams,
    history: list[dict],
    web_tools: WebTools | None,
) -> AsyncIterator[dict]:
    """Pick the producer: the web-access tool loop when ``web_tools`` is set,
    otherwise a plain ``stream_chat`` adapted to the same event-dict shape."""
    if web_tools is not None:
        return run_tool_loop(llm, system_prompt, params, history, web_tools)

    async def _direct() -> AsyncGenerator[dict]:
        async for chunk in llm.stream_chat(history, system_prompt, params):
            if chunk.kind == "thinking":
                yield {"type": "thinking", "content": chunk.content}
            elif chunk.kind == "token":
                yield {"type": "token", "content": chunk.content}

    return _direct()


async def stream_and_persist(
    uow_factory: ConversationUnitOfWorkFactory,
    llm: ChatLLM,
    system_prompt: str,
    params: ChatParams,
    conversation_id: UUID,
    history: list[dict],
    web_tools: WebTools | None = None,
) -> AsyncGenerator[dict]:
    """Stream an assistant reply for ``history`` and persist it.

    Yields typed event dicts (``token``/``thinking``/``tool_start``/``tool_end``/
    ``done``). Shared by send/regenerate/edit. When ``web_tools`` is supplied the
    reply is produced by the web-access tool loop (thinking is forced off by the
    caller); otherwise it's a plain token stream. Reasoning (``thinking``) is
    streamed + stored but **never** replayed to the LLM as history; tool activity
    is persisted on ``messages.tool_events`` so chips re-render on reload. The
    reply is persisted in a dedicated UoW inside ``finally`` so a partial reply
    survives a client disconnect (the generator is ``aclose()``d).
    """
    accumulated = ""
    thinking = ""
    tool_records: dict[int, dict] = {}
    assistant_id = uuid4()
    try:
        async for event in _events_source(llm, system_prompt, params, history, web_tools):
            etype = event["type"]
            if etype == "thinking":
                thinking += event["content"]
                yield event
            elif etype == "token":
                accumulated += event["content"]
                yield event
            elif etype == "tool_start":
                tool_records[event["id"]] = {k: v for k, v in event.items() if k != "type"}
                yield event
            elif etype == "tool_end":
                tool_records.setdefault(event["id"], {"id": event["id"]}).update(
                    {k: v for k, v in event.items() if k != "type"}
                )
                yield event
    finally:
        if accumulated:
            tool_events = (
                [ToolEvent.from_json(tool_records[i]) for i in sorted(tool_records)]
                if tool_records
                else None
            )
            assistant_msg = Message(
                id=assistant_id,
                role="assistant",
                content=accumulated,
                created_at=datetime.now(tz=UTC),
                thinking=thinking or None,
                tool_events=tool_events,
            )
            async with uow_factory() as uow:
                await uow.conversations.save_message(assistant_msg, conversation_id)

    yield {
        "type": "done",
        "message_id": str(assistant_id) if accumulated else None,
    }
