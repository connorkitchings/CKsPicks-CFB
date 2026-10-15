# Session: Runbook script paths correction and Week 8 manifest preparation

## TL;DR
- **Worked On:** Corrected two nonexistent script paths in `docs/ops/weekly_runbook.md` and prepared the canonical Week 8 revision manifest template `conf/season/2026/revision_manifest_w8_v1.json`.
- **Outcome:** Operational runbook updated to reference actual ingestion scripts (`ingest_week.py`, `fetch_odds_api_market_quotes.py`, and `build_week_market_snapshot.py`); Week 8 revision manifest template constructed, validated, and verified with all pre- and post-week cutoffs.
- **Plan Contract:** docs/plans/2026-10-14/01-season-operations-and-week7-bridge.md
- **Approval / Status:** User explicitly requested: "Before Week 8 operations, correct the runbook’s two nonexistent script paths and prepare the Week 8 revision manifest."
- **Blockers:** None.
- **Next:** Monitor Week 7 games through Saturday; after Sunday finals, execute the runbook for Week 8 candidate preparation and preview rehearsal.

## Context and Decisions
- **Runbook Ingestion Alignment:** In `docs/ops/weekly_runbook.md`, placeholders `fetch_cfbd_data.py` and `export_market_quotes.py` were replaced with repository-canonical commands:
  - CFBD completed-week plays and betting lines: `scripts/data/ingest_week.py --year 2026 --week <COMPLETED_WEEK> --entities plays,betting_lines`
  - The Odds API market quotes: `scripts/data/fetch_odds_api_market_quotes.py --year 2026 --week <NEXT_WEEK> --confirm`
  - Market snapshots builder: `scripts/pipeline/build_week_market_snapshot.py --year 2026 --week <NEXT_WEEK> --as-of <CUTOFF> ...`
- **Week 8 Manifest Pre- and Post-Week Cutoffs:**
  - Schedule dataset inspection confirmed Week 7 kickoff maximum is Saturday night `2026-10-18T02:30:00Z` (games ending ~06:00:00Z). Week 7 post-week cutoff set to Sunday morning `2026-10-18T15:00:00Z`.
  - Week 8 games schedule has 56 games, with early mid-week games starting Tuesday `2026-10-20T23:00:00Z`. Week 8 pre-week cutoff set to `2026-10-20T18:00:00Z`.
  - Input silver dataset references inherit canonical versions for schedule, venues, and teams, ready to be updated with fresh finals/market quotes upon Sunday ingestion.
- **Validation:** `validate_revision` passes cleanly; season pytest suite (312 passed); Ruff check and format check passed; MkDocs build clean; contracts check passed; quality registry (32 checks) passed; `git diff --check` clean.

## Work Completed
- Updated `docs/ops/weekly_runbook.md` with exact runnable commands for CFBD ingestion, Odds API quote capture, and market snapshot generation.
- Created `conf/season/2026/revision_manifest_w8_v1.json` conforming to `season_revision_v1` schema with pre-week cutoffs 0–8 and post-week cutoffs 0–7.
- Verified manifest schema validation via `cks_picks_cfb.season.manifest.validate_revision`.

## Files Modified
- `docs/ops/weekly_runbook.md` — replaced placeholder script paths with verified ingestion and quote snapshot commands.
- `conf/season/2026/revision_manifest_w8_v1.json` — created canonical Week 8 revision manifest template.
- `session_logs/2026-10-14/13-runbook-script-paths-and-w8-manifest.md` — session log.

## Validation
- [x] `uv run python -c "from cks_picks_cfb.season.manifest import validate_revision; ..."` (PASSED)
- [x] `uv run pytest tests/test_season*.py -q` (312 passed in 24.94s)
- [x] `uv run --extra dev ruff check .` (PASSED)
- [x] `uv run --extra dev ruff format --check .` (PASSED)
- [x] `make contracts-check` (PASSED)
- [x] `PYTHONPATH=src uv run python -m cks_picks_cfb.quality --verify-registry` (PASSED, 32 checks, 0 problems)
- [x] `uv run mkdocs build --quiet` (PASSED)
- [x] `git diff --check` (PASSED)

## Amendments and Blockers
- None.

## Handoff Notes
- **Resume at:** Await completion of Week 7 games (Sunday Oct 18), then follow Section 1 of `docs/ops/weekly_runbook.md` to ingest Week 7 finals/plays and fetch Week 8 market quotes.
- **Watch out for:** Once Week 7 finals and Week 8 market quotes are written, update `conf/season/2026/revision_manifest_w8_v1.json` with the new silver dataset version URIs and SHA-256 hashes before executing `run_season.py prepare`.
- **Proposed commit:** `docs(ops): align weekly runbook ingestion commands and prepare week 8 revision manifest`

**tags:** ["runbook", "operations", "season", "manifest"]
