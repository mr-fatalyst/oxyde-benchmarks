ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim

# Install system dependencies for databases and Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    # PostgreSQL
    postgresql \
    postgresql-contrib \
    # MySQL
    default-mysql-server \
    default-libmysqlclient-dev \
    # Build tools for Python packages
    gcc \
    g++ \
    pkg-config \
    git \
    # SQLite (already included in Python, but CLI is useful)
    sqlite3 \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Create postgres user and database
USER postgres
RUN /etc/init.d/postgresql start && \
    psql --command "CREATE USER bench WITH PASSWORD 'bench';" && \
    createdb -O bench bench && \
    /etc/init.d/postgresql stop
USER root

# Configure PostgreSQL to allow local connections
RUN PG_HBA=$(find /etc/postgresql -name pg_hba.conf) && \
    echo "host all all 127.0.0.1/32 md5" >> "$PG_HBA" && \
    echo "local all all trust" >> "$PG_HBA"

# Configure MySQL
RUN /etc/init.d/mariadb start && \
    mysql -e "CREATE DATABASE bench;" && \
    mysql -e "CREATE USER 'bench'@'localhost' IDENTIFIED BY 'bench';" && \
    mysql -e "GRANT ALL PRIVILEGES ON bench.* TO 'bench'@'localhost';" && \
    mysql -e "FLUSH PRIVILEGES;" && \
    /etc/init.d/mariadb stop

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
# Note: oxyde is installed from local path in entrypoint if needed
RUN pip install --no-cache-dir -r requirements.txt || \
    pip install --no-cache-dir \
    asyncpg psycopg2-binary aiosqlite aiomysql mysqlclient \
    django sqlalchemy tortoise-orm piccolo peewee sqlmodel greenlet \
    orjson rich typer python-dateutil psutil pytest pytest-asyncio

# Copy application code
COPY . .

# Copy and set entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create results directory
RUN mkdir -p /app/results

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["--db", "postgres"]
