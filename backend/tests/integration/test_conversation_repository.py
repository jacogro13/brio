from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import column, event, insert, select, table
from sqlalchemy.dialects.postgresql import JSONB
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
from chatbot.domain.conversation.model import Conversation, Message, Role, ToolEvent
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


@pytest_asyncio.fixture
async def owner_id(pg_session: AsyncSession):
    """A persisted user to own conversations (FK requires a real row)."""
    user = User(
        id=uuid4(),
        username=f"owner-{uuid4().hex[:8]}",
        hashed_password="x",
        created_at=datetime.now(tz=UTC),
    )
    await PostgresUserRepository(pg_session).add(user)
    await pg_session.commit()
    return user.id


# The messages table as raw JSONB (bypasses the ToolEventList type), to write
# and read the stored JSON exactly.
_raw_messages = table(
    "messages",
    column("id"),
    column("conversation_id"),
    column("role"),
    column("content"),
    column("tool_events", JSONB),
    column("created_at"),
)


def _conv(owner_id, title: str | None = None) -> Conversation:
    return Conversation(
        id=uuid4(),
        title=title,
        messages=[],
        created_at=datetime.now(tz=UTC),
        user_id=owner_id,
    )


def _msg(role: Role, content: str, **kw) -> Message:
    return Message(
        id=uuid4(),
        role=role,
        content=content,
        created_at=datetime.now(tz=UTC),
        **kw,
    )


@pytest.mark.asyncio
async def test_add_and_get_conversation(pg_session, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv = _conv(owner_id)
    await repo.add(conv)
    await pg_session.commit()

    fetched = await repo.get(conv.id, owner_id)
    assert fetched is not None
    assert fetched.id == conv.id
    assert fetched.user_id == owner_id


@pytest.mark.asyncio
async def test_get_scoped_to_owner(pg_session, owner_id):
    """A different user cannot read the conversation (cross-user 404)."""
    repo = PostgresConversationRepository(pg_session)
    conv = _conv(owner_id)
    await repo.add(conv)
    await pg_session.commit()

    assert await repo.get(conv.id, uuid4()) is None


@pytest.mark.asyncio
async def test_list_scoped_to_owner(pg_session, owner_id):
    repo = PostgresConversationRepository(pg_session)
    mine = _conv(owner_id, title="mine")
    await repo.add(mine)
    await pg_session.commit()

    mine_ids = {c.id for c in await repo.list(owner_id)}
    assert mine.id in mine_ids
    assert await repo.list(uuid4()) == []


@pytest.mark.asyncio
async def test_delete_scoped_to_owner(pg_session, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv = _conv(owner_id)
    await repo.add(conv)
    await pg_session.commit()

    # Wrong user can't delete it.
    await repo.delete(conv.id, uuid4())
    await pg_session.commit()
    assert await repo.get(conv.id, owner_id) is not None

    await repo.delete(conv.id, owner_id)
    await pg_session.commit()
    assert await repo.get(conv.id, owner_id) is None


@pytest.mark.asyncio
async def test_claim_orphans_adopts_ownerless_only(pg_session, owner_id):
    repo = PostgresConversationRepository(pg_session)
    orphan = Conversation(
        id=uuid4(),
        title="legacy",
        messages=[],
        created_at=datetime.now(tz=UTC),
        user_id=None,
    )
    owned = _conv(owner_id, title="already owned")
    await repo.add(orphan)
    await repo.add(owned)
    await pg_session.commit()

    claimer = uuid4()
    # The claimer must exist for the FK.
    await PostgresUserRepository(pg_session).add(
        User(
            id=claimer,
            username=f"claimer-{uuid4().hex[:8]}",
            hashed_password="x",
            created_at=datetime.now(tz=UTC),
        )
    )
    await pg_session.commit()

    n = await repo.claim_orphans(claimer)
    await pg_session.commit()

    assert n == 1
    assert (await repo.get(orphan.id, claimer)) is not None
    assert (await repo.get(owned.id, owner_id)) is not None  # untouched


@pytest.mark.asyncio
async def test_save_message(pg_session, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv = _conv(owner_id)
    await repo.add(conv)
    await repo.save_message(_msg("user", "Hello"), conv.id)
    await pg_session.commit()

    fetched = await repo.get(conv.id, owner_id)
    assert fetched is not None
    assert len(fetched.messages) == 1
    assert fetched.messages[0].content == "Hello"


@pytest.mark.asyncio
async def test_save_message_round_trips_thinking(pg_session, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv = _conv(owner_id)
    await repo.add(conv)
    await repo.save_message(_msg("assistant", "the answer", thinking="the reasoning"), conv.id)
    await pg_session.commit()

    fetched = await repo.get(conv.id, owner_id)
    assert fetched is not None
    assert fetched.messages[0].thinking == "the reasoning"


@pytest.mark.asyncio
async def test_save_message_round_trips_tool_events(pg_session, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv = _conv(owner_id)
    await repo.add(conv)
    tool_events = [
        {
            "id": 0,
            "tool": "web_search",
            "query": "cats",
            "ok": True,
            "summary": "1 result",
            "results": [{"title": "Cats", "url": "https://cats.example"}],
        }
    ]
    events = [ToolEvent.from_json(e) for e in tool_events]
    message = _msg("assistant", "the answer", tool_events=events)
    await repo.save_message(message, conv.id)
    await pg_session.commit()

    fetched = await repo.get(conv.id, owner_id)
    stored = await pg_session.scalar(
        select(_raw_messages.c.tool_events).where(_raw_messages.c.id == message.id)
    )
    assert fetched is not None
    assert fetched.messages[0].tool_events == events
    assert stored == tool_events  # same JSON as before typed ToolEvents


# Records exactly as the tool loop has written them since Phase 6: a finished
# search, a failed fetch (empty results), and a call the user stopped before it
# ended (no ok/summary/results).
_LEGACY_TOOL_EVENTS = [
    {
        "id": 0,
        "tool": "web_search",
        "query": "cats",
        "ok": True,
        "summary": "2 results",
        "results": [
            {"title": "Cats", "url": "https://cats.example"},
            {"title": "More cats", "url": "https://more.example"},
        ],
    },
    {
        "id": 1,
        "tool": "fetch_page",
        "url": "http://10.0.0.1/",
        "ok": False,
        "summary": "fetch error: blocked",
        "results": [],
    },
    {"id": 2, "tool": "web_search", "query": "dogs"},
]


@pytest.mark.asyncio
async def test_legacy_tool_events_row_loads(pg_session, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv = _conv(owner_id)
    await repo.add(conv)
    await pg_session.execute(
        insert(_raw_messages).values(
            id=uuid4(),
            conversation_id=conv.id,
            role="assistant",
            content="old reply",
            tool_events=_LEGACY_TOOL_EVENTS,
            created_at=datetime.now(tz=UTC),
        )
    )
    await pg_session.commit()

    fetched = await repo.get(conv.id, owner_id)

    assert fetched is not None
    events = fetched.messages[0].tool_events
    assert events is not None
    assert [e.to_json() for e in events] == _LEGACY_TOOL_EVENTS
    assert events[2].ok is None


@pytest.mark.asyncio
async def test_delete_messages_removes_only_listed_ids(pg_session, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv = _conv(owner_id, title="edit")
    await repo.add(conv)
    keep = _msg("user", "keep")
    drop_a = _msg("assistant", "drop-a")
    drop_b = _msg("user", "drop-b")
    for m in (keep, drop_a, drop_b):
        await repo.save_message(m, conv.id)
    await pg_session.commit()

    await repo.delete_messages(conv.id, [drop_a.id, drop_b.id])
    await pg_session.commit()

    fetched = await repo.get(conv.id, owner_id)
    assert fetched is not None
    assert [m.content for m in fetched.messages] == ["keep"]


@pytest.mark.asyncio
async def test_delete_messages_empty_list_is_noop(pg_session, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv = _conv(owner_id, title="noop")
    await repo.add(conv)
    await repo.save_message(_msg("user", "stay"), conv.id)
    await pg_session.commit()

    await repo.delete_messages(conv.id, [])
    await pg_session.commit()

    fetched = await repo.get(conv.id, owner_id)
    assert fetched is not None
    assert len(fetched.messages) == 1


@pytest.mark.asyncio
async def test_update_settings_round_trips(pg_session, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv = _conv(owner_id, title="cfg")
    await repo.add(conv)
    await pg_session.commit()

    await repo.update_settings(
        conv.id,
        {
            "temperature": 0.0,  # explicit 0 must persist, not be dropped
            "max_tokens": 512,
            "system_prompt_override": "Be terse.",
        },
    )
    await pg_session.commit()

    fetched = await repo.get(conv.id, owner_id)
    assert fetched is not None
    assert fetched.temperature == 0.0
    assert fetched.max_tokens == 512
    assert fetched.system_prompt_override == "Be terse."

    # An explicit None resets an override back to the default.
    await repo.update_settings(conv.id, {"temperature": None})
    await pg_session.commit()
    fetched = await repo.get(conv.id, owner_id)
    assert fetched is not None
    assert fetched.temperature is None
    assert fetched.max_tokens == 512  # untouched


@pytest.mark.asyncio
async def test_delete_conversation_cascades_messages(pg_session, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv = _conv(owner_id, title="To delete")
    await repo.add(conv)
    await repo.save_message(_msg("user", "bye"), conv.id)
    await pg_session.commit()

    await repo.delete(conv.id, owner_id)
    await pg_session.commit()

    assert await repo.get(conv.id, owner_id) is None


class StatementRecorder:
    """Collects the SQL the engine sends, via its `before_cursor_execute` event."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.statements: list[str] = []
        self._engine = engine.sync_engine
        event.listen(self._engine, "before_cursor_execute", self._record)

    def _record(self, conn, cursor, statement, parameters, context, executemany) -> None:
        self.statements.append(statement)

    def stop(self) -> None:
        event.remove(self._engine, "before_cursor_execute", self._record)


@pytest.mark.asyncio
async def test_list_returns_conversations_without_loading_messages(
    pg_engine, pg_factory, pg_session, owner_id
):
    repo = PostgresConversationRepository(pg_session)
    conv = _conv(owner_id, title="has messages")
    await repo.add(conv)
    await repo.save_message(_msg("user", "Hello"), conv.id)
    await pg_session.commit()
    recorder = StatementRecorder(pg_engine)

    async with pg_factory() as session:
        listed = await PostgresConversationRepository(session).list(owner_id)
    recorder.stop()

    assert [c.id for c in listed] == [conv.id]
    assert listed[0].messages == []
    assert not [s for s in recorder.statements if "FROM messages" in s]


@pytest.mark.asyncio
async def test_get_then_delete_messages_then_save_message_commits(pg_factory, pg_session, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv = _conv(owner_id)
    await repo.add(conv)
    first, edited, reply = _msg("user", "Q1"), _msg("user", "Q2"), _msg("assistant", "A2")
    for message in (first, edited, reply):
        await repo.save_message(message, conv.id)
    await pg_session.commit()

    # The edit flow, in one session: load, drop the edited turn onwards, save anew.
    async with pg_factory() as session:
        edit_repo = PostgresConversationRepository(session)
        loaded = await edit_repo.get(conv.id, owner_id)
        assert loaded is not None
        await edit_repo.delete_messages(conv.id, [m.id for m in loaded.messages[1:]])
        replacement = _msg("user", "Q2, edited")
        await edit_repo.save_message(replacement, conv.id)
        await session.commit()

    async with pg_factory() as session:
        reloaded = await PostgresConversationRepository(session).get(conv.id, owner_id)
    assert reloaded is not None
    assert [m.content for m in reloaded.messages] == ["Q1", "Q2, edited"]


@pytest.mark.asyncio
async def test_update_settings_on_loaded_conversation_persists(pg_factory, pg_session, owner_id):
    repo = PostgresConversationRepository(pg_session)
    conv = _conv(owner_id)
    conv.system_prompt_override = "be brief"
    await repo.add(conv)
    await pg_session.commit()
    updates = {"temperature": 0.3, "max_tokens": 64, "system_prompt_override": None}

    # As UpdateConversationUseCase does: load, update, then assign on the entity.
    async with pg_factory() as session:
        settings_repo = PostgresConversationRepository(session)
        loaded = await settings_repo.get(conv.id, owner_id)
        assert loaded is not None
        await settings_repo.update_settings(conv.id, updates)
        for key, value in updates.items():
            setattr(loaded, key, value)
        await session.commit()

    async with pg_factory() as session:
        reloaded = await PostgresConversationRepository(session).get(conv.id, owner_id)
    assert reloaded is not None
    assert (reloaded.temperature, reloaded.max_tokens, reloaded.system_prompt_override) == (
        0.3,
        64,
        None,
    )
