.PHONY: help format lint test check all clean contracts-check quality-check data-quality migrate-db web-dev web-local web-build web-lint web-typecheck ingest-season ingest-week inventory-source import-history hydrate-history fetch-source build-silver build-team-game prepare-week team-stats promote-silver matchup-data reconcile audit-data season-close-week season-revision season-market-revision season-prepare season-release season-rollback

# Default target
help:
	@echo "CFB Model - Available Commands:"
	@echo ""
	@echo "Python pipeline:"
	@echo "  make format    - Format code with ruff"
	@echo "  make lint      - Run linter with ruff"
	@echo "  make test      - Run tests with pytest"
	@echo "  make check     - Mirror CI: lint, contracts, tests, docs build, web checks"
	@echo "  make all       - Format + lint + test + contracts + quality registry"
	@echo "  make clean     - Clean cache files"
	@echo "  make contracts-check - Validate contracts/ files are in sync"
	@echo "  DB migrations: run scripts/pipeline/migrate_db.py with an explicit --database-url"
	@echo ""
	@echo "Web app (web/):"
	@echo "  make web-local [ENV=preview|production] - Run the web app locally on real data (matchup pages included)"
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
	@echo "  make prepare-week YEAR=2026 WEEK=1 - Rebuild cumulative Silver/Gold before publish"
	@echo "  make team-stats YEAR=2026 WEEK=6 ENV=preview [DRY=1] - Publish pre-game team stats for the week"
	@echo "  make promote-silver YEAR=2026 [DRY=1] - Register Preview Silver in the production catalog"
	@echo "  make matchup-data YEAR=2026 ENV=preview RATING_URI=... MEASUREMENT_URI=... [APPLY=1] - Publish V5 matchup data (dry run by default)"
	@echo "  make reconcile YEAR=2026 ENV=preview - Catalog orphaned immutable artifacts"
	@echo "  make audit-data YEAR=2026 ENV=preview - Audit Gold training data and lineage"
	@echo ""
	@echo "Weekly season release (docs/ops/weekly_runbook.md; WEEK = upcoming week):"
	@echo "  make season-revision WEEK=8 AS_OF=<post-week cutoff> PRE_WEEK_CUTOFF=... RUN_ID=... [DRY=1]  - Build conf/season/2026/revision_manifest_w<WEEK>_v1.json (Preview)"
	@echo "  make season-market-revision FROM=... TO=... REVISION_ID=... CUTOFF=...  - Market-only mid-week line refresh manifest"
	@echo "  make season-prepare WEEK=8 AS_OF=... [MANIFEST=...] [RECONSTRUCT=1]  - Prepare the candidate from a clean committed tree"
	@echo "  make season-release ENV=preview|production RELEASE_ID=season-2026-... PROJECTION_SHA=... EXPECTED_PREVIOUS=...|INITIAL=1"
	@echo "  make season-rollback RELEASE_ID=... EXPECTED_PREVIOUS=... DECISION_REF=... OWNER_AUTHORIZED=1  - Production, owner credential"
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

# Run all checks (format, lint, test, contracts)
all: format lint test contracts-check quality-check
	@echo ""
	@echo "✅ All checks complete!"

# Mirror of CI: Python lint/contracts/tests, docs build, web checks
check:
	uv run ruff format --check .
	uv run ruff check .
	$(MAKE) contracts-check quality-check
	PYTHONPATH=src:. uv run pytest tests -q -n 4
	uv run mkdocs build --strict
	npm --prefix web run lint
	npm --prefix web run typecheck
	npm --prefix web run test:publication
	npm --prefix web run build
	@echo "✅ All CI-equivalent checks passed"

# ---------------------------------------------------------------------------
# Contracts validation
# ---------------------------------------------------------------------------

contracts-check:
	@echo "📋 Validating contracts..."
	@uv run python contracts/validation.py

quality-check:
	@echo "Verifying data-quality check registry..."
	@PYTHONPATH=src uv run python -m cks_picks_cfb.quality --verify-registry

data-quality:
	@if [ -z "$(STAGE)" ]; then \
		echo "Usage: make data-quality STAGE={ingest|silver|gold|publish} [YEAR=2026] [ENV=preview]"; exit 1; \
	fi
	PYTHONPATH=src uv run python -m cks_picks_cfb.quality --stage $(STAGE) $(if $(YEAR),--year $(YEAR),) $(if $(ENV),--environment $(ENV),)

migrate-db:
	@echo "migrate-db is disabled: ENV does not select a database for this target." >&2
	@echo "Use scripts/pipeline/migrate_db.py --database-url with a verified branch URL." >&2
	@exit 2

# ---------------------------------------------------------------------------
# Web app (web/)
# ---------------------------------------------------------------------------

web-local:
	zsh scripts/ops/run_web_local.sh $(or $(ENV),preview)

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

prepare-week:
	@if [ -z "$(YEAR)" ] || [ -z "$(WEEK)" ] || [ -z "$(AS_OF)" ] || [ -z "$(ENV)" ]; then \
		echo "Usage: make prepare-week YEAR=2026 WEEK=1 AS_OF=ISO-8601 ENV=preview|production"; exit 1; \
	fi
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops prepare-week --year $(YEAR) --week $(WEEK) --as-of $(AS_OF) --environment $(ENV)

# ---------------------------------------------------------------------------
# Weekly operating cycle
# ---------------------------------------------------------------------------

team-stats:
	@if [ -z "$(YEAR)" ] || [ -z "$(WEEK)" ] || [ -z "$(ENV)" ]; then \
		echo "Usage: make team-stats YEAR=2026 WEEK=6 ENV=preview|production [DRY=1]"; exit 1; \
	fi
	PYTHONPATH=src:. uv run python scripts/pipeline/publish_team_stats.py --season $(YEAR) --as-of-week $(WEEK) --environment $(ENV) $(if $(DRY),--dry-run,)

matchup-data:
	@if [ -z "$(YEAR)" ] || [ -z "$(ENV)" ] || [ -z "$(RATING_URI)" ] || [ -z "$(MEASUREMENT_URI)" ]; then \
		echo "Usage: make matchup-data YEAR=2026 ENV=preview|production RATING_URI=... MEASUREMENT_URI=... [APPLY=1]"; exit 1; \
	fi
	PYTHONPATH=src:. uv run python scripts/pipeline/publish_matchup_data.py --season $(YEAR) --environment $(ENV) --rating-manifest-uri $(RATING_URI) --measurement-manifest-uri $(MEASUREMENT_URI) $(if $(APPLY),--apply,)

promote-silver:
	@if [ -z "$(YEAR)" ]; then echo "Usage: make promote-silver YEAR=2026 [DRY=1]"; exit 1; fi
	PYTHONPATH=src:. uv run python scripts/pipeline/promote_silver_versions.py --season $(YEAR) $(if $(DRY),--dry-run,)

# Atomic season releases (docs/ops/weekly_runbook.md). WEEK is the upcoming
# week being forecast; the completed week is WEEK-1. Data commands run under the
# Keychain wrappers in scripts/ops/, never against .env defaults.
SEASON_OUTPUT := artifacts/season/2026/preview
SEASON_ENV := CFB_STORAGE_BACKEND=r2 PYTHONPATH=src:.

# Normal weekly close/open (incremental): fetches only the completed week's
# observations, carries the certified earlier-week captures, and gates the
# completed-week history against the previous manifest. PREVIOUS_MANIFEST
# defaults to the highest-versioned revision_manifest_w<WEEK-1>_v<k>.json.
season-close-week:
	@if [ -z "$(WEEK)" ] || [ -z "$(AS_OF)" ] || [ -z "$(PRE_WEEK_CUTOFF)" ] || [ -z "$(RUN_ID)" ]; then \
		echo "Usage: make season-close-week WEEK=<upcoming week> AS_OF=<completed-week post-week cutoff> PRE_WEEK_CUTOFF=<upcoming-week pre-week cutoff> RUN_ID=<fresh pipeline run id> [PREVIOUS_MANIFEST=<certified manifest; default: highest-versioned week WEEK-1 manifest>] [DRY=1 re-checks an existing RUN_ID]" >&2; exit 1; \
	fi
	$(SEASON_ENV) zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/build_season_revision.py --season 2026 --week $(WEEK) --environment preview --incremental --as-of $(AS_OF) --pre-week-cutoff $(PRE_WEEK_CUTOFF) --pipeline-run-id $(RUN_ID) $(if $(PREVIOUS_MANIFEST),--previous-manifest $(PREVIOUS_MANIFEST),) $(if $(DRY),--dry-run,)

# Full-history repair vehicle: re-ingests every completed week (Weeks 0..WEEK-1)
# and is NOT the weekly rollover. Requires an explicit ack; the normal weekly
# path is season-close-week.
season-revision:
	@if [ "$(FULL_HISTORY)" != "1" ]; then \
		echo "season-revision re-ingests every completed week and is reserved for explicitly approved history repairs." >&2; \
		echo "For the normal weekly rollover use: make season-close-week WEEK=<upcoming week> AS_OF=<post-week cutoff> PRE_WEEK_CUTOFF=<pre-week cutoff> RUN_ID=<fresh id>" >&2; \
		echo "To run the full-history path deliberately, set FULL_HISTORY=1." >&2; exit 1; \
	fi
	@if [ -z "$(WEEK)" ] || [ -z "$(AS_OF)" ] || [ -z "$(PRE_WEEK_CUTOFF)" ] || [ -z "$(RUN_ID)" ]; then \
		echo "Usage: make season-revision FULL_HISTORY=1 WEEK=<upcoming week> AS_OF=<completed-week post-week cutoff> PRE_WEEK_CUTOFF=<upcoming-week pre-week cutoff> RUN_ID=<fresh pipeline run id> [DRY=1 re-checks an existing RUN_ID]" >&2; exit 1; \
	fi
	$(SEASON_ENV) zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/build_season_revision.py --season 2026 --week $(WEEK) --environment preview --as-of $(AS_OF) --pre-week-cutoff $(PRE_WEEK_CUTOFF) --pipeline-run-id $(RUN_ID) $(if $(DRY),--dry-run,)

# Market-only line refresh: reuses every certified football input and changes only
# the quotes, the target week's pre-week cutoff and the revision identity. Reads
# stored captures; never calls a provider.
season-market-revision:
	@if [ -z "$(FROM)" ] || [ -z "$(TO)" ] || [ -z "$(REVISION_ID)" ] || [ -z "$(CUTOFF)" ]; then \
		echo "Usage: make season-market-revision FROM=<certified revision manifest> TO=<new manifest path> REVISION_ID=<id> CUTOFF=<ISO-8601 UTC, last capture + ~5 min>" >&2; exit 1; \
	fi
	$(SEASON_ENV) zsh scripts/ops/with_preview_env.sh uv run python -m scripts.pipeline.build_market_revision --from-manifest $(FROM) --to-manifest $(TO) --revision-id $(REVISION_ID) --cutoff $(CUTOFF)

# MANIFEST defaults to the week's first revision (revision_manifest_w<WEEK>_v1.json);
# pass MANIFEST= for a later one, such as a market-only line refresh.
season-prepare:
	@if [ -z "$(WEEK)" ] || [ -z "$(AS_OF)" ]; then \
		echo "Usage: make season-prepare WEEK=<upcoming week> AS_OF=<PRE_WEEK_CUTOFF> [MANIFEST=<revision manifest>] [RECONSTRUCT=1] (clean committed tree required)" >&2; exit 1; \
	fi
	$(SEASON_ENV) zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/run_season.py prepare --model-manifest conf/season/2026/model_manifest_v1.json --revision-manifest $(or $(MANIFEST),conf/season/2026/revision_manifest_w$(WEEK)_v1.json) --through-week $$(( $(WEEK) - 1 )) --next-week $(WEEK) $(if $(RECONSTRUCT),--reconstruct-next-week,) --as-of $(AS_OF) --output $(SEASON_OUTPUT) --environment preview

season-release:
	@if [ "$(ENV)" != "preview" ] && [ "$(ENV)" != "production" ] || [ -z "$(RELEASE_ID)" ] || [ -z "$(PROJECTION_SHA)" ] || { [ -z "$(EXPECTED_PREVIOUS)" ] && [ -z "$(INITIAL)" ]; }; then \
		echo "Usage: make season-release ENV=preview|production RELEASE_ID=season-2026-... PROJECTION_SHA=<sha256> EXPECTED_PREVIOUS=<active release id> (or INITIAL=1)" >&2; exit 1; \
	fi
	$(SEASON_ENV) zsh scripts/ops/with_preview_env.sh $(if $(filter production,$(ENV)),zsh scripts/ops/with_production_pipeline_env.sh,) uv run python scripts/pipeline/run_season.py release --environment $(ENV) $(if $(INITIAL),--initial,--expected-previous-release-id $(EXPECTED_PREVIOUS)) --run-manifest $(SEASON_OUTPUT)/$(patsubst production-%,%,$(patsubst preview-%,%,$(RELEASE_ID)))/run-manifest.json --projection-payload-sha256 $(PROJECTION_SHA)

season-rollback:
	@if [ -z "$(RELEASE_ID)" ] || [ -z "$(EXPECTED_PREVIOUS)" ] || [ -z "$(DECISION_REF)" ] || [ "$(OWNER_AUTHORIZED)" != "1" ]; then \
		echo "Usage: make season-rollback RELEASE_ID=<prior release id> EXPECTED_PREVIOUS=<active release id> DECISION_REF=<ref> OWNER_AUTHORIZED=1 (Production, owner credential)" >&2; exit 1; \
	fi
	$(SEASON_ENV) zsh scripts/ops/with_production_owner_env.sh uv run python scripts/pipeline/run_season.py rollback --environment production --season 2026 --release-id $(RELEASE_ID) --expected-previous-release-id $(EXPECTED_PREVIOUS) --owner-authorized --decision-ref "$(DECISION_REF)"

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

# Clean cache files
clean:
	@echo "🧹 Cleaning cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cache files cleaned"
