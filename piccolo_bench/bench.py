import asyncio
import random
from typing import Any

from piccolo.engine.sqlite import SQLiteEngine
from piccolo.engine.postgres import PostgresEngine
from piccolo.query.functions.aggregate import Avg, Max

from common.base import Benchmark
from piccolo_bench.models import User, Post, Tag, PostTag


class PiccoloBenchmark(Benchmark):
    """Benchmark implementation for Piccolo ORM."""

    name = "piccolo"
    is_async = True

    def __init__(self):
        self.db_url = None
        self.engine = None

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def setup(self, db_url: str) -> None:
        """Initialize Piccolo ORM."""
        self.db_url = db_url

        # Create engine based on database type
        # NOTE: Piccolo does NOT support MySQL, only PostgreSQL and SQLite
        if "mysql" in db_url.lower():
            raise ValueError("Piccolo does not support MySQL. Skipping.")
        elif "sqlite" in db_url.lower():
            path = db_url.replace("sqlite://", "")
            self.engine = SQLiteEngine(path=path)
        elif "postgres" in db_url.lower():
            # Parse PostgreSQL URL (with or without password)
            import re

            # Try with password first
            match = re.match(r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", db_url)
            if match:
                user, password, host, port, database = match.groups()
                self.engine = PostgresEngine(
                    config={
                        "database": database,
                        "user": user,
                        "password": password,
                        "host": host,
                        "port": int(port),
                    }
                )
            else:
                # Try without password
                match = re.match(r"postgresql://([^@]+)@([^:]+):(\d+)/(.+)", db_url)
                if match:
                    user, host, port, database = match.groups()
                    self.engine = PostgresEngine(
                        config={
                            "database": database,
                            "user": user,
                            "host": host,
                            "port": int(port),
                        }
                    )

        # Set up models with engine
        User._meta.db = self.engine
        Post._meta.db = self.engine
        Tag._meta.db = self.engine
        PostTag._meta.db = self.engine

        # Start connection pool for PostgreSQL
        if isinstance(self.engine, PostgresEngine):
            await self.engine.start_connection_pool(min_size=5, max_size=20)

    async def teardown(self) -> None:
        """Close Piccolo connections."""
        if self.engine and isinstance(self.engine, PostgresEngine):
            await self.engine.close_connection_pool()

    async def clean_data(self) -> None:
        """Clear all data from tables."""
        await PostTag.delete(force=True)
        await Post.delete(force=True)
        await Tag.delete(force=True)
        await User.delete(force=True)

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def insert_single(self) -> int:
        """Insert a single User record."""
        user = User(
            name="TestUser",
            email=f"test{random.randint(1, 999999)}@example.com",
            age=25,
        )
        await user.save()
        return user.id

    async def insert_bulk(self, count: int) -> list[int]:
        """Insert multiple User records at once."""
        import uuid

        batch_id = uuid.uuid4().hex[:8]
        users = [
            User(
                name=f"BulkUser{i}",
                email=f"bulk_{batch_id}_{i}@example.com",
                age=20 + i % 50,
            )
            for i in range(count)
        ]

        # Insert all at once - Piccolo handles batching internally
        await User.insert(*users)

        # Piccolo doesn't return IDs from bulk insert, return placeholder
        # This is consistent with how other ORMs handle this limitation
        return list(range(count))

    async def select_pk(self, pk: int) -> Any:
        """Select a single User by primary key."""
        return await User.objects().where(User.id == pk).first()

    async def select_filter(self) -> list:
        """Select all Users where age >= 18."""
        return await User.objects().where(User.age >= 18)

    async def update_single(self, pk: int) -> None:
        """Update a single User's name."""
        await User.update({User.name: "Updated"}).where(User.id == pk)

    async def update_bulk(self) -> int:
        """Update all Users with age < 18 to set is_active=False."""
        # Piccolo returns None for update, so we can't get row count easily
        await User.update({User.is_active: False}).where(User.age < 18)
        return 0  # Piccolo doesn't return affected rows

    async def delete_single(self, pk: int) -> None:
        """Delete a single User by primary key."""
        await User.delete().where(User.id == pk)

    # =========================================================================
    # Queries
    # =========================================================================

    async def filter_simple(self) -> list:
        """Filter Users WHERE name = 'User0'."""
        return await User.objects().where(User.name == "User0")

    async def filter_complex(self) -> list:
        """Complex filter: (age >= 18 AND is_active) OR name LIKE 'A%'."""
        return await User.objects().where(
            ((User.age >= 18) & (User.is_active == True)) | (User.name.like("A%"))
        )

    async def filter_in(self, ids: list[int]) -> list:
        """Filter Users WHERE id IN (...)."""
        return await User.objects().where(User.id.is_in(ids))

    async def order_limit(self) -> list:
        """Order by created_at DESC and limit to 10 rows."""
        return await User.objects().order_by(User.created_at, ascending=False).limit(10)

    async def aggregate_count(self) -> int:
        """Count all Users."""
        result = await User.count()
        return result

    async def aggregate_mixed(self) -> dict:
        """Multiple aggregates: COUNT, AVG(age), MAX(age)."""
        count_result = await User.count()
        avg_result = await User.select(Avg(User.age)).first()
        max_result = await User.select(Max(User.age)).first()

        return {
            "count": count_result or 0,
            "avg_age": float(avg_result.get("avg", 0)) if avg_result else 0.0,
            "max_age": max_result.get("max", 0) if max_result else 0,
        }

    # =========================================================================
    # Relations
    # =========================================================================

    async def join_simple(self) -> list:
        """Join Posts with Users."""
        return await Post.objects(Post.user_id)

    async def join_filter(self) -> list:
        """Join Posts with Users WHERE user.age >= 18."""
        return await Post.objects(Post.user_id).where(Post.user_id._.age >= 18)

    async def prefetch_related(self) -> list:
        """Load Users with their Posts (avoid N+1)."""
        users = await User.objects()
        user_ids = [u.id for u in users]
        posts = await Post.objects().where(Post.user_id.is_in(user_ids))

        # Group posts by user
        posts_by_user = {}
        for post in posts:
            uid = post.user_id
            if uid not in posts_by_user:
                posts_by_user[uid] = []
            posts_by_user[uid].append(post)

        for user in users:
            user._posts = posts_by_user.get(user.id, [])

        return users

    async def nested_prefetch(self) -> list:
        """Load Users -> Posts -> Tags."""
        users = await User.objects()
        user_ids = [u.id for u in users]
        posts = await Post.objects().where(Post.user_id.is_in(user_ids))
        post_ids = [p.id for p in posts]
        post_tags = await PostTag.objects().where(PostTag.post_id.is_in(post_ids))
        tag_ids = list(set(pt.tag_id for pt in post_tags if pt.tag_id))
        tags = await Tag.objects().where(Tag.id.is_in(tag_ids)) if tag_ids else []

        # Build tags lookup
        tags_by_id = {t.id: t for t in tags}

        # Group tags by post
        tags_by_post = {}
        for pt in post_tags:
            pid = pt.post_id
            if pid not in tags_by_post:
                tags_by_post[pid] = []
            if pt.tag_id and pt.tag_id in tags_by_id:
                tags_by_post[pid].append(tags_by_id[pt.tag_id])

        # Group posts by user with their tags
        posts_by_user = {}
        for post in posts:
            uid = post.user_id
            post._tags = tags_by_post.get(post.id, [])
            if uid not in posts_by_user:
                posts_by_user[uid] = []
            posts_by_user[uid].append(post)

        for user in users:
            user._posts = posts_by_user.get(user.id, [])

        return users

    async def concurrent_select(self, concurrency: int) -> list:
        """Run multiple SELECT queries concurrently."""

        async def select_random_user():
            pk = random.randint(1, 100)
            return await User.objects().where(User.id == pk).first()

        tasks = [select_random_user() for _ in range(concurrency)]
        return await asyncio.gather(*tasks)
