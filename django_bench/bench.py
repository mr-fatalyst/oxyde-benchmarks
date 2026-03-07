import asyncio
import os
import random
from functools import wraps
from typing import Any

import django
from django.db import connection
from django.db.models import Q, Count, Avg, Max

from common.base import Benchmark


def run_sync(func):
    """Decorator to run sync Django code in a thread with proper connection handling."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        def _run():
            connection.ensure_connection()
            return func(*args, **kwargs)

        return await asyncio.to_thread(_run)

    return wrapper


class DjangoBenchmark(Benchmark):
    """Benchmark implementation for Django ORM."""

    name = "django"
    is_async = False  # Django is sync, wrapped in asyncio.to_thread

    def __init__(self):
        self.db_url = None
        self._django_setup_done = False

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def setup(self, db_url: str) -> None:
        """Initialize Django and configure database."""
        self.db_url = db_url

        # Configure Django settings
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bench.settings")

        # Update database configuration
        from django.conf import settings

        # Close existing connections and reset connection handlers before reconfiguring
        try:
            from django.db import connections

            connections.close_all()
            # Force Django to create new connection wrappers for new settings
            for alias in list(connections._connections):
                del connections._connections[alias]
        except Exception:
            pass

        # Common options for all database backends
        common_options = {
            "TIME_ZONE": None,
            "CONN_HEALTH_CHECKS": False,
            "CONN_MAX_AGE": None,
            "AUTOCOMMIT": True,
            "OPTIONS": {},
            "ATOMIC_REQUESTS": False,
        }

        if "sqlite" in db_url.lower():
            db_path = db_url.replace("sqlite://", "")
            settings.DATABASES["default"] = {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": db_path,
                **common_options,
            }
        elif "postgres" in db_url.lower():
            # Parse PostgreSQL URL (with or without password)
            import re

            match = re.match(r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", db_url)
            if match:
                user, password, host, port, dbname = match.groups()
                settings.DATABASES["default"] = {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": dbname,
                    "USER": user,
                    "PASSWORD": password,
                    "HOST": host,
                    "PORT": port,
                    **common_options,
                }
            else:
                # Try without password
                match = re.match(r"postgresql://([^@]+)@([^:]+):(\d+)/(.+)", db_url)
                if match:
                    user, host, port, dbname = match.groups()
                    settings.DATABASES["default"] = {
                        "ENGINE": "django.db.backends.postgresql",
                        "NAME": dbname,
                        "USER": user,
                        "HOST": host,
                        "PORT": port,
                        **common_options,
                    }
        elif "mysql" in db_url.lower():
            # Parse MySQL URL: mysql://user:pass@host:port/dbname
            from urllib.parse import urlparse

            parsed = urlparse(db_url)
            settings.DATABASES["default"] = {
                "ENGINE": "django.db.backends.mysql",
                "NAME": parsed.path.lstrip("/"),
                "USER": parsed.username or "bench",
                "PASSWORD": parsed.password or "bench",
                "HOST": parsed.hostname or "localhost",
                "PORT": str(parsed.port or 3306),
                **common_options,
            }

        if not self._django_setup_done:
            django.setup()
            self._django_setup_done = True

    async def teardown(self) -> None:
        """Close database connections."""

        def _close():
            connection.close()

        await asyncio.to_thread(_close)

    async def clean_data(self) -> None:
        """Clear all data from tables."""
        from django_bench.models import User, Post, Tag, PostTag

        @run_sync
        def _clean():
            PostTag.objects.all().delete()
            Post.objects.all().delete()
            Tag.objects.all().delete()
            User.objects.all().delete()

        await _clean()

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def insert_single(self) -> int:
        """Insert a single User record."""
        import uuid
        from django_bench.models import User

        email = f"test_{uuid.uuid4().hex}@example.com"

        @run_sync
        def _insert():
            user = User.objects.create(
                name="TestUser",
                email=email,
                age=25,
            )
            return user.id

        return await _insert()

    async def insert_bulk(self, count: int) -> list[int]:
        """Insert multiple User records at once."""
        import uuid
        from django_bench.models import User

        batch_id = uuid.uuid4().hex[:8]

        @run_sync
        def _insert():
            users = [
                User(
                    name=f"BulkUser{i}",
                    email=f"bulk_{batch_id}_{i}@example.com",
                    age=20 + i % 50,
                )
                for i in range(count)
            ]
            created = User.objects.bulk_create(users)
            return [u.id for u in created]

        return await _insert()

    async def select_pk(self, pk: int) -> Any:
        """Select a single User by primary key."""
        from django_bench.models import User

        @run_sync
        def _select():
            return User.objects.get(id=pk)

        return await _select()

    async def select_filter(self) -> list:
        """Select all Users where age >= 18."""
        from django_bench.models import User

        @run_sync
        def _select():
            return list(User.objects.filter(age__gte=18))

        return await _select()

    async def update_single(self, pk: int) -> None:
        """Update a single User's name."""
        from django_bench.models import User

        @run_sync
        def _update():
            User.objects.filter(id=pk).update(name="Updated")

        await _update()

    async def update_bulk(self) -> int:
        """Update all Users with age < 18 to set is_active=False."""
        from django_bench.models import User

        @run_sync
        def _update():
            return User.objects.filter(age__lt=18).update(is_active=False)

        return await _update()

    async def delete_single(self, pk: int) -> None:
        """Delete a single User by primary key."""
        from django_bench.models import User

        @run_sync
        def _delete():
            User.objects.filter(id=pk).delete()

        await _delete()

    # =========================================================================
    # Queries
    # =========================================================================

    async def filter_simple(self) -> list:
        """Filter Users WHERE name = 'User0'."""
        from django_bench.models import User

        @run_sync
        def _filter():
            return list(User.objects.filter(name="User0"))

        return await _filter()

    async def filter_complex(self) -> list:
        """Complex filter: (age >= 18 AND is_active) OR name LIKE 'A%'."""
        from django_bench.models import User

        @run_sync
        def _filter():
            return list(
                User.objects.filter(
                    Q(age__gte=18, is_active=True) | Q(name__startswith="A")
                )
            )

        return await _filter()

    async def filter_in(self, ids: list[int]) -> list:
        """Filter Users WHERE id IN (...)."""
        from django_bench.models import User

        @run_sync
        def _filter():
            return list(User.objects.filter(id__in=ids))

        return await _filter()

    async def order_limit(self) -> list:
        """Order by created_at DESC and limit to 10 rows."""
        from django_bench.models import User

        @run_sync
        def _query():
            return list(User.objects.order_by("-created_at")[:10])

        return await _query()

    async def aggregate_count(self) -> int:
        """Count all Users."""
        from django_bench.models import User

        @run_sync
        def _count():
            return User.objects.count()

        return await _count()

    async def aggregate_mixed(self) -> dict:
        """Multiple aggregates: COUNT, AVG(age), MAX(age)."""
        from django_bench.models import User

        @run_sync
        def _aggregate():
            result = User.objects.aggregate(
                count=Count("id"),
                avg_age=Avg("age"),
                max_age=Max("age"),
            )
            return {
                "count": result["count"] or 0,
                "avg_age": result["avg_age"] or 0,
                "max_age": result["max_age"] or 0,
            }

        return await _aggregate()

    # =========================================================================
    # Relations
    # =========================================================================

    async def join_simple(self) -> list:
        """Join Posts with Users."""
        from django_bench.models import Post

        @run_sync
        def _join():
            return list(Post.objects.select_related("user"))

        return await _join()

    async def join_filter(self) -> list:
        """Join Posts with Users WHERE user.age >= 18."""
        from django_bench.models import Post

        @run_sync
        def _join():
            return list(Post.objects.select_related("user").filter(user__age__gte=18))

        return await _join()

    async def prefetch_related(self) -> list:
        """Load Users with their Posts (avoid N+1)."""
        from django_bench.models import User

        @run_sync
        def _prefetch():
            return list(User.objects.prefetch_related("post_set"))

        return await _prefetch()

    async def nested_prefetch(self) -> list:
        """Load Users -> Posts -> Tags."""
        from django_bench.models import User

        @run_sync
        def _prefetch():
            return list(User.objects.prefetch_related("post_set__posttag_set__tag"))

        return await _prefetch()

    async def concurrent_select(self, concurrency: int) -> list:
        """Run multiple SELECT queries concurrently."""
        from django_bench.models import User

        async def select_random_user():
            @run_sync
            def _select():
                pk = random.randint(1, 1000)
                try:
                    return User.objects.get(id=pk)
                except User.DoesNotExist:
                    return None

            return await _select()

        tasks = [select_random_user() for _ in range(concurrency)]
        return await asyncio.gather(*tasks)
