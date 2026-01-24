import asyncio
import random
from typing import Any

from tortoise import Tortoise
from tortoise.functions import Count, Avg, Max
from tortoise.expressions import Q

from common.base import Benchmark
from tortoise_bench.models import User, Post, Tag, PostTag


class TortoiseBenchmark(Benchmark):
    """Benchmark implementation for Tortoise ORM."""

    name = "tortoise"
    is_async = True

    def __init__(self):
        self.db_url = None

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def setup(self, db_url: str) -> None:
        """Initialize Tortoise ORM."""
        import sys

        print(
            f"[TORTOISE] setup() called with db_url={db_url}",
            file=sys.stderr,
            flush=True,
        )
        self.db_url = db_url

        # Convert URL format for Tortoise
        if db_url.startswith("sqlite://"):
            path = db_url[9:]  # Remove "sqlite://"
            tortoise_url = f"sqlite://{path}"
        elif db_url.startswith("postgresql://"):
            tortoise_url = db_url.replace("postgresql://", "postgres://")
        else:
            tortoise_url = db_url

        print(
            f"[TORTOISE] Calling Tortoise.init() with url={tortoise_url}",
            file=sys.stderr,
            flush=True,
        )
        await Tortoise.init(
            db_url=tortoise_url,
            modules={"models": ["tortoise_bench.models"]},
        )
        print("[TORTOISE] Tortoise.init() completed", file=sys.stderr, flush=True)

    async def teardown(self) -> None:
        """Close Tortoise connections and reset singleton state."""
        import sys

        print("[TORTOISE] teardown() called", file=sys.stderr, flush=True)
        await Tortoise.close_connections()
        print("[TORTOISE] close_connections() done", file=sys.stderr, flush=True)
        # Reset singleton state for next init (required for repeated init/teardown cycles)
        await Tortoise._reset_apps()
        print("[TORTOISE] _reset_apps() done", file=sys.stderr, flush=True)
        Tortoise._inited = False
        print("[TORTOISE] teardown() completed", file=sys.stderr, flush=True)

    async def clean_data(self) -> None:
        """Clear all data from tables."""
        await PostTag.all().delete()
        await Post.all().delete()
        await Tag.all().delete()
        await User.all().delete()

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def insert_single(self) -> int:
        """Insert a single User record."""
        import uuid
        from datetime import datetime, timezone

        now_dt = datetime.now(timezone.utc)

        user = await User.create(
            name="TestUser",
            email=f"test_{uuid.uuid4().hex}@example.com",
            age=25,
            created_at=now_dt,
        )
        return user.id

    async def insert_bulk(self, count: int) -> list[int]:
        """Insert multiple User records at once."""
        import uuid
        from datetime import datetime, timezone

        batch_id = uuid.uuid4().hex[:8]
        now_dt = datetime.now(timezone.utc)

        users = [
            User(
                name=f"BulkUser{i}",
                email=f"bulk_{batch_id}_{i}@example.com",
                age=20 + i % 50,
                created_at=now_dt,
            )
            for i in range(count)
        ]
        await User.bulk_create(users)
        # Return placeholder IDs - bulk_create doesn't return IDs
        return list(range(count))

    async def select_pk(self, pk: int) -> Any:
        """Select a single User by primary key."""
        return await User.get(id=pk)

    async def select_filter(self) -> list:
        """Select all Users where age >= 18."""
        return await User.filter(age__gte=18).all()

    async def update_single(self, pk: int) -> None:
        """Update a single User's name."""
        await User.filter(id=pk).update(name="Updated")

    async def update_bulk(self) -> int:
        """Update all Users with age < 18 to set is_active=False."""
        return await User.filter(age__lt=18).update(is_active=False)

    async def delete_single(self, pk: int) -> None:
        """Delete a single User by primary key."""
        await User.filter(id=pk).delete()

    # =========================================================================
    # Queries
    # =========================================================================

    async def filter_simple(self) -> list:
        """Filter Users WHERE name = 'User0'."""
        return await User.filter(name="User0").all()

    async def filter_complex(self) -> list:
        """Complex filter: (age >= 18 AND is_active) OR name LIKE 'A%'."""
        return await User.filter(
            Q(age__gte=18, is_active=True) | Q(name__startswith="A")
        ).all()

    async def filter_in(self, ids: list[int]) -> list:
        """Filter Users WHERE id IN (...)."""
        return await User.filter(id__in=ids).all()

    async def order_limit(self) -> list:
        """Order by created_at DESC and limit to 10 rows."""
        return await User.all().order_by("-created_at").limit(10)

    async def aggregate_count(self) -> int:
        """Count all Users."""
        return await User.all().count()

    async def aggregate_mixed(self) -> dict:
        """Multiple aggregates: COUNT, AVG(age), MAX(age)."""
        result = (
            await User.all()
            .annotate(
                count=Count("id"),
                avg_age=Avg("age"),
                max_age=Max("age"),
            )
            .values("count", "avg_age", "max_age")
        )

        if result:
            return {
                "count": result[0]["count"] or 0,
                "avg_age": float(result[0]["avg_age"]) if result[0]["avg_age"] else 0.0,
                "max_age": result[0]["max_age"] or 0,
            }
        return {"count": 0, "avg_age": 0.0, "max_age": 0}

    # =========================================================================
    # Relations
    # =========================================================================

    async def join_simple(self) -> list:
        """Join Posts with Users."""
        return await Post.all().prefetch_related("user")

    async def join_filter(self) -> list:
        """Join Posts with Users WHERE user.age >= 18."""
        return await Post.filter(user__age__gte=18).prefetch_related("user").all()

    async def prefetch_related(self) -> list:
        """Load Users with their Posts (avoid N+1)."""
        return await User.all().prefetch_related("posts")

    async def nested_prefetch(self) -> list:
        """Load Users -> Posts -> Tags."""
        return await User.all().prefetch_related("posts__post_tags__tag")

    async def concurrent_select(self, concurrency: int) -> list:
        """Run multiple SELECT queries concurrently."""

        async def select_random_user():
            pk = random.randint(1, 100)
            try:
                return await User.get(id=pk)
            except Exception:
                return None

        tasks = [select_random_user() for _ in range(concurrency)]
        return await asyncio.gather(*tasks)
