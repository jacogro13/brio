from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from chatbot.adapters.security.fake.fake_password_hasher import FakePasswordHasher
from chatbot.adapters.security.jwt.pyjwt_token_service import PyJwtTokenService
from chatbot.domain.conversation.model import Conversation
from chatbot.domain.user.model import InvalidCredentials, UsernameTaken
from chatbot.domain.user.ports.token_service import TokenService
from chatbot.services.user.login_user import LoginUserUseCase
from chatbot.services.user.register_user import RegisterUserUseCase
from tests.unit.fakes import make_uow_factory

SECRET = "unit-test-secret"
HASHER = FakePasswordHasher()
TOKENS = PyJwtTokenService(SECRET, "HS256", 60)


class RecordingTokenService(TokenService):
    """Remembers what it was asked to issue; decode is not used here."""

    def __init__(self) -> None:
        self.issued: list[tuple[str, dict[str, str | int | bool]]] = []

    def issue(self, subject: str, claims: Mapping[str, str | int | bool]) -> str:
        self.issued.append((subject, dict(claims)))
        return "issued-token"

    def decode(self, token: str) -> str:
        raise NotImplementedError


def _conv(user_id=None) -> Conversation:
    return Conversation(
        id=uuid4(),
        title="legacy",
        messages=[],
        created_at=datetime.now(tz=UTC),
        user_id=user_id,
    )


@pytest.mark.asyncio
async def test_register_first_user_adopts_orphan_conversations():
    legacy = _conv()  # ownerless
    store = {legacy.id: legacy}
    users: dict = {}
    uc = RegisterUserUseCase(make_uow_factory(store, users=users), HASHER)

    user = await uc.execute("alice", "pw")

    assert store[legacy.id].user_id == user.id  # adopted
    assert users[user.id].username == "alice"


@pytest.mark.asyncio
async def test_register_defaults_to_english():
    users: dict = {}
    uc = RegisterUserUseCase(make_uow_factory({}, users=users), HASHER)
    user = await uc.execute("alice", "pw")
    assert user.language == "en"


@pytest.mark.asyncio
async def test_register_persists_initial_language():
    users: dict = {}
    uc = RegisterUserUseCase(make_uow_factory({}, users=users), HASHER)
    user = await uc.execute("gigi", "pw", language="it")
    assert user.language == "it"
    assert users[user.id].language == "it"


@pytest.mark.asyncio
async def test_set_language_updates_the_user():
    users: dict = {}
    user = await RegisterUserUseCase(make_uow_factory({}, users=users), HASHER).execute(
        "hans", "pw"
    )
    factory = make_uow_factory({}, users=users)
    async with factory() as uow:
        await uow.users.set_language(user.id, "de")
        stored = await uow.users.get_by_id(user.id)
    assert stored is not None
    assert stored.language == "de"


@pytest.mark.asyncio
async def test_register_second_user_does_not_adopt():
    legacy = _conv()
    store = {legacy.id: legacy}
    users: dict = {}
    factory = make_uow_factory(store, users=users)
    first = await RegisterUserUseCase(factory, HASHER).execute("alice", "pw")

    second = await RegisterUserUseCase(factory, HASHER).execute("bob", "pw")

    # legacy stayed with the first registrant; bob adopts nothing
    assert store[legacy.id].user_id == first.id
    assert second.id != first.id


@pytest.mark.asyncio
async def test_register_duplicate_username_rejected():
    factory = make_uow_factory({}, users={})
    await RegisterUserUseCase(factory, HASHER).execute("alice", "pw")
    with pytest.raises(UsernameTaken):
        await RegisterUserUseCase(factory, HASHER).execute("alice", "other")


@pytest.mark.asyncio
async def test_login_returns_valid_token():
    users: dict = {}
    factory = make_uow_factory({}, users=users)
    user = await RegisterUserUseCase(factory, HASHER).execute("alice", "pw")

    token = await LoginUserUseCase(factory, HASHER, TOKENS).execute("alice", "pw")

    assert TOKENS.decode(token) == str(user.id)


@pytest.mark.asyncio
async def test_login_token_carries_the_username_claim():
    users: dict = {}
    factory = make_uow_factory({}, users=users)
    user = await RegisterUserUseCase(factory, HASHER).execute("alice", "pw")
    tokens = RecordingTokenService()

    await LoginUserUseCase(factory, HASHER, tokens).execute("alice", "pw")

    assert tokens.issued == [(str(user.id), {"username": "alice"})]


@pytest.mark.asyncio
async def test_login_bad_password_rejected():
    factory = make_uow_factory({}, users={})
    await RegisterUserUseCase(factory, HASHER).execute("alice", "pw")
    login = LoginUserUseCase(factory, HASHER, TOKENS)
    with pytest.raises(InvalidCredentials):
        await login.execute("alice", "nope")


@pytest.mark.asyncio
async def test_login_unknown_user_rejected():
    login = LoginUserUseCase(make_uow_factory({}, users={}), HASHER, TOKENS)
    with pytest.raises(InvalidCredentials):
        await login.execute("ghost", "pw")
