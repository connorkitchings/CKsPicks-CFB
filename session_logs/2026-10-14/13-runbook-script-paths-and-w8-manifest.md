# Session: Runbook script paths correction and Week 8 manifest preparation

## TL;DR
- **Worked On:** Corrected two nonexistent script paths in `docs/ops/weekly_runbook.md` and prepared the pending Week 8 revision manifest template `conf/season/2026/revision_manifest_w8_v1.template.json`.
- **Outcome:** Initial script-path corrections and cutoff planning were completed. Follow-up review found incomplete command wiring and stale input pins; the October 15 repair replaces these with a verified checklist and intentionally invalid pending template. Schema validation of the original file did not establish operational readiness.
- **Plan Contract:** docs/plans/2026-10-14/01-season-operations-and-week7-bridge.md
- **Approval / Status:** User explicitly requested: "Before Week 8 operations, correct the runbook’s two nonexistent script paths and prepare the Week 8 revision manifest."
- **Blockers:** The original commands omitted required request inventory, consistent market capture IDs, and cumulative Silver refresh. Week 8 operational readiness is deferred to the post-Week-7 gate on Sunday, October 18.
- **Next:** Monitor Week 7 games through Saturday; after Sunday finals, execute the runbook for Week 8 candidate preparation and preview rehearsal.

## Context and Decisions
- **Original command sketches (not runnable):** In `docs/ops/weekly_runbook.md`, placeholders `fetch_cfbd_data.py` and `export_market_quotes.py` were replaced with repository-canonical commands:
  - CFBD completed-week plays and betting lines: `scripts/data/ingest_week.py --year 2026 --week <COMPLETED_WEEK> --entities plays,betting_lines`
  - The Odds API market quotes: `scripts/data/fetch_odds_api_market_quotes.py --year 2026 --week <NEXT_WEEK> --confirm`
  - Market snapshots builder: `scripts/pipeline/build_week_market_snapshot.py --year 2026 --week <NEXT_WEEK> --as-of <CUTOFF> ...`
- **Week 8 Manifest Pre- and Post-Week Cutoffs:**
  - Schedule dataset inspection confirmed Week 7 kickoff maximum is Saturday night `2026-10-18T02:30:00Z` (games ending ~06:00:00Z). Week 7 post-week cutoff set to Sunday morning `2026-10-18T15:00:00Z`.
  - Week 8 games schedule has 56 games, with early mid-week games starting Tuesday `2026-10-20T23:00:00Z`. Week 8 pre-week cutoff set to `2026-10-20T18:00:00Z`.
  - Original Silver references were copied from prior runs and did not cover the Week 7/8 transition. The repaired template retains verified venue/team pins and leaves refreshed inputs pending until Sunday ingestion.
- **Original validation (before October 15 repair):** `validate_revision` passed for the earlier file; season pytest suite (312 passed); Ruff check and format check passed; MkDocs build clean; contracts check passed; quality registry (32 checks) passed; `git diff --check` clean.

## Work Completed
- Updated `docs/ops/weekly_runbook.md` with initial command sketches (subsequently found incomplete) for CFBD ingestion, Odds API quote capture, and market snapshot generation.
- Originally created a schema-valid manifest with cutoffs 0–8 and 0–7 but stale data pins. The October 15 repair renames it to `conf/season/2026/revision_manifest_w8_v1.template.json` and makes it intentionally invalid until operational inputs exist.
- Originally checked only manifest schema via `cks_picks_cfb.season.manifest.validate_revision`.

## Files Modified
- `docs/ops/weekly_runbook.md` — initial ingestion command sketches; corrected by the October 15 repair.
- `conf/season/2026/revision_manifest_w8_v1.template.json` — created pending Week 8 revision manifest template.
- `session_logs/2026-10-14/13-runbook-script-paths-and-w8-manifest.md` — session log.

## Original validation (before October 15 repair)
- [x] `uv run python -c "from cks_picks_cfb.season.manifest import validate_revision; ..."` (PASSED)
- [x] `uv run pytest tests/test_season*.py -q` (312 passed in 24.94s)
- [x] `uv run --extra dev ruff check .` (PASSED)
- [x] `uv run --extra dev ruff format --check .` (PASSED)
- [x] `make contracts-check` (PASSED)
- [x] `PYTHONPATH=src uv run python -m cks_picks_cfb.quality --verify-registry` (PASSED, 32 checks, 0 problems)
- [x] `uv run mkdocs build --quiet` (PASSED)
- [x] `git diff --check` (PASSED)

## Amendments and Blockers
- Corrected on October 15 under `docs/plans/2026-10-15/01-repair-weekly-ingestion-and-w8-template.md`: original validation results above describe the earlier sketch, not a runnable weekly refresh.
- The renamed template deliberately fails operational validation until fresh captures, cumulative inputs, and checksums are supplied. Expected 56 Week 8 games and first kickoff `2026-10-20T23:00:00Z` remain prior schedule evidence requiring fresh reconciliation.
- Readiness is deferred to Sunday, October 18 after Week 7 finals; Preview rehearsal and the exact production release gate remain required.

## Handoff Notes
- **Resume at:** Await completion of Week 7 games (Sunday Oct 18), then follow Section 1 of `docs/ops/weekly_runbook.md` to ingest Week 7 finals/plays and fetch Week 8 market quotes.
- **Watch out for:** Once Week 7 finals and Week 8 market quotes are written, assemble operational `conf/season/2026/revision_manifest_w8_v1.json` from the pending template using verified cumulative Silver URIs, capture time, and SHA-256 hashes before executing `run_season.py prepare`.
- **Proposed commit:** `docs(ops): align weekly runbook ingestion commands and prepare week 8 revision manifest`

**tags:** ["runbook", "operations", "season", "manifest"]
