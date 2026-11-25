from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from chatbot.adapters.persistence.postgres.conversation_repository_impl import (
    PostgresConversationRepository,
)
from chatbot.adapters.persistence.postgres.orm import metadata, start_mappers
from chatbot.adapters.persistence.postgres.user_repository_impl import (
    PostgresUserRepository,
)
from chatbot.domain.conversation.model import (
    Attachment,
    Conversation,
    Message,
    ToolEvent,
    ToolResult,
)
from chatbot.domain.user.model import User


@pytest.fixture(scope="module")
def pg_container():
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest_asyncio.fixture
async def pg_engine(pg_container):
    start_mappers()
    url = pg_container.get_connection_url().replace("psycopg2", "asyncpg")
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def pg_factory(pg_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Sessions as the Unit of Work opens them (a fresh one per use case)."""
    return async_sessionmaker(pg_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def pg_session(pg_factory: async_sessionmaker[AsyncSession]):
    async with pg_factory() as session:
        yield session


def _now():
    return datetime.now(tz=UTC)


@pytest_asyncio.fixture
async def owner_id(pg_session: AsyncSession):
    user = User(
        id=uuid4(),
        username=f"owner-{uuid4().hex[:8]}",
        hashed_password="x",
        created_at=_now(),
    )
    await PostgresUserRepository(pg_session).add(user)
    await pg_session.commit()
    return user.id


async def _new_conv(repo: PostgresConversationRepository, session: AsyncSession, owner_id):
    conv = Conversation(id=uuid4(), title=None, messages=[], created_at=_now(), user_id=owner_id)
    await repo.add(conv)
    await session.commit()
    return conv


def _attachment(conversation_id, text=None):
    aid = uuid4()
    return Attachment(
        id=aid,
        conversation_id=conversation_id,
        message_id=None,
        filename="notes.md",
        content_type="text/markdown",
        size=7,
        s3_key=f"conversations/{conversation_id}/{aid}/notes.md",
        extracted_text=text,
        created_at=_now(),
    )


@pytest.mark.asyncio
async def test_add_and_get_attachment(pg_session: AsyncSession, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv = await _new_conv(repo, pg_session, owner_id)
    att = _attachment(conv.id, "body")
    await repo.add_attachment(att)
    await pg_session.commit()

    fetched = await repo.get_attachment(att.id)
    assert fetched is not None
    assert fetched.extracted_text == "body"
    assert fetched.message_id is None


@pytest.mark.asyncio
async def test_link_attachment_sets_message_id_and_loads_onto_message(
    pg_session: AsyncSession, owner_id
):
    repo = PostgresConversationRepository(pg_session)
    conv = await _new_conv(repo, pg_session, owner_id)
    att = _attachment(conv.id, "body")
    await repo.add_attachment(att)
    msg = Message(id=uuid4(), role="user", content="hi", created_at=_now())
    await repo.save_message(msg, conv.id)
    await pg_session.commit()

    linked = await repo.link_attachments(conv.id, msg.id, [att.id])
    await pg_session.commit()
    assert [a.id for a in linked] == [att.id]

    fetched = await repo.get(conv.id, owner_id)
    assert fetched is not None
    assert [a.id for a in fetched.messages[0].attachments] == [att.id]


@pytest.mark.asyncio
async def test_link_ignores_foreign_conversation_attachments(pg_session: AsyncSession, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv_a = await _new_conv(repo, pg_session, owner_id)
    conv_b = await _new_conv(repo, pg_session, owner_id)
    att_b = _attachment(conv_b.id)
    await repo.add_attachment(att_b)
    msg = Message(id=uuid4(), role="user", content="hi", created_at=_now())
    await repo.save_message(msg, conv_a.id)
    await pg_session.commit()

    # Trying to link conv_b's attachment to conv_a's message is a no-op.
    linked = await repo.link_attachments(conv_a.id, msg.id, [att_b.id])
    assert linked == []
    unlinked = await repo.get_attachment(att_b.id)
    assert unlinked is not None
    assert unlinked.message_id is None


@pytest.mark.asyncio
async def test_delete_conversation_cascades_attachments(pg_session: AsyncSession, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv = await _new_conv(repo, pg_session, owner_id)
    att = _attachment(conv.id)
    await repo.add_attachment(att)
    await pg_session.commit()

    await repo.delete(conv.id, owner_id)
    await pg_session.commit()

    assert await repo.get_attachment(att.id) is None


@pytest.mark.asyncio
async def test_message_with_tool_events_and_attachment_round_trips(
    pg_factory, pg_session: AsyncSession, owner_id
):
    repo = PostgresConversationRepository(pg_session)
    conv = await _new_conv(repo, pg_session, owner_id)
    att = _attachment(conv.id, "body")
    await repo.add_attachment(att)
    events = [
        ToolEvent(
            id=0,
            tool="web_search",
            query="cats",
            ok=True,
            summary="1 result",
            results=[ToolResult(title="Cats", url="https://cats.example")],
        ),
        ToolEvent(id=1, tool="fetch_page", url="https://cats.example"),
    ]
    msg = Message(id=uuid4(), role="user", content="hi", created_at=_now(), tool_events=events)
    await repo.save_message(msg, conv.id)
    await repo.link_attachments(conv.id, msg.id, [att.id])
    await pg_session.commit()

    async with pg_factory() as session:
        reloaded = await PostgresConversationRepository(session).get(conv.id, owner_id)

    assert reloaded is not None
    expected_attachment = _linked_copy(att, msg.id)
    assert reloaded.messages == [
        Message(
            id=msg.id,
            role="user",
            content="hi",
            created_at=msg.created_at,
            tool_events=events,
            attachments=[expected_attachment],
        )
    ]
    assert all(isinstance(e, ToolEvent) for e in reloaded.messages[0].tool_events or [])


def _linked_copy(attachment: Attachment, message_id) -> Attachment:
    """A plain (unsaved) copy of an attachment's values, linked to `message_id`."""
    return Attachment(
        id=attachment.id,
        conversation_id=attachment.conversation_id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        size=attachment.size,
        s3_key=attachment.s3_key,
        created_at=attachment.created_at,
        message_id=message_id,
        extracted_text=attachment.extracted_text,
    )
