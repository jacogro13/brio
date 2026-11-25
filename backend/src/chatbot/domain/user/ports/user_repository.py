from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from chatbot.domain.user.model import Language, User


class AbstractUserRepository(ABC):
    @abstractmethod
    async def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def add(self, user: User) -> None: ...

    @abstractmethod
    async def set_language(self, user_id: UUID, language: Language) -> None: ...

    @abstractmethod
    async def count(self) -> int: ...

    @abstractmethod
    async def list(self) -> list[User]: ...
