.PHONY: help format lint test check all clean contracts-check quality-check data-quality migrate-db web-dev web-local web-build web-lint web-typecheck db-publish db-score ingest-season ingest-week inventory-source import-history hydrate-history fetch-source build-silver build-team-game build-features build-baselines assemble-model-ready prepare-week team-stats promote-silver matchup-data preflight readiness publish-week freeze-week close-week replay-season reconcile audit-data train-week0 generate-game-ordinal evaluate-week0 refit-week0-bundle evaluate-game-ordinal refit-game-ordinal weekly export-pickem season-revision season-market-revision season-prepare season-release season-rollback

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
	@echo "  make readiness YEAR=2026 WEEK=1 AS_OF=2026-08-20 ENV=preview"
	@echo "  make prepare-week YEAR=2026 WEEK=1 - Rebuild cumulative Silver/Gold before publish"
	@echo "  make team-stats YEAR=2026 WEEK=6 ENV=preview [DRY=1] - Publish pre-game team stats for the week"
	@echo "  make promote-silver YEAR=2026 [DRY=1] - Register Preview Silver in the production catalog"
	@echo "  make matchup-data YEAR=2026 ENV=preview RATING_URI=... MEASUREMENT_URI=... [APPLY=1] - Publish V5 matchup data (dry run by default)"
	@echo "  make reconcile YEAR=2026 ENV=preview - Catalog orphaned immutable artifacts"
	@echo "  make audit-data YEAR=2026 ENV=preview - Audit Gold training data and lineage"
	@echo "  make train-week0 - Generate temporal regime candidate predictions"
	@echo "  make evaluate-week0 OOF=... WEIGHTS=... REPORT_URI=..."
	@echo "  make refit-week0-bundle FEATURE_REF_URI=... REPORT_URI=... BUNDLE_ID=... ENV=preview"
	@echo "  make generate-game-ordinal STAGE=selection|locked FEATURE_REF_URI=... OUTPUT=... ENV=preview"
	@echo "  make evaluate-game-ordinal STAGE=selection|locked CANDIDATES=... REPORT_URI=... ENV=preview"
	@echo "  make refit-game-ordinal FEATURE_REF_URI=... REPORT_URI=... BUNDLE_ID=... ENV=preview"
	@echo ""
	@echo "Weekly season release (docs/ops/weekly_runbook.md; WEEK = upcoming week):"
	@echo "  make season-revision WEEK=8 AS_OF=<post-week cutoff> PRE_WEEK_CUTOFF=... RUN_ID=... [DRY=1]  - Build conf/season/2026/revision_manifest_w<WEEK>_v1.json (Preview)"
	@echo "  make season-market-revision FROM=... TO=... REVISION_ID=... CUTOFF=...  - Market-only mid-week line refresh manifest"
	@echo "  make season-prepare WEEK=8 AS_OF=... [MANIFEST=...] [RECONSTRUCT=1]  - Prepare the candidate from a clean committed tree"
	@echo "  make season-release ENV=preview|production RELEASE_ID=season-2026-... PROJECTION_SHA=... EXPECTED_PREVIOUS=...|INITIAL=1"
	@echo "  make season-rollback RELEASE_ID=... EXPECTED_PREVIOUS=... DECISION_REF=... OWNER_AUTHORIZED=1  - Production, owner credential"
	@echo "  make weekly / publish-week / freeze-week / close-week  - Removed (legacy path); they exit with an error"
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

build-features:
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops build-features --year $(YEAR) --as-of $(AS_OF) --matchups-ref-uri $(MATCHUPS_REF_URI) --schedule-ref-uri $(SCHEDULE_REF_URI) --output-ref-uri $(OUTPUT_REF_URI) --environment $(ENV) $(if $(BASELINES_REF_URI),--baselines-ref-uri $(BASELINES_REF_URI),)

build-baselines:
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops build-baselines --year $(YEAR) --as-of $(AS_OF) --core-ref-uri $(CORE_REF_URI) --output-ref-uri $(OUTPUT_REF_URI) --environment $(ENV) $(if $(FROZEN_DESIGN_SHA),--include-locked-2025 --frozen-design-sha $(FROZEN_DESIGN_SHA),)

assemble-model-ready:
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops assemble-model-ready --year $(YEAR) --as-of $(AS_OF) --core-ref-uri $(CORE_REF_URI) --baselines-ref-uri $(BASELINES_REF_URI) $(if $(MARKETS_REF_URI),--markets-ref-uri $(MARKETS_REF_URI),) $(if $(PRESEASON_FEATURES_REF_URI),--preseason-features-ref-uri $(PRESEASON_FEATURES_REF_URI) --feature-track $(FEATURE_TRACK),) --output-ref-uri $(OUTPUT_REF_URI) --environment $(ENV)

prepare-week:
	@if [ -z "$(YEAR)" ] || [ -z "$(WEEK)" ] || [ -z "$(AS_OF)" ] || [ -z "$(ENV)" ]; then \
		echo "Usage: make prepare-week YEAR=2026 WEEK=1 AS_OF=ISO-8601 ENV=preview|production"; exit 1; \
	fi
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops prepare-week --year $(YEAR) --week $(WEEK) --as-of $(AS_OF) --environment $(ENV)

# ---------------------------------------------------------------------------
# Weekly operating cycle
# ---------------------------------------------------------------------------

preflight:
	@if [ -z "$(YEAR)" ] || [ -z "$(WEEK)" ] || [ -z "$(AS_OF)" ]; then \
		echo "Usage: make preflight YEAR=2026 WEEK=1 AS_OF=2026-08-20"; exit 1; \
	fi
	@echo "🩺 Running weekly preflight for $(YEAR) week $(WEEK)..."
	PYTHONPATH=.:src uv run python scripts/pipeline/preflight.py --year $(YEAR) --week $(WEEK) --as-of $(AS_OF) $(if $(CONFIG),--config $(CONFIG),)

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

readiness:
	@if [ "$(ENV)" != "preview" ]; then \
		echo "Usage: make readiness YEAR=2026 WEEK=1 AS_OF=ISO-8601 ENV=preview [CONFIG=conf/weekly_bets/v2_preview_2026.yaml]"; exit 1; \
	fi
	PYTHONPATH=src uv run python -m cks_picks_cfb.ops readiness --year $(YEAR) --week $(WEEK) --as-of $(AS_OF) --environment $(ENV) $(if $(CONFIG),--config $(CONFIG),)

# Legacy publication path: it writes public.prediction_runs, which the atomic
# season release now serves. Removed from operation; the code goes in Phase 3.
publish-week freeze-week close-week weekly:
	@echo "make $@ is removed — see docs/ops/weekly_runbook.md (make season-revision / season-prepare / season-release)" >&2; exit 1

# Atomic season releases (docs/ops/weekly_runbook.md). WEEK is the upcoming
# week being forecast; the completed week is WEEK-1. Data commands run under the
# Keychain wrappers in scripts/ops/, never against .env defaults.
SEASON_OUTPUT := artifacts/season/2026/preview
SEASON_ENV := CFB_STORAGE_BACKEND=r2 PYTHONPATH=src:.

season-revision:
	@if [ -z "$(WEEK)" ] || [ -z "$(AS_OF)" ] || [ -z "$(PRE_WEEK_CUTOFF)" ] || [ -z "$(RUN_ID)" ]; then \
		echo "Usage: make season-revision WEEK=<upcoming week> AS_OF=<completed-week post-week cutoff> PRE_WEEK_CUTOFF=<upcoming-week pre-week cutoff> RUN_ID=<fresh pipeline run id> [DRY=1 re-checks an existing RUN_ID]" >&2; exit 1; \
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

evaluate-game-ordinal:
	@if [ -z "$(STAGE)" ] || [ -z "$(CANDIDATES)" ] || [ -z "$(REPORT_URI)" ] || [ -z "$(ENV)" ]; then \
		echo "Usage: make evaluate-game-ordinal STAGE=selection|locked CANDIDATES=... REPORT_URI=... ENV=preview"; exit 1; \
	fi
	PYTHONPATH=.:src uv run python scripts/pipeline/evaluate_game_ordinal_predictions.py --stage $(STAGE) --candidates-csv $(CANDIDATES) --output-uri $(REPORT_URI) --environment $(ENV) $(if $(FEATURE_REF_URI),--feature-ref-uri $(FEATURE_REF_URI),) $(if $(SELECTION_REPORT_URI),--selection-report-uri $(SELECTION_REPORT_URI),) $(if $(BLEND_WEIGHTS),--blend-weights-json $(BLEND_WEIGHTS),)

generate-game-ordinal:
	@if [ -z "$(STAGE)" ] || [ -z "$(FEATURE_REF_URI)" ] || [ -z "$(OUTPUT)" ] || [ -z "$(ENV)" ]; then \
		echo "Usage: make generate-game-ordinal STAGE=selection|locked FEATURE_REF_URI=... OUTPUT=... ENV=preview [SELECTION_REPORT_URI=...]"; exit 1; \
	fi
	PYTHONPATH=.:src uv run python scripts/pipeline/generate_game_ordinal_candidates.py --stage $(STAGE) --feature-ref-uri $(FEATURE_REF_URI) --output-csv $(OUTPUT) --environment $(ENV) $(if $(SELECTION_REPORT_URI),--selection-report-uri $(SELECTION_REPORT_URI),)

refit-game-ordinal:
	PYTHONPATH=.:src uv run python scripts/pipeline/refit_game_ordinal_bundle.py --feature-ref-uri $(FEATURE_REF_URI) --routing-report-uri $(REPORT_URI) --bundle-id $(BUNDLE_ID) --environment $(ENV)

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

.PHONY: rebuild-6a
rebuild-6a:
	@test -n "$(OP)" || (echo 'usage: make rebuild-6a OP=preflight|build|verify|publish' && exit 2)
	uv run python scripts/pipeline/rebuild_6a.py $(OP) --expected-code-sha $$(git rev-parse HEAD)
