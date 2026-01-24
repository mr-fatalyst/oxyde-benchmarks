.PHONY: install run run-pg run-mysql run-quick clean help venv \
        docker-build docker-pg docker-mysql docker-sqlite docker-all

PYTHON := python3
VENV := venv
BIN := $(VENV)/bin
IMAGE := oxyde-benchmarks
PYTHON_VERSION := 3.12
MEMORY := 4g
CPUS := 2

# Default target
help:
	@echo "Oxyde ORM Benchmarks"
	@echo ""
	@echo "Local Usage (requires local DB setup):"
	@echo "  make install       Create virtualenv and install dependencies"
	@echo "  make run           Run benchmarks (SQLite)"
	@echo "  make run-pg        Run benchmarks (PostgreSQL)"
	@echo "  make run-mysql     Run benchmarks (MySQL)"
	@echo "  make run-quick     Quick test run (fewer iterations)"
	@echo ""
	@echo "Docker Usage (isolated, reproducible):"
	@echo "  make docker-build  Build Docker image"
	@echo "  make docker-pg     Run PostgreSQL benchmarks in Docker"
	@echo "  make docker-mysql  Run MySQL benchmarks in Docker"
	@echo "  make docker-sqlite Run SQLite benchmarks in Docker"
	@echo "  make docker-all    Run all database benchmarks in Docker"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean         Clean local files (venv, __pycache__)"
	@echo "  make clean-results Clean benchmark results"
	@echo "  make clean-docker  Clean Docker images"
	@echo "  make clean-all     Clean everything"
	@echo ""
	@echo "Options:"
	@echo "  ORMS=oxyde,django    Run specific ORMs only"
	@echo "  TESTS=select_pk      Run specific tests only"
	@echo "  ITERATIONS=100       Set number of iterations"
	@echo "  LOGS=1               Show subprocess stderr for debugging"
	@echo "  PYTHON_VERSION=3.11  Python version for Docker (default: 3.12)"
	@echo "  MEMORY=4g            Container memory limit (default: 4g)"
	@echo "  CPUS=2               Container CPU limit (default: 2)"
	@echo ""
	@echo "Examples:"
	@echo "  make run ORMS=oxyde,sqlalchemy"
	@echo "  make docker-pg ORMS=oxyde,asyncpg"
	@echo "  make docker-all ITERATIONS=200"
	@echo "  make docker-pg PYTHON_VERSION=3.11"

# =============================================================================
# Local Development
# =============================================================================

# Create virtualenv and install dependencies
venv:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip

install: venv
	$(BIN)/pip install -r requirements.txt
	@echo ""
	@echo "Installation complete! Activate with:"
	@echo "  source $(VENV)/bin/activate"

# Build command with optional args
define RUN_CMD
$(BIN)/python bench.py --db $(1) \
	$(if $(ORMS),--orms $(ORMS)) \
	$(if $(TESTS),--tests $(TESTS)) \
	$(if $(ITERATIONS),--iterations $(ITERATIONS)) \
	$(if $(WARMUP),--warmup $(WARMUP)) \
	$(if $(LOGS),--logs)
endef

# Run benchmarks on SQLite
run:
	$(call RUN_CMD,sqlite)

# Run benchmarks on PostgreSQL
run-pg:
	$(call RUN_CMD,postgres)

# Run benchmarks on MySQL
run-mysql:
	$(call RUN_CMD,mysql)

# Quick test run
run-quick:
	$(BIN)/python bench.py --db sqlite --iterations 10 --warmup 2 \
		$(if $(ORMS),--orms $(ORMS)) \
		$(if $(TESTS),--tests $(TESTS))

# =============================================================================
# Docker
# =============================================================================

# Build Docker image
docker-build:
	docker build --build-arg PYTHON_VERSION=$(PYTHON_VERSION) -t $(IMAGE):py$(PYTHON_VERSION) .
	docker tag $(IMAGE):py$(PYTHON_VERSION) $(IMAGE):latest

# Docker run command with optional args
# Mount code directory to pick up changes without rebuild
define DOCKER_CMD
docker run --rm \
	--memory=$(MEMORY) --cpus=$(CPUS) \
	-v $(PWD):/app \
	$(IMAGE):latest \
	--db $(1) \
	$(if $(ORMS),--orms $(ORMS)) \
	$(if $(TESTS),--tests $(TESTS)) \
	$(if $(ITERATIONS),--iterations $(ITERATIONS)) \
	$(if $(WARMUP),--warmup $(WARMUP)) \
	$(if $(LOGS),--logs)
endef

# Run PostgreSQL benchmarks in Docker
docker-pg: docker-build
	$(call DOCKER_CMD,postgres)

# Run MySQL benchmarks in Docker
docker-mysql: docker-build
	$(call DOCKER_CMD,mysql)

# Run SQLite benchmarks in Docker
docker-sqlite: docker-build
	$(call DOCKER_CMD,sqlite)

# Run all database benchmarks in Docker
docker-all: docker-build
	$(call DOCKER_CMD,all)

# =============================================================================
# Cleanup
# =============================================================================

# Clean up local files
clean:
	rm -rf $(VENV)
	rm -f bench.db
	rm -rf __pycache__ */__pycache__
	rm -rf *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Clean results (may need sudo for Docker-created files)
clean-results:
	rm -rf results/* 2>/dev/null || sudo rm -rf results/*

# Clean Docker images
clean-docker:
	docker rmi $(IMAGE):latest 2>/dev/null || true
	docker rmi $(IMAGE):py3.10 2>/dev/null || true
	docker rmi $(IMAGE):py3.11 2>/dev/null || true
	docker rmi $(IMAGE):py3.12 2>/dev/null || true
	docker rmi $(IMAGE):py3.13 2>/dev/null || true
	docker image prune -f

# Full clean (including results and Docker)
clean-all: clean clean-results clean-docker
