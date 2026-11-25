from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def make_engine(database_url: str):
    # `pool_pre_ping` checks a pooled connection is still alive before handing it
    # to a request, transparently replacing dead ones. Without it a connection
    # the DB has since dropped (idle timeout, a Postgres restart during an
    # Infrastructure update, a CI network blip) surfaces as an immediate 500 on
    # the next request that reuses it. `pool_recycle` proactively retires
    # connections older than 30 min so they never get that stale.
    return create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
