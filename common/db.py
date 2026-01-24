import asyncio
import os
from typing import Literal


DatabaseType = Literal["postgres", "mysql", "sqlite"]


def parse_db_url(db_type: DatabaseType, base_url: str | None = None) -> str:
    """Get database URL based on type.

    Args:
        db_type: Either "postgres", "mysql", or "sqlite"
        base_url: Optional custom database URL

    Returns:
        Full database connection URL
    """
    if base_url:
        return base_url

    if db_type == "postgres":
        return os.environ.get(
            "POSTGRES_URL", "postgresql://bench:bench@localhost:5432/bench"
        )
    elif db_type == "mysql":
        return os.environ.get("MYSQL_URL", "mysql://bench:bench@localhost:3306/bench")
    elif db_type == "sqlite":
        # Oxyde requires absolute path for SQLite
        abs_path = os.path.abspath("bench.db")
        return os.environ.get("SQLITE_URL", f"sqlite://{abs_path}")
    else:
        raise ValueError(f"Unknown database type: {db_type}")


async def ensure_postgres_ready(url: str, timeout: int = 30) -> bool:
    """Check if PostgreSQL is ready to accept connections.

    Args:
        url: PostgreSQL connection URL
        timeout: Maximum seconds to wait

    Returns:
        True if database is ready, False otherwise
    """
    import asyncpg

    deadline = asyncio.get_event_loop().time() + timeout

    while asyncio.get_event_loop().time() < deadline:
        try:
            # Parse URL to extract connection parameters
            conn = await asyncpg.connect(url)
            await conn.close()
            return True
        except (asyncpg.PostgresError, ConnectionRefusedError, OSError):
            await asyncio.sleep(0.5)

    return False


async def reset_postgres_schema(url: str) -> None:
    """Drop and recreate all tables in PostgreSQL database.

    Args:
        url: PostgreSQL connection URL
    """
    import asyncpg

    conn = await asyncpg.connect(url)
    try:
        # Drop all tables
        await conn.execute("""
            DROP SCHEMA public CASCADE;
            CREATE SCHEMA public;
            GRANT ALL ON SCHEMA public TO public;
        """)
    finally:
        await conn.close()


async def reset_sqlite_db(path: str = "bench.db") -> None:
    """Delete SQLite database file if it exists.

    Args:
        path: Path to SQLite database file
    """
    import os

    if os.path.exists(path):
        os.remove(path)
