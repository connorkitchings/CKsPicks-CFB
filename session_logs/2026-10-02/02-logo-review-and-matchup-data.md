# Session: Logo review and matchup data pipeline (Preview)

## TL;DR
- **Worked On:** (1) Reviewed the logo rollout (contract 07). (2) Finished the matchup team-stats data architecture (contract 10, Phase 5) and ran it on Preview, with venues (contract 08).
- **Outcome:** Logos were applied correctly (138 teams, 552 files, all hashes match); fit and test gaps fixed. Team stats weeks 1-5 (10,460 rows) and 271 venues are live on Preview; matchup pages render real Week 5 data. Found and fixed a bug that would have hidden venues, team stats and sportsbook selections in production.
- **Plan Contract:** `docs/plans/2026-10-01/10-authentic-team-stats-pipeline.md` (Amendment 1); `08-game-venue-location.md` log.
- **Approval / Status:** User approved the plan (Sol plan, implemented in-session) with decisions: promote Silver to the production catalog; Preview only this session; include venues, pre-game ratings, logo fixes. Contract 10 stays Approved until production runs.
- **Blockers:** None for Preview. Production steps await the user's go.
- **Next:** See Handoff Notes.

## Context and Decisions
- Preview and production share one R2 bucket, so Silver promotion is catalog registration only (no copy); a different bucket is refused.
- `source_versions` added to migration 0020 in place (unapplied on both databases at the time).
- Verifier gates on like-for-like teams because CFBD includes FCS games (all-teams rho 0.77-0.88 in weeks 3-4; like-for-like 0.96-0.99).

## Work Completed
- `team_stats.py`: `yards_to_first`, conversion/dropback flags, regular season, coverage check, error wrapping (+12 tests, schema pin).
- Migration 0020 `source_versions`; `publish_team_stats.py` `--weeks`, version pins, provenance.
- `promotion.py` + `promote_silver_versions.py` (+3 tests with two databases); `verify_team_stats.py`.
- Web: `getRatingsAsOf`, percentile rank tiers, `db-result.ts` guard fix, legacy rating names, footer link spacing, `TeamLogo` sizing (+ e2e for `/`, `/results`, `/matchup`), `contracts/validation.py` logo check, `test:logos` in `test:publication`.
- Preview: applied 0019 and 0020; published venues (271) and team stats weeks 1-5; CFBD verification; real matchup screenshots viewed (light and dark, 3x, no external hosts).
- Docs: contract 10 amendment, contract 08 log, status, plans index, decision log, weekly pipeline, operator checklist, Makefile targets, AGENTS pitfall.

## Files Modified
`src/cks_picks_cfb/data/{team_stats,promotion}.py`, `scripts/pipeline/{publish_team_stats,promote_silver_versions,verify_team_stats}.py`, `contracts/{migrations/0020,schema.sql,schema.ts,validation.py}`, `web/src/{lib,components,app/matchup}/**`, `web/e2e/logos.spec.ts`, `web/package.json`, `tests/{test_team_stats,test_promotion,test_migration_integration}.py`, docs and Makefile as listed above.

## Validation
- [x] Python `pytest tests/ -W error`: 1,578 passed (two local test databases for migration and promotion tests).
- [x] Web: lint, typecheck, `test:publication` (84), `CFB_UI_TEST_MODE=1 npm run build`, Playwright 33/33.
- [x] `contracts/validation.py` (including the new logo check, negative-tested).
- [x] Preview: dry run, publish, SQL checks (games per team <= weeks elapsed), CFBD verification weeks 2-5.
- [x] Production promotion dry run (read-only): 6 new versions, 11 captures, hashes verified.
- [x] `git diff --check`, ruff, mkdocs (see final run).

## Amendments and Blockers
- Mistake: the first real-data page showed "not published" because of the Neon result-shape bug; fixture mode could not reveal it. Fixed and documented.
- Not changed, noted: `getTeamRankMap` (rank on Picks cards) still keys by game team name, so the nine legacy-named teams get no rank there; `publish_review.py` email logos still broken (pre-existing); `/teams/<team>` link targets for legacy-named teams not verified; `web/test-results/.last-run.json` is tracked in git and changes on every Playwright run.
- Releasing `dev` to production also switches on the sportsbook selection display (its guard was always false).

## Handoff Notes
- **Resume at:** user decides production: (1) `promote_silver_versions.py` real run via the production wrapper, (2) apply 0019/0020 with the owner credential, (3) publish venues and team stats weeks 1-5 to production, (4) set `CFB_MATCHUP_ENABLED=1` when ready; then Week 5 matchup page design.
- **Watch out for:** week 5 snapshot is final only after week 4 finals; re-run for week 6 after Week 5 finals. Production writes use the restricted pipeline wrapper; migrations use the owner credential.

**tags:** ["matchup", "pipeline", "logos", "web", "data"]
