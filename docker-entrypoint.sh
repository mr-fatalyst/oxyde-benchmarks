#!/bin/bash
set -e

# Parse --db argument
DB="postgres"
ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --db)
            DB="$2"
            ARGS+=("$1" "$2")
            shift 2
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

echo "=== ORM Benchmark Runner ==="
echo "Database: $DB"
echo ""

# Start required database services
start_postgres() {
    echo "Starting PostgreSQL..."
    service postgresql start
    # Wait for PostgreSQL to be ready
    for i in {1..30}; do
        if pg_isready -h localhost -U bench -d bench > /dev/null 2>&1; then
            echo "PostgreSQL is ready"
            return 0
        fi
        sleep 1
    done
    echo "PostgreSQL failed to start"
    return 1
}

start_mysql() {
    echo "Starting MySQL/MariaDB..."
    service mariadb start
    # Wait for MySQL to be ready
    for i in {1..30}; do
        if mysqladmin ping -h localhost --silent > /dev/null 2>&1; then
            echo "MySQL is ready"
            return 0
        fi
        sleep 1
    done
    echo "MySQL failed to start"
    return 1
}

case "$DB" in
    postgres|postgresql)
        start_postgres
        ;;
    mysql|mariadb)
        start_mysql
        ;;
    sqlite)
        echo "SQLite requires no service"
        # Use /tmp for SQLite to avoid volume mount locking issues
        export SQLITE_URL="sqlite:///tmp/bench.db"
        echo "SQLite URL: $SQLITE_URL"
        ;;
    all)
        start_postgres
        start_mysql
        echo "SQLite requires no service"
        # Use /tmp for SQLite to avoid volume mount locking issues
        export SQLITE_URL="sqlite:///tmp/bench.db"
        ;;
    *)
        echo "Unknown database: $DB"
        echo "Supported: postgres, mysql, sqlite, all"
        exit 1
        ;;
esac

echo ""
echo "Running benchmark..."
echo ""

# Run the benchmark
exec python bench.py "${ARGS[@]}"
