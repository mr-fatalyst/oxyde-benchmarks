from typing import Any
from urllib.parse import urlparse

import asyncpg
import aiosqlite
import aiomysql

from common.base import Benchmark
from asyncpg_bench import queries


class AsyncpgBenchmark(Benchmark):
    """Benchmark using raw asyncpg/aiosqlite/aiomysql (no ORM overhead)."""

    name = "asyncpg"  # Will be updated in setup() based on DB type
    is_async = True

    def __init__(self):
        self.pool: asyncpg.Pool | None = None
        self.sqlite_conn: aiosqlite.Connection | None = None
        self.mysql_pool: aiomysql.Pool | None = None
        self.db_type = "postgres"  # postgres, sqlite, or mysql
        self.db_url = ""

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def setup(self, db_url: str) -> None:
        """Initialize connection pool."""
        self.db_url = db_url

        if "sqlite" in db_url.lower():
            self.db_type = "sqlite"
            self.name = "aiosqlite"
            db_path = db_url.replace("sqlite://", "")
            self.sqlite_conn = await aiosqlite.connect(db_path)
            await self.sqlite_conn.execute("PRAGMA foreign_keys=ON")
        elif "mysql" in db_url.lower():
            self.db_type = "mysql"
            self.name = "aiomysql"
            params = self._parse_mysql_url(db_url)
            self.mysql_pool = await aiomysql.create_pool(
                host=params["host"],
                port=params["port"],
                user=params["user"],
                password=params["password"],
                db=params["db"],
                minsize=5,
                maxsize=20,
            )
        else:
            self.db_type = "postgres"
            self.name = "asyncpg"
            self.pool = await asyncpg.create_pool(
                db_url,
                min_size=5,
                max_size=20,
            )

    def _parse_mysql_url(self, db_url: str) -> dict:
        """Parse MySQL URL into connection parameters."""
        parsed = urlparse(db_url)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 3306,
            "user": parsed.username or "bench",
            "password": parsed.password or "bench",
            "db": parsed.path.lstrip("/") or "bench",
        }

    async def teardown(self) -> None:
        """Close all connections."""
        if self.pool:
            await self.pool.close()
        if self.sqlite_conn:
            await self.sqlite_conn.close()
        if self.mysql_pool:
            self.mysql_pool.close()
            await self.mysql_pool.wait_closed()

    async def clean_data(self) -> None:
        """Clear all data from tables."""
        if self.db_type == "sqlite":
            await self.sqlite_conn.execute(queries.TRUNCATE_POST_TAGS)
            await self.sqlite_conn.execute(queries.TRUNCATE_POSTS)
            await self.sqlite_conn.execute(queries.TRUNCATE_TAGS)
            await self.sqlite_conn.execute(queries.TRUNCATE_USERS)
            await self.sqlite_conn.commit()
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(queries.TRUNCATE_POST_TAGS)
                    await cursor.execute(queries.TRUNCATE_POSTS)
                    await cursor.execute(queries.TRUNCATE_TAGS)
                    await cursor.execute(queries.TRUNCATE_USERS)
                await conn.commit()
        else:
            async with self.pool.acquire() as conn:
                await conn.execute(queries.TRUNCATE_POST_TAGS)
                await conn.execute(queries.TRUNCATE_POSTS)
                await conn.execute(queries.TRUNCATE_TAGS)
                await conn.execute(queries.TRUNCATE_USERS)

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def insert_single(self) -> int:
        """Insert a single User record."""
        import uuid

        email = f"test_{uuid.uuid4().hex}@example.com"

        if self.db_type == "sqlite":
            # Use execute_fetchall for fair comparison (single round-trip)
            rows = await self.sqlite_conn.execute_fetchall(
                queries.INSERT_USER_SQLITE, ("TestUser", email, 25)
            )
            await self.sqlite_conn.commit()
            return rows[0][0] if rows else None
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        queries.INSERT_USER_MYSQL, ("TestUser", email, 25)
                    )
                    user_id = cursor.lastrowid
                await conn.commit()
            return user_id
        else:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(queries.INSERT_USER, "TestUser", email, 25)
                return row["id"]

    async def insert_bulk(self, count: int) -> list[int]:
        """Insert multiple User records at once."""
        import uuid

        batch_id = uuid.uuid4().hex[:8]
        records = [
            (f"BulkUser{i}", f"bulk_{batch_id}_{i}@example.com", 20 + i % 50)
            for i in range(count)
        ]

        if self.db_type == "sqlite":
            await self.sqlite_conn.executemany(
                "INSERT INTO users (name, email, age) VALUES (?, ?, ?)",
                records,
            )
            await self.sqlite_conn.commit()
            return list(range(count))
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.executemany(
                        "INSERT INTO users (name, email, age) VALUES (%s, %s, %s)",
                        records,
                    )
                await conn.commit()
            return list(range(count))
        else:
            async with self.pool.acquire() as conn:
                await conn.executemany(
                    "INSERT INTO users (name, email, age) VALUES ($1, $2, $3)",
                    records,
                )
                return list(range(count))

    async def select_pk(self, pk: int) -> Any:
        """Select a single User by primary key."""
        if self.db_type == "sqlite":
            # Use execute_fetchall for fair comparison (single round-trip)
            rows = await self.sqlite_conn.execute_fetchall(
                queries.SELECT_USER_BY_ID_SQLITE, (pk,)
            )
            return rows[0] if rows else None
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(queries.SELECT_USER_BY_ID_MYSQL, (pk,))
                    return await cursor.fetchone()
        else:
            async with self.pool.acquire() as conn:
                return await conn.fetchrow(queries.SELECT_USER_BY_ID, pk)

    async def select_filter(self) -> list:
        """Select all Users where age >= 18."""
        if self.db_type == "sqlite":
            # Use execute_fetchall for fair comparison (single round-trip)
            return await self.sqlite_conn.execute_fetchall(
                queries.SELECT_USERS_AGE_GTE_SQLITE, (18,)
            )
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(queries.SELECT_USERS_AGE_GTE_MYSQL, (18,))
                    return await cursor.fetchall()
        else:
            async with self.pool.acquire() as conn:
                return await conn.fetch(queries.SELECT_USERS_AGE_GTE, 18)

    async def update_single(self, pk: int) -> None:
        """Update a single User's name."""
        if self.db_type == "sqlite":
            await self.sqlite_conn.execute(
                queries.UPDATE_USER_NAME_SQLITE, ("Updated", pk)
            )
            await self.sqlite_conn.commit()
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        queries.UPDATE_USER_NAME_MYSQL, ("Updated", pk)
                    )
                await conn.commit()
        else:
            async with self.pool.acquire() as conn:
                await conn.execute(queries.UPDATE_USER_NAME, "Updated", pk)

    async def update_bulk(self) -> int:
        """Update all Users with age < 18 to set is_active=False."""
        if self.db_type == "sqlite":
            cursor = await self.sqlite_conn.execute(
                queries.UPDATE_USERS_BULK_SQLITE, (0, 18)
            )
            await self.sqlite_conn.commit()
            return cursor.rowcount
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(queries.UPDATE_USERS_BULK_MYSQL, (False, 18))
                    rowcount = cursor.rowcount
                await conn.commit()
            return rowcount
        else:
            async with self.pool.acquire() as conn:
                result = await conn.execute(queries.UPDATE_USERS_BULK, False, 18)
                return int(result.split()[-1]) if result else 0

    async def delete_single(self, pk: int) -> None:
        """Delete a single User by primary key."""
        if self.db_type == "sqlite":
            await self.sqlite_conn.execute(queries.DELETE_USER_SQLITE, (pk,))
            await self.sqlite_conn.commit()
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(queries.DELETE_USER_MYSQL, (pk,))
                await conn.commit()
        else:
            async with self.pool.acquire() as conn:
                await conn.execute(queries.DELETE_USER, pk)

    # =========================================================================
    # Queries
    # =========================================================================

    async def filter_simple(self) -> list:
        """Filter Users WHERE name = 'User0'."""
        if self.db_type == "sqlite":
            # Use execute_fetchall for fair comparison (single round-trip)
            return await self.sqlite_conn.execute_fetchall(
                queries.FILTER_SIMPLE_SQLITE, ("User0",)
            )
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(queries.FILTER_SIMPLE_MYSQL, ("User0",))
                    return await cursor.fetchall()
        else:
            async with self.pool.acquire() as conn:
                return await conn.fetch(queries.FILTER_SIMPLE, "User0")

    async def filter_complex(self) -> list:
        """Complex filter: (age >= 18 AND is_active) OR name LIKE 'A%'."""
        if self.db_type == "sqlite":
            # Use execute_fetchall for fair comparison (single round-trip)
            return await self.sqlite_conn.execute_fetchall(
                queries.FILTER_COMPLEX_SQLITE, (18, 1, "A%")
            )
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(queries.FILTER_COMPLEX_MYSQL, (18, True, "A%"))
                    return await cursor.fetchall()
        else:
            async with self.pool.acquire() as conn:
                return await conn.fetch(queries.FILTER_COMPLEX, 18, True, "A%")

    async def filter_in(self, ids: list[int]) -> list:
        """Filter Users WHERE id IN (...)."""
        if self.db_type == "sqlite":
            # Use execute_fetchall for fair comparison (single round-trip)
            placeholders = ",".join(["?" for _ in ids])
            query = f"SELECT * FROM users WHERE id IN ({placeholders})"
            return await self.sqlite_conn.execute_fetchall(query, ids)
        elif self.db_type == "mysql":
            placeholders = ",".join(["%s" for _ in ids])
            query = f"SELECT * FROM users WHERE id IN ({placeholders})"
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, ids)
                    return await cursor.fetchall()
        else:
            placeholders = ",".join(["$" + str(i + 1) for i in range(len(ids))])
            query = f"SELECT * FROM users WHERE id IN ({placeholders})"
            async with self.pool.acquire() as conn:
                return await conn.fetch(query, *ids)

    async def order_limit(self) -> list:
        """Order by created_at DESC and limit to 10 rows."""
        if self.db_type == "sqlite":
            # Use execute_fetchall for fair comparison (single round-trip)
            return await self.sqlite_conn.execute_fetchall(
                queries.ORDER_LIMIT_SQLITE, (10,)
            )
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(queries.ORDER_LIMIT_MYSQL, (10,))
                    return await cursor.fetchall()
        else:
            async with self.pool.acquire() as conn:
                return await conn.fetch(queries.ORDER_LIMIT, 10)

    async def aggregate_count(self) -> int:
        """Count all Users."""
        if self.db_type == "sqlite":
            # Use execute_fetchall for fair comparison (single round-trip)
            rows = await self.sqlite_conn.execute_fetchall(queries.AGGREGATE_COUNT)
            return rows[0][0] if rows else 0
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(queries.AGGREGATE_COUNT)
                    row = await cursor.fetchone()
                    return row["count"] if row else 0
        else:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(queries.AGGREGATE_COUNT)
                return row["count"]

    async def aggregate_mixed(self) -> dict:
        """Multiple aggregates: COUNT, AVG(age), MAX(age)."""
        if self.db_type == "sqlite":
            # Use execute_fetchall for fair comparison (single round-trip)
            rows = await self.sqlite_conn.execute_fetchall(queries.AGGREGATE_MIXED)
            if rows and rows[0]:
                row = rows[0]
                return {"count": row[0], "avg_age": row[1], "max_age": row[2]}
            return {"count": 0, "avg_age": 0, "max_age": 0}
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(queries.AGGREGATE_MIXED)
                    row = await cursor.fetchone()
                    if row:
                        return {
                            "count": row["count"],
                            "avg_age": row["avg_age"],
                            "max_age": row["max_age"],
                        }
                    return {"count": 0, "avg_age": 0, "max_age": 0}
        else:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(queries.AGGREGATE_MIXED)
                return {
                    "count": row["count"],
                    "avg_age": row["avg_age"],
                    "max_age": row["max_age"],
                }

    # =========================================================================
    # Relations
    # =========================================================================

    async def join_simple(self) -> list:
        """Join Posts with Users."""
        if self.db_type == "sqlite":
            # Use execute_fetchall for fair comparison (single round-trip)
            return await self.sqlite_conn.execute_fetchall(queries.JOIN_SIMPLE)
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(queries.JOIN_SIMPLE)
                    return await cursor.fetchall()
        else:
            async with self.pool.acquire() as conn:
                return await conn.fetch(queries.JOIN_SIMPLE)

    async def join_filter(self) -> list:
        """Join Posts with Users WHERE user.age >= 18."""
        if self.db_type == "sqlite":
            # Use execute_fetchall for fair comparison (single round-trip)
            return await self.sqlite_conn.execute_fetchall(
                queries.JOIN_FILTER_SQLITE, (18,)
            )
        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(queries.JOIN_FILTER_MYSQL, (18,))
                    return await cursor.fetchall()
        else:
            async with self.pool.acquire() as conn:
                return await conn.fetch(queries.JOIN_FILTER, 18)

    async def prefetch_related(self) -> list:
        """Load Users with their Posts (avoid N+1)."""
        if self.db_type == "sqlite":
            # Use execute_fetchall for fair comparison (single round-trip per query)
            users = await self.sqlite_conn.execute_fetchall("SELECT * FROM users")
            posts = await self.sqlite_conn.execute_fetchall("SELECT * FROM posts")
            # Group posts by user_id (index 1 for sqlite tuple)
            posts_by_user = {}
            for post in posts:
                uid = post[1]
                if uid not in posts_by_user:
                    posts_by_user[uid] = []
                posts_by_user[uid].append(post)
            return [(user, posts_by_user.get(user[0], [])) for user in users]

        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("SELECT * FROM users")
                    users = await cursor.fetchall()
                    await cursor.execute("SELECT * FROM posts")
                    posts = await cursor.fetchall()
            posts_by_user = {}
            for post in posts:
                uid = post["user_id"]
                if uid not in posts_by_user:
                    posts_by_user[uid] = []
                posts_by_user[uid].append(post)
            return [(user, posts_by_user.get(user["id"], [])) for user in users]

        else:
            async with self.pool.acquire() as conn:
                users = await conn.fetch("SELECT * FROM users")
                posts = await conn.fetch("SELECT * FROM posts")
            posts_by_user = {}
            for post in posts:
                uid = post["user_id"]
                if uid not in posts_by_user:
                    posts_by_user[uid] = []
                posts_by_user[uid].append(post)
            return [(user, posts_by_user.get(user["id"], [])) for user in users]

    async def nested_prefetch(self) -> list:
        """Load Users -> Posts -> Tags."""
        if self.db_type == "sqlite":
            # Use execute_fetchall for fair comparison (single round-trip per query)
            users = await self.sqlite_conn.execute_fetchall("SELECT * FROM users")
            posts = await self.sqlite_conn.execute_fetchall("SELECT * FROM posts")
            post_tags = await self.sqlite_conn.execute_fetchall(
                "SELECT * FROM post_tags"
            )
            tags = await self.sqlite_conn.execute_fetchall("SELECT * FROM tags")
            # Build lookups using tuple indices
            tags_by_id = {tag[0]: tag for tag in tags}
            tags_by_post = {}
            for pt in post_tags:
                pid, tid = pt[1], pt[2]
                if pid not in tags_by_post:
                    tags_by_post[pid] = []
                if tid in tags_by_id:
                    tags_by_post[pid].append(tags_by_id[tid])
            posts_by_user = {}
            for post in posts:
                uid, pid = post[1], post[0]
                if uid not in posts_by_user:
                    posts_by_user[uid] = []
                posts_by_user[uid].append((post, tags_by_post.get(pid, [])))
            return [(user, posts_by_user.get(user[0], [])) for user in users]

        elif self.db_type == "mysql":
            async with self.mysql_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("SELECT * FROM users")
                    users = await cursor.fetchall()
                    await cursor.execute("SELECT * FROM posts")
                    posts = await cursor.fetchall()
                    await cursor.execute("SELECT * FROM post_tags")
                    post_tags = await cursor.fetchall()
                    await cursor.execute("SELECT * FROM tags")
                    tags = await cursor.fetchall()
            tags_by_id = {tag["id"]: tag for tag in tags}
            tags_by_post = {}
            for pt in post_tags:
                pid, tid = pt["post_id"], pt["tag_id"]
                if pid not in tags_by_post:
                    tags_by_post[pid] = []
                if tid in tags_by_id:
                    tags_by_post[pid].append(tags_by_id[tid])
            posts_by_user = {}
            for post in posts:
                uid, pid = post["user_id"], post["id"]
                if uid not in posts_by_user:
                    posts_by_user[uid] = []
                posts_by_user[uid].append((post, tags_by_post.get(pid, [])))
            return [(user, posts_by_user.get(user["id"], [])) for user in users]

        else:
            async with self.pool.acquire() as conn:
                users = await conn.fetch("SELECT * FROM users")
                posts = await conn.fetch("SELECT * FROM posts")
                post_tags = await conn.fetch("SELECT * FROM post_tags")
                tags = await conn.fetch("SELECT * FROM tags")
            tags_by_id = {tag["id"]: tag for tag in tags}
            tags_by_post = {}
            for pt in post_tags:
                pid, tid = pt["post_id"], pt["tag_id"]
                if pid not in tags_by_post:
                    tags_by_post[pid] = []
                if tid in tags_by_id:
                    tags_by_post[pid].append(tags_by_id[tid])
            posts_by_user = {}
            for post in posts:
                uid, pid = post["user_id"], post["id"]
                if uid not in posts_by_user:
                    posts_by_user[uid] = []
                posts_by_user[uid].append((post, tags_by_post.get(pid, [])))
            return [(user, posts_by_user.get(user["id"], [])) for user in users]
