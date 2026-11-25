from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace
from uuid import UUID, uuid4

from chatbot.domain.conversation.model import Attachment, Conversation, Message
from chatbot.domain.conversation.ports.attachment_storage import (
    AbstractAttachmentStorage,
)
from chatbot.domain.conversation.ports.chat_llm import ChatLLM, ChatParams, LlmChunk
from chatbot.domain.conversation.ports.conversation_repository import (
    AbstractConversationRepository,
)
from chatbot.domain.conversation.ports.conversation_unit_of_work import (
    AbstractConversationUnitOfWork,
)
from chatbot.domain.user.model import Language, User
from chatbot.domain.user.ports.user_repository import AbstractUserRepository
from chatbot.domain.user.ports.user_unit_of_work import AbstractUserUnitOfWork

# Default acting user for use-case tests. Conversations built via the test
# helpers are owned by this id; scoped reads with it succeed, others 404.
USER_ID = uuid4()


class FakeConversationRepository(AbstractConversationRepository):
    """In-memory repo. ``get`` returns a detached snapshot (fresh messages list)
    just like the SQLAlchemy repo, so writes via ``save_message`` don't mutate a
    conversation already handed to a use case. Reads/writes are scoped by
    ``user_id`` — a mismatched owner reads as ``None`` (cross-user 404)."""

    def __init__(
        self,
        store: dict[UUID, Conversation],
        attachments: dict[UUID, Attachment],
    ) -> None:
        self._store = store
        self._attachments = attachments

    def _owned(self, conv: Conversation | None, user_id: UUID) -> bool:
        # ``None`` owner = legacy/ownerless (visible to any user, like prod
        # before adoption); otherwise the owner must match.
        return conv is not None and (conv.user_id is None or conv.user_id == user_id)

    async def get(self, id: UUID, user_id: UUID) -> Conversation | None:
        conv = self._store.get(id)
        if conv is None or not self._owned(conv, user_id):
            return None
        return Conversation(
            id=conv.id,
            title=conv.title,
            messages=[
                replace(
                    m,
                    attachments=[a for a in self._attachments.values() if a.message_id == m.id],
                )
                for m in conv.messages
            ],
            created_at=conv.created_at,
            user_id=conv.user_id,
            temperature=conv.temperature,
            max_tokens=conv.max_tokens,
            system_prompt_override=conv.system_prompt_override,
        )

    async def list(self, user_id: UUID) -> list[Conversation]:
        return [c for c in self._store.values() if self._owned(c, user_id)]

    async def add(self, conversation: Conversation) -> None:
        self._store[conversation.id] = conversation

    async def claim_orphans(self, user_id: UUID) -> int:
        n = 0
        for conv in self._store.values():
            if conv.user_id is None:
                conv.user_id = user_id
                n += 1
        return n

    async def save_message(self, message: Message, conversation_id: UUID) -> None:
        self._store[conversation_id].messages.append(message)

    async def delete_messages(self, conversation_id: UUID, message_ids: list[UUID]) -> None:
        conv = self._store[conversation_id]
        ids = set(message_ids)
        conv.messages = [m for m in conv.messages if m.id not in ids]

    async def update_title(self, conversation_id: UUID, title: str) -> None:
        self._store[conversation_id].title = title

    async def update_settings(self, conversation_id: UUID, updates: dict) -> None:
        conv = self._store[conversation_id]
        for key, value in updates.items():
            setattr(conv, key, value)

    async def delete(self, id: UUID, user_id: UUID) -> None:
        conv = self._store.get(id)
        if not self._owned(conv, user_id):
            return
        self._store.pop(id, None)
        # FK cascade in Postgres; mirror it here.
        for aid in [a.id for a in self._attachments.values() if a.conversation_id == id]:
            self._attachments.pop(aid, None)

    async def add_attachment(self, attachment: Attachment) -> None:
        self._attachments[attachment.id] = attachment

    async def get_attachment(self, attachment_id: UUID) -> Attachment | None:
        return self._attachments.get(attachment_id)

    async def link_attachments(
        self, conversation_id: UUID, message_id: UUID, attachment_ids: list[UUID]
    ) -> list[Attachment]:
        linked: list[Attachment] = []
        for aid in attachment_ids:
            a = self._attachments.get(aid)
            if a is not None and a.conversation_id == conversation_id and a.message_id is None:
                a.message_id = message_id
                linked.append(a)
        return linked


class FakeUserRepository(AbstractUserRepository):
    def __init__(self, store: dict[UUID, User]) -> None:
        self._store = store

    async def get_by_username(self, username: str) -> User | None:
        return next((u for u in self._store.values() if u.username == username), None)

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._store.get(user_id)

    async def add(self, user: User) -> None:
        self._store[user.id] = user

    async def set_language(self, user_id: UUID, language: Language) -> None:
        user = self._store.get(user_id)
        if user is not None:
            self._store[user_id] = replace(user, language=language)

    async def count(self) -> int:
        return len(self._store)

    async def list(self) -> list[User]:
        return list(self._store.values())


class FakeUnitOfWork(AbstractConversationUnitOfWork, AbstractUserUnitOfWork):
    # Declared by both bases; redeclared here so the two declarations agree.
    conversations: AbstractConversationRepository
    users: AbstractUserRepository

    def __init__(
        self,
        store: dict[UUID, Conversation],
        attachments: dict[UUID, Attachment],
        users: dict[UUID, User],
    ) -> None:
        self._store = store
        self._attachments = attachments
        self._users = users
        self.committed = False

    async def __aenter__(self) -> FakeUnitOfWork:
        self.conversations = FakeConversationRepository(self._store, self._attachments)
        self.users = FakeUserRepository(self._users)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


def make_uow_factory(
    store: dict[UUID, Conversation],
    attachments: dict[UUID, Attachment] | None = None,
    users: dict[UUID, User] | None = None,
):
    shared_attachments = attachments if attachments is not None else {}
    shared_users = users if users is not None else {}

    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(store, shared_attachments, shared_users)

    return factory


class FakeAttachmentStorage(AbstractAttachmentStorage):
    """In-memory attachment storage for use-case tests."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    async def upload_file(self, key: str, data: bytes, content_type: str) -> None:
        self.store[key] = data

    async def get_file(self, key: str) -> bytes:
        return self.store[key]

    async def delete_prefix(self, prefix: str) -> None:
        for key in [k for k in self.store if k.startswith(prefix)]:
            del self.store[key]


class FakeLLM(ChatLLM):
    def __init__(self, tokens: list[str], thinking: list[str] | None = None) -> None:
        self._tokens = tokens
        self._thinking = thinking or []
        self.last_history: list[dict] | None = None
        self.last_system_prompt: str | None = None
        self.last_params: ChatParams | None = None

    async def stream_chat(
        self, messages: list[dict], system_prompt: str, params: ChatParams
    ) -> AsyncIterator[LlmChunk]:
        self.last_history = messages
        self.last_system_prompt = system_prompt
        self.last_params = params
        for chunk in self._thinking:
            yield LlmChunk(kind="thinking", content=chunk)
        for token in self._tokens:
            yield LlmChunk(kind="token", content=token)
