# =============================================================================
# Resync Makefile - UV Commands
# =============================================================================
# Common development commands using UV
# Usage: make <command>
# =============================================================================

.PHONY: help install dev test lint format clean run docker-build docker-run

# Default target
help:
	@echo "🚀 Resync Development Commands (UV)"
	@echo "===================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install      Install production dependencies"
	@echo "  make dev          Install all dependencies (including dev)"
	@echo ""
	@echo "Development:"
	@echo "  make run          Run development server (hot reload)"
	@echo "  make shell        Open IPython shell with project loaded"
	@echo ""
	@echo "Code Quality:"
	@echo "  make test         Run tests with coverage"
	@echo "  make lint         Run linter (ruff)"
	@echo "  make format       Format code (black + ruff)"
	@echo "  make typecheck    Run type checker (mypy)"
	@echo "  make check        Run all checks (lint + format + test)"
	@echo ""
	@echo "Dependencies:"
	@echo "  make lock         Generate uv.lock lockfile"
	@echo "  make sync         Sync dependencies from lockfile"
	@echo "  make update       Update all dependencies"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build Build Docker image"
	@echo "  make docker-run   Run Docker container"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean        Remove cache and build artifacts"
	@echo ""

# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------

install:
	@echo "📦 Installing production dependencies..."
	uv sync --no-dev

dev:
	@echo "📦 Installing all dependencies (including dev)..."
	uv sync

# -----------------------------------------------------------------------------
# Development
# -----------------------------------------------------------------------------

run:
	@echo "🚀 Starting development server..."
	uv run uvicorn resync.main:app --reload --port 8000

shell:
	@echo "🐍 Opening IPython shell..."
	uv run ipython

# -----------------------------------------------------------------------------
# Code Quality
# -----------------------------------------------------------------------------

test:
	@echo "🧪 Running tests..."
	uv run pytest

test-cov:
	@echo "🧪 Running tests with coverage report..."
	uv run pytest --cov=resync --cov-report=html
	@echo "📊 Coverage report: htmlcov/index.html"

lint:
	@echo "🔍 Running linter..."
	uv run ruff check .

format:
	@echo "✨ Formatting code..."
	uv run black .
	uv run ruff check --fix .

typecheck:
	@echo "🔎 Running type checker..."
	uv run mypy resync

check: lint typecheck test
	@echo "✅ All checks passed!"

# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------

lock:
	@echo "🔒 Generating lockfile..."
	uv lock

sync:
	@echo "🔄 Syncing dependencies from lockfile..."
	uv sync --frozen

update:
	@echo "⬆️  Updating all dependencies..."
	uv lock --upgrade
	uv sync

add:
	@echo "➕ Adding dependency..."
	@echo "Usage: make add PACKAGE=fastapi"
	uv add $(PACKAGE)

add-dev:
	@echo "➕ Adding dev dependency..."
	@echo "Usage: make add-dev PACKAGE=pytest"
	uv add --dev $(PACKAGE)

# -----------------------------------------------------------------------------
# Docker
# -----------------------------------------------------------------------------

docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t resync:5.9.8 .

docker-run:
	@echo "🐳 Running Docker container..."
	docker run -p 8000:8000 \
		-e DATABASE_URL=${DATABASE_URL} \
		-e REDIS_URL=${REDIS_URL} \
		resync:5.9.8

docker-compose-up:
	@echo "🐳 Starting with docker-compose..."
	docker-compose up -d

docker-compose-down:
	@echo "🐳 Stopping docker-compose..."
	docker-compose down

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------

db-migrate:
	@echo "🗄️  Running database migrations..."
	uv run alembic upgrade head

db-revision:
	@echo "🗄️  Creating new migration..."
	@echo "Usage: make db-revision MESSAGE='add users table'"
	uv run alembic revision --autogenerate -m "$(MESSAGE)"

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------

clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build dist htmlcov .coverage
	@echo "✅ Cleanup complete!"

# -----------------------------------------------------------------------------
# Production
# -----------------------------------------------------------------------------

build:
	@echo "📦 Building distribution packages..."
	uv build

publish:
	@echo "📤 Publishing to PyPI..."
	uv publish

# -----------------------------------------------------------------------------
# CI/CD Helpers
# -----------------------------------------------------------------------------

ci-install:
	@echo "📦 CI: Installing dependencies..."
	uv sync --frozen --no-dev

ci-test:
	@echo "🧪 CI: Running tests..."
	uv run pytest --cov=resync --cov-report=xml

ci-lint:
	@echo "🔍 CI: Running linter..."
	uv run ruff check .
	uv run black --check .

# -----------------------------------------------------------------------------
# Automation Systems
# -----------------------------------------------------------------------------

automation-start:
	@echo "🚀 Starting automation systems..."
	./scripts/start_automation.sh

automation-stop:
	@echo "🛑 Stopping automation systems..."
	./scripts/stop_automation.sh

automation-status:
	@echo "📊 Automation Systems Status:"
	@if [ -f /tmp/resync_self_healing.pid ]; then \
		pid=$$(cat /tmp/resync_self_healing.pid); \
		if ps -p $$pid > /dev/null 2>&1; then \
			echo "  ✅ Self-Healing: Running (PID: $$pid)"; \
		else \
			echo "  ❌ Self-Healing: Not running"; \
		fi \
	else \
		echo "  ❌ Self-Healing: Not running"; \
	fi
	@if [ -f /tmp/resync_code_guardian.pid ]; then \
		pid=$$(cat /tmp/resync_code_guardian.pid); \
		if ps -p $$pid > /dev/null 2>&1; then \
			echo "  ✅ Code Guardian: Running (PID: $$pid)"; \
		else \
			echo "  ❌ Code Guardian: Not running"; \
		fi \
	else \
		echo "  ❌ Code Guardian: Not running"; \
	fi

automation-logs:
	@echo "📋 Automation Logs:"
	@echo ""
	@echo "=== Self-Healing ==="
	@tail -20 logs/self_healing.log 2>/dev/null || echo "No logs yet"
	@echo ""
	@echo "=== Code Guardian ==="
	@tail -20 logs/code_guardian.log 2>/dev/null || echo "No logs yet"

guardian:
	@echo "🔍 Starting Code Quality Guardian (foreground)..."
	uv run python resync/tools/code_quality_guardian.py

self-heal:
	@echo "🏥 Starting Self-Healing System (foreground)..."
	uv run python resync/tools/self_healing.py
