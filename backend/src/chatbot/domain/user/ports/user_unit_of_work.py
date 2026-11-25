from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from chatbot.domain.conversation.ports.conversation_repository import (
    AbstractConversationRepository,
)
from chatbot.domain.user.ports.user_repository import AbstractUserRepository


class AbstractUserUnitOfWork(ABC):
    """Transactional boundary for user use cases. Exposes both ``users`` and
    ``conversations`` so first-user adoption (register + ``claim_orphans``) is a
    single atomic transaction. One concrete UoW implements this and
    ``AbstractConversationUnitOfWork``; there is no second session."""

    users: AbstractUserRepository
    conversations: AbstractConversationRepository

    @abstractmethod
    async def __aenter__(self) -> AbstractUserUnitOfWork: ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


UserUnitOfWorkFactory = Callable[[], AbstractUserUnitOfWork]
