import asyncio
import random
from typing import Any

from sqlalchemy import select, update, delete, func, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from common.base import Benchmark
from sqlalchemy_bench.models import User, Post, Tag, PostTag


class SQLAlchemyBenchmark(Benchmark):
    """Benchmark implementation for SQLAlchemy 2.0 (async)."""

    name = "sqlalchemy"
    is_async = True

    def __init__(self):
        self.engine = None
        self.SessionLocal = None

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def setup(self, db_url: str) -> None:
        """Initialize SQLAlchemy async engine."""
        # Convert sync URL to async URL
        if db_url.startswith("sqlite://"):
            # SQLite URLs: sqlite+aiosqlite:/// for relative, sqlite+aiosqlite://// for absolute
            # Extract path after sqlite://
            path = db_url[9:]  # Remove "sqlite://"
            if path.startswith("/"):
                # Absolute path - need 4 slashes total
                async_url = f"sqlite+aiosqlite:///{path}"
            else:
                # Relative path - 3 slashes total
                async_url = f"sqlite+aiosqlite:///{path}"
        elif db_url.startswith("postgresql://"):
            async_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        elif db_url.startswith("mysql://"):
            async_url = db_url.replace("mysql://", "mysql+aiomysql://")
        else:
            async_url = db_url

        self.engine = create_async_engine(
            async_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )

        # Enable foreign keys for SQLite
        if "sqlite" in db_url.lower():

            @event.listens_for(self.engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        self.SessionLocal = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def teardown(self) -> None:
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()

    async def clean_data(self) -> None:
        """Clear all data from tables."""
        async with self.SessionLocal() as session:
            await session.execute(delete(PostTag))
            await session.execute(delete(Post))
            await session.execute(delete(Tag))
            await session.execute(delete(User))
            await session.commit()

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def insert_single(self) -> int:
        """Insert a single User record."""
        async with self.SessionLocal() as session:
            user = User(
                name="TestUser",
                email=f"test{random.randint(1, 999999)}@example.com",
                age=25,
            )
            session.add(user)
            await session.commit()
            # expire_on_commit=False keeps the id available without refresh
            return user.id

    async def insert_bulk(self, count: int) -> list[int]:
        """Insert multiple User records at once."""
        import uuid

        batch_id = uuid.uuid4().hex[:8]
        async with self.SessionLocal() as session:
            users = [
                User(
                    name=f"BulkUser{i}",
                    email=f"bulk_{batch_id}_{i}@example.com",
                    age=20 + i % 50,
                )
                for i in range(count)
            ]
            session.add_all(users)
            await session.commit()
            return [u.id for u in users]

    async def select_pk(self, pk: int) -> Any:
        """Select a single User by primary key."""
        async with self.SessionLocal() as session:
            result = await session.execute(select(User).where(User.id == pk))
            return result.scalar_one()

    async def select_filter(self) -> list:
        """Select all Users where age >= 18."""
        async with self.SessionLocal() as session:
            result = await session.execute(select(User).where(User.age >= 18))
            return result.scalars().all()

    async def update_single(self, pk: int) -> None:
        """Update a single User's name."""
        async with self.SessionLocal() as session:
            await session.execute(
                update(User).where(User.id == pk).values(name="Updated")
            )
            await session.commit()

    async def update_bulk(self) -> int:
        """Update all Users with age < 18 to set is_active=False."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                update(User).where(User.age < 18).values(is_active=False)
            )
            await session.commit()
            return result.rowcount

    async def delete_single(self, pk: int) -> None:
        """Delete a single User by primary key."""
        async with self.SessionLocal() as session:
            await session.execute(delete(User).where(User.id == pk))
            await session.commit()

    # =========================================================================
    # Queries
    # =========================================================================

    async def filter_simple(self) -> list:
        """Filter Users WHERE name = 'User0'."""
        async with self.SessionLocal() as session:
            result = await session.execute(select(User).where(User.name == "User0"))
            return result.scalars().all()

    async def filter_complex(self) -> list:
        """Complex filter: (age >= 18 AND is_active) OR name LIKE 'A%'."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(User).where(
                    ((User.age >= 18) & (User.is_active == True))
                    | (User.name.startswith("A"))
                )
            )
            return result.scalars().all()

    async def filter_in(self, ids: list[int]) -> list:
        """Filter Users WHERE id IN (...)."""
        async with self.SessionLocal() as session:
            result = await session.execute(select(User).where(User.id.in_(ids)))
            return result.scalars().all()

    async def order_limit(self) -> list:
        """Order by created_at DESC and limit to 10 rows."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(User).order_by(User.created_at.desc()).limit(10)
            )
            return result.scalars().all()

    async def aggregate_count(self) -> int:
        """Count all Users."""
        async with self.SessionLocal() as session:
            result = await session.execute(select(func.count(User.id)))
            return result.scalar()

    async def aggregate_mixed(self) -> dict:
        """Multiple aggregates: COUNT, AVG(age), MAX(age)."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(
                    func.count(User.id).label("count"),
                    func.avg(User.age).label("avg_age"),
                    func.max(User.age).label("max_age"),
                )
            )
            row = result.one()
            return {
                "count": row.count or 0,
                "avg_age": float(row.avg_age) if row.avg_age else 0.0,
                "max_age": row.max_age or 0,
            }

    # =========================================================================
    # Relations
    # =========================================================================

    async def join_simple(self) -> list:
        """Join Posts with Users."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(Post).join(User).options(selectinload(Post.user))
            )
            return result.scalars().all()

    async def join_filter(self) -> list:
        """Join Posts with Users WHERE user.age >= 18."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(Post)
                .join(User)
                .where(User.age >= 18)
                .options(selectinload(Post.user))
            )
            return result.scalars().all()

    async def prefetch_related(self) -> list:
        """Load Users with their Posts (avoid N+1)."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(User).options(selectinload(User.posts))
            )
            return result.scalars().all()

    async def nested_prefetch(self) -> list:
        """Load Users -> Posts -> Tags."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(User).options(
                    selectinload(User.posts)
                    .selectinload(Post.post_tags)
                    .selectinload(PostTag.tag)
                )
            )
            return result.scalars().all()

    async def concurrent_select(self, concurrency: int) -> list:
        """Run multiple SELECT queries concurrently."""

        async def select_random_user():
            async with self.SessionLocal() as session:
                pk = random.randint(1, 100)
                result = await session.execute(select(User).where(User.id == pk))
                return result.scalar_one_or_none()

        tasks = [select_random_user() for _ in range(concurrency)]
        return await asyncio.gather(*tasks)
