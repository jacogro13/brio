from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from chatbot.adapters.extraction.text_extraction import TextExtractionAdapter
from chatbot.adapters.llm.mock.mock_llm_adapter import MockLLMAdapter
from chatbot.adapters.llm.openai.openai_llm_adapter import OpenAILikeLLMAdapter
from chatbot.adapters.persistence.postgres.database import make_engine, make_session_factory
from chatbot.adapters.persistence.postgres.unit_of_work import SqlAlchemyConversationUnitOfWork
from chatbot.adapters.security.bcrypt.bcrypt_password_hasher import BcryptPasswordHasher
from chatbot.adapters.security.jwt.pyjwt_token_service import PyJwtTokenService
from chatbot.adapters.storage.garage.garage_storage_adapter import GarageStorageAdapter
from chatbot.adapters.storage.null.null_storage_adapter import NullAttachmentStorage
from chatbot.adapters.web.ddgs_search import DdgsWebSearch
from chatbot.adapters.web.mock import MockPageFetcher, MockWebSearch
from chatbot.adapters.web.trafilatura_fetcher import TrafilaturaPageFetcher
from chatbot.domain.conversation.ports.attachment_storage import AbstractAttachmentStorage
from chatbot.domain.conversation.ports.chat_llm import ChatLLM
from chatbot.domain.conversation.ports.conversation_unit_of_work import (
    ConversationUnitOfWorkFactory,
)
from chatbot.domain.conversation.ports.text_extractor import AbstractTextExtractor
from chatbot.domain.conversation.ports.web_tools import PageFetcher, WebSearch
from chatbot.domain.user.model import InvalidToken
from chatbot.domain.user.ports.password_hasher import PasswordHasher
from chatbot.domain.user.ports.token_service import TokenService
from chatbot.domain.user.ports.user_unit_of_work import UserUnitOfWorkFactory
from chatbot.entrypoints.settings import Settings, get_settings
from chatbot.services.conversation.create_conversation import CreateConversationUseCase
from chatbot.services.conversation.delete_conversation import DeleteConversationUseCase
from chatbot.services.conversation.download_attachment import DownloadAttachmentUseCase
from chatbot.services.conversation.edit_message import EditMessageUseCase
from chatbot.services.conversation.get_conversation import GetConversationUseCase
from chatbot.services.conversation.list_conversations import ListConversationsUseCase
from chatbot.services.conversation.regenerate_message import RegenerateMessageUseCase
from chatbot.services.conversation.send_message import SendMessageUseCase
from chatbot.services.conversation.update_conversation import UpdateConversationUseCase
from chatbot.services.conversation.upload_attachment import UploadAttachmentUseCase
from chatbot.services.user.login_user import LoginUserUseCase
from chatbot.services.user.register_user import RegisterUserUseCase

_engine = None
_session_factory = None


def _get_session_factory():
    global _engine, _session_factory
    if _session_factory is None:
        settings = get_settings()
        _engine = make_engine(settings.async_database_url())
        _session_factory = make_session_factory(_engine)
    return _session_factory


async def shutdown_engine() -> None:
    if _engine is not None:
        await _engine.dispose()


def get_uow_factory() -> ConversationUnitOfWorkFactory:
    session_factory = _get_session_factory()

    def factory():
        return SqlAlchemyConversationUnitOfWork(session_factory)

    return factory


def get_user_uow_factory() -> UserUnitOfWorkFactory:
    """The same UoW as ``get_uow_factory``, typed for the user ports."""
    session_factory = _get_session_factory()

    def factory():
        return SqlAlchemyConversationUnitOfWork(session_factory)

    return factory


_llm: ChatLLM | None = None


def get_llm(settings: Annotated[Settings, Depends(get_settings)]) -> ChatLLM:
    global _llm
    if _llm is None:
        if settings.llm_base_url:
            _llm = OpenAILikeLLMAdapter(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
            )
        else:
            _llm = MockLLMAdapter()
    return _llm


_storage: AbstractAttachmentStorage | None = None


def get_attachment_storage(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AbstractAttachmentStorage:
    global _storage
    if _storage is None:
        if settings.garage_endpoint:
            _storage = GarageStorageAdapter(
                endpoint_url=settings.garage_endpoint,
                access_key_id=settings.garage_access_key_id,
                secret_access_key=settings.garage_secret_access_key,
                bucket_name=settings.garage_bucket,
                region_name=settings.garage_region,
            )
        else:
            _storage = NullAttachmentStorage()
    return _storage


def get_text_extractor(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AbstractTextExtractor:
    return TextExtractionAdapter(max_extracted_chars=settings.attachment_max_extracted_chars)


_web_search: WebSearch | None = None
_page_fetcher: PageFetcher | None = None


def get_web_search(settings: Annotated[Settings, Depends(get_settings)]) -> WebSearch:
    global _web_search
    if _web_search is None:
        _web_search = DdgsWebSearch() if settings.web_tools_enabled else MockWebSearch()
    return _web_search


def get_page_fetcher(settings: Annotated[Settings, Depends(get_settings)]) -> PageFetcher:
    global _page_fetcher
    if _page_fetcher is None:
        _page_fetcher = (
            TrafilaturaPageFetcher(max_chars=settings.web_fetch_max_chars)
            if settings.web_tools_enabled
            else MockPageFetcher()
        )
    return _page_fetcher


_password_hasher: PasswordHasher | None = None


def get_password_hasher() -> PasswordHasher:
    """Always the real bcrypt adapter; tests override it with the fake."""
    global _password_hasher
    if _password_hasher is None:
        _password_hasher = BcryptPasswordHasher()
    return _password_hasher


def get_token_service(settings: Annotated[Settings, Depends(get_settings)]) -> TokenService:
    return PyJwtTokenService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expiry_minutes=settings.jwt_access_token_expire_minutes,
    )


_bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> UUID:
    """Validate the bearer token and return the user_id. A bad or expired token is
    a 401 (``InvalidToken`` / ``TokenExpired``), mapped by the error handler."""
    subject = tokens.decode(credentials.credentials)
    try:
        return UUID(subject)
    except ValueError as exc:
        raise InvalidToken("Invalid token: subject is not a user id") from exc


async def get_current_language(
    user_id: Annotated[UUID, Depends(get_current_user)],
    uow_factory: Annotated[UserUnitOfWorkFactory, Depends(get_user_uow_factory)],
) -> str:
    """Resolve the acting user's reply-language preference. Loads it fresh from
    the DB (the JWT is not re-minted on a language change) so a switch takes
    effect on the next message. Falls back to ``en`` if the user vanished."""
    async with uow_factory() as uow:
        user = await uow.users.get_by_id(user_id)
    return user.language if user is not None else "en"


def get_register_use_case(
    uow_factory: Annotated[UserUnitOfWorkFactory, Depends(get_user_uow_factory)],
    hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
) -> RegisterUserUseCase:
    return RegisterUserUseCase(uow_factory=uow_factory, hasher=hasher)


def get_login_use_case(
    uow_factory: Annotated[UserUnitOfWorkFactory, Depends(get_user_uow_factory)],
    hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> LoginUserUseCase:
    return LoginUserUseCase(uow_factory=uow_factory, hasher=hasher, tokens=tokens)


def get_create_use_case(
    uow_factory: Annotated[ConversationUnitOfWorkFactory, Depends(get_uow_factory)],
) -> CreateConversationUseCase:
    return CreateConversationUseCase(uow_factory=uow_factory)


def get_list_use_case(
    uow_factory: Annotated[ConversationUnitOfWorkFactory, Depends(get_uow_factory)],
) -> ListConversationsUseCase:
    return ListConversationsUseCase(uow_factory=uow_factory)


def get_get_use_case(
    uow_factory: Annotated[ConversationUnitOfWorkFactory, Depends(get_uow_factory)],
) -> GetConversationUseCase:
    return GetConversationUseCase(uow_factory=uow_factory)


def get_delete_use_case(
    uow_factory: Annotated[ConversationUnitOfWorkFactory, Depends(get_uow_factory)],
    storage: Annotated[AbstractAttachmentStorage, Depends(get_attachment_storage)],
) -> DeleteConversationUseCase:
    return DeleteConversationUseCase(uow_factory=uow_factory, storage=storage)


def get_send_message_use_case(
    uow_factory: Annotated[ConversationUnitOfWorkFactory, Depends(get_uow_factory)],
    llm: Annotated[ChatLLM, Depends(get_llm)],
    settings: Annotated[Settings, Depends(get_settings)],
    web_search: Annotated[WebSearch, Depends(get_web_search)],
    page_fetcher: Annotated[PageFetcher, Depends(get_page_fetcher)],
) -> SendMessageUseCase:
    return SendMessageUseCase(
        uow_factory=uow_factory,
        llm=llm,
        system_prompt=settings.system_prompt,
        enable_thinking=settings.llm_chat_enable_thinking,
        web_search=web_search,
        page_fetcher=page_fetcher,
        web_tool_max_iterations=settings.web_tool_max_iterations,
        web_search_max_results=settings.web_search_max_results,
    )


def get_update_use_case(
    uow_factory: Annotated[ConversationUnitOfWorkFactory, Depends(get_uow_factory)],
) -> UpdateConversationUseCase:
    return UpdateConversationUseCase(uow_factory=uow_factory)


def get_regenerate_use_case(
    uow_factory: Annotated[ConversationUnitOfWorkFactory, Depends(get_uow_factory)],
    llm: Annotated[ChatLLM, Depends(get_llm)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RegenerateMessageUseCase:
    return RegenerateMessageUseCase(
        uow_factory=uow_factory,
        llm=llm,
        system_prompt=settings.system_prompt,
        enable_thinking=settings.llm_chat_enable_thinking,
    )


def get_edit_use_case(
    uow_factory: Annotated[ConversationUnitOfWorkFactory, Depends(get_uow_factory)],
    llm: Annotated[ChatLLM, Depends(get_llm)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EditMessageUseCase:
    return EditMessageUseCase(
        uow_factory=uow_factory,
        llm=llm,
        system_prompt=settings.system_prompt,
        enable_thinking=settings.llm_chat_enable_thinking,
    )


def get_upload_attachment_use_case(
    uow_factory: Annotated[ConversationUnitOfWorkFactory, Depends(get_uow_factory)],
    storage: Annotated[AbstractAttachmentStorage, Depends(get_attachment_storage)],
    extractor: Annotated[AbstractTextExtractor, Depends(get_text_extractor)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UploadAttachmentUseCase:
    return UploadAttachmentUseCase(
        uow_factory=uow_factory,
        storage=storage,
        extractor=extractor,
        max_bytes=settings.attachment_max_bytes,
    )


def get_download_attachment_use_case(
    uow_factory: Annotated[ConversationUnitOfWorkFactory, Depends(get_uow_factory)],
    storage: Annotated[AbstractAttachmentStorage, Depends(get_attachment_storage)],
) -> DownloadAttachmentUseCase:
    return DownloadAttachmentUseCase(uow_factory=uow_factory, storage=storage)
