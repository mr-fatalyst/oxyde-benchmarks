import asyncpg
import aiosqlite
import aiomysql


# PostgreSQL schema
POSTGRES_SCHEMA = """
DROP TABLE IF EXISTS post_tags CASCADE;
DROP TABLE IF EXISTS tags CASCADE;
DROP TABLE IF EXISTS posts CASCADE;
DROP TABLE IF EXISTS users CASCADE;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    age INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT DEFAULT '',
    views INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE post_tags (
    id SERIAL PRIMARY KEY,
    post_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
"""


# MySQL schema
MYSQL_SCHEMA = """
DROP TABLE IF EXISTS post_tags;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    age INT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT,
    views INT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE post_tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL,
    tag_id INT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
) ENGINE=InnoDB;
"""


# SQLite schema
SQLITE_SCHEMA = """
DROP TABLE IF EXISTS post_tags;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    age INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    views INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE post_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
"""


async def setup_schema(db_url: str) -> None:
    """Drop and recreate all tables.

    Args:
        db_url: Database connection URL
    """
    if "sqlite" in db_url.lower():
        await _setup_sqlite(db_url)
    elif "postgres" in db_url.lower():
        await _setup_postgres(db_url)
    elif "mysql" in db_url.lower():
        await _setup_mysql(db_url)
    else:
        raise ValueError(f"Unsupported database: {db_url}")


async def _setup_sqlite(db_url: str) -> None:
    """Setup SQLite schema."""
    # Extract path from URL
    if "sqlite://" in db_url:
        db_path = db_url.replace("sqlite://", "")
    else:
        db_path = ":memory:"

    # Ensure file exists
    if db_path != ":memory:":
        import os

        if not os.path.exists(db_path):
            open(db_path, "a").close()

    conn = await aiosqlite.connect(db_path)
    try:
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.executescript(SQLITE_SCHEMA)
        await conn.commit()
    finally:
        await conn.close()


async def _setup_postgres(db_url: str) -> None:
    """Setup PostgreSQL schema."""
    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(POSTGRES_SCHEMA)
    finally:
        await conn.close()


async def kill_all_connections(db_url: str) -> None:
    """Kill all connections to the database.

    This ensures clean state between ORM benchmarks.
    """
    if "postgres" in db_url.lower():
        await _kill_postgres_connections(db_url)
    elif "mysql" in db_url.lower():
        await _kill_mysql_connections(db_url)
    # SQLite doesn't need connection killing - it's file-based


async def _kill_postgres_connections(db_url: str) -> None:
    """Kill all PostgreSQL connections."""
    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute("""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND pid <> pg_backend_pid()
              AND usename = 'bench'
        """)
    except Exception:
        pass
    finally:
        await conn.close()


async def _kill_mysql_connections(db_url: str) -> None:
    """Kill all MySQL connections.

    NOTE: MySQL/MariaDB may have connection limits. This aggressively kills
    all connections for the bench user to ensure clean state between ORMs.
    """
    import asyncio

    params = _parse_mysql_url(db_url)
    conn = await aiomysql.connect(**params)
    try:
        async with conn.cursor() as cursor:
            # Get all connections for bench user except current
            # Also kill connections in sleep/idle state
            await cursor.execute("""
                SELECT id FROM information_schema.processlist
                WHERE user = 'bench' AND id != CONNECTION_ID()
            """)
            rows = await cursor.fetchall()
            killed = 0
            for (pid,) in rows:
                try:
                    await cursor.execute(f"KILL {pid}")
                    killed += 1
                except Exception:
                    pass
            # Small delay to let MySQL clean up
            if killed > 0:
                await asyncio.sleep(0.1)
    except Exception:
        pass
    finally:
        conn.close()
        # Extra delay after closing our connection
        await asyncio.sleep(0.05)


def _parse_mysql_url(db_url: str) -> dict:
    """Parse MySQL URL into connection parameters."""
    # mysql://user:pass@host:port/dbname
    from urllib.parse import urlparse

    parsed = urlparse(db_url)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": parsed.username or "bench",
        "password": parsed.password or "bench",
        "db": parsed.path.lstrip("/") or "bench",
    }


async def _setup_mysql(db_url: str) -> None:
    """Setup MySQL schema."""
    params = _parse_mysql_url(db_url)
    conn = await aiomysql.connect(**params)
    try:
        async with conn.cursor() as cursor:
            # Execute each statement separately (MySQL doesn't support multi-statement by default)
            for statement in MYSQL_SCHEMA.strip().split(";"):
                statement = statement.strip()
                if statement:
                    await cursor.execute(statement)
        await conn.commit()
    finally:
        conn.close()


async def prepare_data(db_url: str, users: int = 1000, posts_per_user: int = 5) -> None:
    """Populate database with test data using raw SQL.

    Args:
        db_url: Database connection URL
        users: Number of users to create
        posts_per_user: Number of posts per user
    """

    if "sqlite" in db_url.lower():
        await _prepare_sqlite(db_url, users, posts_per_user)
    elif "postgres" in db_url.lower():
        await _prepare_postgres(db_url, users, posts_per_user)
    elif "mysql" in db_url.lower():
        await _prepare_mysql(db_url, users, posts_per_user)
    else:
        raise ValueError(f"Unsupported database: {db_url}")


async def _prepare_sqlite(db_url: str, users: int, posts_per_user: int) -> None:
    """Prepare test data for SQLite."""
    import random

    # Handle both sqlite:// and sqlite:/// formats
    if db_url.startswith("sqlite:///"):
        db_path = db_url[len("sqlite://") :]  # Keep the leading / for absolute paths
    elif db_url.startswith("sqlite://"):
        db_path = db_url[len("sqlite://") :]
    else:
        db_path = ":memory:"

    conn = await aiosqlite.connect(db_path)
    try:
        await conn.execute("PRAGMA foreign_keys=ON")

        # Insert users
        user_data = [
            (
                f"User{i}",
                f"user{i}@example.com",
                random.randint(15, 70),
                random.choice([0, 1]),
            )
            for i in range(users)
        ]
        await conn.executemany(
            "INSERT INTO users (name, email, age, is_active) VALUES (?, ?, ?, ?)",
            user_data,
        )

        # Get user IDs
        cursor = await conn.execute("SELECT id FROM users")
        user_ids = [row[0] for row in await cursor.fetchall()]

        # Insert posts
        post_data = []
        for user_id in user_ids:
            for j in range(posts_per_user):
                post_data.append(
                    (
                        user_id,
                        f"Post {j} by user {user_id}",
                        f"Content for post {j}" * 10,
                        random.randint(0, 1000),
                    )
                )
        await conn.executemany(
            "INSERT INTO posts (user_id, title, content, views) VALUES (?, ?, ?, ?)",
            post_data,
        )

        # Insert tags
        tag_data = [(f"tag{i}",) for i in range(50)]
        await conn.executemany("INSERT INTO tags (name) VALUES (?)", tag_data)

        # Get post and tag IDs
        cursor = await conn.execute("SELECT id FROM posts LIMIT 1000")
        post_ids = [row[0] for row in await cursor.fetchall()]

        cursor = await conn.execute("SELECT id FROM tags")
        tag_ids = [row[0] for row in await cursor.fetchall()]

        # Insert post_tags
        post_tag_data = []
        for post_id in post_ids:
            num_tags = random.randint(1, 3)
            selected_tags = random.sample(tag_ids, num_tags)
            for tag_id in selected_tags:
                post_tag_data.append((post_id, tag_id))
        await conn.executemany(
            "INSERT INTO post_tags (post_id, tag_id) VALUES (?, ?)", post_tag_data
        )

        await conn.commit()
    finally:
        await conn.close()


async def _prepare_postgres(db_url: str, users: int, posts_per_user: int) -> None:
    """Prepare test data for PostgreSQL."""
    import random

    conn = await asyncpg.connect(db_url)
    try:
        # Insert users
        user_data = [
            (
                f"User{i}",
                f"user{i}@example.com",
                random.randint(15, 70),
                random.choice([True, False]),
            )
            for i in range(users)
        ]
        await conn.executemany(
            "INSERT INTO users (name, email, age, is_active) VALUES ($1, $2, $3, $4)",
            user_data,
        )

        # Get user IDs
        rows = await conn.fetch("SELECT id FROM users")
        user_ids = [row["id"] for row in rows]

        # Insert posts
        post_data = []
        for user_id in user_ids:
            for j in range(posts_per_user):
                post_data.append(
                    (
                        user_id,
                        f"Post {j} by user {user_id}",
                        f"Content for post {j}" * 10,
                        random.randint(0, 1000),
                    )
                )
        await conn.executemany(
            "INSERT INTO posts (user_id, title, content, views) VALUES ($1, $2, $3, $4)",
            post_data,
        )

        # Insert tags
        tag_data = [(f"tag{i}",) for i in range(50)]
        await conn.executemany("INSERT INTO tags (name) VALUES ($1)", tag_data)

        # Get post and tag IDs
        rows = await conn.fetch("SELECT id FROM posts LIMIT 1000")
        post_ids = [row["id"] for row in rows]

        rows = await conn.fetch("SELECT id FROM tags")
        tag_ids = [row["id"] for row in rows]

        # Insert post_tags
        post_tag_data = []
        for post_id in post_ids:
            num_tags = random.randint(1, 3)
            selected_tags = random.sample(tag_ids, num_tags)
            for tag_id in selected_tags:
                post_tag_data.append((post_id, tag_id))
        await conn.executemany(
            "INSERT INTO post_tags (post_id, tag_id) VALUES ($1, $2)", post_tag_data
        )
    finally:
        await conn.close()


async def _prepare_mysql(db_url: str, users: int, posts_per_user: int) -> None:
    """Prepare test data for MySQL."""
    import random

    params = _parse_mysql_url(db_url)
    conn = await aiomysql.connect(**params)
    try:
        async with conn.cursor() as cursor:
            # Insert users
            user_data = [
                (
                    f"User{i}",
                    f"user{i}@example.com",
                    random.randint(15, 70),
                    random.choice([True, False]),
                )
                for i in range(users)
            ]
            await cursor.executemany(
                "INSERT INTO users (name, email, age, is_active) VALUES (%s, %s, %s, %s)",
                user_data,
            )

            # Get user IDs
            await cursor.execute("SELECT id FROM users")
            user_ids = [row[0] for row in await cursor.fetchall()]

            # Insert posts
            post_data = []
            for user_id in user_ids:
                for j in range(posts_per_user):
                    post_data.append(
                        (
                            user_id,
                            f"Post {j} by user {user_id}",
                            f"Content for post {j}" * 10,
                            random.randint(0, 1000),
                        )
                    )
            await cursor.executemany(
                "INSERT INTO posts (user_id, title, content, views) VALUES (%s, %s, %s, %s)",
                post_data,
            )

            # Insert tags
            tag_data = [(f"tag{i}",) for i in range(50)]
            await cursor.executemany("INSERT INTO tags (name) VALUES (%s)", tag_data)

            # Get post and tag IDs
            await cursor.execute("SELECT id FROM posts LIMIT 1000")
            post_ids = [row[0] for row in await cursor.fetchall()]

            await cursor.execute("SELECT id FROM tags")
            tag_ids = [row[0] for row in await cursor.fetchall()]

            # Insert post_tags
            post_tag_data = []
            for post_id in post_ids:
                num_tags = random.randint(1, 3)
                selected_tags = random.sample(tag_ids, num_tags)
                for tag_id in selected_tags:
                    post_tag_data.append((post_id, tag_id))
            await cursor.executemany(
                "INSERT INTO post_tags (post_id, tag_id) VALUES (%s, %s)", post_tag_data
            )

        await conn.commit()
    finally:
        conn.close()
