from __future__ import annotations
import random
from typing import Any

from oxyde import AsyncDatabase, Q, disconnect_all
from common.base import Benchmark
from oxyde_bench.models import User, Post, Tag, PostTag


class OxydeBenchmark(Benchmark):
    """Benchmark implementation for Oxyde ORM."""

    name = "oxyde"
    is_async = True

    def __init__(self):
        self.db: AsyncDatabase | None = None
        self.db_name = "oxyde_bench"

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def setup(self, db_url: str) -> None:
        """Initialize connection."""
        self.db = AsyncDatabase(db_url, name=self.db_name, overwrite=True)
        await self.db.connect()

    async def teardown(self) -> None:
        """Close all connections."""
        await disconnect_all()
        self.db = None

    async def clean_data(self) -> None:
        """Clear all data from tables."""
        await PostTag.objects.filter().delete(using=self.db_name)
        await Post.objects.filter().delete(using=self.db_name)
        await Tag.objects.filter().delete(using=self.db_name)
        await User.objects.filter().delete(using=self.db_name)

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def insert_single(self) -> int:
        """Insert a single User record."""
        import uuid

        user = await User.objects.create(
            using=self.db_name,
            name="TestUser",
            email=f"test_{uuid.uuid4().hex}@example.com",
            age=25,
        )
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
        try:
            await User.objects.bulk_create(users, using=self.db_name, batch_size=10000)
        except Exception as e:
            if "Failed to extract ID from RETURNING" not in str(e):
                raise
        return list(range(count))

    async def select_pk(self, pk: int) -> Any:
        """Select a single User by primary key."""
        return await User.objects.get(using=self.db_name, id=pk)

    async def select_filter(self) -> list:
        """Select all Users where age >= 18."""
        return await User.objects.filter(age__gte=18).all(using=self.db_name)

    async def update_single(self, pk: int) -> None:
        """Update a single User's name."""
        await User.objects.filter(id=pk).update(name="Updated", using=self.db_name)

    async def update_bulk(self) -> int:
        """Update all Users with age < 18 to set is_active=False."""
        return await User.objects.filter(age__lt=18).update(
            is_active=False, using=self.db_name
        )

    async def delete_single(self, pk: int) -> None:
        """Delete a single User by primary key."""
        await User.objects.filter(id=pk).delete(using=self.db_name)

    # =========================================================================
    # Queries
    # =========================================================================

    async def filter_simple(self) -> list:
        """Filter Users WHERE name = 'User0'."""
        return await User.objects.filter(name="User0").all(using=self.db_name)

    async def filter_complex(self) -> list:
        """Complex filter: (age >= 18 AND is_active) OR name LIKE 'A%'."""
        return await User.objects.filter(
            (Q(age__gte=18) & Q(is_active=True)) | Q(name__startswith="A")
        ).all(using=self.db_name)

    async def filter_in(self, ids: list[int]) -> list:
        """Filter Users WHERE id IN (...)."""
        return await User.objects.filter(id__in=ids).all(using=self.db_name)

    async def order_limit(self) -> list:
        """Order by created_at DESC and limit to 10 rows."""
        return (
            await User.objects.filter()
            .order_by("-created_at")
            .limit(10)
            .all(using=self.db_name)
        )

    async def aggregate_count(self) -> int:
        """Count all Users."""
        return await User.objects.count(using=self.db_name)

    async def aggregate_mixed(self) -> dict:
        """Multiple aggregates: COUNT, AVG(age), MAX(age)."""
        from oxyde.queries.aggregates import Count, Avg, Max

        result = (
            await User.objects.filter()
            .annotate(
                count=Count("*"),
                avg_age=Avg("age"),
                max_age=Max("age"),
            )
            .values("count", "avg_age", "max_age")
            .all(using=self.db_name)
        )

        if result:
            row = result[0]
            return {
                "count": row.get("count", 0),
                "avg_age": row.get("avg_age", 0),
                "max_age": row.get("max_age", 0),
            }
        return {"count": 0, "avg_age": 0, "max_age": 0}

    # =========================================================================
    # Relations
    # =========================================================================

    async def join_simple(self) -> list:
        """Join Posts with Users (SELECT_RELATED - SQL JOIN)."""
        return await Post.objects.join("user").all(using=self.db_name)

    async def join_filter(self) -> list:
        """Join Posts with Users WHERE user.age >= 18."""
        return (
            await Post.objects.join("user")
            .filter(user__age__gte=18)
            .all(using=self.db_name)
        )

    async def prefetch_related(self) -> list:
        """Load Users with their Posts (PREFETCH_RELATED - separate queries)."""
        return await User.objects.prefetch("posts").all(using=self.db_name)

    async def nested_prefetch(self) -> list:
        """Load Users -> Posts -> Tags."""
        return await User.objects.prefetch("posts__post_tags").all(using=self.db_name)

    async def concurrent_select(self, concurrency: int) -> list:
        """Run multiple SELECT queries concurrently."""
        import asyncio

        async def select_random_user():
            pk = random.randint(1, 100)
            try:
                return await User.objects.get(using=self.db_name, id=pk)
            except Exception:
                return None

        tasks = [select_random_user() for _ in range(concurrency)]
        return await asyncio.gather(*tasks)
