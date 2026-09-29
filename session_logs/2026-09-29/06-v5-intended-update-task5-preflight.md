# Session: Task 5 preflight — lineage-aware release and serving

## TL;DR
- **Worked On:** Task 5 of `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` — release registry, batch selection, publication boundary, rating-currency gate, web lineage scoping; preflight only.
- **Outcome:** Scaffolding reviewed against the contract; all unit/static gates pass; migration 0018 proven on scratch Postgres (clean apply, idempotent re-apply, legacy backfill, least-privilege grants). No repo code changed; no Preview/Prod mutation. Web `build` deferred to Task 6 per plan.
- **Plan Contract:** `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` (`In Progress`).
- **Approval / Status:** User approved the Task 5 preflight plan. Exact production release remains a later packet-specific decision.
- **Blockers:** None for preflight. One interface question for Task 6 (below).
- **Next:** Task 6 (Preview rehearsal + exact packets).

## Context and Decisions
- Task 5 scaffolding already existed (12 modified + related untracked files); this session changed no repo code.
- `validate_intended_update_release_record` pins `environment: production` and `require_…` queries production authorizations only. Consequence: a Preview batch selection of successor runs needs production authorizations to exist as reference. This is either rehearsal-fixture design (mirror prod authorizations) or a gap requiring an environment-aware `require_`. Flagged as a Task 6 decision, not a Task 5 blocker.
- `ownerSourceForCutoff` changed newest-wins → first-published-wins deliberately (legacy deep links keep original lineage); test updated to match.

## Work Completed
- Consistency: all 10 statements of 0018 present in `schema.sql`; both tables in `contracts/schema.ts` + `web/src/lib/schema.ts`; `RECOMPUTE_STATS_SQL` import resolves; `source_manifest_sha256` predates 0018 (from 0013).
- Contract review: old pair preserved via backfill; new tables SELECT-only for pipeline, nothing for web; batch selects weeks in order in the caller's transaction with stats recompute last; publication boundary verifies the full serving→forecast→verifier→artifact chain; web scopes every rating query to the selected run's rating SHA with `rating_manifest_sha256` mandatory for `v5-%` models.
- Gates: 62 pytest (public_selection + publish_to_db) passed; `make contracts-check` passed; Ruff format+lint clean (7 files); web typecheck + lint clean; node web tests 9/9 passed.
- Scratch Postgres (local, thrown away): `schema.sql` applies clean to an empty DB; 0018 applies cleanly onto a pre-0018 state, re-applies idempotently, backfills `legacy-v5-<bundle>` from `v5_release_policy`, and grants verify (pipeline SELECT-only, web none).

## Files Modified
- None. `session_logs/2026-09-29/06-v5-intended-update-task5-preflight.md` — this log.

## Validation
- [x] 0018 numbering confirmed (0017 is the endpoint); no DROP/ALTER/TRUNCATE; `IF NOT EXISTS` + `ON CONFLICT DO NOTHING` throughout.
- [x] Batch atomicity failure-injection test passes (no stats recompute after a failed week).
- [x] Scratch-DB proof of schema snapshot + upgrade path (see above).
- [x] `git diff --check`: clean.
- [ ] Web `build`, Preview migration apply, Preview batch selection, exact production packets — Tasks 6–7.

## Amendments and Blockers
- No architecture amendment. The production-pinned authorization question is recorded above for Task 6.

## Handoff Notes
- **Resume at:** Task 6 Preview rehearsal: commit first, then R2 `--apply` chain (Tasks 2–4 artifacts + verifiers), Preview migration 0018, rating projection, replacement runs + grades, atomic batch selection (resolving the authorization-environment question), rollback/reactivation test, exact production packets.
- **Watch out for:** W5 kickoff 2026-10-02T00:00Z bounds the prospective decision. No `--apply` or DB writes until the commit decision is resolved.

**tags:** ["ratings", "v5", "production", "implementation", "task5"]
