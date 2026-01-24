import os
from dataclasses import dataclass


@dataclass
class BenchConfig:
    """Configuration for benchmark runs."""

    # Measurement settings
    iterations: int = 100  # Number of iterations per test
    warmup: int = 10  # Number of warmup iterations

    # Data size
    users_count: int = 1000  # Number of users to generate
    posts_per_user: int = 20  # Number of posts per user
    tags_count: int = 50  # Number of tags to generate

    # Database URLs (defaults, can be overridden via environment)
    postgres_url: str = os.environ.get(
        "POSTGRES_URL", "postgresql://bench:bench@localhost:5432/bench"
    )
    mysql_url: str = os.environ.get(
        "MYSQL_URL", "mysql://bench:bench@localhost:3306/bench"
    )
    sqlite_url: str = os.environ.get("SQLITE_URL", "sqlite:///bench.db")

    # Which ORMs to test (None = all available)
    orms: list[str] | None = None

    # Which tests to run (None = all)
    tests: list[str] | None = None

    # Output directory for results
    output_dir: str = "results"


# Default configuration instance
default_config = BenchConfig()


# Available test categories
TEST_CATEGORIES = {
    "crud": [
        "insert_single",
        "insert_bulk_100",
        "select_pk",
        "select_filter",
        "update_single",
        "update_bulk",
        "delete_single",
    ],
    "queries": [
        "filter_simple",
        "filter_complex",
        "filter_in",
        "order_limit",
        "aggregate_count",
        "aggregate_mixed",
    ],
    "relations": [
        "join_simple",
        "join_filter",
        "prefetch_related",
        "nested_prefetch",
    ],
    "concurrent": [
        "concurrent_10",
        "concurrent_25",
        "concurrent_50",
        "concurrent_75",
        "concurrent_100",
        "concurrent_150",
        "concurrent_200",
    ],
}


# All available tests
ALL_TESTS = [
    test for category_tests in TEST_CATEGORIES.values() for test in category_tests
]


# Mutating tests - these modify data and need setup/teardown between iterations
# to maintain consistent database state
MUTATING_TESTS = [
    "insert_single",
    "insert_bulk_100",
    "delete_single",
]

# Read-only tests - these only read data and don't need per-iteration reset
READ_ONLY_TESTS = [test for test in ALL_TESTS if test not in MUTATING_TESTS]


# Available ORMs
AVAILABLE_ORMS = [
    "oxyde",
    "asyncpg",
    "django",
    "sqlalchemy",
    "tortoise",
    "piccolo",
    "peewee",
    "sqlmodel",
]
