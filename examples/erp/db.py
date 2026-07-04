import os

from sqlalchemy.ext.asyncio import create_async_engine


def _resolve_database_url() -> str:
    """Pick the database URL: in-memory for E2E, ``DATABASE_URL`` if set, else local SQLite.

    A plain ``postgresql://`` URL is normalised to the async ``postgresql+asyncpg://`` driver
    so the same value works whether it came from docker-compose or a developer's shell.
    """
    if os.environ.get("E2E_TESTING"):
        return "sqlite+aiosqlite:///:memory:"
    url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///erp.db")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


DB_URL = _resolve_database_url()

# check_same_thread is a SQLite-only connect arg; passing it to asyncpg would error.
_connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}

engine = create_async_engine(DB_URL, connect_args=_connect_args)
