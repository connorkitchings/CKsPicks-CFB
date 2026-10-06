# Stage 7A: Release Foundations

- **Status:** In Progress (2026-10-06; implementation started in the task explicitly authorized for this exact contract path)
- **Created:** 2026-10-06
- **Planner:** Sol planning workflow
- **Approval source:** User instruction in this task: “PLEASE IMPLEMENT THIS PLAN,” naming this exact path
- **Implementation log:** `session_logs/2026-10-06/06-stage7a-release-foundations-implementation.md`
- **Commit policy:** Separate plan commit before implementation; all Git operations are user-run
- **Baseline:** `dev` at `320436f1d13b38068b9e21a2ea64d41a755c1551`; Stage 6B Implemented with Preview-only evidence
- **Authority:** Contract 04 Amendment 2 and [Appendix B](../2026-10-03/window2/release-schema-and-web.md)

## Goal

Build and verify the schema, authorization guards, parameterized release controller and web read paths needed for Stage 7B. Cutover week `N` remains a runtime packet value. Stage 7A changes no public selections or serving pointers, creates no authorization or revocation records, and does not activate reconstructed history.

Stage 7A is complete when the migrations, roles, guards, controller and web behavior pass the checks below; the Preview schema and effective grants have been independently read back after a separately authorized Preview migration; documentation and an exit log are complete. Production migration and the live Preview cutover rehearsal remain Stage 7B gates.

## Current State and Decisions

- Stage 6B is Implemented and published to Preview on build SHA `eca6871`; the Stage 6B close-out commit is `320436f`.
- `contracts/migrations/0022_grant_market_quotes_web.sql` is the latest migration and is reported applied. Before applying a new migration, inspect each target database's migration ledger and stop on drift.
- The approved new migrations are mechanically numbered `0023_prospective_week_records.sql` and `0024_v5_release_revocations.sql`. Do not edit applied migrations.
- The existing authorization registries are `public.v5_model_bundle_approvals` and `public.v5_intended_update_release_authorizations` (migration 0018). The revocation trigger references these actual tables; no additional reconstruction or publication-authorization table is introduced.
- Existing batch selection is `v5_intended_update_batch_selection_v1`. Add v2 while preserving v1 behavior. The packet's `N` is variable; only Stage 7B chooses a concrete week.
- Current public selection reads `site_week_selections`; current Performance aggregation is selection-based; matchup visibility does not yet compare forecast/rating provenance with published team-stat lineage.
- Stage 7A may prepare and test code with isolated databases. Preview schema migration is an operator action after a separate migration authorization. No Preview or production serving-state, selection, authorization, or revocation rows are written in Stage 7A.

## Scope and Interfaces

### Included

- `public.prospective_week_records` and `ops.v5_release_revocations`, including SQL triggers, role grants, canonical Python/TypeScript schemas, and migration tests.
- Packet-bound authorization and revocation tooling; shared transaction-scoped revocation locks and checks in public selection and all V5 freeze entrypoints.
- `v5_intended_update_batch_selection_v2` dry-run, apply and exact rollback capability, exercised only against isolated databases in Stage 7A.
- Separate retrospective reconstruction and prospective V5 Performance queries and labels, plus matchup lineage states and share controls.
- Preview-only schema and effective-grant readback following a separately authorized migration operation.

### Excluded

- Choosing `N`, preparing a concrete release packet, inserting approvals/authorizations, or revoking them.
- Preview or production run selection, `current_week` changes, freeze, scoring, matchup repin, or rollback execution.
- Production migrations, production database writes, public deployment, model changes, or changes to Stage 6B artifacts.
- A new table that duplicates the Stage 6B receipt or existing authorization registries.

## Implementation Tasks

### 1. Add the prospective and revocation schemas

Create the two append-only migrations after 0022 and synchronize `contracts/schema.sql`, `contracts/schema.ts`, and `web/src/lib/schema.ts`.

`public.prospective_week_records` has primary key `(season, week)`, unique `run_id` referencing `prediction_runs` with `ON DELETE RESTRICT`, `freeze_receipt_uri`, 64-character `freeze_receipt_sha256`, `frozen_at`, `first_kickoff_utc`, and nonempty `decision_ref`. Restrict this schema version to season 2026 and weeks 5 onward. Database validation binds a row to the same-slate V5 run and authentic freeze metadata and requires `frozen_at < first_kickoff_utc`. The application verifies immutable receipt bytes and signature. Reject deletes. Permit an update only for a verified replacement freeze for the same slate before the earliest kickoff evidenced by both stored and current schedule state; an identical retry is a no-op. Historical inserts require original, authentic pre-kickoff selection/freeze evidence and cannot manufacture prospective status.

`ops.v5_release_revocations` has key `(record_type, record_id)`, with `record_type` limited to `bundle_approval` or `intended_update_authorization`, plus nonempty `decision_ref` and `revoked_at TIMESTAMPTZ DEFAULT NOW()`. Its trigger validates the ID against the corresponding public registry. Revoke UPDATE and DELETE through both triggers and privileges; identical inserts are no-ops and conflicting retries fail.

Create `cks_release_authorizer` as a NOLOGIN group. Grant it SELECT and INSERT on revocations; grant `cks_pipeline` SELECT only there and SELECT/INSERT/UPDATE on prospective records subject to triggers; grant `cks_web` SELECT only on prospective records and no access to revocations. Explicitly revoke default and inherited grants that would broaden these permissions. Verify effective role membership and privileges for actual Preview identities. Resolve the existing Production authorization identity from verified operator configuration before adding its membership; do not infer or create a replacement identity in this task.

**Acceptance:** fresh-schema and upgrade tests pass from the 0022 chain; constraints, foreign keys, scope, no-delete, verified pre-kickoff replacement, post-kickoff rejection, authentic historical insertion, idempotence, and role denials behave as specified.

### 2. Add packet-bound authorization and revocation guards

Extend the Preview authorization tool to accept exact packet-bound IDs, hashes, `N`, and decision reference while retaining its Preview environment and exact identity guards. Add the separately Production-guarded authorization path using the verified existing Production authorization identity. Both record an immutable receipt with code SHA, canonical record hashes and decision reference. The pipeline only verifies authorizations; it never inserts them. Add a separate user-run revocation operation that appends a revocation and retains its receipt.

Implement shared transaction-scoped advisory-lock helpers keyed by approval and authorization IDs, acquired in deterministic sorted order. Selection and every V5 freeze path take shared locks and check both bundle and run-authorization revocations through the protected transaction. Revocation takes exclusive locks for those same keys. Cover `src/cks_picks_cfb/ops/public_selection.py`, `src/cks_picks_cfb/ops/v5_release.py`, `src/cks_picks_cfb/ops/v5_intended_update_release.py`, `src/cks_picks_cfb/ops/v5_cycle.py`, `scripts/pipeline/freeze_week.py`, and `scripts/pipeline/run_v5_weekly_cycle.py`; no alternate V5 entrypoint may bypass the checks. Keep the existing pipeline lease and current/session-user guards.

**Acceptance:** missing, mismatched, or revoked approvals fail before selection/freeze writes; Preview and Production identities cannot cross environments; pipeline/web roles cannot create or alter authorization/revocation rows; same-record retries are idempotent; concurrent revoke-versus-select/freeze tests prove serialization without deadlock.

### 3. Add the v2 atomic selection and rollback controller

Add `v5_intended_update_batch_selection_v2` to the existing batch CLI and cursor-level `ops` helpers. Keep v1 parsing and behavior intact. Validate signed packet and payload bytes by their raw SHA-256 references, complete expected current state, protected runs, exact authorization IDs and receipts, and exact before/after payloads. Require replay replacements for contiguous Weeks `0..N-1` that are certified and stabilized, plus one corrected pending run for unstarted `N` that still meets the existing freeze deadline. Keep original quote/cutoff bindings and the approved one-hour freeze and 24-hour stabilization rules.

In one caller-owned transaction, use a fixed lock order for selections, `current_week`, prospective records, team stats and system stats, plus existing per-week locks in ascending order. Recheck live state and revocations under locks. Require before/after team-stat payloads to have identical complete keys and provenance, preserve newly unavailable metrics as null-valued rows, select the replay set and pending `N`, move `current_week` to `N`, register only eligible completed-week prospective mappings, recompute public system stats, and read back all expected business/provenance rows before commit. Helpers may not open another connection or commit independently.

Use a distinct signed rollback packet with exact expected after-state and retained before payload. Route rollback through the same locks, authorization checks, protected-run checks and readback. Preserve prospective history and approval records. Reject rollback against stale state or later dependent releases; if `N` has started, require the safe serving decision specified by Appendix B. Provide an idempotent exact retry and a read-only dry run. Exercise apply, retry, failure rollback and compensating rollback only in isolated test databases.

**Acceptance:** malformed/tampered packets, duplicate normalized weeks, gaps, late `N`, stale selections, protected-run changes, missing keys, invalid authorizations, revoked approvals, and failures after each write boundary fail atomically. Exact retries create no duplicate selection history or payload changes. Existing v1 tests and behavior remain unchanged.

### 4. Separate web evidence classes and guard matchup lineage

Add explicit queries for selected retrospective replay runs and for prospective V5 runs designated in `prospective_week_records`; neither class uses a latest-run fallback. Reject duplicate designations. Compute separate spread and total W-L-P and win rates with pushes excluded from the denominator. Show clear empty and ungraded states and expose the original run/grade provenance for audit without changing public selection. Keep `system_stats` labeled as selected-public performance, never prospective.

Add a pure matchup lineage helper that compares selected forecast/rating references with matchup publication and team-stat provenance. It returns `ready`, `updating`, or `unavailable`; missing table or provenance cannot imply compatibility. When incompatible, hide model-derived sections and disable sharing while retaining safe schedule and venue content. Recheck lineage after repin so compatible content can recover.

**Acceptance:** Performance never combines retrospective and prospective totals or duplicates a run; mismatch/missing-provenance states hide model fields and block export; repin recovery restores the ready view. No web credentials can read revocations.

### 5. Verify Preview schema and prepare the Stage 7B handoff

After the code checkpoint and separate operator authorization, run the Preview migration through the approved migrator procedure. First inspect the migration ledger and target identity; stop on unexpected state. Read back the new schema and effective grants using read-only connections under the actual Preview roles. Do not insert test prospective rows or alter any selection, current-week, freeze, matchup-publication, authorization, or revocation state in Stage 7A.

The fixture and Playwright suites cover deliberate mismatch and recovery. The real Preview scenario using a selected reconstructed week, its original prospective record, deliberately mismatched matchup publication, repin, selection, freeze and rollback is explicitly retained as a Stage 7B rehearsal gate requiring a separately authorized operation and retained before payload.

Update this contract’s execution record and the Stage 7A implementation log. Do not update `docs/status.md` during Stage 7A; it remains the authority for serving/week state and changes only when the exact release changes that state.

## Validation

- Focused migration, registry, selection, freeze, revocation, packet, and rollback tests, including PostgreSQL concurrency tests.
- Full Python suite: `uv run python -m pytest tests -q --no-cov`; lint: `uv run ruff check .`.
- Contract synchronization: `make contracts-check`.
- Web checks from `web/`: `npm run lint`, `npm run typecheck`, `npm run test:publication`, `npm run build`, and Playwright Performance/matchup scenarios.
- Documentation: `uv run mkdocs build --quiet` and `git diff --check`.
- Preview after the separately authorized migration: migration ledger, `session_user`/`current_user`, effective table/schema privileges, migration-created constraints, and actual web query readback. No serving-state write is part of these checks.

## Risks and Stop Conditions

- Stop if either database migration ledger differs from the expected chain or if inherited grants give pipeline/web identities unapproved access.
- Stop if the existing Production authorization identity cannot be verified from the trusted operator configuration; do not guess a role name or add role membership.
- Stop if original prospective freeze evidence cannot be verified. Never infer a prospective record from a reconstructed replay or a current selection alone.
- Stop on any need to change model identity, cutover policy, table identities, selection scope, role boundary, or authorized write scope; return to Contract 04 for amendment.

## Definition of Done

- [ ] Migrations and canonical schema copies pass fresh and upgrade tests from 0022, including effective grants for the real Preview login identities.
- [ ] Role grants, revocation checks, and every V5 freeze/selection path pass negative and concurrency tests.
- [ ] v2 select, dry-run, idempotent retry, rollback and failure rollback pass in isolated databases; v1 remains compatible.
- [ ] Performance and matchup behavior pass unit, publication and Playwright tests.
- [ ] Separately authorized Preview migrations and read-only identity/grant/schema checks pass; no serving-state or authorization records are written.
- [ ] Required Python, Ruff, contract, web, docs and diff checks pass.
- [ ] Contract execution record and implementation log capture evidence, unresolved limits, and Stage 7B gates.
- [ ] The contract is marked Implemented only after all gates above pass.

## Execution record (2026-10-06)

- Implemented locally: migrations 0023/0024 and synchronized canonical schemas; packet-bound Preview/Production authorization tools; append-only revocation helper and operator entrypoint; revocation locks in public selection, intended-update authorization, direct freeze, and descriptor-driven weekly-cycle freeze; decision references are bound into weekly-cycle preflight/apply evidence; prospective freeze receipt registration; v2 packet validation, atomic cursor controller, dry-run/idempotent paths, rollback guards, and prospective-record preservation; separate replay/prospective Performance queries; fail-closed matchup lineage UI and fixtures.
- Local evidence: the full Python suite passed 2,017 tests with 12 skips. The focused Stage 7A suite passed 49 tests against a disposable UTF-8 PostgreSQL cluster, including all seven migration integration tests and database-backed v2 preflight, six-week selection, idempotent retry, compensating rollback, two injected transaction failures, and observed revocation lock serialization. The migration integration also reconstructs the logical 0022 boundary and verifies incremental application of 0023/0024. Ruff, direct `contracts/validation.py`, MkDocs, and `git diff --check` passed. Web lint, typecheck, 131 publication tests, production build, and all 24 Performance/matchup Playwright tests passed.
- The controller integration exercises real schema and transaction mutations while stubbing the external registered-authorization/finals evidence reads and exact Preview database identity check; those live identities and source reads remain for the operator read-only gate. Preview migration-ledger inspection, real-login effective grants, and read-only web query execution have not been run.
- `make contracts-check` could not run through `uv`: the configured cache first returned a filesystem permission error and a writable cache retry hit a local uv runtime panic. Its underlying `contracts/validation.py` command passed directly.
- The full Python run was `.venv/bin/python -m pytest -q`: 2,017 passed, 12 skipped in 292.35 seconds. The focused Stage 7A rerun with `TEST_DATABASE_URL` passed 49 tests; a final migration-upgrade/controller subset passed 7 tests after the last test refinements.
- The disposable PostgreSQL cluster lived under `/private/tmp` and was stopped after testing. Migration tests check Week 5+ scope rejection before run-identity validation, incremental upgrade from the logical 0022 boundary, and distinguish authorizer UPDATE privilege denial from the owner-level append-only trigger. The controller test verifies whole-transaction rollback after selection writes and after team-stat/current-week writes; the lock test observes the revocation backend waiting on PostgreSQL's advisory lock and confirms the resulting revocation blocks a later guard check.
- Stage 7A remains **In Progress**. The separately authorized Preview migration, actual login/effective-privilege readback, migration-ledger inspection, and read-only web query check remain. No Preview or Production serving, selection, authorization, or revocation records were changed.

## Amendments

No amendments at approval. Any change to the approved schemas, role boundaries, runtime cutover policy or serving write scope returns to Contract 04 for review before implementation.
