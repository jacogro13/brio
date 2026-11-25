from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from chatbot.adapters.persistence.postgres.orm import metadata, start_mappers
from chatbot.adapters.persistence.postgres.user_repository_impl import (
    PostgresUserRepository,
)
from chatbot.domain.user.model import User


@pytest.fixture(scope="module")
def pg_container():
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest_asyncio.fixture
async def pg_session(pg_container):
    start_mappers()
    url = pg_container.get_connection_url().replace("psycopg2", "asyncpg")
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _user(username: str) -> User:
    return User(
        id=uuid4(),
        username=username,
        hashed_password="hashed",
        created_at=datetime.now(tz=UTC),
    )


@pytest.mark.asyncio
async def test_add_and_get_by_username(pg_session):
    repo = PostgresUserRepository(pg_session)
    user = _user("alice")
    await repo.add(user)
    await pg_session.commit()

    fetched = await repo.get_by_username("alice")
    assert fetched is not None
    assert fetched.id == user.id
    assert fetched.hashed_password == "hashed"
    assert await repo.get_by_username("nobody") is None


@pytest.mark.asyncio
async def test_count_and_list(pg_session):
    # The testcontainer is shared across the module, so assert relative to the
    # current baseline rather than an empty table.
    repo = PostgresUserRepository(pg_session)
    baseline = await repo.count()
    u1, u2 = _user(f"a-{uuid4().hex[:6]}"), _user(f"b-{uuid4().hex[:6]}")
    await repo.add(u1)
    await repo.add(u2)
    await pg_session.commit()

    assert await repo.count() == baseline + 2
    usernames = {u.username for u in await repo.list()}
    assert {u1.username, u2.username} <= usernames


@pytest.mark.asyncio
async def test_get_by_id_and_default_language(pg_session):
    repo = PostgresUserRepository(pg_session)
    user = _user(f"lang-{uuid4().hex[:6]}")
    await repo.add(user)
    await pg_session.commit()

    fetched = await repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.id == user.id
    # Column server_default applies to rows added without an explicit language.
    assert fetched.language == "en"
    assert await repo.get_by_id(uuid4()) is None


@pytest.mark.asyncio
async def test_set_language_persists(pg_session):
    repo = PostgresUserRepository(pg_session)
    user = _user(f"setlang-{uuid4().hex[:6]}")
    await repo.add(user)
    await pg_session.commit()

    await repo.set_language(user.id, "de")
    await pg_session.commit()

    fetched = await repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.language == "de"
