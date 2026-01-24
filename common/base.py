from abc import ABC, abstractmethod
from typing import Any


class Benchmark(ABC):
    """Base class for all ORM benchmarks.

    Each ORM implementation must subclass this and implement all abstract methods.
    """

    name: str  # "oxyde", "django", "sqlalchemy", etc.
    is_async: bool = True

    # =========================================================================
    # Lifecycle
    # =========================================================================

    @abstractmethod
    async def setup(self, db_url: str) -> None:
        """Initialize connection and create tables.

        Args:
            db_url: Database connection URL
        """
        pass

    @abstractmethod
    async def teardown(self) -> None:
        """Close all connections and cleanup resources."""
        pass

    @abstractmethod
    async def clean_data(self) -> None:
        """Clear all data from tables (TRUNCATE or DELETE)."""
        pass

    async def prepare_test_data(
        self, users: int = 100, posts_per_user: int = 5
    ) -> None:
        """Prepare test data for benchmarks.

        Default implementation does nothing - each ORM should override if needed
        or use the common prepare_data() function.
        """
        pass

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    @abstractmethod
    async def insert_single(self) -> int:
        """Insert a single User record.

        Returns:
            ID of the inserted user
        """
        pass

    @abstractmethod
    async def insert_bulk(self, count: int) -> list[int]:
        """Insert multiple User records at once.

        Args:
            count: Number of users to insert

        Returns:
            List of inserted user IDs
        """
        pass

    @abstractmethod
    async def select_pk(self, pk: int) -> Any:
        """Select a single User by primary key.

        Args:
            pk: Primary key value

        Returns:
            User instance or dict
        """
        pass

    @abstractmethod
    async def select_filter(self) -> list:
        """Select all Users where age >= 18.

        Returns:
            List of user instances
        """
        pass

    @abstractmethod
    async def update_single(self, pk: int) -> None:
        """Update a single User's name.

        Args:
            pk: Primary key of user to update
        """
        pass

    @abstractmethod
    async def update_bulk(self) -> int:
        """Update all Users with age < 18 to set is_active=False.

        Returns:
            Number of rows updated
        """
        pass

    @abstractmethod
    async def delete_single(self, pk: int) -> None:
        """Delete a single User by primary key.

        Args:
            pk: Primary key of user to delete
        """
        pass

    # =========================================================================
    # Queries
    # =========================================================================

    @abstractmethod
    async def filter_simple(self) -> list:
        """Filter Users WHERE name = 'User0'.

        Returns:
            List of matching users
        """
        pass

    @abstractmethod
    async def filter_complex(self) -> list:
        """Complex filter: (age >= 18 AND is_active) OR name LIKE 'A%'.

        Returns:
            List of matching users
        """
        pass

    @abstractmethod
    async def filter_in(self, ids: list[int]) -> list:
        """Filter Users WHERE id IN (...).

        Args:
            ids: List of IDs to match

        Returns:
            List of matching users
        """
        pass

    @abstractmethod
    async def order_limit(self) -> list:
        """Order by created_at DESC and limit to 10 rows.

        Returns:
            First 10 users ordered by created_at descending
        """
        pass

    @abstractmethod
    async def aggregate_count(self) -> int:
        """Count all Users.

        Returns:
            Total number of users
        """
        pass

    @abstractmethod
    async def aggregate_mixed(self) -> dict:
        """Multiple aggregates: COUNT, AVG(age), MAX(age).

        Returns:
            Dict with keys: count, avg_age, max_age
        """
        pass

    # =========================================================================
    # Relations
    # =========================================================================

    @abstractmethod
    async def join_simple(self) -> list:
        """Join Posts with Users.

        Returns:
            List of posts with author data loaded
        """
        pass

    @abstractmethod
    async def join_filter(self) -> list:
        """Join Posts with Users WHERE user.age >= 18.

        Returns:
            List of posts from adult users
        """
        pass

    @abstractmethod
    async def prefetch_related(self) -> list:
        """Load Users with their Posts (avoid N+1).

        Returns:
            List of users with posts preloaded
        """
        pass

    @abstractmethod
    async def nested_prefetch(self) -> list:
        """Load Users -> Posts -> Tags.

        Returns:
            List of users with posts and tags preloaded
        """
        pass

    # =========================================================================
    # Concurrent (optional for async ORMs)
    # =========================================================================

    async def concurrent_select(self, n: int) -> list:
        """Execute N parallel select_pk queries.

        Default implementation using asyncio.gather.
        Override for custom behavior.

        Args:
            n: Number of concurrent queries

        Returns:
            List of results
        """
        import asyncio
        import random

        tasks = [self.select_pk(random.randint(1, 1000)) for _ in range(n)]
        return await asyncio.gather(*tasks, return_exceptions=True)
