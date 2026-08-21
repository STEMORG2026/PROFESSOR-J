# Makefile — PROFESSOR-J Common Commands

.PHONY: help install test typecheck lint format clean langfuse-up langfuse-down langfuse-logs eval

# Default target
help:
	@echo "PROFESSOR-J — Available Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install dependencies (pip)"
	@echo "  make install-dev      Install with dev dependencies"
	@echo ""
	@echo "Verification:"
	@echo "  make test             Run pytest (unit + integration)"
	@echo "  make test-cov         Run pytest with coverage report"
	@echo "  make typecheck        Run mypy --strict on app/"
	@echo "  make lint             Run pre-commit on all files"
	@echo "  make format           Run ruff format"
	@echo ""
	@echo "Observability:"
	@echo "  make langfuse-up      Start Langfuse (Postgres + ClickHouse + UI)"
	@echo "  make langfuse-down    Stop Langfuse"
	@echo "  make langfuse-logs    View Langfuse logs"
	@echo ""
	@echo "Evaluation:"
	@echo "  make eval             Run evaluation harness (Phase 9+)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean            Remove caches, build artifacts"
	@echo "  make reset-venv       Recreate virtual environment"

# ── Setup ─────────────────────────────────────────────────────────────

install:
	.venv/bin/pip install -r requirements.txt

install-dev:
	.venv/bin/pip install -r requirements.txt

# ── Verification ──────────────────────────────────────────────────────

test:
	.venv/bin/python -m pytest tests/ -v --tb=short

test-cov:
	.venv/bin/python -m pytest tests/ -v --tb=short --cov=app --cov-report=term-missing --cov-report=html

typecheck:
	.venv/bin/mypy app/

lint:
	.venv/bin/pre-commit run --all-files

format:
	.venv/bin/ruff format app/ tests/
	.venv/bin/ruff check --fix app/ tests/

# ── Observability ─────────────────────────────────────────────────────

langfuse-up:
	docker-compose -f docker/observability.yml up -d
	@echo "Langfuse UI: http://localhost:3000"
	@echo "Postgres:    localhost:5432"
	@echo "ClickHouse:  localhost:8123"

langfuse-down:
	docker-compose -f docker/observability.yml down

langfuse-logs:
	docker-compose -f docker/observability.yml logs -f

# ── Evaluation ────────────────────────────────────────────────────────

eval:
	@echo "Evaluation harness not yet implemented (Phase 9)"
	@echo "Will run: .venv/bin/python -m pytest tests/evals/ -v"

# ── Maintenance ───────────────────────────────────────────────────────

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov dist build *.egg-info 2>/dev/null || true

reset-venv:
	rm -rf .venv
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
