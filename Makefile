.PHONY: help format lint test health check all clean contracts-check web-dev web-build web-lint web-typecheck db-publish db-score ingest-season ingest-week preflight weekly

# Default target
help:
	@echo "CFB Model - Available Commands:"
	@echo ""
	@echo "Python pipeline:"
	@echo "  make format    - Format code with ruff"
	@echo "  make lint      - Run linter with ruff"
	@echo "  make test      - Run tests with pytest"
	@echo "  make health    - Run full health checks"
	@echo "  make check     - Format + lint + test (alias for 'all')"
	@echo "  make all       - Run all quality checks"
	@echo "  make clean     - Clean cache files"
	@echo "  make contracts-check - Validate contracts/ files are in sync"
	@echo ""
	@echo "Web app (web/):"
	@echo "  make web-dev       - Start Next.js dev server"
	@echo "  make web-build     - Production build"
	@echo "  make web-lint      - ESLint"
	@echo "  make web-typecheck - TypeScript typecheck"
	@echo ""
	@echo "Data ingestion (requires CFB_STORAGE_BACKEND + CFBD_API_KEY in .env):"
	@echo "  make ingest-season YEAR=2026  - Ingest teams+venues+games for a season"
	@echo "  make ingest-week YEAR=2026 WEEK=1  - Ingest plays+betting_lines for a week"
	@echo "  make preflight YEAR=2026 WEEK=1  - Validate R2, Neon, artifact paths, deploy config"
	@echo "  make weekly YEAR=2026 WEEK=1  - Full weekly cycle (ingest → preagg → predict → publish)"
	@echo ""
	@echo "Database (requires DATABASE_URL):"
	@echo "  make db-publish YEAR=2026 WEEK=1  - Publish predictions CSV to Postgres"
	@echo "  make db-score   YEAR=2026         - Score + refresh system_stats"
	@echo ""

# Code formatting
format:
	@echo "🎨 Formatting code..."
	uv run ruff format .

# Linting
lint:
	@echo "🔍 Running linter..."
	uv run ruff check .

# Tests (with PYTHONPATH set for proper imports)
test:
	@echo "🧪 Running tests..."
	PYTHONPATH=src:. uv run pytest tests/ -q

# Full health check
health:
	@echo "🏥 Running health checks..."
	sh .agent/workflows/health-check.sh

# Run all checks (format, lint, test, contracts)
all: format lint test contracts-check
	@echo ""
	@echo "✅ All checks complete!"

# Alias for 'all'
check: all

# ---------------------------------------------------------------------------
# Contracts validation
# ---------------------------------------------------------------------------

contracts-check:
	@echo "📋 Validating contracts..."
	@uv run python contracts/validation.py

# ---------------------------------------------------------------------------
# Web app (web/)
# ---------------------------------------------------------------------------

web-dev:
	@echo "🌐 Starting Next.js dev server..."
	cd web && npm run dev

web-build:
	@echo "📦 Building Next.js app..."
	cd web && npm run build

web-lint:
	@echo "🔍 Linting web/..."
	cd web && npm run lint

web-typecheck:
	@echo "🔧 Typechecking web/..."
	cd web && npm run typecheck

# ---------------------------------------------------------------------------
# Data ingestion (CFBD API → R2/S3/local)
# ---------------------------------------------------------------------------

ingest-season:
	@if [ -z "$(YEAR)" ]; then \
		echo "Usage: make ingest-season YEAR=2026 [ENTITIES=teams,venues,games]"; exit 1; \
	fi
	@echo "📥 Ingesting $(YEAR) season data..."
	PYTHONPATH=.:src uv run python scripts/data/ingest_season.py --year $(YEAR) $(if $(ENTITIES),--entities $(ENTITIES),)

ingest-week:
	@if [ -z "$(YEAR)" ] || [ -z "$(WEEK)" ]; then \
		echo "Usage: make ingest-week YEAR=2026 WEEK=1"; exit 1; \
	fi
	@echo "📥 Ingesting $(YEAR) week $(WEEK)..."
	PYTHONPATH=.:src uv run python scripts/data/ingest_week.py --year $(YEAR) --week $(WEEK)

# ---------------------------------------------------------------------------
# Full weekly cycle (ingest → preagg → predict → publish)
# ---------------------------------------------------------------------------

preflight:
	@if [ -z "$(YEAR)" ] || [ -z "$(WEEK)" ]; then \
		echo "Usage: make preflight YEAR=2026 WEEK=1"; exit 1; \
	fi
	@echo "🩺 Running weekly preflight for $(YEAR) week $(WEEK)..."
	PYTHONPATH=.:src uv run python scripts/pipeline/preflight.py --year $(YEAR) --week $(WEEK)

weekly:
	@if [ -z "$(YEAR)" ] || [ -z "$(WEEK)" ]; then \
		echo "Usage: make weekly YEAR=2026 WEEK=1"; exit 1; \
	fi
	@echo "🔄 Starting weekly cycle for $(YEAR) week $(WEEK)..."
	@echo ""
	@echo "Step 1/5: Preflight checks..."
	PYTHONPATH=.:src uv run python scripts/pipeline/preflight.py --year $(YEAR) --week $(WEEK)
	@echo ""
	@echo "Step 2/5: Ingesting raw data..."
	PYTHONPATH=.:src uv run python scripts/data/ingest_week.py --year $(YEAR) --week $(WEEK)
	@echo ""
	@echo "Step 3/5: Running pre-aggregation (raw → processed/team_game)..."
	PYTHONPATH=.:src uv run python scripts/pipeline/run_pipeline_generic.py --year $(YEAR)
	@echo ""
	@echo "Step 4/5: Generating predictions and uploading durable artifact..."
	PYTHONPATH=.:src uv run python scripts/pipeline/generate_weekly_bets.py --year $(YEAR) --week $(WEEK) --upload-artifact
	@echo ""
	@echo "Step 5/5: Publishing durable artifact to Neon..."
	PYTHONPATH=.:src uv run python scripts/pipeline/publish_to_db.py --year $(YEAR) --week $(WEEK) --from-artifact
	@echo ""
	@echo "✅ Weekly cycle complete! Vercel ISR will refresh within 5 minutes."

# ---------------------------------------------------------------------------
# Database publish (Python → Postgres)
# ---------------------------------------------------------------------------

db-publish:
	@if [ -z "$(YEAR)" ] || [ -z "$(WEEK)" ]; then \
		echo "Usage: make db-publish YEAR=2026 WEEK=1"; exit 1; \
	fi
	@echo "📤 Publishing $(YEAR) week $(WEEK) predictions to Postgres..."
	PYTHONPATH=.:src uv run python scripts/pipeline/publish_to_db.py --year $(YEAR) --week $(WEEK)

db-score:
	@if [ -z "$(YEAR)" ]; then \
		echo "Usage: make db-score YEAR=2026 [WEEK=1]"; exit 1; \
	fi
	@if [ -n "$(WEEK)" ]; then \
		PYTHONPATH=.:src uv run python scripts/pipeline/score_to_db.py --year $(YEAR) --week $(WEEK); \
	else \
		PYTHONPATH=.:src uv run python scripts/pipeline/score_to_db.py --year $(YEAR) --backfill-season; \
	fi

# Clean cache files
clean:
	@echo "🧹 Cleaning cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cache files cleaned"
