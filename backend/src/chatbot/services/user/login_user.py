from __future__ import annotations

from chatbot.domain.user.model import InvalidCredentials
from chatbot.domain.user.ports.password_hasher import PasswordHasher
from chatbot.domain.user.ports.token_service import TokenService
from chatbot.domain.user.ports.user_unit_of_work import UserUnitOfWorkFactory


class LoginUserUseCase:
    """Verify credentials and issue a bearer token for the user."""

    def __init__(
        self,
        uow_factory: UserUnitOfWorkFactory,
        hasher: PasswordHasher,
        tokens: TokenService,
    ) -> None:
        self._uow_factory = uow_factory
        self._hasher = hasher
        self._tokens = tokens

    async def execute(self, username: str, password: str) -> str:
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_username(username)
            if user is None or not await self._hasher.verify(password, user.hashed_password):
                raise InvalidCredentials("Invalid username or password")
            return self._tokens.issue(str(user.id), {"username": user.username})
