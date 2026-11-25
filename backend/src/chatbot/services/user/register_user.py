from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from chatbot.domain.user.model import Language, User, UsernameTaken
from chatbot.domain.user.ports.password_hasher import PasswordHasher
from chatbot.domain.user.ports.user_unit_of_work import UserUnitOfWorkFactory


class RegisterUserUseCase:
    """Open self-registration. The very first user to register adopts every
    ownerless (legacy) conversation, atomically in the same transaction."""

    def __init__(self, uow_factory: UserUnitOfWorkFactory, hasher: PasswordHasher) -> None:
        self._uow_factory = uow_factory
        self._hasher = hasher

    async def execute(self, username: str, password: str, language: Language = "en") -> User:
        async with self._uow_factory() as uow:
            if await uow.users.get_by_username(username) is not None:
                raise UsernameTaken(f"Username '{username}' is already taken")
            is_first_user = await uow.users.count() == 0
            user = User(
                id=uuid4(),
                username=username,
                hashed_password=await self._hasher.hash(password),
                created_at=datetime.now(tz=UTC),
                language=language,
            )
            await uow.users.add(user)
            if is_first_user:
                await uow.conversations.claim_orphans(user.id)
            return user
