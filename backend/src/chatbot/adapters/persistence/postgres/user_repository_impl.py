from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from chatbot.adapters.persistence.postgres.orm import users
from chatbot.domain.user.model import Language, User
from chatbot.domain.user.ports.user_repository import AbstractUserRepository


class PostgresUserRepository(AbstractUserRepository):
    """Loads and saves the mapped `User` entity itself (see `orm.py`)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(select(User).where(users.c.username == username))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def add(self, user: User) -> None:
        self._session.add(user)
        await self._session.flush()

    async def set_language(self, user_id: UUID, language: Language) -> None:
        await self._session.execute(
            update(User).where(users.c.id == user_id).values(language=language)
        )

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(users))
        return int(result.scalar_one())

    async def list(self) -> list[User]:
        result = await self._session.execute(select(User).order_by(users.c.created_at))
        return list(result.scalars())
