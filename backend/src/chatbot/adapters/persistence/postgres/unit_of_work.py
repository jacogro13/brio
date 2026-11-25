from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from chatbot.adapters.persistence.postgres.conversation_repository_impl import (
    PostgresConversationRepository,
)
from chatbot.adapters.persistence.postgres.user_repository_impl import (
    PostgresUserRepository,
)
from chatbot.domain.conversation.ports.conversation_repository import (
    AbstractConversationRepository,
)
from chatbot.domain.conversation.ports.conversation_unit_of_work import (
    AbstractConversationUnitOfWork,
)
from chatbot.domain.user.ports.user_repository import AbstractUserRepository
from chatbot.domain.user.ports.user_unit_of_work import AbstractUserUnitOfWork


class SqlAlchemyConversationUnitOfWork(AbstractConversationUnitOfWork, AbstractUserUnitOfWork):
    """One concrete UoW backing both the conversation and user ports (a single
    session, so first-user adoption commits atomically)."""

    # Declared by both bases; redeclared here so the two declarations agree.
    conversations: AbstractConversationRepository
    users: AbstractUserRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> SqlAlchemyConversationUnitOfWork:
        self._session = self._session_factory()
        self.conversations = PostgresConversationRepository(self._session)
        self.users = PostgresUserRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._session is not None
        try:
            if exc_type is None:
                await self.commit()
            else:
                await self.rollback()
        finally:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        assert self._session is not None
        await self._session.commit()

    async def rollback(self) -> None:
        assert self._session is not None
        await self._session.rollback()
