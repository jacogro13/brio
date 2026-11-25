from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from chatbot.domain.conversation.ports.conversation_repository import AbstractConversationRepository


class AbstractConversationUnitOfWork(ABC):
    conversations: AbstractConversationRepository

    @abstractmethod
    async def __aenter__(self) -> AbstractConversationUnitOfWork: ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


ConversationUnitOfWorkFactory = Callable[[], AbstractConversationUnitOfWork]
