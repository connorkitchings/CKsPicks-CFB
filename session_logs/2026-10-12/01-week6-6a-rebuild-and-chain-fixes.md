# Session: Week 6 6A rebuild, audit fixes and Week 7 fallback draft

## TL;DR

- **Worked On:** Resumed the Week 6 replay chain toward the Week 7 cutover. Built the Week 6 6A rebuild in Preview, fixed two code blockers found by a read-only audit, and drafted the standalone Week 7 fallback.
- **Outcome:** `6a-rebuild-w6-20261012-r2` built all 11 stages in Preview (not yet verified or published). The leakage audit now handles a Week 6 replay and a Week 7 live run. The historical byplay_v1 collisions are declared per season.
- **Plan Contract:** [`docs/plans/2026-10-11/02-week7-cutover-gate-waiver-and-readiness.md`](../../docs/plans/2026-10-11/02-week7-cutover-gate-waiver-and-readiness.md); run sheet [`docs/plans/2026-10-10/01-week7-cutover-run-sheet.md`](../../docs/plans/2026-10-10/01-week7-cutover-run-sheet.md)
- **Approval / Status:** Owner chose audit Option A (Week 6 replay audited game by game), approved the collision-exception fix, and approved pivoting to the single-week route if the Advance-Mode producers are not small. Contract remains In Progress.
- **Blockers:** None for the next step. Verify and publish of 6A are separate Preview writes awaiting go-ahead. Three Advance-Mode cutover producers do not exist (see Handoff).
- **Next:** `rebuild_6a.py verify` then `publish` for `conf/rebuild/6a_w6_v1.yaml` at the HEAD SHA, then fill the Task 4 root-manifest hash and commit.

**tags:** ["week7", "rebuild", "6a", "leakage-audit", "cutover"]

## Context and Decisions

- The first 6A attempt died overnight on an R2 network error. The second failed ~20 minutes in with `byplay_v1 cannot represent distinct source plays at one sequence`.
- Diagnosis (read-only): the collisions are in pinned historical plays, not Week 6: 2021 game 401310699 and 2025 games 401756916, 401761632, 401762831. The Oct 9 collision guard (`d855bd55`) postdates the Week 5 rebuild, which silently kept the first row.
- Decision: declare those games per season in `byplay_v1_collision_exceptions`; listed games keep the first row (legacy parity), unlisted collisions fail, unused exceptions fail. This re-accepts the loss of one play per collided sequence (silent in every existing lineage).
- The first run's preflight record is immutable and bound to the old plan hash, so the plan got a new run ID, `6a-rebuild-w6-20261012-r2`.
- A read-only audit of the chain scripts found: the leakage audit would flag all 58 Week 6 replay games (single-cutoff rule) and was capped at Week 6; the 6B plan must keep `6b_source_refs_w5_v1.json`; `make rebuild-6a` ignores `--plan`; the Week 7 live rating and several run-sheet commands were missing.
- Owner decisions: Option A for the Week 6 cutoff; if the three missing cutover producers (finals-certification receipts, prospective-records payloads, R2 ref uploader) are not small, pivot to the `publish_to_db` then `select_public_run` route for Week 7 and keep Advance Mode for Week 8.

## Work Completed

- Audit fix: `audit_point_in_time_leakage.py` applies the single pre-kickoff rule only to display/live runs; adds `--live-week`; `--through-week` up to 7.
- Collision exceptions threaded through `allplays_to_byplay`, `build_preaggregation_pipeline` and the silver stage, with the policy in the Week 6 6A plan.
- Run rename to `-r2` in the 6A and Task 4 plans, plus the refreshed plan pin.
- Preflight passed (`e2609793…`); the build ran under `caffeinate` from 18:33Z to 19:43Z.
- Drafted `docs/plans/2026-10-11/03-week7-standalone-fallback.md` (uncommitted, awaiting approval). The audit showed Advance-Mode v2 cannot protect Weeks 0–6, so it uses the single-week route.
- Stage hashes of the build: baseline `6d4f4984…`, silver `85c3fbea…`, eligibility `1216637e…`, comparison `900c18e2…`, gold `7a73878a…`, measurements parity `cdb81d9e…`, ratings parity `60ee3496…`, ratings `70d9c626…`, offsets `6b8e0ac9…`, silver_2026 `dd21cd07…`, states_2026 `3c1084c9…`.

## Files Modified

- `scripts/pipeline/audit_point_in_time_leakage.py`, `tests/test_point_in_time_loader.py` — commit `23318090`
- `src/cks_picks_cfb/features/byplay/enrichment.py`, `src/cks_picks_cfb/features/pipeline.py`, `src/cks_picks_cfb/rebuild/silver.py`, `tests/test_play_identity_v2.py`, `tests/test_rebuild_silver.py`, `conf/rebuild/6a_w6_v1.yaml`, `conf/rebuild/6a_task4_w6_v1.yaml` — commit `432ff040`
- `conf/rebuild/6a_w6_v1.yaml`, `conf/rebuild/6a_task4_w6_v1.yaml` (run rename, plan pin) — commit `30a12a6d`
- `docs/plans/2026-10-11/03-week7-standalone-fallback.md` — new, uncommitted
- `session_logs/2026-10-12/01-week6-6a-rebuild-and-chain-fixes.md` — this log, uncommitted
- Local only: `.claude/` added to the repo's git exclude.

## Validation

- [x] Full pytest at the collision-exception change: 2658 passed, 24 skipped; leakage-audit and loader tests: 29 passed; ruff check and format clean on touched files.
- [x] Plan and silver tests after the rename: 28 passed.
- [x] 6A preflight passed; all 11 stages built.
- [ ] 6A `verify` and `publish` not yet run.
- [ ] The collision exceptions were exercised on the real 2021 and 2025 plays by the build (it passed), but no separate parity report was reviewed.
- [x] `git diff --check`
- [ ] `uv run mkdocs build --quiet` not run (the only docs change is the uncommitted fallback draft).

## Amendments and Blockers

- None filed yet. The collision exceptions and the run rename should be recorded in the repair-track contract as an amendment.
- The audit's other findings are open: Makefile `rebuild-6a` target, run-sheet corrections for steps 4–9, the Week 7 live rating, and the three missing Advance-Mode producers.

## Handoff Notes

- **Resume at:** `rebuild_6a.py verify --plan conf/rebuild/6a_w6_v1.yaml --expected-code-sha $(git rev-parse HEAD)`, then `publish`, each its own Preview go-ahead.
- **Watch out for:** every apply needs a clean committed tree. Commit the fallback draft or move it out first. Pivot gate is Tue 14:00Z; the Week 7 market must be complete for all 59 games or three Week 7 scripts fail. If the producers are not small, take the single-week route.
