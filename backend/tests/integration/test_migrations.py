"""Safety net: the migrated schema equals what the ORM maps.

Runs every migration on a fresh Postgres, then asks Alembic's autogenerate to
compare the result with the ORM metadata. An empty diff means the mapping
describes exactly the tables, columns, types, indexes and FKs the migrations
create — so swapping the mapping needs no new migration.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import MetaData, create_engine
from testcontainers.postgres import PostgresContainer

from chatbot.adapters.persistence.postgres import orm

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migrated_url():
    with PostgresContainer("postgres:15-alpine") as pg:
        sync_url = pg.get_connection_url()
        async_url = sync_url.replace("psycopg2", "asyncpg")
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("DATABASE_URL", async_url)
            config = Config(str(BACKEND_DIR / "alembic.ini"))
            config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
            command.upgrade(config, "head")
        yield sync_url


@pytest.mark.parametrize("metadata", [orm.metadata], ids=["imperative"])
def test_migrated_schema_matches_orm_metadata(migrated_url: str, metadata: MetaData):
    engine = create_engine(migrated_url)

    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), metadata)
    engine.dispose()

    assert diff == []
