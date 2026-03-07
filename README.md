# Oxyde ORM Benchmarks

Comprehensive benchmark suite comparing Python ORM performance, including Oxyde (async ORM with Rust core).

## Overview

This project benchmarks 7 Python ORMs across 3 databases:

| ORM | Type | Notes |
|-----|------|-------|
| **Oxyde** | async | Rust core via PyO3 |
| **Django ORM** | sync→async | Industry standard |
| **SQLAlchemy 2.0** | async | Most popular |
| **Tortoise ORM** | async | Django-like async |
| **Piccolo** | async | Modern typed ORM |
| **Peewee** | sync→async | Lightweight |
| **SQLModel** | async | Pydantic-based |

Raw drivers (asyncpg, aiomysql, aiosqlite) are also tested as baseline.

**Databases:** PostgreSQL, MySQL, SQLite

## Benchmark Results

See the full benchmark report with charts and detailed analysis:

**[View Benchmark Report (REPORT.md)](REPORT.md)**

Latest results from January 23, 2026 comparing all 7 ORMs across PostgreSQL, MySQL, and SQLite.

## Quick Start

### Docker (Recommended)

Isolated, reproducible benchmarks with all databases included:

```bash
# Build image
make docker-build

# Run PostgreSQL benchmarks
make docker-pg

# Run MySQL benchmarks
make docker-mysql

# Run SQLite benchmarks
make docker-sqlite

# Run all databases
make docker-all

# With options
make docker-pg ORMS=oxyde,sqlalchemy ITERATIONS=200
```

### Local Development

```bash
# Install dependencies
make install

# Run benchmarks (requires local DB)
make run          # SQLite
make run-pg       # PostgreSQL
make run-mysql    # MySQL

# Quick test
make run-quick ORMS=oxyde
```

## Docker Details

The Docker image includes PostgreSQL, MySQL, and SQLite in a single container:

```bash
# Build
docker build -t oxyde-benchmarks .

# Run with resource limits (recommended for reproducibility)
docker run --rm \
  --memory=4g --cpus=2 \
  -v $(pwd)/results:/app/results \
  oxyde-benchmarks --db postgres

# Run specific ORMs
docker run --rm \
  -v $(pwd)/results:/app/results \
  oxyde-benchmarks --db mysql --orms oxyde,django,sqlalchemy
```

Or use docker-compose:

```bash
docker-compose run bench-postgres
docker-compose run bench-mysql
docker-compose run bench-sqlite
```

## Test Categories

### CRUD Operations (7 tests)
- `insert_single` - Insert one record
- `insert_bulk_100` - Bulk insert 100 records
- `select_pk` - Select by primary key
- `select_filter` - Filter with WHERE clause
- `update_single` - Update one record
- `update_bulk` - Bulk update
- `delete_single` - Delete one record

### Queries (6 tests)
- `filter_simple` - Simple WHERE clause
- `filter_complex` - Complex boolean logic
- `filter_in` - WHERE IN clause
- `order_limit` - ORDER BY + LIMIT
- `aggregate_count` - COUNT(*)
- `aggregate_mixed` - COUNT, AVG, MAX

### Relations (4 tests)
- `join_simple` - Basic JOIN
- `join_filter` - JOIN with WHERE
- `prefetch_related` - Avoid N+1 queries
- `nested_prefetch` - Multi-level prefetch

### Concurrent (7 tests, async only)
- `concurrent_10` - 10 parallel queries
- `concurrent_25` - 25 parallel queries
- `concurrent_50` - 50 parallel queries
- `concurrent_75` - 75 parallel queries
- `concurrent_100` - 100 parallel queries
- `concurrent_150` - 150 parallel queries
- `concurrent_200` - 200 parallel queries

## Command Line Options

```bash
python bench.py [OPTIONS]

Options:
  --db TEXT          Database: postgres, mysql, sqlite, all
  --db-url TEXT      Custom database URL
  --orms TEXT        Comma-separated list of ORMs
  --tests TEXT       Comma-separated list of tests
  --category TEXT    Test category: crud, queries, relations, concurrent, mutating, readonly
  --iterations INT   Number of iterations (default: 100)
  --warmup INT       Warmup iterations (default: 10)
  --output TEXT      Output directory (default: results)
  --logs             Show subprocess stderr for debugging
```

## Results

Results are saved to `results/{timestamp}_{database}/`:

```
results/2026-01-23_09-12-34_postgres/
├── env.json             # System info, versions
├── postgres.json        # Raw benchmark data
└── postgres_report.md   # Markdown report
```

## Methodology

- **Isolation**: Database reset before each test
- **Warmup**: 10 iterations (discarded)
- **Measurement**: 100 iterations per test
- **Metrics**: ops/sec, mean, median, stddev, p95, p99
- **Fair comparison**: Same SQL, same data volume, same pool settings

### SQLite Note

Each ORM is benchmarked with its default configuration — no manual tuning is applied. Oxyde enables `journal_mode=WAL` and `synchronous=NORMAL` by default for SQLite connections, while other ORMs use SQLite defaults (`journal_mode=DELETE`, `synchronous=FULL`). This significantly impacts write performance on SQLite and reflects the real out-of-the-box experience for each ORM.

### Test Isolation

- **Before each test**: Schema dropped, recreated, data populated
- **Mutating tests** (insert/delete): Per-iteration setup/teardown
- **Read-only tests**: Run on stable data

## Project Structure

```
oxyde-benchmarks/
├── common/              # Shared utilities
│   ├── base.py         # Abstract Benchmark class
│   ├── timer.py        # Performance measurement
│   ├── schema.py       # Database schema setup
│   ├── db.py           # Database utilities
│   └── report.py       # Results generation
├── oxyde_bench/         # Oxyde implementation
├── asyncpg_bench/       # Raw asyncpg baseline
├── django_bench/        # Django ORM
├── sqlalchemy_bench/    # SQLAlchemy 2.0
├── tortoise_bench/      # Tortoise ORM
├── piccolo_bench/       # Piccolo
├── peewee_bench/        # Peewee
├── sqlmodel_bench/      # SQLModel
├── config.py            # Configuration
├── bench.py             # Main runner
├── Dockerfile           # Docker image
├── docker-compose.yml   # Docker compose
├── Makefile             # Build commands
└── requirements.txt     # Dependencies
```

## Adding a New ORM

1. Create directory: `{orm}_bench/`
2. Implement `models.py` with User, Post, Tag, PostTag
3. Implement `bench.py` extending `Benchmark` base class
4. Add to `AVAILABLE_ORMS` in `config.py`
5. Add import in `bench.py:get_benchmark_class()`

## Local Database Setup

### PostgreSQL

```bash
sudo -u postgres createuser -P bench  # password: bench
sudo -u postgres createdb -O bench bench
```

### MySQL

```bash
mysql -u root -p
CREATE DATABASE bench;
CREATE USER 'bench'@'localhost' IDENTIFIED BY 'bench';
GRANT ALL PRIVILEGES ON bench.* TO 'bench'@'localhost';
```

### SQLite

No setup required - file created automatically.
