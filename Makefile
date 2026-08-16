.PHONY: help format lint test health check all clean contracts-check migrate-db web-dev web-build web-lint web-typecheck db-publish db-score ingest-season ingest-week inventory-source import-history hydrate-history fetch-source build-silver build-team-game build-features build-baselines assemble-model-ready preflight readiness publish-week freeze-week close-week replay-season reconcile audit-data train-week0 evaluate-week0 refit-week0-bundle weekly export-pickem

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
	@echo "  make migrate-db - Apply checksummed contracts/migrations"
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
	@echo "  make fetch-source YEAR=2026 WEEK=0 ENTITY=games ENV=preview"
	@echo "  make build-silver YEAR=2026 DATASET=games CAPTURE_ID=... AS_OF=... ENV=preview"
	@echo "  make readiness YEAR=2026 WEEK=1 AS_OF=2026-08-20 ENV=preview"
	@echo "  make publish-week YEAR=2026 WEEK=1  - Pregame publish (refresh lines → predict → publish)"
	@echo "  make freeze-week YEAR=2026 WEEK=1  - Freeze the active run before kickoff"
	@echo "  make close-week YEAR=2026 WEEK=1  - Postgame close (refresh scores → score → stats)"
	@echo "  make reconcile YEAR=2026 ENV=preview - Catalog orphaned immutable artifacts"
	@echo "  make audit-data YEAR=2026 ENV=preview - Audit Gold training data and lineage"
	@echo "  make train-week0 - Generate temporal regime candidate predictions"
	@echo "  make evaluate-week0 OOF=... WEIGHTS=... REPORT_URI=..."
	@echo "  make refit-week0-bundle FEATURE_REF_URI=... REPORT_URI=... BUNDLE_ID=... ENV=preview"
	@echo "  make weekly YEAR=2026 WEEK=1  - Alias for publish-week"
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

migrate-db:
	@echo "📋 Applying checksummed database migrations..."
	PYTHONPATH=src uv run python scripts/pipeline/migrate_db.py

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

fetch-source:
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops fetch-source --year $(YEAR) $(if $(WEEK),--week $(WEEK),) --entity $(ENTITY) --environment $(ENV)

inventory-source:
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops inventory-source --year 2026 --environment preview $(if $(PREFIX),--prefix $(PREFIX),)

import-history:
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops import-history --year 2026 --environment preview $(if $(PREFIX),--prefix $(PREFIX),)

hydrate-history:
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops hydrate-history --year 2026 --environment preview $(if $(PREFIX),--prefix $(PREFIX),)

import-history-silver:
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops import-history --year 2026 --environment preview --skip-imports $(if $(PREFIX),--prefix $(PREFIX),)

build-silver:
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops build-silver --year $(YEAR) --dataset $(DATASET) --capture-id $(CAPTURE_ID) --as-of $(AS_OF) --output-ref-uri $(OUTPUT_REF_URI) --environment $(ENV) $(if $(GAMES_REF_URI),--games-ref-uri $(GAMES_REF_URI),)

build-team-game:
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops build-team-game --year $(YEAR) --as-of $(AS_OF) --plays-ref-uri $(PLAYS_REF_URI) --games-ref-uri $(GAMES_REF_URI) --corrections-ref-uri $(CORRECTIONS_REF_URI) --output-ref-uri $(OUTPUT_REF_URI) --environment $(ENV) $(if $(TEAMS_REF_URI),--teams-ref-uri $(TEAMS_REF_URI),) $(if $(VENUES_REF_URI),--venues-ref-uri $(VENUES_REF_URI),) $(if $(WEATHER_REF_URI),--weather-ref-uri $(WEATHER_REF_URI),) $(if $(GAME_STATS_REF_URI),--game-stats-ref-uri $(GAME_STATS_REF_URI),)

build-features:
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops build-features --year $(YEAR) --as-of $(AS_OF) --matchups-ref-uri $(MATCHUPS_REF_URI) --schedule-ref-uri $(SCHEDULE_REF_URI) --output-ref-uri $(OUTPUT_REF_URI) --environment $(ENV) $(if $(BASELINES_REF_URI),--baselines-ref-uri $(BASELINES_REF_URI),)

build-baselines:
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops build-baselines --year $(YEAR) --as-of $(AS_OF) --core-ref-uri $(CORE_REF_URI) --output-ref-uri $(OUTPUT_REF_URI) --environment $(ENV) $(if $(FROZEN_DESIGN_SHA),--include-locked-2025 --frozen-design-sha $(FROZEN_DESIGN_SHA),)

assemble-model-ready:
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops assemble-model-ready --year $(YEAR) --as-of $(AS_OF) --core-ref-uri $(CORE_REF_URI) --baselines-ref-uri $(BASELINES_REF_URI) --markets-ref-uri $(MARKETS_REF_URI) --output-ref-uri $(OUTPUT_REF_URI) --environment $(ENV)

# ---------------------------------------------------------------------------
# Weekly operating cycle
# ---------------------------------------------------------------------------

preflight:
	@if [ -z "$(YEAR)" ] || [ -z "$(WEEK)" ] || [ -z "$(AS_OF)" ]; then \
		echo "Usage: make preflight YEAR=2026 WEEK=1 AS_OF=2026-08-20"; exit 1; \
	fi
	@echo "🩺 Running weekly preflight for $(YEAR) week $(WEEK)..."
	PYTHONPATH=.:src uv run python scripts/pipeline/preflight.py --year $(YEAR) --week $(WEEK) --as-of $(AS_OF) $(if $(CONFIG),--config $(CONFIG),)

readiness:
	@if [ "$(ENV)" != "preview" ]; then \
		echo "Usage: make readiness YEAR=2026 WEEK=1 AS_OF=ISO-8601 ENV=preview [CONFIG=conf/weekly_bets/v2_preview_2026.yaml]"; exit 1; \
	fi
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops readiness --year $(YEAR) --week $(WEEK) --as-of $(AS_OF) --environment $(ENV) $(if $(CONFIG),--config $(CONFIG),)

publish-week:
	@if [ -z "$(YEAR)" ] || [ -z "$(WEEK)" ] || [ -z "$(AS_OF)" ] || [ -z "$(ENV)" ]; then \
		echo "Usage: make publish-week YEAR=2026 WEEK=1 AS_OF=2026-08-20 ENV=preview|production"; exit 1; \
	fi
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops publish-week --year $(YEAR) --week $(WEEK) --as-of $(AS_OF) --environment $(ENV) $(if $(CONFIG),--config $(CONFIG),)

freeze-week:
	@if [ -z "$(YEAR)" ] || [ -z "$(WEEK)" ] || [ -z "$(ENV)" ]; then \
		echo "Usage: make freeze-week YEAR=2026 WEEK=1 ENV=preview|production [WAIVER='reason']"; exit 1; \
	fi
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops freeze-week --year $(YEAR) --week $(WEEK) --environment $(ENV) $(if $(WAIVER),--waiver "$(WAIVER)",)

close-week:
	@if [ -z "$(YEAR)" ] || [ -z "$(WEEK)" ] || [ -z "$(ENV)" ]; then \
		echo "Usage: make close-week YEAR=2026 WEEK=1 ENV=preview|production"; exit 1; \
	fi
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops close-week --year $(YEAR) --week $(WEEK) --environment $(ENV)

weekly: publish-week

replay-season:
	@if [ -z "$(YEAR)" ] || [ "$(ENV)" != "preview" ]; then \
		echo "Usage: make replay-season YEAR=2025 ENV=preview"; exit 1; \
	fi
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops replay-season --year $(YEAR) --environment preview

reconcile:
	@if [ -z "$(YEAR)" ] || [ -z "$(ENV)" ]; then \
		echo "Usage: make reconcile YEAR=2026 ENV=preview"; exit 1; \
	fi
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops reconcile --year $(YEAR) --environment $(ENV)

audit-data:
	@if [ -z "$(YEAR)" ] || [ -z "$(ENV)" ]; then \
		echo "Usage: make audit-data YEAR=2026 ENV=preview"; exit 1; \
	fi
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops audit-data --year $(YEAR) --environment $(ENV) $(if $(MODE),--mode $(MODE),)

train-week0:
	PYTHONPATH=src uv run python -m cks_picks_cfb.train experiment=week0_regimes

evaluate-week0:
	@if [ -z "$(OOF)" ] || [ -z "$(WEIGHTS)" ] || [ -z "$(REPORT_URI)" ]; then \
		echo "Usage: make evaluate-week0 OOF=/path/candidates.csv WEIGHTS=/path/weights.json REPORT_URI=artifacts/preview/models/report.json"; exit 1; \
	fi
	PYTHONPATH=.:src uv run python scripts/pipeline/evaluate_regimes.py --oof-csv $(OOF) --blend-weights-json $(WEIGHTS) --output-uri $(REPORT_URI)

refit-week0-bundle:
	@if [ -z "$(FEATURE_REF_URI)" ] || [ -z "$(REPORT_URI)" ] || [ -z "$(BUNDLE_ID)" ] || [ -z "$(ENV)" ]; then \
		echo "Usage: make refit-week0-bundle FEATURE_REF_URI=... REPORT_URI=... BUNDLE_ID=... ENV=preview"; exit 1; \
	fi
	PYTHONPATH=.:src uv run python scripts/pipeline/refit_regime_bundle.py --feature-ref-uri $(FEATURE_REF_URI) --routing-report-uri $(REPORT_URI) --bundle-id $(BUNDLE_ID) --environment $(ENV)

# ---------------------------------------------------------------------------
# Database publish (Python → Postgres)
# ---------------------------------------------------------------------------

db-publish:
	@if [ -z "$(YEAR)" ] || [ -z "$(WEEK)" ]; then \
		echo "Usage: make db-publish YEAR=2026 WEEK=1"; exit 1; \
	fi
	@echo "📤 Publishing $(YEAR) week $(WEEK) predictions to Postgres from durable R2 artifact..."
	PYTHONPATH=.:src uv run python scripts/pipeline/publish_to_db.py --year $(YEAR) --week $(WEEK) --from-artifact

db-score:
	@if [ -z "$(YEAR)" ]; then \
		echo "Usage: make db-score YEAR=2026 [WEEK=1]"; exit 1; \
	fi
	@if [ -n "$(WEEK)" ]; then \
		PYTHONPATH=.:src uv run python scripts/pipeline/score_to_db.py --year $(YEAR) --week $(WEEK) --from-artifact; \
	else \
		PYTHONPATH=.:src uv run python scripts/pipeline/score_to_db.py --year $(YEAR) --backfill-season --from-artifact; \
	fi

train-champion:
	@echo "🏋️ Training champion spread and total models..."
	PYTHONPATH=src uv run python -m cks_picks_cfb.train model=linear model.target=spread_target
	PYTHONPATH=src uv run python -m cks_picks_cfb.train model=linear model.target=total_target

export-pickem:
	@if [ -z "$(YEAR)" ] || [ -z "$(WEEK)" ]; then \
		echo "Usage: make export-pickem YEAR=2026 WEEK=0 [VALIDATE=1] [DRY_RUN=1] [SUBMIT=1]"; exit 1; \
	fi
	PYTHONPATH=.:src uv run python scripts/pipeline/export_cfbd_pickem.py --year $(YEAR) --week $(WEEK) $(if $(VALIDATE),--validate-api,) $(if $(DRY_RUN),--dry-run,) $(if $(SUBMIT),--submit-api,)

# Clean cache files
clean:
	@echo "🧹 Cleaning cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cache files cleaned"
