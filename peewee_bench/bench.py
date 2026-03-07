import asyncio
import random
from typing import Any

from peewee import SqliteDatabase, PostgresqlDatabase, MySQLDatabase, fn, prefetch

from common.base import Benchmark
from peewee_bench.models import User, Post, Tag, PostTag


class PeeweeBenchmark(Benchmark):
    """Benchmark implementation for Peewee ORM."""

    name = "peewee"
    is_async = False  # Peewee is sync, wrapped in asyncio.to_thread

    def __init__(self):
        self.db = None
        self._db_url = None

    def _run_sync(self, func):
        """Run sync function ensuring DB is connected in the thread.

        IMPORTANT: Opens connection, runs function, closes connection.
        This prevents connection leaks in threaded operations.
        """

        def wrapper():
            # Peewee uses thread-local connections, so connect in this thread
            self.db.connect(reuse_if_open=True)
            try:
                return func()
            finally:
                # Always close to prevent connection leaks
                if not self.db.is_closed():
                    self.db.close()

        return wrapper

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def setup(self, db_url: str) -> None:
        """Initialize Peewee database."""
        self._db_url = db_url

        # Create database instance based on URL
        if "sqlite" in db_url.lower():
            path = db_url.replace("sqlite://", "")
            self.db = SqliteDatabase(path, pragmas={"foreign_keys": 1})
        elif "mysql" in db_url.lower():
            # Parse MySQL URL
            from urllib.parse import urlparse

            parsed = urlparse(db_url)
            self.db = MySQLDatabase(
                parsed.path.lstrip("/"),
                user=parsed.username or "bench",
                password=parsed.password or "bench",
                host=parsed.hostname or "localhost",
                port=parsed.port or 3306,
            )
        elif "postgres" in db_url.lower():
            # Parse PostgreSQL URL (with or without password)
            import re

            # Try with password first
            match = re.match(r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", db_url)
            if match:
                user, password, host, port, database = match.groups()
                self.db = PostgresqlDatabase(
                    database,
                    user=user,
                    password=password,
                    host=host,
                    port=int(port),
                )
            else:
                # Try without password
                match = re.match(r"postgresql://([^@]+)@([^:]+):(\d+)/(.+)", db_url)
                if match:
                    user, host, port, database = match.groups()
                    self.db = PostgresqlDatabase(
                        database,
                        user=user,
                        host=host,
                        port=int(port),
                    )

        if self.db is None:
            raise ValueError(f"Failed to parse database URL: {db_url}")

        # Bind models to database
        self.db.bind([User, Post, Tag, PostTag])

    async def teardown(self) -> None:
        """Close database connections."""
        if self.db:
            if not self.db.is_closed():
                self.db.close()
            self.db = None

    async def clean_data(self) -> None:
        """Clear all data from tables."""

        def _clean():
            PostTag.delete().execute()
            Post.delete().execute()
            Tag.delete().execute()
            User.delete().execute()

        await asyncio.to_thread(self._run_sync(_clean))

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def insert_single(self) -> int:
        """Insert a single User record."""
        import uuid

        email = f"test_{uuid.uuid4().hex}@example.com"

        def _insert():
            user = User.create(
                name="TestUser",
                email=email,
                age=25,
            )
            return user.id

        return await asyncio.to_thread(self._run_sync(_insert))

    async def insert_bulk(self, count: int) -> list[int]:
        """Insert multiple User records at once."""
        import uuid

        batch_id = uuid.uuid4().hex[:8]

        def _insert():
            users = [
                {
                    "name": f"BulkUser{i}",
                    "email": f"bulk_{batch_id}_{i}@example.com",
                    "age": 20 + i % 50,
                }
                for i in range(count)
            ]
            User.insert_many(users).execute()
            # Return placeholder IDs - insert_many doesn't return IDs
            return list(range(count))

        return await asyncio.to_thread(self._run_sync(_insert))

    async def select_pk(self, pk: int) -> Any:
        """Select a single User by primary key."""

        def _select():
            return User.get_by_id(pk)

        return await asyncio.to_thread(self._run_sync(_select))

    async def select_filter(self) -> list:
        """Select all Users where age >= 18."""

        def _select():
            return list(User.select().where(User.age >= 18))

        return await asyncio.to_thread(self._run_sync(_select))

    async def update_single(self, pk: int) -> None:
        """Update a single User's name."""

        def _update():
            User.update(name="Updated").where(User.id == pk).execute()

        await asyncio.to_thread(self._run_sync(_update))

    async def update_bulk(self) -> int:
        """Update all Users with age < 18 to set is_active=False."""

        def _update():
            return User.update(is_active=False).where(User.age < 18).execute()

        return await asyncio.to_thread(self._run_sync(_update))

    async def delete_single(self, pk: int) -> None:
        """Delete a single User by primary key."""

        def _delete():
            User.delete().where(User.id == pk).execute()

        await asyncio.to_thread(self._run_sync(_delete))

    # =========================================================================
    # Queries
    # =========================================================================

    async def filter_simple(self) -> list:
        """Filter Users WHERE name = 'User0'."""

        def _filter():
            return list(User.select().where(User.name == "User0"))

        return await asyncio.to_thread(self._run_sync(_filter))

    async def filter_complex(self) -> list:
        """Complex filter: (age >= 18 AND is_active) OR name LIKE 'A%'."""

        def _filter():
            return list(
                User.select().where(
                    ((User.age >= 18) & (User.is_active == True))
                    | (User.name.startswith("A"))
                )
            )

        return await asyncio.to_thread(self._run_sync(_filter))

    async def filter_in(self, ids: list[int]) -> list:
        """Filter Users WHERE id IN (...)."""

        def _filter():
            return list(User.select().where(User.id.in_(ids)))

        return await asyncio.to_thread(self._run_sync(_filter))

    async def order_limit(self) -> list:
        """Order by created_at DESC and limit to 10 rows."""

        def _query():
            return list(User.select().order_by(User.created_at.desc()).limit(10))

        return await asyncio.to_thread(self._run_sync(_query))

    async def aggregate_count(self) -> int:
        """Count all Users."""

        def _count():
            return User.select().count()

        return await asyncio.to_thread(self._run_sync(_count))

    async def aggregate_mixed(self) -> dict:
        """Multiple aggregates: COUNT, AVG(age), MAX(age)."""

        def _aggregate():
            result = User.select(
                fn.COUNT(User.id).alias("count"),
                fn.AVG(User.age).alias("avg_age"),
                fn.MAX(User.age).alias("max_age"),
            ).scalar(as_tuple=True)
            # Result is a tuple when using scalar with as_tuple=True
            if result:
                count, avg_age, max_age = result
                return {
                    "count": count or 0,
                    "avg_age": float(avg_age) if avg_age else 0.0,
                    "max_age": max_age or 0,
                }
            return {"count": 0, "avg_age": 0.0, "max_age": 0}

        return await asyncio.to_thread(self._run_sync(_aggregate))

    # =========================================================================
    # Relations
    # =========================================================================

    async def join_simple(self) -> list:
        """Join Posts with Users."""

        def _join():
            return list(Post.select(Post, User).join(User))

        return await asyncio.to_thread(self._run_sync(_join))

    async def join_filter(self) -> list:
        """Join Posts with Users WHERE user.age >= 18."""

        def _join():
            return list(Post.select(Post, User).join(User).where(User.age >= 18))

        return await asyncio.to_thread(self._run_sync(_join))

    async def prefetch_related(self) -> list:
        """Load Users with their Posts (avoid N+1)."""

        def _prefetch():
            # Use Peewee's prefetch() to avoid N+1 queries
            users = User.select()
            posts = Post.select()
            return list(prefetch(users, posts))

        return await asyncio.to_thread(self._run_sync(_prefetch))

    async def nested_prefetch(self) -> list:
        """Load Users -> Posts -> Tags."""

        def _prefetch():
            # Use Peewee's prefetch() with multiple related models
            users = User.select()
            posts = Post.select()
            post_tags = PostTag.select()
            tags = Tag.select()
            return list(prefetch(users, posts, post_tags, tags))

        return await asyncio.to_thread(self._run_sync(_prefetch))

    async def concurrent_select(self, concurrency: int) -> list:
        """Run multiple SELECT queries concurrently."""

        async def select_random_user():
            def _select():
                pk = random.randint(1, 1000)
                try:
                    return User.get_by_id(pk)
                except Exception:
                    return None

            return await asyncio.to_thread(self._run_sync(_select))

        tasks = [select_random_user() for _ in range(concurrency)]
        return await asyncio.gather(*tasks)
