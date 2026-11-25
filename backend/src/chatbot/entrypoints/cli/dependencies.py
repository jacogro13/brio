from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from chatbot.adapters.llm.mock.mock_llm_adapter import MockLLMAdapter
from chatbot.adapters.llm.openai.openai_llm_adapter import OpenAILikeLLMAdapter
from chatbot.adapters.persistence.postgres.database import make_engine, make_session_factory
from chatbot.adapters.persistence.postgres.orm import start_mappers
from chatbot.adapters.persistence.postgres.unit_of_work import SqlAlchemyConversationUnitOfWork
from chatbot.adapters.storage.null.null_storage_adapter import NullAttachmentStorage
from chatbot.domain.conversation.ports.chat_llm import ChatLLM
from chatbot.domain.user.model import Language
from chatbot.entrypoints.settings import describe_settings_error, get_settings
from chatbot.services.conversation.create_conversation import CreateConversationUseCase
from chatbot.services.conversation.delete_conversation import DeleteConversationUseCase
from chatbot.services.conversation.get_conversation import GetConversationUseCase
from chatbot.services.conversation.list_conversations import ListConversationsUseCase
from chatbot.services.conversation.send_message import SendMessageUseCase


@dataclass
class CliContext:
    engine: AsyncEngine
    uow_factory: Callable[[], SqlAlchemyConversationUnitOfWork]
    llm: ChatLLM
    cwd: Path
    create: CreateConversationUseCase
    list: ListConversationsUseCase
    get: GetConversationUseCase
    send: SendMessageUseCase
    delete: DeleteConversationUseCase
    # Assistant reply language ('en' | 'it' | 'de'), from CHATBOT_LANGUAGE.
    language: Language = "en"
    # Resolved after build_context, once the DB is reachable (see resolve_user).
    user_id: UUID | None = None

    @property
    def acting_user(self) -> UUID:
        """The resolved user; the REPL only runs after ``resolve_user_id``."""
        if self.user_id is None:
            raise RuntimeError("CLI user not resolved yet")
        return self.user_id

    async def close(self) -> None:
        await self.engine.dispose()


async def resolve_user_id(ctx: CliContext) -> UUID:
    """Pick the CLI's acting user (the CLI has no JWT). ``CHATBOT_CLI_USER``
    names one explicitly; otherwise a single existing user is used implicitly.
    Raises ``RuntimeError`` (surfaced as a clean exit) when the choice is
    ambiguous, the named user is missing, or no users exist yet."""
    async with ctx.uow_factory() as uow:
        users = await uow.users.list()

    requested = get_settings().chatbot_cli_user
    if requested:
        match = next((u for u in users if u.username == requested), None)
        if match is None:
            raise RuntimeError(
                f"CHATBOT_CLI_USER='{requested}' not found. "
                f"Known users: {', '.join(u.username for u in users) or '(none)'}."
            )
        return match.id

    if not users:
        raise RuntimeError(
            "No users exist yet. Register the first user via the web UI, then retry."
        )
    if len(users) == 1:
        return users[0].id
    raise RuntimeError(
        "Multiple users exist; set CHATBOT_CLI_USER to one of: "
        + ", ".join(u.username for u in users)
    )


def _find_dotenv() -> Path | None:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    return None


def build_context() -> CliContext:
    dotenv_path = _find_dotenv()
    if dotenv_path is not None:
        load_dotenv(dotenv_path, override=False)

    try:
        settings = get_settings()
    except ValidationError as exc:
        raise RuntimeError(describe_settings_error(exc)) from exc

    llm_base_url = settings.llm_base_url
    llm_api_key = settings.llm_api_key
    llm_model = settings.llm_model
    enable_thinking = settings.llm_chat_enable_thinking
    system_prompt = settings.system_prompt
    language = settings.chatbot_language

    start_mappers()
    engine = make_engine(settings.async_database_url())
    session_factory = make_session_factory(engine)

    def uow_factory() -> SqlAlchemyConversationUnitOfWork:
        return SqlAlchemyConversationUnitOfWork(session_factory)

    llm: ChatLLM = (
        OpenAILikeLLMAdapter(
            base_url=llm_base_url,
            api_key=llm_api_key,
            model=llm_model,
        )
        if llm_base_url
        else MockLLMAdapter()
    )

    return CliContext(
        engine=engine,
        uow_factory=uow_factory,
        llm=llm,
        cwd=Path.cwd(),
        create=CreateConversationUseCase(uow_factory=uow_factory),
        list=ListConversationsUseCase(uow_factory=uow_factory),
        get=GetConversationUseCase(uow_factory=uow_factory),
        send=SendMessageUseCase(
            uow_factory=uow_factory,
            llm=llm,
            system_prompt=system_prompt,
            enable_thinking=enable_thinking,
        ),
        delete=DeleteConversationUseCase(uow_factory=uow_factory, storage=NullAttachmentStorage()),
        language=language,
    )
