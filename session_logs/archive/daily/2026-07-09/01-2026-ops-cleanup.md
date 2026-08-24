# Session: 2026 Operations Cleanup

## TL;DR
- **Worked On:** Simplified the 2026 MVP operating model around R2 durable artifacts and Neon as the derived web-serving database.
- **Completed:** Added explicit artifact paths, weekly preflight checks, artifact-first weekly publish flow, stricter local storage guardrails, contract validation hardening, deployment cleanup, and updated docs.
- **Blockers:** None remaining. Nx initially failed in the sandbox because of a Unix socket permission issue, then passed on the user's machine with `NX_DAEMON=false`.
- **Next:** Make `make db-publish` / `make db-score` artifact-first by default, then decide whether to move or delete `scripts/archive/` in a separate cleanup.

## Changes Made
- **Storage/artifacts:** Added `src/cks_picks_cfb/artifacts.py` for local working-copy paths and durable `artifacts/production/...` paths.
- **Weekly pipeline:** Added `scripts/pipeline/preflight.py`; wired `make preflight` and changed `make weekly` to preflight, generate/upload prediction artifacts, then publish from durable storage into Neon.
- **Pipeline CLIs:** Added `--upload-artifact`, `--from-artifact`, and explicit artifact path options to prediction publishing and scoring scripts.
- **Guardrails:** Removed repo-local `data/` fallback from `BaseIngester` and the legacy `utils.local_storage.LocalStorage` shim; local backend now requires `CFB_MODEL_DATA_ROOT`.
- **Contracts:** Strengthened `contracts/validation.py` to compare full `TEAM_LOGO_MAP` key/value mappings, not just keys.
- **Deployment:** Removed root `vercel.json`; Vercel deployment now relies on Root Directory `web/`. Added `turbopack.root` to `web/next.config.ts`.
- **Docs/config:** Updated `README.md`, `AGENTS.md`, `.codex/QUICKSTART.md`, `.codex/MAP.md`, `web/README.md`, `.env.example`, `.gitignore`, and `docs/ops/weekly_pipeline.md` to reflect R2 as durable storage and Neon as serving state.
- **Tests:** Added tests for artifact path conventions, contract validation helpers, and storage guardrails.

## Testing
- [x] `uv run ruff check .` passed
- [x] `uv run pytest -q` passed: 194 tests
- [x] `uv run python contracts/validation.py` passed
- [x] `npm run lint` passed in `web/`
- [x] `npm run typecheck` passed in `web/`
- [x] `npm run build` passed in `web/`
- [x] `make preflight YEAR=2026 WEEK=1` passed live against R2 + Neon
- [x] `NX_DAEMON=false npx nx run-many -t lint typecheck test build` passed on user machine

## Technical Details
- R2 is now documented and implemented as the durable home for raw data, processed features, prediction CSVs, and scored CSVs.
- Neon remains a derived serving database for the web app tables: `games`, `game_results`, `system_stats`, and `current_week`.
- Local `data/production/...` CSVs are now treated as working copies only and remain ignored by git.
- The supported weekly path is now `make weekly YEAR=2026 WEEK=N`; recovery commands remain documented for individual steps.

## Notes for Next Session

**Resume at:**
- Consider updating `make db-publish` and `make db-score` so their default behavior also reads durable artifacts, matching `make weekly`.

**Context:**
- Vercel is configured with Root Directory `web/`; the root `vercel.json` was deleted to avoid competing deploy assumptions.
- `make preflight YEAR=2026 WEEK=1` confirmed R2 storage and Neon schema connectivity. Current Neon `current_week` was `2025 week 14`.

**Watch out for:**
- `scripts/archive/` is excluded from active quality gates but still exists. Move or delete it in a separate focused commit if the project wants a stricter production surface.
- Nx may fail in sandboxed environments because the daemon cannot bind a Unix socket; user-side `NX_DAEMON=false npx nx run-many -t lint typecheck test build` passed.

**Next steps:**
1. Make standalone DB publish/score Make targets artifact-first.
2. Decide whether to remove or relocate `scripts/archive/`.
3. Add CI for contracts, Python checks, web checks, and Nx aggregate once the repo cleanup is stable.

**tags:** ["ops", "r2", "neon", "weekly-pipeline", "artifacts", "vercel", "cleanup"]
