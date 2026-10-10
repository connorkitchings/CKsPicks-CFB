# Session: Preview verification, Week 6 market-sources lock, Week 7 packet smoke test

## TL;DR
- **Worked On:** the three remaining pre-Monday engineering tasks.
- **Outcome:** Preview verified (one approval difference found); Week 6 market-sources lock tool built, unit tested and dry-run on real data; Week 7 advance and rollback packets validated against the real Preview Week 5 prospective record; one packet defect fixed (empty `protected_runs`).
- **Plan Contract:** `docs/plans/2026-10-08/02-repair-track-certification-and-closure.md` Amendment 7.
- **Approval / Status:** user requested all three tasks in-session (2026-10-10); Preview approval fix is a user-run SQL, not applied.
- **Blockers:** Preview B2 approval `first_live_week` is 5 (Production 6), so a Preview forward packet is refused until the user updates it.
- **Next:** Monday sequence in `docs/plans/2026-10-10/01-week7-cutover-run-sheet.md`.

## Context and Decisions
- The smoke test is the first end-to-end use of real evidence: real Week 5 legacy attestation (database and R2), real run manifests, real registered authorizations and both approvals. Week 7 runs and statistics are fixtures because they do not exist yet.
- The lock tool reuses `select_best_quote` for eligibility so the lock and the replay cannot disagree.

## Files Modified
- New: `src/cks_picks_cfb/rebuild/market_sources_lock.py`, `scripts/pipeline/build_week_market_sources_lock.py`, `tests/test_market_sources_lock.py`, `tests/test_serving_quote_gaps.py`, `tests/test_week7_packet.py`.
- Changed: `src/cks_picks_cfb/rebuild/successor_lock.py` (declared gaps, display-only original run), `scripts/pipeline/build_v5_intended_update_serving.py` (declared gaps for either target, display-only replay source), `src/cks_picks_cfb/ops/v5_batch_selection_v2.py` and `v5_packet_builder.py` (empty `protected_runs`, outside-week selection check), `tests/test_successor_lock.py`.
- Docs: contract Amendment 7, run sheet, this log.

## Validation
- [x] `ruff check`, `ruff format --check`, `make contracts-check`, strict mkdocs.
- [x] Parallel suite with `-W error`: 2,465 passed, 3 skipped.
- [x] Postgres files on a scratch PostgreSQL 14: 28 passed, 1 failed (`test_publish_null_lean_database.py::test_null_lean_with_quotes_persists_no_selection`, fails identically on the committed baseline).
- [x] Read-only real-data runs: Preview and Production registered-release export; lock tool on d2-era Week 6 data (58 games, 55 eligible, 3 gaps per target, matching the d2 omitted games); Week 7 packet smoke test.
- [ ] 6B flow test, web checks, Preview rehearsal, replay serving verifier with declared spread gaps.

## Handoff Notes
- **Resume at:** Monday run sheet; first the Preview migrator `UPDATE` for the B2 approval.
- **Watch out for:** the serving verifier, packager and publisher were not run on a replay with declared spread gaps.

**tags:** ["week7", "cutover", "market", "release"]
