# Quick Start Commands

> **Essential commands for CFB Model development**
>
> Quick reference for common operations. Copy-paste ready.

---

## Environment Setup

### Install Dependencies

```bash
# Install all dependencies (from repo root)
uv sync --extra dev

# Activate virtual environment
source .venv/bin/activate

# Verify installation
uv pip list | grep cfb-model
```

### Environment Variables

```bash
# 2026 MVP cloud path
export CFB_STORAGE_BACKEND='r2'
export CFB_R2_BUCKET='your_bucket'
export CFB_R2_ACCOUNT_ID='your_account_id'
export CFB_R2_ACCESS_KEY='your_access_key'
export CFB_R2_SECRET_KEY='your_secret_key'
export DATABASE_URL='postgres://...?sslmode=require'
export PREVIEW_DATABASE_URL='postgres://isolated-preview...?sslmode=require'
export CFB_R2_PREVIEW_BUCKET='your_preview_bucket'

# Required for ingestion
export CFBD_API_KEY='your_api_key_here'

# Optional: opt-in live The Odds API market capture during publish-week
# (~2 credits/run; soft-fails to CFBD-only on provider errors)
export THE_ODDS_API_KEY='your_odds_api_key_here'
export CFB_ODDS_API_ENABLED='1'

# Required for CFBD Model Pick'em API submission (optional path)
export CFBD_PREDICTION_TOKEN='your_prediction_token_here'

# Local-only development when CFB_STORAGE_BACKEND=local
export CFB_MODEL_DATA_ROOT='/Volumes/CK SSD/Coding Projects/cfb_model/'

# Vercel publication scope (web app)
export CFB_PUBLICATION_MODE='predictions' # current approved release mode; all other values fail closed to market-only
export CFB_PUBLICATION_SEASON='2026'
export CFB_PUBLICATION_WEEKS='0,1'        # comma-separated; update each week after publish + readiness pass

# Optional: MLflow tracking
export MLFLOW_TRACKING_URI='file:///path/to/mlruns'
```

**Best practice:** Add to `.env` file in repo root:

```bash
# .env file
CFB_STORAGE_BACKEND=r2
CFB_R2_BUCKET=your_bucket
CFB_R2_ACCOUNT_ID=your_account_id
CFB_R2_ACCESS_KEY=your_access_key
CFB_R2_SECRET_KEY=your_secret_key
DATABASE_URL=postgres://...?sslmode=require
CFBD_API_KEY=your_api_key
```

---

## Testing & Code Quality

### Run Tests

```bash
# Run all tests
uv run pytest

# Run tests quietly (summary only)
uv run pytest -q

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_aggregations_core.py

# Run tests matching pattern
uv run pytest -k "test_aggregate"

# Stop on first failure
uv run pytest -x
```

### Format and Lint

```bash
# Format code (automatic fixes)
uv run ruff format .

# Check linting issues
uv run ruff check .

# Fix auto-fixable linting issues
uv run ruff check . --fix

# Format + Lint together (recommended before commits)
uv run ruff format . && uv run ruff check .
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run hooks on all files
pre-commit run --all-files

# Update hooks to latest versions
pre-commit autoupdate
```

---

## Model Training

### Basic Training

```bash
# Train with default config
PYTHONPATH=src uv run python -m cks_picks_cfb.train

# Generate the 2022-2024 OOF + locked-2025 Week 0 candidate tournament
PYTHONPATH=src uv run python -m cks_picks_cfb.train experiment=week0_regimes

# Train with specific model
PYTHONPATH=src uv run python -m cks_picks_cfb.train model=catboost_v1

# Train with specific feature set
PYTHONPATH=src uv run python -m cks_picks_cfb.train features=matchup_v2

# Train on different test year
PYTHONPATH=src uv run python -m cks_picks_cfb.train data.test_year=2025
```

### Experiment Configs

```bash
# Run pre-configured experiment (2026 regime tournament)
PYTHONPATH=src uv run python -m cks_picks_cfb.train experiment=week0_regimes

# Preseason-regime experiment
PYTHONPATH=src uv run python -m cks_picks_cfb.train experiment=preseason_regimes

# Override experiment parameters
PYTHONPATH=src uv run python -m cks_picks_cfb.train \
    experiment=week0_regimes \
    data.test_year=2025
```

### Hyperparameter Optimization

```bash
# Run Optuna optimization
PYTHONPATH=src uv run python -m cks_picks_cfb.train mode=optimize

# Optimize with custom trials
PYTHONPATH=src uv run python -m cks_picks_cfb.train \
    mode=optimize \
    optuna.n_trials=100
```

### Debug Configuration

```bash
# See composed config (before running)
PYTHONPATH=src uv run python -m cks_picks_cfb.train --cfg job

# See config with interpolations resolved
PYTHONPATH=src uv run python -m cks_picks_cfb.train --cfg job --resolve

# Validate config only (no training)
PYTHONPATH=src uv run python -m cks_picks_cfb.train --help
```

---

## Production Pipeline

### Weekly Operating Cycle (2026)

```bash
# Validate env, R2, Neon schema, artifact paths, and deploy assumptions
make audit-data YEAR=2026 ENV=preview
make readiness YEAR=2026 WEEK=0 AS_OF=YYYY-MM-DD ENV=preview

# Apply append-only contracts/migrations to the configured Neon branch
make migrate-db

# Pregame publish (refresh schedule/lines → predict → R2 artifact → Neon):
# Use ENV=production and CONFIG=conf/weekly_bets/v4_2026.yaml for the launch model
make publish-week YEAR=2026 WEEK=0 AS_OF=YYYY-MM-DD ENV=preview
make publish-week YEAR=2026 WEEK=0 AS_OF=YYYY-MM-DD ENV=production \
     CONFIG=conf/weekly_bets/v4_2026.yaml

# Freeze the exact artifact that will later be scored
make freeze-week YEAR=2026 WEEK=0 ENV=preview

# Postgame close (refresh finals → score → scored R2 artifact → Neon stats):
make close-week YEAR=2026 WEEK=0 AS_OF=YYYY-MM-DDTHH:MM:SSZ ENV=preview

# Preview-only frozen rating candidate evidence (Phase 5):
# See docs/ops/rating_shadow_operations.md for preflight and recovery rules.
PYTHONPATH=.:src uv run python scripts/pipeline/audit_rating_prospective_evidence.py \
  --environment preview --through-week 1 --verification-games-ref-uri <games-ref> \
  --verification-outcomes-ref-uri <outcomes-ref> --expected-code-sha <committed-sha>

# Rebuild current-season Gold before a Week 1 rehearsal:
make prepare-week YEAR=2026 WEEK=1 AS_OF=YYYY-MM-DDTHH:MM:SSZ ENV=preview

# Discover registered/orphaned immutable artifacts
make reconcile YEAR=2026 ENV=preview

# Alias for pregame publish:
make weekly YEAR=2026 WEEK=1

# Durable recovery: resume the same recorded state-machine run
PYTHONPATH=src uv run python -m cks_picks_cfb.ops publish-week \
  --year 2026 --week 1 --as-of YYYY-MM-DD --environment preview \
  --pipeline-run-id <existing-pipeline-run-id>
```

### Weekly Predictions (standalone)

```bash
# Generate predictions for upcoming week
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py

# Generate for specific week
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py \
    --year 2024 \
    --week 12

# Generate and upload durable R2/S3 artifact
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py \
    --year 2026 \
    --week 1 \
    --upload-artifact
```

### CFBD Model Pick'em Export & API Submission

```bash
# Export weekly predictions to CFBD Model Pick'em CSV format
make export-pickem YEAR=2026 WEEK=0

# Export and submit picks directly to CFBD Pick'em API (requires CFBD_PREDICTION_TOKEN;
# submission additionally requires explicit user approval of game IDs and margins)
make export-pickem YEAR=2026 WEEK=0 SUBMIT=1

# Standalone CLI execution (validate without submitting)
PYTHONPATH=.:src uv run python scripts/pipeline/export_cfbd_pickem.py \
    --year 2026 \
    --week 0 \
    --validate-api \
    --dry-run
```

### Performance Scoring

```bash
# Score all bets for a week
PYTHONPATH=. uv run python scripts/pipeline/score_weekly_bets.py \
    --year 2024 \
    --week 12 \
    --from-artifact \
    --upload-artifact

# Upsert scored artifact into Neon and refresh YTD stats
PYTHONPATH=. uv run python scripts/pipeline/score_to_db.py \
    --year 2024 \
    --week 12 \
    --from-artifact
```

---

## Data Management

### Ingestion (CFBD API → cloud storage)

```bash
# Preseason: ingest season schedule + metadata
make ingest-season YEAR=2026
# Or specific entities:
make ingest-season YEAR=2026 ENTITIES=teams,venues,games

# Request-level Bronze capture (Week 0 is valid)
make fetch-source YEAR=2026 WEEK=0 ENTITY=games ENV=preview

# Build source-neutral Silver from an explicit capture observation
make build-silver YEAR=2026 DATASET=games CAPTURE_ID=<capture-id> \
  AS_OF=2026-08-20T00:00:00Z ENV=preview \
  OUTPUT_REF_URI=artifacts/preview/refs/games-2026.json

# Legacy compatibility command; not an authoritative production input
make ingest-week YEAR=2026 WEEK=0

# Retro-load frozen Silver market quotes into Neon market_quotes (idempotent)
PYTHONPATH=.:src uv run python scripts/pipeline/backfill_market_quotes_db.py \
  --season 2026 --dry-run

# Opt-in live The Odds API capture (estimate first; --confirm spends ~2 credits)
PYTHONPATH=.:src uv run python scripts/data/fetch_odds_api_market_quotes.py \
  --year 2026 --week 2

# Direct scripts (no Make):
PYTHONPATH=.:src uv run python scripts/data/ingest_season.py --year 2026
PYTHONPATH=.:src uv run python scripts/data/ingest_week.py --year 2026 --week 1
```

### Versioned aggregation and features

```bash
# Inventory and import production history through read-only source storage.
make inventory-source
make import-history

# Build reconciled team-game data from explicit Silver refs
make build-team-game YEAR=2026 AS_OF=2026-08-20T00:00:00Z ENV=preview \
  PLAYS_REF_URI=... GAMES_REF_URI=... CORRECTIONS_REF_URI=... \
  OUTPUT_REF_URI=...

# Build canonical team-side Gold and deterministic wide model features
make build-features YEAR=2026 AS_OF=2026-08-20T00:00:00Z ENV=preview \
  MATCHUPS_REF_URI=... SCHEDULE_REF_URI=... \
  OUTPUT_REF_URI=...

# Generate temporal OOF baselines and assemble market-aware model-ready Gold.
make build-baselines YEAR=2026 AS_OF=2026-08-20T00:00:00Z ENV=preview \
  CORE_REF_URI=... OUTPUT_REF_URI=...
make assemble-model-ready YEAR=2026 AS_OF=2026-08-20T00:00:00Z ENV=preview \
  CORE_REF_URI=... BASELINES_REF_URI=... MARKETS_REF_URI=... OUTPUT_REF_URI=...
```

### Feature Generation

Weekly features are built through the versioned Gold pipeline above
(`make build-features`, `make assemble-model-ready`) rather than standalone
scripts. See `.codex/MAP.md` and `docs/ops/weekly_pipeline.md`.

---

## MLflow

### Start MLflow UI

```bash
# Start MLflow server (Docker)
MLFLOW_PORT=5050 docker compose -f docker/mlops/docker-compose.yml up mlflow

# Access at http://localhost:5050

# Start MLflow UI (local, no Docker)
mlflow ui --backend-store-uri file:///path/to/mlruns --port 5050
```

### Model Registry

> MLflow is a development-time tracker only. Production models are checksummed
> bundles in R2 (`artifacts/preview|production/models/...`) activated through
> the ops state machine — not the MLflow registry.

```bash
# List registered models (development experiments)
mlflow models list

# Promote a dev model to staging
mlflow models update-model-version \
    --name "my_dev_model" \
    --version 1 \
    --stage Staging
```

---

## Git Workflows

### Branch Management

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Create fix branch
git checkout -b fix/issue-description

# Create experiment branch
git checkout -b experiment/model-name

# Switch back to main
git checkout main

# Delete merged branch
git branch -d feature/your-feature-name
```

### Commits

```bash
# Stage specific files
git add src/cks_picks_cfb/train.py tests/test_models.py

# Stage all changes
git add -A

# Commit with message
git commit -m "feat: Add new feature X

- Implemented feature computation
- Added unit tests
- Updated documentation

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Amend last commit (if needed)
git commit --amend
```

### Syncing

```bash
# Pull latest changes
git pull origin main

# Push feature branch
git push -u origin feature/your-feature-name

# Force push (use carefully!)
git push --force-with-lease origin feature/your-feature-name
```

---

## Debugging

### Python Debugging

```bash
# Run script with debugger
PYTHONPATH=src python -m pdb -m cks_picks_cfb.train

# Run pytest with debugger (drops into pdb on failure)
uv run pytest --pdb

# Run pytest with print statements visible
uv run pytest -s
```

### Data Inspection

```bash
# Check the configured storage backend and weekly artifact paths
PYTHONPATH=.:src uv run python scripts/pipeline/preflight.py --year 2026 --week 1 --skip-db

# Local-only data root inspection
ls -lh "$CFB_MODEL_DATA_ROOT"
```

### Environment Debugging

```bash
# Check Python version
python --version

# Check uv version
uv --version

# Verify packages installed
uv pip list

# Check environment variables
env | grep CFB

# Verify PYTHONPATH
echo $PYTHONPATH
```

---

## Documentation

### Build Docs

```bash
# Build MkDocs documentation
mkdocs build

# Build with strict mode (fail on warnings)
mkdocs build --strict

# Serve docs locally
mkdocs serve

# Access at http://localhost:8000
```

### Generate API Docs

```bash
# Generate API documentation
mkdocs build --strict

# Deploy docs to GitHub Pages
mkdocs gh-deploy
```

---

## Analysis & Experiments

Exploratory analysis lives in `research/` and MLflow (development only). For
2026 model comparison, use the sealed tournament tooling:

```bash
# Compare preview model bundles (V2/V3/V4 style diffs)
PYTHONPATH=.:src uv run python scripts/pipeline/compare_preview_model_bundles.py --help
```

See `docs/modeling/early_season_regimes.md` for the tournament/evaluation
contract and `docs/experiments/index.md` for the experiment lineage.

---

## Utilities

### Clean Up

```bash
# Remove Python cache files
find . -type d -name "__pycache__" -exec rm -r {} +

# Remove pytest cache
rm -rf .pytest_cache

# Remove Hydra outputs
rm -rf artifacts/hydra_outputs/

# Clean all build artifacts
rm -rf build/ dist/ *.egg-info/
```

### Dependency Management

```bash
# Update all dependencies
uv sync --upgrade

# Add new dependency
uv add package-name

# Add dev dependency
uv add --dev package-name

# Remove dependency
uv remove package-name

# Export requirements
uv pip freeze > requirements.txt
```

---

## Nx Task Runner (cross-stack caching)

The repo uses [Nx](https://nx.dev) for cached task orchestration across both the
Python pipeline and the Next.js web app. Nx is installed at the repo root.

### Setup

```bash
npm install        # installs nx at root (one-time)
```

### Available targets

| Project | Target | Command | Cached |
|---|---|---|---|
| `pipeline` | `test` | `uv run pytest -q` | ✅ |
| `pipeline` | `lint` | `uv run ruff check .` | ✅ |
| `pipeline` | `format` | `uv run ruff format .` | ❌ |
| `web` | `build` | `npm run build` (in `web/`) | ✅ |
| `web` | `lint` | `npm run lint` (in `web/`) | ✅ |
| `web` | `typecheck` | `npm run typecheck` (in `web/`) | ✅ |
| `web` | `dev` | `npm run dev` (in `web/`) | ❌ |

### Usage

```bash
# Run a single target
npx nx run pipeline:test
npx nx run web:build

# Run a target across all projects that have it
npx nx run-many -t lint
npx nx run-many -t test typecheck

# Run everything (all targets, all projects)
npx nx run-many -t lint typecheck test build

# Skip the cache (force re-run)
npx nx run pipeline:test --skip-nx-cache

# Show the project graph
npx nx show projects
```

### How caching works

Nx hashes the target's `inputs` (scoped to each project's source files — see
`project.json` and `nx.json`). If the hash matches a prior run, the command is
skipped and cached `outputs` are restored. The cache lives in `.nx/cache/`
(gitignored). Example: after `npx nx run web:build`, a second run with no
changed files completes instantly from cache.

> **Note:** The Makefile remains the source of truth for multi-step production
> workflows (e.g., `make weekly`). Nx wraps individual tasks with caching.

---

## Common Command Chains

### Full Quality Check

```bash
# Format, lint, test (run before every commit)
uv run ruff format . && \
uv run ruff check . && \
uv run pytest -q
```

### Training + Evaluation

```bash
# Train regime experiment, then generate weekly predictions
PYTHONPATH=src uv run python -m cks_picks_cfb.train \
    experiment=week0_regimes && \
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py
```

### Weekly Production Pipeline

```bash
# Complete resumable weekly workflow
make publish-week YEAR=2026 WEEK=0 AS_OF=YYYY-MM-DD ENV=production
```

---

## Keyboard Shortcuts (IDE)

### VSCode

- `Cmd+Shift+P` - Command palette
- `Cmd+P` - Quick open file
- `Cmd+Shift+F` - Search in files
- `Cmd+B` - Toggle sidebar
- `Cmd+J` - Toggle terminal
- `F5` - Start debugging
- `Shift+F5` - Stop debugging

### Cursor / Claude Code

- `Cmd+K` - Ask Claude
- `Cmd+L` - Continue conversation
- `Cmd+Shift+E` - Open files

---

_Last Updated: 2026-08-31_
_Quick command reference for CKsPicks-CFB_
