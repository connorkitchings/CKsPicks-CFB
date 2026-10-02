# Session: Matchup data layer v2, Phase A on Preview

## TL;DR
- **Worked On:** Contract `docs/plans/2026-10-02/01-matchup-data-layer-v2.md` Tasks 0-7 and Phase A of Task 8 (2026, Preview only).
- **Outcome:** Everything the V5 ratings use per team per week is now in Neon on Preview, bound to the rating manifest the site serves and reconciled by gates; matchup pages show the new raw metrics in three sections. Production, the release and Phase B (2025) are pending.
- **Plan Contract:** `docs/plans/2026-10-02/01-matchup-data-layer-v2.md` (Approved).
- **Approval / Status:** User approved the plan and its refinements in-session; "carry on through Phase A (Tasks 1-7 and Phase A of Task 8)", Preview and dev only.
- **Blockers:** None.
- **Next:** See Handoff Notes.

## Context and Decisions
- The ratings use the `possession_*` family (PPP, EPA/possession, plays/possession, non-offense points), not the older `rating_measurement_*` family I first described.
- Weekly adjusted values are recomputed with the ratings' own adjuster (`adjust_possession_history`) per cutoff because stitched post-week terminals disagree with the rating evidence for weeks 3 and 4; the recompute matches the evidence to 9e-16 for all weeks.
- Names: artifact names resolved against the season's game names (a blind inverse of `TEAM_LOGO_MAP` is wrong for Hawai_i and FIU).

## Work Completed
Migration 0021 (5 tables, FK to `v5_rating_snapshots`, read indexes) and tests; public ratings helpers; pure builders and 13 tests; verified loader, 11 gates, stale-key/conflict checks, payload hash, receipt, `publish_matchup_data.py` and read-only `verify_matchup_data.py` with tests (DB tests on a local Postgres); Silver play filter aligned to V5 with `--diff`; web read layer (raw only), grouped 14-metric table; operator command `publish-matchup-data`, runbook, Makefile; Preview migration, publish, verify, Silver republish; real Week 5 pages viewed (Ohio State at Iowa, San José State at Hawai'i, light and dark, 3x).

## Files Modified
`contracts/{migrations/0021,schema.sql,schema.ts,validation.py}`, `web/src/lib/{schema,queries,team-stats,matchup}.ts`, `web/src/components/matchup/UnitMatchupTable.tsx`, `web/e2e/matchup.spec.ts`, `src/cks_picks_cfb/data/{matchup_data,matchup_publish,team_stats}.py`, `src/cks_picks_cfb/ratings/possession_*.py` (aliases), `src/cks_picks_cfb/ops/__main__.py`, `scripts/pipeline/{publish_matchup_data,verify_matchup_data,publish_team_stats}.py`, tests, docs, Makefile.

## Validation
- [x] Python `pytest tests/ -W error`: 1,609 passed; `ruff format --check`, `ruff check`, `contracts/validation.py`, `mkdocs build --strict`.
- [x] Web: lint, typecheck, `test:publication` (88), `CFB_UI_TEST_MODE=1 npm run build`, Playwright 33/33.
- [x] Preview: dry run (11 gates ok), publish, idempotent re-run (1 receipt), verifier "0 rows differing", SQL spot checks, real pages viewed.
- [x] `git diff --check`.

## Amendments and Blockers
- The old Silver filter counted overtime drives and placeholder plays (contract amendment): production republish needs the user's go.
- `ops project-v5-ratings` still does not dispatch the intended-update manifest (documented).
- Not verified: production behaviour of the new tables (not migrated there), Week 6+ lineage.

## Handoff Notes
- **Resume at:** user decides production: (1) migration 0021 with the owner credential, (2) publish with `--expect-payload-sha a4a1062db790164850f31707350a93d1f2650363b47502ad3b67b99407571215`, (3) republish Silver team stats weeks 1-5 (`--diff` first), (4) merge `dev` into `main`. Then Phase B (2025).
- **Watch out for:** the publisher refuses to leave stale rows (pipeline role cannot DELETE); components are append-only per manifest; matchup pages stay closed until `CFB_MATCHUP_ENABLED=1`.

**tags:** ["matchup", "pipeline", "ratings", "web", "data"]
