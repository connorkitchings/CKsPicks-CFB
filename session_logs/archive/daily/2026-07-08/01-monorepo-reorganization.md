# Session: Monorepo Reorganization

## TL;DR
- **Worked On:** Reorganizing the monorepo structure to improve navigation and separation of concerns
- **Completed:** Created `contracts/` for shared schema/team maps, `research/` for non-production scripts, moved logos to `assets/`, removed stale root-level artifacts
- **Blockers:** None
- **Next:** Update `.codex/MAP.md` and `.codex/QUICKSTART.md` to reflect new paths; consider extracting TEAM_LOGO_MAP imports in Python scripts to use `contracts/teams.py`

## Changes Made
- **contracts/** (NEW): Single source of truth for DB schema (`schema.sql`, `schema.ts`) and team mappings (`teams.py`, `teams.ts`) with validation script
- **research/** (NEW): Moved all non-production scripts from `scripts/` (analysis, debug, tuning, experiments, ratings, notebooks, migration, validation, utils, training)
- **assets/logos/** (NEW): Moved from root-level `Logos/` directory
- **scripts/**: Now contains only production code (`pipeline/`, `data/`, `cli.py`)
- **Removed:** Stale root-level `models/`, `mlruns/`, `catboost_info/`, `site/` directories
- **pyproject.toml**: Updated pytest norecursedirs and ruff extend-exclude to include `research/`
- **Makefile**: Added `contracts-check` target
- **AGENTS.md**: Updated architecture table and conventions to reflect new structure
- **web/scripts/sync-logos.mjs**: Updated source path to `assets/logos/`
- **scripts/pipeline/publish_review.py**: Synced TEAM_LOGO_MAP with canonical `contracts/teams.py`

## Testing
- [x] Health checks pass (ruff format + ruff check)
- [x] Tests pass (187 tests)
- [x] Web build passes (npm run build)
- [x] Web typecheck passes (tsc --noEmit)
- [x] Contracts validation passes

## Technical Details

### Why contracts/ has local copies in web/src/lib/
TypeScript module resolution requires imports to be within the project root or explicitly configured. Importing from `../../contracts/` works but breaks the `@/` path alias pattern. Solution: keep canonical versions in `contracts/`, maintain local copies in `web/src/lib/`, and use `validation.py` to ensure they stay in sync.

### What stayed in scripts/
Only production pipeline code that runs weekly:
- `scripts/pipeline/` - Weekly prediction generation and publishing
- `scripts/data/` - Season and week data ingestion
- `scripts/cli.py` - Typer CLI entry point

### What moved to research/
All exploration, debugging, and one-off analysis scripts:
- `research/analysis/` - Statistical analysis
- `research/debug/` - Debugging and inspection
- `research/tuning/` - Hyperparameter tuning
- `research/ratings/` - Power ratings R&D
- `research/notebooks/` - Jupyter notebooks
- `research/migration/` - One-time migration scripts
- `research/validation/` - Data validation scripts
- `research/utils/` - Utility scripts
- `research/training/` - Cross-validation runner

## Notes for Next Session

**Resume at:**
- Update `.codex/MAP.md` to reflect new directory structure
- Update `.codex/QUICKSTART.md` command examples if any reference moved scripts

**Context:**
- Decision made: Keep monorepo but reorganize for clarity (Option C from planning session)
- Key insight: `contracts/` solves the schema/team-map sync problem that required manual updates across 3+ files
- Pattern to follow: Production code in `scripts/`, exploration in `research/`, shared truth in `contracts/`

**Watch out for:**
- Python scripts still have inline `TEAM_LOGO_MAP` definitions; could refactor to import from `contracts/teams.py` but not critical
- `research/` scripts may have hardcoded paths that reference old locations (e.g., `scripts/analysis/...` in docstrings)
- Hydra configs in `conf/` still reference `src/` paths (unchanged, as intended)

**Next steps:**
1. Update `.codex/MAP.md` with new directory layout
2. Optionally refactor Python scripts to import `TEAM_LOGO_MAP` from `contracts/teams.py`
3. Test full weekly pipeline (`make weekly YEAR=2026 WEEK=1`) to ensure no path breakage

**tags:** ["refactoring", "project-structure", "contracts", "research"]
